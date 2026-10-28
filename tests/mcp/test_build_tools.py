import asyncio
import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

import shell.mcp.tools.builds as builds
from shell.context import Context
from shell.engines.builds import inventory, sheet as sheet_mod
from shell.mcp.server import build_server
from tests.engines.builds.test_optimize import COSTS, INTENT, base_pieces, p


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Sheet "t" in a tmp profile, an empty armor snapshot, a fake catalog; returns (call, sheet path, catalog)."""
    from shell.core import paths
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(paths, "profile_dir", lambda: tmp_path / "profile")
    path = sheet_mod.path_for("t")
    sheet_mod.save(path, {"name": "T", "class": "Warlock", "subclass": {"element": "Arc", "fragments": []},
                          "intent": INTENT, "resolved": {"weapons": [], "rationale": ["r"]}})
    (tmp_path / "profile" / "inventory").mkdir(parents=True)
    (tmp_path / "profile" / "inventory" / "armor.json").write_text("[]", encoding="utf-8")
    catalog = {"sets": {}, "costs": COSTS}
    monkeypatch.setattr(builds, "load_catalog", lambda manifest: catalog)
    monkeypatch.setattr(inventory, "load_pieces", lambda *a, **k: base_pieces())
    monkeypatch.setattr(builds, "fragment_stats", lambda *a, **k: {})
    ctx = Context()
    ctx.__dict__.update(manifest=None)
    mcp = build_server(ctx)

    def call(**args):
        return json.loads(asyncio.run(mcp.call_tool("optimize_build", {"slug": "t", **args})).content[0].text)
    return call, path, catalog


def set_intent(path, **changes):
    s = sheet_mod.load(path)
    s["intent"] = {**INTENT, **changes}
    sheet_mod.save(path, s)


def test_optimize_build_tool_writes_pick(env, monkeypatch):
    call, path, _ = env
    pieces = base_pieces()
    pieces["Helmet"].append(p("h3", "Helmet", Health=25, tuned="Melee"))   # a tuned piece is never pruned
    monkeypatch.setattr(inventory, "load_pieces", lambda *a, **k: pieces)
    out = call(top=2, write=True, pick=2)
    assert out["written"] == 2
    assert out["feasible"] and len(out["results"]) == 2 and out["snapshot"]
    assert any("tuning" in w for w in out["warnings"])          # the empty snapshot has no tuning stat
    saved = json.loads(path.read_text(encoding="utf-8"))["resolved"]
    assert [a["itemId"] for a in saved["armor"]] == [a["itemId"] for a in out["results"][1]["armor"]]
    assert saved["stats"] == out["results"][1]["stats"]


def test_write_refuses_infeasible_without_force(env):
    call, path, _ = env
    set_intent(path, stats={"minimums": {"Health": 200}, "priority": []})
    before = path.read_text(encoding="utf-8")
    with pytest.raises(ToolError, match="force"):
        call(write=True)
    assert path.read_text(encoding="utf-8") == before
    call(write=True, force=True)
    assert "armor" in json.loads(path.read_text(encoding="utf-8"))["resolved"]


def test_missing_snapshot_asks_for_refresh(env, tmp_path):
    call, _, _ = env
    (tmp_path / "profile" / "inventory" / "armor.json").unlink()
    with pytest.raises(ToolError, match="Call refresh_inventory first"):
        call()


def test_unknown_slug_lists_sheets(env):
    call, _, _ = env
    with pytest.raises(ToolError, match=r"unknown build: \.\./x \(sheets: t\)"):
        call(slug="../x")


def test_top_below_one_and_pick_out_of_range(env):
    call, _, _ = env
    with pytest.raises(ToolError, match="top"):
        call(top=0)
    with pytest.raises(ToolError, match="pick 0"):
        call(write=True, pick=0)


def test_write_error_is_a_tool_error(env, monkeypatch):
    call, _, _ = env

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(sheet_mod, "save", boom)
    with pytest.raises(ToolError, match="disk full"):
        call(write=True)


def test_no_result_is_a_warning(env):
    call, path, catalog = env
    set_intent(path, sets=[{"set": "AION", "pieces": 4}])
    catalog["sets"] = {1: {"set": "AION", "bonus": []}}
    out = call()
    assert out["results"] == [] and any("no valid combination" in w for w in out["warnings"])


def test_set_override_is_recorded_in_resolved(env):
    call, path, catalog = env
    set_intent(path, sets=[{"set": "AION", "pieces": 4}])
    catalog["sets"] = {1: {"set": "AION", "bonus": []}}
    call(sets=["AION:2"], write=True)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["intent"]["sets"] == [{"set": "AION", "pieces": 4}]        # the intent does not move
    assert saved["resolved"]["sets"] == [{"set": "AION", "pieces": 2}]
    assert "Sets applied: 2 × AION (intent: 4 × AION)" in path.with_suffix(".md").read_text(encoding="utf-8")
    call(no_sets=True, write=True)
    assert json.loads(path.read_text(encoding="utf-8"))["resolved"]["sets"] == []
    set_intent(path, sets=[{"set": "AION", "pieces": 2}])
    call(write=True)                                                          # no override: cleared
    assert "sets" not in json.loads(path.read_text(encoding="utf-8"))["resolved"]


@pytest.mark.parametrize("args,message", [
    ({"sets": ["AION"]}, "sets"), ({"sets": ["AION:3"]}, "sets"), ({"sets": ["AION:2"], "no_sets": True}, "no_sets"),
])
def test_invalid_set_override(env, args, message):
    call, _, _ = env
    with pytest.raises(ToolError, match=message):
        call(**args)


def test_unknown_set_suggests_manifest_name(env):
    call, path, catalog = env
    set_intent(path, sets=[{"set": "smoke jumper", "pieces": 2}])
    catalog["sets"] = {1: {"set": "Smoke Jumper Set", "bonus": []}}
    with pytest.raises(ToolError, match=r"unknown set: smoke jumper \(suggestion: Smoke Jumper Set\)"):
        call()


def test_invalid_sheet_is_a_one_line_error(env):
    call, path, _ = env
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ToolError, match="invalid JSON"):
        call()
