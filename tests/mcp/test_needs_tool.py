import asyncio
import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

import shell.mcp.tools.needs as needs_tool
from shell.context import Context
from shell.engines.builds import sheet as sheet_mod
from shell.mcp.server import build_server
from tests.engines.todo.test_needs import COSTS, ITEMS, SHEET


class FakeManifest:
    def table(self, name, keep=True):
        return {}


@pytest.fixture
def call(tmp_path, monkeypatch):
    """Sheet "b" and an armor snapshot in a tmp profile, no weapon snapshot, no Aegis data, a fake catalog."""
    from shell.core import paths
    from shell.sources.aegis import lookup
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(paths, "profile_dir", lambda: tmp_path / "profile")
    monkeypatch.setattr(lookup, "DATA", None)
    monkeypatch.setattr(lookup, "_warned", False)
    sheet_mod.save(sheet_mod.path_for("b"), SHEET)
    (tmp_path / "profile" / "inventory").mkdir(parents=True)
    (tmp_path / "profile" / "inventory" / "armor.json").write_text(json.dumps(ITEMS), encoding="utf-8")
    (tmp_path / "profile" / "todo").mkdir()
    (tmp_path / "profile" / "todo" / "state.json").write_text(
        json.dumps({"aegis/truth": {"status": "todo", "since": "x"}}), encoding="utf-8")
    monkeypatch.setattr(needs_tool, "load_catalog", lambda manifest: {"sets": {}, "costs": COSTS})
    ctx = Context()
    ctx.__dict__.update(manifest=FakeManifest())
    mcp = build_server(ctx)
    return lambda **args: json.loads(asyncio.run(mcp.call_tool("farm_needs", args)).content[0].text)


def test_farm_needs_writes_needs_state_and_sheets(call, tmp_path):
    out = call()
    todo = tmp_path / "profile" / "todo"
    saved = json.loads((todo / "needs.json").read_text(encoding="utf-8"))
    assert out["total"] == len(saved["needs"]) and out["counts"]["catalyst"] == 1
    assert set(out["counts"]) == {"armor", "catalyst", "masterwork"}
    assert out["warnings"] == saved["warnings"] and out["snapshot"]
    assert out["saved_to"] == str(todo / "needs.json")
    assert any("Shopping List missing" in w for w in out["warnings"])
    st = json.loads((todo / "state.json").read_text(encoding="utf-8"))
    assert st["aegis/truth"]["status"] == "todo"   # Aegis not checked: kept
    assert st["catalyst/cat"]["status"] == "todo"
    assert "## To fetch" in (tmp_path / "profile" / "builds" / "b.md").read_text(encoding="utf-8")


def test_farm_needs_without_armor_snapshot_asks_for_refresh(call, tmp_path):
    (tmp_path / "profile" / "inventory" / "armor.json").unlink()
    with pytest.raises(ToolError, match=r"No armor snapshot\. Call refresh_inventory first\."):
        call()
