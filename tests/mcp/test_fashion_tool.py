import asyncio
import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.core import paths
from shell.mcp.server import build_server
from shell.mcp.tools import fashion as tool
from tests.engines.test_fashion import COLLECTIBLES, CTX, ITEMS, LOOK, PLUG_SETS, STATE


class FakeManifest:
    def table(self, name, keep=True):
        return {"DestinyInventoryItemDefinition": ITEMS, "DestinyCollectibleDefinition": COLLECTIBLES,
                "DestinyPlugSetDefinition": PLUG_SETS}[name]


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "profile_dir", lambda: tmp_path / "profile")
    monkeypatch.setattr(tool, "collectibles_state", lambda ctx, cls: STATE)
    (tmp_path / "profile" / "inventory").mkdir(parents=True)
    (tmp_path / "profile" / "inventory" / "armor.json").write_text(json.dumps([{"itemHash": 6}]), encoding="utf-8")
    (tmp_path / "profile" / "context").mkdir()
    (tmp_path / "profile" / "context" / "2026-10-28.json").write_text(json.dumps(CTX), encoding="utf-8")
    return tmp_path


def call(name, args):
    ctx = Context()
    ctx.__dict__.update(manifest=FakeManifest())
    result = asyncio.run(build_server(ctx).call_tool(name, args))
    return (result.structured_content or {}).get("result", json.loads(result.content[0].text) if result.content
                                                  else [])


def test_fashion_check_uses_inventory_and_saves(root):
    r = call("fashion_check", {"character": "Warlock", "look": LOOK, "save_as": "Purple Seraph",
                               "credit": "Trimedic13"})
    jade = next(x for x in r["rows"] if x["name"] == "Jade Rabbit Robes")
    assert jade["owned"] is True                                  # in the armor snapshot (hash 6)
    assert r["summary"].startswith("5 of 8 owned") and r["saved_to"].endswith("purple-seraph.json")
    saved = json.loads((root / "profile" / "fashion" / "purple-seraph.json").read_text(encoding="utf-8"))
    assert saved["class"] == "Warlock" and saved["credit"] == "Trimedic13" and saved["look"] == LOOK
    assert call("wardrobes", {}) == [{"name": "Purple Seraph", "class": "Warlock", "credit": "Trimedic13",
                                      "slots": 4, "saved": saved["saved"], "file": "purple-seraph.json", "look": LOOK}]


def test_fashion_check_errors(root):
    with pytest.raises(ToolError, match="titan, hunter or warlock"):
        call("fashion_check", {"character": "ghost", "look": LOOK})
    with pytest.raises(ToolError, match="empty look"):
        call("fashion_check", {"character": "warlock", "look": []})
    with pytest.raises(ToolError, match="slot is one of"):
        call("fashion_check", {"character": "warlock", "look": [{"slot": "Boots", "shader": "Ceramic Alloy"}]})


def test_wardrobes_return_the_look(root):
    call("fashion_check", {"character": "Warlock", "look": LOOK, "save_as": "Purple Seraph"})
    assert call("wardrobes", {})[0]["look"] == LOOK


def test_collectibles_owned_in_either_scope(monkeypatch):
    profile = {"profileCollectibles": {"data": {"collectibles": {"15": {"state": 1}, "16": {"state": 1}}}},
               "characterCollectibles": {"data": {"c1": {"collectibles": {"15": {"state": 0}}}}}}
    monkeypatch.setattr(tool, "primary_membership", lambda client: {})
    monkeypatch.setattr(tool, "get_profile", lambda client, account, components: profile)
    monkeypatch.setattr(tool, "character_id", lambda p, cls: "c1")
    assert tool.collectibles_state(Context(), "Warlock") == {15: 0, 16: 1}
