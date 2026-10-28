import asyncio
import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.core import paths
from shell.mcp.server import build_server
from tests.engines.test_recommend import ITEMS, write_ratings


@pytest.fixture
def root(tmp_path, monkeypatch):
    from shell.sources.aegis import lookup
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(paths, "profile_dir", lambda: tmp_path / "profile")
    monkeypatch.setattr(lookup, "DATA", None)
    monkeypatch.setattr(lookup, "_warned", False)
    return tmp_path


def call(name, args):
    result = asyncio.run(build_server(Context()).call_tool(name, args))
    return json.loads(result.content[0].text)


def test_recommend_weapons(root):
    with pytest.raises(ToolError, match="refresh_inventory"):
        call("recommend_weapons", {"character": "warlock"})
    (root / "profile" / "inventory").mkdir(parents=True)
    (root / "profile" / "inventory" / "weapons.json").write_text(json.dumps(ITEMS), encoding="utf-8")
    with pytest.raises(ToolError, match="refresh_references"):
        call("recommend_weapons", {"character": "warlock"})
    write_ratings(root / "cache" / "aegis")
    with pytest.raises(ToolError, match="character"):
        call("recommend_weapons", {"character": "ghost"})
    result = call("recommend_weapons", {"character": "Warlock", "slot": "kinetic", "top": 2})
    assert result["snapshot"] and len(result["picks"]) == 2 and result["picks"][0].startswith("1 | 3 | Rufus's Fury")
    assert set(result) == {"snapshot", "equipped", "picks", "not_owned", "warnings"}
