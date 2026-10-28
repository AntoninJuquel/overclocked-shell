import asyncio
import json
import time

import httpx
import pytest

from shell.context import Context
from shell.core import paths
from shell.core.bungie import BungieClient
from shell.core.settings import Settings
from shell.mcp.server import build_server
from tests.engines.fixtures import DEFS, profile

SETTINGS = Settings("k", "1", "s", "https://localhost:7777/callback")


class FakeOAuth:
    def access_token(self):
        return "a"


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "profile_dir", lambda: tmp_path)
    calls = []

    def handler(request):
        if request.url.path.startswith("/Platform/User/"):
            body = {"destinyMemberships": [{"membershipType": 3, "membershipId": "1"}]}
        else:
            calls.append(request.url.params["components"])
            time.sleep(0.2)
            body = profile()
        return httpx.Response(200, json={"ErrorCode": 1, "Response": body})

    ctx = Context()
    ctx.__dict__.update(settings=SETTINGS, oauth=FakeOAuth(), defs=DEFS, client=BungieClient(
        SETTINGS, FakeOAuth(), http=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None))
    mcp = build_server(ctx)
    call = lambda name, args=None: json.loads(  # noqa: E731
        asyncio.run(mcp.call_tool(name, args or {})).content[0].text)
    return call, calls, tmp_path


def test_refresh_writes_snapshot(server):
    call, calls, tmp = server
    assert call("refresh_inventory") == {"armor": 3, "weapons": 3, "saved_to": str(tmp / "inventory")}
    assert calls == ["102,200,201,205,300,304,305,310"]
    assert len(json.loads((tmp / "inventory" / "armor.json").read_text())) == 3
    assert len(json.loads((tmp / "inventory" / "weapons.json").read_text())) == 3


def test_find_armor_filters_and_limit(server):
    call, _, _ = server
    result = call("find_armor", {"class_type": "WARLOCK", "limit": 1})
    assert result["total"] == 2 and result["truncated"] is True and len(result["items"]) == 1
    assert set(result["items"][0]) == {"itemId", "name", "slot", "classType", "rarity", "location", "locked",
                                       "gearTier", "stats", "total", "tunedStat", "plugs"}
    assert call("find_armor", {"rarity": "exotic", "name": "star"})["items"][0]["itemId"] == "a1"


def test_find_weapons_by_perk(server):
    call, _, _ = server
    result = call("find_weapons", {"perk": "kill clip"})
    assert result["total"] == 1 and result["truncated"] is False
    assert result["items"][0]["name"] == "Gun"
    assert result["items"][0]["perks"] == ["Arrowhead Brake", "Kill Clip"]


def test_find_loads_on_first_use_only(server):
    call, calls, _ = server
    call("find_weapons", {"type": "auto rifle"})
    call("find_armor")
    assert len(calls) == 1


def test_limit_clamped_and_offset_pages(server):
    call, _, _ = server
    page = call("find_armor", {"limit": 1, "offset": 1})
    assert page["total"] == 3 and page["offset"] == 1 and page["truncated"] is True and len(page["items"]) == 1
    assert len(call("find_armor", {"limit": -1})["items"]) == 1
    assert call("find_armor", {"offset": 2})["truncated"] is False


def test_class_filter_keeps_any_class_armor(server, monkeypatch):
    call, _, _ = server
    DEFS["gear"]["200"][2] = 3
    try:
        call("refresh_inventory")
        assert call("find_armor", {"class_type": "warlock"})["total"] == 3
    finally:
        DEFS["gear"]["200"][2] = 1


def test_parallel_first_calls_fetch_once(server):
    from concurrent.futures import ThreadPoolExecutor
    call, calls, _ = server
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(lambda name: call(name), ["find_armor", "find_weapons"]))
    assert len(calls) == 1
