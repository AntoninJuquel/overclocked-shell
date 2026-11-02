"""equip_build: one previewed plan, all its writes in order, stopping at the first real failure."""
import asyncio
import copy
import json
import os

import pytest
from mcp.server.mcpserver.exceptions import ToolError

import shell.mcp.tools.builds as builds
import shell.mcp.tools.equip_build as eb
from shell.context import Context
from shell.engines.builds import sheet as sheet_mod
from shell.mcp.server import build_server
from tests.engines.builds.test_equip_plan import ARMOR, COSTS, FRAG, IDX, SHEET, WEAPONS


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Sheet "t" and fresh snapshots; every write helper replaced by a recorder. Returns (call, log, inventory dir)."""
    from shell.core import paths
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(paths, "profile_dir", lambda: tmp_path / "profile")
    s = copy.deepcopy(SHEET)
    s["intent"].update(stats={"minimums": {}, "priority": []}, sets=[])
    s["intent"].pop("artifact", None)
    sheet_mod.save(sheet_mod.path_for("t"), s)
    inv = tmp_path / "profile" / "inventory"
    inv.mkdir(parents=True)
    (inv / "armor.json").write_text(json.dumps(ARMOR), encoding="utf-8")
    (inv / "weapons.json").write_text(json.dumps(WEAPONS), encoding="utf-8")
    monkeypatch.setattr(builds, "load_catalog", lambda manifest: {"sets": {}, "costs": COSTS, "subclass": IDX})
    monkeypatch.setattr(builds, "fragment_stats", lambda *a, **k: FRAG)
    log, fail = [], {}
    subclass = builds.equip_mod.SUBCLASS_ITEMS[s["class"]][s["subclass"]["element"]]
    monkeypatch.setattr(eb, "_item_ids", lambda ctx, plan: ("777", None, False, []) if subclass else None)

    def socket_result(changes, dry):
        name = "armor" if changes[0]["itemId"] != "777" else "subclass"
        log.append((name, dry))
        result = fail.get(name, "would change" if dry else "done")
        return {"dry_run": dry, "applied": 0, "notes": [f"{name}: no socket takes \"X\""],
                "changes": [{"itemId": "1", "name": "n", "socketIndex": 0, "from": "a", "to": "Plug", "result": result}]}

    monkeypatch.setattr(eb, "plan_sockets", lambda ctx, changes, defs: changes)
    monkeypatch.setattr(eb, "run_sockets", lambda ctx, changes, dry: socket_result(changes, dry))

    def equip(ctx, character, ids, dry):
        log.append(("equip", dry, tuple(ids)))
        result = fail.get("equip", "would equip" if dry else "equipped")
        return {"dry_run": dry, "equipped": 0, "moves": [],
                "equip": [{"itemId": i, "name": i, "result": result} for i in ids]}

    def perks(ctx, changes, dry):
        log.append(("perks", dry))
        return {"dry_run": dry, "applied": 0, "notes": [], "changes": []}

    def locks(ctx, ids, locked, dry):
        log.append(("lock", dry, locked))
        return {"dry_run": dry, "changed": 0, "items": []}

    monkeypatch.setattr(eb, "equip_on", equip)
    monkeypatch.setattr(eb, "change_perks", perks)
    monkeypatch.setattr(eb, "change_locks", locks)
    ctx = Context()
    ctx.__dict__.update(manifest=None)
    mcp = build_server(ctx)

    def call(**args):
        return json.loads(asyncio.run(mcp.call_tool("equip_build", {"slug": "t", **args})).content[0].text)
    return call, log, inv, fail


def test_preview_writes_nothing_and_gives_a_code(env):
    call, log, _, _ = env
    out = call()
    assert out["dry_run"] and out["ready"] and out["confirm"] and out["stopped_at"] is None
    assert all(entry[1] is True for entry in log)
    assert log[0][2] == (*("h", "g", "c", "l", "b", "w1"), "777")   # the plan's items, then the subclass
    assert [e[0] for e in log][:2] == ["equip", "subclass"] and log[-1][0] == "lock"
    assert any("no socket takes" in r for r in out["refused"])


@pytest.mark.parametrize("confirm", [None, "wrong"])
def test_run_refused_without_the_preview_s_code(env, confirm):
    call, log, _, _ = env
    with pytest.raises(ToolError, match="No preview"):
        call(dry_run=False, **({"confirm": confirm} if confirm else {}))
    assert log == []


def test_run_refused_when_the_plan_changed_since_the_preview(env):
    call, log, inv, _ = env
    code = call()["confirm"]
    log.clear()
    (inv / "armor.json").write_text(json.dumps([{**ARMOR[0], "locked": not ARMOR[0].get("locked")}, *ARMOR[1:]]),
                                    encoding="utf-8")
    with pytest.raises(ToolError, match="No preview"):
        call(dry_run=False, confirm=code)
    assert log == []


def test_run_applies_every_step_in_order(env):
    call, log, _, _ = env
    code = call()["confirm"]
    log.clear()
    out = call(dry_run=False, confirm=code)
    assert out["stopped_at"] is None and "confirm" not in out
    assert [e[0] for e in log] == [s["step"] for s in out["steps"]]
    assert all(e[1] is False for e in log)
    assert log[-1] == ("lock", False, True)


def test_failed_equip_stops_before_any_socket(env):
    call, log, _, fail = env
    code = call()["confirm"]
    log.clear()
    fail["equip"] = "not equipped: character not in orbit"
    out = call(dry_run=False, confirm=code)
    assert out["stopped_at"] == "equip" and [e[0] for e in log] == ["equip"]
    assert "character not in orbit" in out["blocked"][0]


def test_failed_socket_stops_the_sequence(env):
    call, log, _, fail = env
    code = call()["confirm"]
    log.clear()
    fail["subclass"] = "failed: plug not unlocked"
    out = call(dry_run=False, confirm=code)
    assert out["stopped_at"] == "subclass" and [e[0] for e in log] == ["equip", "subclass"]


def test_bungie_error_keeps_what_was_done(env, monkeypatch):
    from shell.core.bungie import BungieApiError
    call, _, _, _ = env
    code = call()["confirm"]

    def down(ctx, changes, dry):
        raise BungieApiError("down")

    monkeypatch.setattr(eb, "run_sockets", down)
    out = call(dry_run=False, confirm=code)
    assert out["stopped_at"] == "subclass" and [s["step"] for s in out["steps"]] == ["equip"]


def test_old_snapshot_refused(env):
    call, log, inv, _ = env
    old = os.path.getmtime(inv / "armor.json") - 3600
    os.utime(inv / "armor.json", (old, old))
    with pytest.raises(ToolError, match="refresh_inventory"):
        call()
    assert log == []


def test_blocking_problems_do_nothing(env):
    call, log, inv, _ = env
    (inv / "armor.json").write_text(json.dumps(ARMOR[1:]), encoding="utf-8")
    out = call()
    assert out["ready"] is False and out["problems"] and "confirm" not in out and log == []


def test_blocked(env):
    moves = {"moves": [{"itemId": "a", "name": "A", "result": "in the postmaster: pull it first"},
                       {"itemId": "b", "name": "B", "result": "would move vault -> warlock"}], "equip": []}
    assert eb._blocked("equip", moves, True) == ["A: in the postmaster: pull it first"]
    empty = {"changes": [{"name": "n", "to": "Empty Mod Socket", "result": "failed: x"}]}
    assert eb._blocked("armor", empty, False) == []   # a removal with no effect does not matter
