import asyncio
import copy
import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

import shell.mcp.tools.builds as builds
from shell.context import Context
from shell.engines.builds import sheet as sheet_mod
from shell.mcp.server import build_server
from tests.engines.builds.test_equip_plan import ARMOR, COSTS, FRAG, IDX, SHEET, WEAPONS


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Sheet "t" and armor + weapon snapshots in a tmp profile, a fake catalog; returns (call, inventory dir)."""
    from shell.core import paths
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(paths, "profile_dir", lambda: tmp_path / "profile")
    s = copy.deepcopy(SHEET)
    s["intent"].update(stats={"minimums": {}, "priority": []}, sets=[])
    sheet_mod.save(sheet_mod.path_for("t"), s)
    inv = tmp_path / "profile" / "inventory"
    inv.mkdir(parents=True)
    (inv / "armor.json").write_text(json.dumps(ARMOR), encoding="utf-8")
    (inv / "weapons.json").write_text(json.dumps(WEAPONS), encoding="utf-8")
    monkeypatch.setattr(builds, "load_catalog", lambda manifest: {"sets": {}, "costs": COSTS, "subclass": IDX})
    monkeypatch.setattr(builds, "fragment_stats", lambda *a, **k: FRAG)
    ctx = Context()
    ctx.__dict__.update(manifest=None)
    mcp = build_server(ctx)

    def call(**args):
        return json.loads(asyncio.run(mcp.call_tool("equip_plan", {"slug": "t", **args})).content[0].text)
    return call, inv


def test_equip_plan_tool(env):
    call, inv = env
    out = call()
    assert out["ready"] and out["snapshot"]
    assert out["equip"] == ["h", "g", "c", "l", "b", "w1"]
    assert out["masterwork_todo"] == ["Hood"]
    (inv / "armor.json").write_text(json.dumps(ARMOR[1:]), encoding="utf-8")
    out = call()
    assert not out["ready"] and "Helmet: Hood (h) not in the inventory" in out["problems"]
    (inv / "weapons.json").unlink()
    with pytest.raises(ToolError, match="Call refresh_inventory first"):
        call()
    with pytest.raises(ToolError, match="unknown build"):
        call(slug="nope")


def test_malformed_snapshot_is_one_line_error(env):
    call, inv = env
    (inv / "armor.json").write_text('[{"bad": "row"}]', encoding="utf-8")
    with pytest.raises(ToolError, match="malformed snapshot"):
        call()
