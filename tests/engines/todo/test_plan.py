import json
from datetime import datetime, timedelta, timezone

import pytest

from shell.engines.todo import plan

E = "2026-10-13T17:00:00Z"
NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
SE = {"type": "activity", "kind": "raid", "name": "Salvation's Edge", "detail": 'Source: "Salvation\'s Edge" Raid'}
INDEX = {"by_set": {("Promised", "Warlock", "Helmet"): [SE]}, "by_name": {}}
HOOD = {"hash": 1, "name": "Promised Victory Hood", "type": "armor", "class": "Warlock", "slot": "Helmet",
        "set": "Promised", "tier": "Legendary"}
CTX = {
    "date": "2026-10-07", "reset": {"start": "2026-10-06T17:00:00Z", "end": E},
    "activities": [
        {"hash": 7, "name": "Salvation's Edge: Standard", "boosts": [], "until": E, "rewards": []},
        {"hash": 9, "name": "Contest of Elders: Matchmade", "boosts": ["focus"], "until": E, "rewards": [HOOD]},
        {"hash": 11, "name": "Nightfall: The Glassway", "boosts": ["bonus"], "until": E, "rewards": []},
    ],
    "vendors": [], "notes": [{"text": "Double dungeon loot", "until": E}], "warnings": [],
}


def need(nid, kind, label, target, score, build="b", effects=(), stats=None):
    return {"id": nid, "kind": kind, "label": label, "target": target,
            "builds": [{"build": build, "gain": {"stats": stats or {}, "effects": list(effects), "score": score}}]}


NEEDS = {"date": "2026-10-07", "warnings": [], "needs": [
    need("armor/Warlock/Helmet/Promised/Demolitionist/*", "armor", "Promised Warlock Helmet — Demolitionist",
         {"class": "Warlock", "slot": "Helmet", "set": "Promised", "archetypes": ["Demolitionist"],
          "tertiaries": None}, 0.1, effects=["Promised — 2 pieces: Stable Resonance"], stats={"Class": 5}),
    need("masterwork/9", "masterwork", "Masterwork: Ferropotent Cover",
         {"itemId": "9", "name": "Ferropotent Cover", "slot": "Helmet"}, 0.007, stats={"Grenade": 10}),
    need("catalyst/collective-obligation", "catalyst", "Catalyst: Collective Obligation",
         {"name": "Collective Obligation"}, 0.1),
    need("upgrade/unto-the-breach", "upgrade", "Upgrade: Unto the Breach", {"name": "Unto the Breach"}, 0.05),
    need("masterwork/8", "masterwork", "Masterwork: Other", {"itemId": "8", "name": "Other", "slot": "Legs"},
         0.02, build="c"),
]}
STATE = {"upgrade/unto-the-breach": {"status": "ignored", "since": "2026-10-07"},
         "masterwork/7": {"status": "done", "since": "2026-10-07"}}


def test_build_plan_sections_and_priorities():
    doc = plan.build_plan(NEEDS, STATE, CTX, INDEX, {}, "2026-10-07")
    assert [(e["id"], e["section"], e["priority"]) for e in doc["entries"]] == [
        ("armor/Warlock/Helmet/Promised/Demolitionist/*", "This week", 0.15),
        ("masterwork/8", "When you can", 0.02),
        ("masterwork/9", "When you can", 0.007),
        ("catalyst/collective-obligation", "Later", 0.03),
    ]
    hood = doc["entries"][0]
    assert hood["availability"] == 1.5
    assert [s["name"] for s in hood["sources"]] == ["Salvation's Edge: Standard", "Contest of Elders: Matchmade",
                                                    "Salvation's Edge"]
    assert doc["entries"][2]["note"] == ("useless if you replace the piece with: "
                                         "Promised Warlock Helmet — Demolitionist")
    assert "note" not in doc["entries"][1]
    assert doc["hidden"] == {"done": 0, "ignored": 1}
    assert doc["reset"] == CTX["reset"]
    assert doc["context"] == {"end": E, "focus": ["Contest of Elders"],
                              "bonus": ["Nightfall: The Glassway"], "notes": ["Double dungeon loot"]}
    assert doc["build"] is None


def test_context_summary_groups_activity_variants():
    ctx = {"reset": {"end": E}, "activities": [
        {"name": "Astral Alignment: Customize", "boosts": ["focus"]},
        {"name": "Astral Alignment: Matchmade", "boosts": ["focus"]},
        {"name": "Salvation's Edge: Master", "boosts": ["focus"]},
        {"name": "Salvation's Edge: Standard", "boosts": ["focus"]},
        {"name": "The Coil: Normal", "boosts": ["focus", "bonus"]},
        {"name": "Battleground: Foothold: Customize", "boosts": ["focus"]},
        {"name": "Patrol"},
    ]}
    assert plan._context_summary(ctx) == {
        "end": E, "focus": ["Astral Alignment", "Salvation's Edge", "The Coil", "Battleground: Foothold"],
        "bonus": ["The Coil"], "notes": []}


def test_build_plan_filter_and_no_context():
    doc = plan.build_plan(NEEDS, STATE, None, INDEX, {}, "2026-10-07", build="b")
    assert [e["id"] for e in doc["entries"]] == [
        "armor/Warlock/Helmet/Promised/Demolitionist/*", "masterwork/9", "catalyst/collective-obligation"]
    assert doc["entries"][0]["section"] == "When you can" and doc["entries"][0]["priority"] == 0.1
    assert doc["reset"] is None and doc["context"] is None
    assert doc["build"] == "b"
    assert doc["hidden"] == {"done": 0, "ignored": 1}   # the ignored upgrade is b's
    other = plan.build_plan(NEEDS, STATE, None, INDEX, {}, "2026-10-07", build="c")
    assert other["hidden"] == {"done": 0, "ignored": 0}


def test_num_three_significant_digits():
    assert [plan._num(v) for v in (0.007, 0.15, 0.098, 0.1, 0.0073, 0.0102)] == [
        "0.007", "0.15", "0.098", "0.1", "0.0073", "0.0102"]


def test_load_context(tmp_path):
    ctx, warnings = plan.load_context(tmp_path, NOW)
    assert ctx is None and "unavailable" in warnings[0]
    (tmp_path / "2026-09-30.json").write_text(json.dumps({**CTX, "reset": {"start": "x", "end": "2026-10-06T17:00:00Z"}}),
                                              encoding="utf-8")
    ctx, warnings = plan.load_context(tmp_path, NOW)
    assert ctx is None and "out of date" in warnings[0] and "2026-09-30" in warnings[0]
    (tmp_path / "2026-10-07.json").write_text(json.dumps({**CTX, "warnings": ["w"]}), encoding="utf-8")
    ctx, warnings = plan.load_context(tmp_path, NOW)
    assert ctx["date"] == "2026-10-07" and warnings == ["w"]


def test_load_context_defaults_to_week_folder(tmp_path):
    week_dir = tmp_path / "profile" / "todo" / "week"
    week_dir.mkdir(parents=True)
    (week_dir / "2026-10-07.json").write_text(json.dumps(CTX), encoding="utf-8")
    ctx, _ = plan.load_context(None, NOW)
    assert ctx["date"] == "2026-10-07"


def test_render_md():
    doc = plan.build_plan(NEEDS, STATE, CTX, INDEX, {}, "2026-10-07")
    doc["warnings"] = ["careful"]
    md = plan.render_md(doc)
    assert md.startswith("# TODO for 2026-10-07\n")
    assert ("Week until 2026-10-13 17:00 UTC · Focus: Contest of Elders · "
            "Bonus: Nightfall: The Glassway") in md
    assert "- Note: Double dungeon loot" in md
    assert "> careful" in md
    assert md.index("## This week") < md.index("## When you can") < md.index("## Later")
    assert "1. **Promised Warlock Helmet — Demolitionist** · priority 0.15" in md
    assert "1. **Masterwork: Other** · priority 0.02" in md
    assert "2. **Masterwork: Ferropotent Cover** · priority 0.007" in md
    assert "   For: b (Class +5; Promised — 2 pieces: Stable Resonance)" in md
    assert ("   Where: Salvation's Edge (until 2026-10-13); Contest of Elders (focus, "
            "until 2026-10-13)\n") in md
    assert "   Note: useless if you replace the piece with: Promised Warlock Helmet — Demolitionist" in md
    assert ("   Where: unknown source, add it to profile/todo/sources.json "
            "(key \"catalyst/collective-obligation\")") in md
    assert md.rstrip().endswith("_Ignored: 1 · Done: 0_")


def test_render_md_vendor_and_no_context():
    doc = plan.build_plan(NEEDS, {}, None, INDEX, {}, "2026-10-07")
    doc["entries"][0]["sources"] = [{"type": "vendor", "name": "Ada-1", "boost": "sale", "until": E,
                                     "costs": [{"name": "Glimmer", "quantity": 5000}]}]
    md = plan.render_md(doc)
    assert "Week until" not in md
    assert "   Where: Ada-1 (on sale until 2026-10-13 · 5000 Glimmer)" in md


def test_format_source():
    assert plan.format_source(SE) == "Salvation's Edge (raid)"
    assert plan.format_source({"type": "world", "name": "Pantheon"}) == "Pantheon"
    assert plan.format_source({"type": "vendor", "name": "Xûr", "until": None,
                               "costs": [{"name": "Glimmer", "quantity": 0},
                                         {"name": "Legendary Shards", "quantity": 3}]}) == \
        "Xûr (on sale · 3 Legendary Shards)"
    assert plan.format_source({"type": "vendor", "name": "Kiosk", "until": None,
                               "costs": [{"name": "Glimmer", "quantity": 0}]}) == "Kiosk (on sale)"


def test_display_sources_groups_activities():
    found = [
        {"type": "activity", "name": "Salvation's Edge: Master", "boost": None, "until": E},
        {"type": "activity", "name": "Salvation's Edge: Standard", "boost": None, "until": E},
        {"type": "activity", "name": "Salvation's Edge: Standard", "boost": "focus", "until": E},
        SE,
        {"type": "activity", "kind": "raid", "name": "Vow of the Disciple", "detail": "x"},
    ]
    assert [plan.format_source(s) for s in plan.display_sources(found)] == [
        "Salvation's Edge (until 2026-10-13)", "Salvation's Edge (focus, until 2026-10-13)",
        "Vow of the Disciple (raid)"]
    assert plan.display_sources([SE]) == [SE]


def test_render_md_with_build():
    doc = plan.build_plan(NEEDS, STATE, None, INDEX, {}, "2026-10-07", build="b")
    assert plan.render_md(doc).startswith("# TODO for 2026-10-07 — b\n")


def test_summary():
    doc = plan.build_plan(NEEDS, STATE, CTX, INDEX, {}, "2026-10-07")
    assert plan.summary(doc, top=2) == [
        "This week · Promised Warlock Helmet — Demolitionist · 0.15 · Contest of Elders (focus, until 2026-10-13)",
        "When you can · Masterwork: Other · 0.02 · masterwork in game",
    ]


def _dirs(tmp_path):
    todo_dir, week_dir = tmp_path / "todo", tmp_path / "week"
    todo_dir.mkdir()
    week_dir.mkdir()
    (todo_dir / "needs.json").write_text(json.dumps(NEEDS), encoding="utf-8")
    return todo_dir, week_dir


def test_run_writes_files(tmp_path):
    todo_dir, week_dir = _dirs(tmp_path)
    (todo_dir / "state.json").write_text(json.dumps(STATE), encoding="utf-8")
    (week_dir / "2026-10-07.json").write_text(json.dumps(CTX), encoding="utf-8")
    doc = plan.run(todo_dir, week_dir, INDEX, {}, NOW)
    assert json.loads((todo_dir / "2026-10-07.json").read_text(encoding="utf-8")) == doc
    assert (todo_dir / "2026-10-07.md").read_text(encoding="utf-8") == plan.render_md(doc)
    assert doc["warnings"] == [plan.NO_ROTATION]          # no rotation cached in this test


def test_run_with_build_writes_separate_files(tmp_path):
    todo_dir, week_dir = _dirs(tmp_path)
    doc = plan.run(todo_dir, week_dir, INDEX, {}, NOW, build="b")
    assert not (todo_dir / "2026-10-07.json").exists() and not (todo_dir / "2026-10-07.md").exists()
    assert json.loads((todo_dir / "2026-10-07-b.json").read_text(encoding="utf-8")) == doc
    assert (todo_dir / "2026-10-07-b.md").read_text(encoding="utf-8").startswith("# TODO for 2026-10-07 — b\n")
    assert doc["build"] == "b"


def test_run_without_needs(tmp_path):
    with pytest.raises(ValueError, match="Call farm_needs first"):
        plan.run(tmp_path, tmp_path, INDEX, {}, NOW)


def test_render_md_labels_aegis_needs():
    needs_doc = {"date": "2026-10-09", "warnings": [], "needs": [
        need("aegis/truth", "aegis", "Aegis: Truth", {"name": "Truth", "type": "weapon", "source": "Kiosk"}, 0.1,
             build="aegis", effects=["Aegis role: exotic sustained heavy (priority high)"])]}
    doc = plan.build_plan(needs_doc, {}, None, INDEX, {}, "2026-10-09")
    md = plan.render_md(doc)
    assert "For: Aegis Shopping List (Aegis role: exotic sustained heavy (priority high))" in md
    assert "Where: Kiosk" in md


def write_rotation(tmp_path):
    from tests.sources.test_distortions import ORDER
    folder = tmp_path / "cache" / "distortions"
    folder.mkdir(parents=True)
    (folder / "rotation.json").write_text(json.dumps(
        {"order": ORDER, "anchor_hour": 494803, "anchor_index": 5, "source": "u", "fetched": "2026-10-07"}),
        encoding="utf-8")


def test_run_adds_distorted_times(tmp_path, isolated_dirs):
    todo_dir, week_dir = _dirs(tmp_path)
    write_rotation(isolated_dirs)
    manual = {"catalyst/collective-obligation": [{"type": "activity", "name": "Europa"},
                                                 {"type": "vendor", "name": "Ada-1"}]}
    doc = plan.run(todo_dir, week_dir, INDEX, manual, NOW)
    by_id = {e["id"]: e for e in doc["entries"]}
    line = by_id["catalyst/collective-obligation"]["distorted"]
    assert line.startswith("Europa ") and line.count("Europa") == 1 and ", then every 7 h (UTC" in line
    assert "distorted" not in by_id["masterwork/9"] and plan.NO_ROTATION not in doc["warnings"]
    assert f"   Distorted: {line}\n" in plan.render_md(doc)


def test_run_warns_about_an_old_rotation(tmp_path, isolated_dirs):
    todo_dir, week_dir = _dirs(tmp_path)
    write_rotation(isolated_dirs)
    manual = {"catalyst/collective-obligation": [{"type": "activity", "name": "Exploring Europa"}]}
    doc = plan.run(todo_dir, week_dir, INDEX, manual, NOW + timedelta(days=8))
    assert any(w.startswith("rotation fetched on 2026-10-07") for w in doc["warnings"])
    assert not any("rotation fetched" in w for w in plan.run(todo_dir, week_dir, INDEX, manual, NOW)["warnings"])


def test_run_without_rotation_warns(tmp_path):
    todo_dir, week_dir = _dirs(tmp_path)
    doc = plan.run(todo_dir, week_dir, INDEX, {"catalyst/collective-obligation": [{"type": "activity", "name": "Moon"}]},
                   NOW)
    assert plan.NO_ROTATION in doc["warnings"] and "Distorted:" not in plan.render_md(doc)
