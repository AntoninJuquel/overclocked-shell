"""Gear-changing tools only preview unless dry_run=false: no POST may leave without it."""
import asyncio
import json
import re

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.core.bungie import BungieClient
from shell.core.settings import Settings
from shell.mcp.server import build_server
from tests.engines.fixtures import DEFS, profile

SETTINGS = Settings("k", "1", "s", "https://localhost:7777/callback")


class FakeOAuth:
    def access_token(self):
        return "a"


def item_response(sockets):
    return {"item": {"data": {"itemHash": 200}}, "sockets": {"data": {"sockets": [{"plugHash": h} for h in sockets]}}}


@pytest.fixture
def server():
    posts, state = [], {"sockets": [1], "entries": [{"reusablePlugItems": [{"plugItemHash": 1}, {"plugItemHash": 2}]}]}

    def handler(request):
        path = request.url.path
        if request.method == "POST":
            posts.append(path)
            body = {}
        elif path.startswith("/Platform/User/"):
            body = {"destinyMemberships": [{"membershipType": 3, "membershipId": "1"}]}
        elif "/Item/" in path:
            body = item_response(state["sockets"])
        elif "/Manifest/" in path:
            body = {"displayProperties": {"name": "Star-Eater Scales"}, "sockets": {"socketEntries": state["entries"]}}
        else:
            body = profile()
        return httpx.Response(200, json={"ErrorCode": 1, "Response": body})

    ctx = Context()
    ctx.__dict__.update(settings=SETTINGS, oauth=FakeOAuth(), defs=DEFS, client=BungieClient(
        SETTINGS, FakeOAuth(), http=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None))
    mcp = build_server(ctx)
    call = lambda name, args: json.loads(asyncio.run(mcp.call_tool(name, args)).content[0].text)  # noqa: E731
    return call, posts, state, mcp


@pytest.mark.parametrize("name,args", [
    ("transfer_items", {"item_ids": ["g1"], "to": "warlock"}),
    ("pull_from_postmaster", {"character": "warlock", "pull_all": True}),
    ("equip_items", {"character": "warlock", "item_ids": ["g1"]}),
    ("set_sockets", {"changes": [{"itemId": "1", "plugs": ["Empty Mod Socket"]}]}),
    ("set_perks", {"changes": [{"itemId": "g1", "select": ["Corkscrew Rifling"]}]}),
])
def test_gear_tools_preview_by_default(server, name, args):
    call, posts, _, _ = server
    result = call(name, args)
    assert result["dry_run"] is True and posts == []


def test_set_sockets_preview_plans_the_change(server):
    call, _, _, _ = server
    result = call("set_sockets", {"changes": [{"itemId": "1", "plugs": ["Empty Mod Socket"]}]})
    assert [(c["from"], c["to"], c["result"]) for c in result["changes"]] == [
        ("Weapons Mod", "Empty Mod Socket", "would change")]


def test_set_sockets_rejects_ids_that_are_not_numbers(server):
    call, posts, _, _ = server
    result = call("set_sockets", {"changes": [{"itemId": "1/../../User", "plugs": ["Weapons Mod"]}]})
    assert result["changes"] == [] and result["notes"] == ["1/../../User: not an item id"]


def test_set_sockets_refuses_more_than_30_actions(server):
    call, posts, state, mcp = server
    DEFS["plugs"].update({str(1000 + i): {"n": f"Mod {i}", "t": "Mod", "p": "x"} for i in range(31)})
    state["entries"] = [{"reusablePlugItems": [{"plugItemHash": 1000 + i}]} for i in range(31)]
    state["sockets"] = [0] * 31
    with pytest.raises(ToolError, match="split it into batches of 30"):
        asyncio.run(mcp.call_tool("set_sockets", {"changes": [{"itemId": "1", "plugs": [f"Mod {i}" for i in range(31)]}],
                                                  "dry_run": False}))
    assert posts == []


def test_set_perks_defers_beyond_30(server, monkeypatch):
    import shell.mcp.tools.perks as perks
    call, _, _, _ = server
    plan = {"itemId": "g1", "characterId": "w", "name": "Gun", "column": "Barrel", "socketIndex": 1, "from": "a",
            "to": "b", "hashes": [12]}
    monkeypatch.setattr(perks, "plan_perks", lambda row, cid, select: ([plan] * 31, []))
    result = call("set_perks", {"changes": [{"itemId": "g1", "select": ["x"]}]})
    assert [c["result"] for c in result["changes"]].count("deferred: call again") == 1
