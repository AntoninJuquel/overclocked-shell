import json

import pytest

from shell.engines.builds import mods
from shell.engines.builds.inventory import Piece
from shell.engines.builds.stats import STATS
from shell.engines.todo import needs, state as state_mod
from tests.sources.aegis.conftest import write_aegis

COSTS = {**{f"{s} Mod": 3 for s in STATS}, **{f"Minor {s} Mod": 1 for s in STATS}}
Z = dict.fromkeys(STATS, 0)


def p(item_id, slot, *, exotic=False, set_=None, mw_todo=False, energy=11, **st):
    return Piece(item_id=item_id, name=item_id, slot=slot, tier=5, exotic=exotic, stats={**Z, **st},
                 energy=energy, tuned=None, set=set_, masterwork_todo=mw_todo, location="Warlock", locked=True)


def combo(**over):
    base = {"Helmet": p("h1", "Helmet", Health=30), "Gauntlets": p("g1", "Gauntlets", Health=30),
            "Chest": p("x", "Chest", exotic=True, Health=10), "Legs": p("l1", "Legs", Health=30),
            "Class Item": p("c1", "Class Item", Health=30)}
    base.update(over)
    return tuple(base.values())


INTENT = {"exotic": {"name": "x"}, "stats": {"minimums": {}, "priority": ["Grenade"]}, "sets": [], "armor_mods": {}}


def ctx(intent=INTENT):
    return needs.Ctx(slug="b", intent=intent, frag={}, costs=COSTS, cls="Warlock")


@pytest.fixture
def aegis_dir(isolated_dirs):
    return isolated_dirs / "cache" / "aegis"


def test_virtual_piece_stats():
    v = needs.virtual_piece("Helmet", "Promised", "Demolitionist", "Health", "Warlock")
    assert v.stats == {"Weapons": 5, "Health": 20, "Class": 25, "Grenade": 30, "Super": 5, "Melee": 5}
    assert v.set == "Promised" and v.energy == 11 and not v.masterwork_todo and not v.exotic
    assert v.item_id == "armor/Warlock/Helmet/Promised/Demolitionist/Health"
    assert v.name == "Helmet Promised Warlock — Demolitionist (Grenade/Class), tertiary Health"
    with pytest.raises(ValueError):
        needs.virtual_piece("Helmet", None, "Demolitionist", "Grenade", "Warlock")


def test_virtual_piece_without_set_id():
    v = needs.virtual_piece("Legs", None, "Gunner", "Class", "Warlock")
    assert v.item_id == "armor/Warlock/Legs/-/Gunner/Class"
    assert v.name.startswith("Legs legendary Warlock")


def test_score_weights_sets_minimums_priorities():
    intent = {"stats": {"minimums": {"Health": 100}, "priority": ["Grenade", "Class"]},
              "sets": [{"set": "AION", "pieces": 2}]}
    c = combo(Helmet=p("h2", "Helmet", set_="AION"))
    res = mods.Result(totals={**Z, "Grenade": 100, "Class": 50, "Health": 80}, choices=[], deficit={"Health": 20})
    # sets 1/2, minimums 1 - 20/100, priorities (2 × 100/200 + 1 × 50/200) / 3
    assert needs.score(c, res, intent) == pytest.approx(0.4 * 0.5 + 0.3 * 0.8 + 0.3 * (1.25 / 3))


def test_score_without_constraints_is_full():
    res = mods.Result(totals=dict(Z), choices=[])
    assert needs.score(combo(), res, {"stats": {}}) == pytest.approx(1.0)


def test_merge_combines_builds_of_same_id():
    a = {"id": "x", "kind": "masterwork", "label": "X", "target": {}, "builds": [{"build": "a", "gain": {}}]}
    b = {"id": "x", "kind": "masterwork", "label": "X", "target": {}, "builds": [{"build": "b", "gain": {}}]}
    c = {"id": "a", "kind": "upgrade", "label": "A", "target": {}, "builds": [{"build": "a", "gain": {}}]}
    out = needs.merge([a, b, c])
    assert [n["id"] for n in out] == ["a", "x"]
    assert [x["build"] for x in out[1]["builds"]] == ["a", "b"]
    assert [x["build"] for x in a["builds"]] == ["a"]   # original entry untouched


def test_slot_upgrades_target_priority_stat():
    out = needs.slot_upgrades(combo(), ctx())
    assert [n["target"]["slot"] for n in out] == ["Helmet", "Gauntlets", "Legs", "Class Item"]
    for n in out:
        slot = n["target"]["slot"]
        assert n["kind"] == "armor"
        # only Grenade counts: Demolitionist and Grenadier, any tertiary, are tied
        assert n["target"] == {"class": "Warlock", "slot": slot, "set": None,
                               "archetypes": ["Demolitionist", "Grenadier"], "tertiaries": None}
        assert n["id"] == f"armor/Warlock/{slot}/-/Demolitionist+Grenadier/*"
        gain = n["builds"][0]
        assert gain["build"] == "b"
        assert gain["gain"]["stats"]["Grenade"] == 30
        assert gain["gain"]["score"] == pytest.approx(0.3 * 30 / 200, abs=1e-3)
    assert out[0]["label"] == "Helmet legendary Warlock — Demolitionist or Grenadier, tertiary any"


def test_slot_upgrades_lists_tied_tertiaries():
    # two unreachable minimums of the same weight: tertiary Health or Melee, tied; Weapons / Super useless
    intent = {**INTENT, "stats": {"minimums": {"Health": 1000, "Melee": 1000}, "priority": ["Grenade", "Class"]}}
    n = needs.slot_upgrades(combo(), ctx(intent))[0]
    assert n["target"]["archetypes"] == ["Demolitionist"]
    assert n["target"]["tertiaries"] == ["Health", "Melee"]
    assert n["id"] == "armor/Warlock/Helmet/-/Demolitionist/Health+Melee"
    assert n["label"] == "Helmet legendary Warlock — Demolitionist, tertiary Health or Melee"


def test_slot_upgrades_id_independent_of_piece_order():
    c = combo()
    ids = [n["id"] for n in needs.slot_upgrades(c, ctx())]
    rev = [n["id"] for n in needs.slot_upgrades(tuple(reversed(c)), ctx())]
    assert sorted(ids) == sorted(rev)


def test_slot_upgrades_skip_pieces_already_ideal():
    best = needs.virtual_piece("Helmet", None, "Demolitionist", "Super", "Warlock")
    out = needs.slot_upgrades(combo(Helmet=best), ctx())
    assert [n["target"]["slot"] for n in out] == ["Gauntlets", "Legs", "Class Item"]


def test_slot_upgrades_keep_current_set_when_needed():
    intent = {**INTENT, "sets": [{"set": "AION", "pieces": 1}]}
    out = needs.slot_upgrades(combo(Helmet=p("h2", "Helmet", set_="AION", Health=30)), ctx(intent))
    assert out[0]["target"]["slot"] == "Helmet" and out[0]["target"]["set"] == "AION"
    assert out[0]["id"].startswith("armor/Warlock/Helmet/AION/")


def test_slot_upgrades_drop_unneeded_set():
    out = needs.slot_upgrades(combo(Helmet=p("h2", "Helmet", set_="Junk", Health=30)), ctx())
    assert out[0]["target"]["slot"] == "Helmet" and out[0]["target"]["set"] is None


def test_slot_upgrades_drop_set_in_excess():
    intent = {**INTENT, "sets": [{"set": "AION", "pieces": 1}]}
    c = combo(Helmet=p("h2", "Helmet", set_="AION", Health=30), Legs=p("l2", "Legs", set_="AION", Health=30))
    out = needs.slot_upgrades(c, ctx(intent))
    assert {n["target"]["slot"]: n["target"]["set"] for n in out}["Helmet"] is None


def test_set_needs_complete_missing_set():
    intent = {**INTENT, "sets": [{"set": "AION", "pieces": 2}]}
    slots = {"AION": {"Helmet", "Gauntlets", "Legs", "Class Item"}}
    bonus = {"AION": ["2 pieces: Foo", "4 pieces: Bar"]}
    out, warnings = needs.set_needs(combo(), ctx(intent), slots, bonus)
    assert warnings == []
    assert len(out) == 2
    assert len({n["target"]["slot"] for n in out}) == 2
    for n in out:
        assert n["target"]["set"] == "AION"
        assert n["target"]["archetypes"] == ["Demolitionist", "Grenadier"]
        assert n["id"] == f"armor/Warlock/{n['target']['slot']}/AION/Demolitionist+Grenadier/*"
        g = n["builds"][0]["gain"]
        assert "AION — 2 pieces: Foo" in g["effects"]
        assert not any("4 pieces" in e for e in g["effects"])
        assert any(e.startswith("lot of 2 pieces, with: ") for e in g["effects"])
        assert g["score"] > 0.4 * 1.0 / 2 - 0.01   # the full set is worth 0.4 × 1, shared by 2 pieces


def test_set_needs_warn_when_set_has_no_piece_for_class():
    intent = {**INTENT, "sets": [{"set": "AION", "pieces": 2}]}
    out, warnings = needs.set_needs(combo(), ctx(intent), {"AION": {"Helmet"}}, {})
    assert out == []
    assert warnings == ["b: set AION: 1 slot(s) available for Warlock out of 2 needed, need not generated"]


def test_set_needs_nothing_when_set_satisfied():
    intent = {**INTENT, "sets": [{"set": "AION", "pieces": 2}]}
    c = combo(Helmet=p("h2", "Helmet", set_="AION"), Legs=p("l2", "Legs", set_="AION"))
    assert needs.set_needs(c, ctx(intent), {"AION": {"Helmet", "Legs"}}, {}) == ([], [])


def test_set_needs_two_sets_use_disjoint_slots():
    intent = {**INTENT, "sets": [{"set": "A", "pieces": 2}, {"set": "B", "pieces": 2}]}
    legs = {"Helmet", "Gauntlets", "Legs", "Class Item"}
    out, warnings = needs.set_needs(combo(), ctx(intent), {"A": legs, "B": legs}, {})
    assert warnings == []
    assert len(out) == 4
    by_set = {}
    for n in out:
        by_set.setdefault(n["target"]["set"], set()).add(n["target"]["slot"])
    assert set(by_set) == {"A", "B"} and len(by_set["A"]) == 2 and len(by_set["B"]) == 2
    assert not by_set["A"] & by_set["B"]
    for n in out:   # each completed set is worth 0.4 × 2/4, shared by 2 pieces
        assert n["builds"][0]["gain"]["score"] > 0.4 * 0.5 / 2 - 0.01


def test_set_needs_effects_only_newly_active_bonuses():
    intent = {**INTENT, "sets": [{"set": "AION", "pieces": 4}]}
    c = combo(Helmet=p("h2", "Helmet", set_="AION", Health=30), Gauntlets=p("g2", "Gauntlets", set_="AION", Health=30))
    slots = {"AION": {"Helmet", "Gauntlets", "Legs", "Class Item"}}
    bonus = {"AION": ["2 pieces: Foo", "4 pieces: Bar"]}
    out, warnings = needs.set_needs(c, ctx(intent), slots, bonus)
    assert warnings == [] and len(out) == 2
    for n in out:
        effects = n["builds"][0]["gain"]["effects"]
        assert "AION — 4 pieces: Bar" in effects
        assert "AION — 2 pieces: Foo" not in effects


def test_set_needs_warn_when_gain_too_small():
    # completing A can only break B, whose pieces are already ideal: no gain
    intent = {**INTENT, "sets": [{"set": "A", "pieces": 2}, {"set": "B", "pieces": 2}]}
    c = combo(Helmet=needs.virtual_piece("Helmet", "B", "Demolitionist", "Super", "Warlock"),
              Gauntlets=needs.virtual_piece("Gauntlets", "B", "Demolitionist", "Super", "Warlock"))
    out, warnings = needs.set_needs(c, ctx(intent), {"A": {"Helmet", "Gauntlets"}}, {})
    assert out == []
    assert len(warnings) == 1 and warnings[0].startswith("b: set A: completing it only gains ")
    assert warnings[0].endswith("score (minimum 0.005), need not generated")


@pytest.fixture
def base_not_rated(monkeypatch):
    """The base combination (holding h1) cannot be rated; variants without h1 can."""
    real = needs.optimize.evaluate
    monkeypatch.setattr(needs.optimize, "evaluate",
                        lambda combo, *a, **k: None if any(x.item_id == "h1" for x in combo) else real(combo, *a, **k))


def test_needs_empty_when_base_combo_not_rated(base_not_rated):
    intent = {**INTENT, "sets": [{"set": "AION", "pieces": 2}]}
    c = combo(Helmet=p("h1", "Helmet", mw_todo=True, Health=30))
    assert needs.slot_upgrades(c, ctx()) == []
    assert needs.masterwork_needs(c, {"h1": {"stats": dict(Z), "plugs": []}}, ctx()) == []
    out, warnings = needs.set_needs(c, ctx(intent), {"AION": {"Helmet", "Legs"}}, {})
    assert out == [] and warnings == ["b: utility mods impossible on the combination, set needs not generated"]


def test_score_ignores_empty_set_entries_and_clamps_minimums():
    intent = {"stats": {"minimums": {"Health": 100}, "priority": []}, "sets": [{"set": "AION", "pieces": 0}]}
    res = mods.Result(totals=dict(Z), choices=[], deficit={"Health": 250})
    assert needs.score(combo(), res, intent) == pytest.approx(0.4 + 0.3)


def test_masterwork_need_gain():
    piece = p("h9", "Helmet", mw_todo=True, Health=30, Grenade=25, Super=20, Weapons=5, Class=5, Melee=5)
    items = {"h9": {"stats": {**Z, "Health": 30, "Grenade": 25, "Super": 20}, "plugs": []}}
    intent = {**INTENT, "stats": {"minimums": {}, "priority": ["Class"]}}
    out = needs.masterwork_needs(combo(Helmet=piece), items, ctx(intent))
    assert [n["id"] for n in out] == ["masterwork/h9"]
    n = out[0]
    assert n["kind"] == "masterwork" and n["label"] == "Masterwork: h9"
    assert n["target"] == {"itemId": "h9", "name": "h9", "slot": "Helmet"}
    g = n["builds"][0]["gain"]
    assert g["stats"]["Class"] == 5
    assert g["score"] > 0


def test_masterwork_need_skips_done_and_unknown_items():
    piece = p("h9", "Helmet", mw_todo=True)
    assert needs.masterwork_needs(combo(Helmet=piece), {}, ctx()) == []
    assert needs.masterwork_needs(combo(), {}, ctx()) == []


def test_gap_needs():
    gaps = [{"kind": "catalyst", "target": "Collective Obligation", "effects": ["Repulsor Brace"]}]
    assert needs.gap_needs(gaps, "b") == [{
        "id": "catalyst/collective-obligation", "kind": "catalyst", "label": "Catalyst: Collective Obligation",
        "target": {"name": "Collective Obligation"},
        "builds": [{"build": "b", "gain": {"stats": {}, "effects": ["Repulsor Brace"], "score": 0.1}}]}]
    assert needs.gap_needs([{"kind": "weapon", "target": "Ex Diris"}], "b")[0]["label"] == "Weapon: Ex Diris"


def item(item_id, slot, *, exotic=False, item_hash=0, masterworked=True, **st):
    return {"itemId": item_id, "itemHash": item_hash, "name": item_id, "slot": slot, "classType": "Warlock",
            "rarity": "Exotic" if exotic else "Legendary", "location": "Warlock", "locked": True,
            "masterworked": masterworked, "gearTier": 5, "energy": "11/11", "stats": {**Z, **st}, "plugs": [],
            "tunedStat": None}


ITEMS = [item("h1", "Helmet", Health=30, Grenade=25, Super=20, masterworked=False),
         item("g1", "Gauntlets", Health=30, Weapons=25, Class=20),
         item("x", "Chest", exotic=True, Health=30, Class=25, Super=20),
         item("l1", "Legs", Health=30, Weapons=25, Class=20),
         item("c1", "Class Item", Health=30, Weapons=25, Class=20)]

SHEET = {"name": "B", "class": "Warlock", "subclass": {"element": "Void", "fragments": []},
         "intent": {"exotic": {"name": "x"}, "stats": {"minimums": {}, "priority": ["Grenade"]},
                    "sets": [], "armor_mods": {}},
         "resolved": {"armor": [{"slot": s, "itemId": i, "name": i} for s, i in
                                [("Helmet", "h1"), ("Gauntlets", "g1"), ("Chest", "x"), ("Legs", "l1"),
                                 ("Class Item", "c1")]],
                      "gaps": [{"kind": "catalyst", "target": "Cat"}]}}


def test_build_needs_lists_all_kinds():
    out, warnings, complete = needs.build_needs(SHEET, "b", ITEMS, {}, COSTS, lambda cls: {})
    kinds = {n["kind"] for n in out}
    assert kinds == {"catalyst", "masterwork", "armor"} and warnings == [] and complete


def test_build_needs_warns_when_resolved_piece_is_gone():
    out, warnings, complete = needs.build_needs(SHEET, "b", ITEMS[1:], {}, COSTS, lambda cls: {})
    assert [n["kind"] for n in out] == ["catalyst"]
    assert warnings == ["b: resolved pieces missing from the snapshot (h1): run optimize_build again"]
    assert not complete


def test_build_needs_keeps_gap_needs_when_armor_part_fails():
    s = {**SHEET, "intent": {**SHEET["intent"], "armor_mods": {"Helmet": ["Bogus Mod"]}}}
    out, warnings, complete = needs.build_needs(s, "b", ITEMS, {}, COSTS, lambda cls: {})
    assert [n["id"] for n in out] == ["catalyst/cat"] and not complete
    assert len(warnings) == 1 and warnings[0].startswith("b: ") and "Bogus Mod" in warnings[0]


def test_build_needs_without_armor_result():
    s = {**SHEET, "resolved": {"gaps": []}}
    # still complete (as dim-agent: the needs come back once the sheet is resolved), but no longer silent
    assert needs.build_needs(s, "b", ITEMS, {}, COSTS, lambda cls: {}) == (
        [], ["b: no resolved armor, armor needs not computed (run optimize_build)"], True)


def _run(tmp_path, builds):
    bdir, tdir = tmp_path / "builds", tmp_path / "todo"
    bdir.mkdir(exist_ok=True)
    for name, content in builds.items():
        (bdir / f"{name}.json").write_text(content if isinstance(content, str) else json.dumps(content),
                                           encoding="utf-8")
    return needs.run(bdir, tdir, ITEMS, {}, COSTS, lambda cls: {}, "2026-10-07"), tdir, bdir


def test_run_writes_needs_state_and_sheet(tmp_path):
    (tmp_path / "todo").mkdir()
    (tmp_path / "todo" / "state.json").write_text(json.dumps({"armor/old": {"status": "todo", "since": "x"}}),
                                                  encoding="utf-8")
    doc, tdir, bdir = _run(tmp_path, {"b": SHEET})
    saved = json.loads((tdir / "needs.json").read_text(encoding="utf-8"))
    assert saved == doc and saved["date"] == "2026-10-07" and saved["needs"]
    st = json.loads((tdir / "state.json").read_text(encoding="utf-8"))
    assert st["armor/old"]["status"] == "done"
    assert all(st[n["id"]]["status"] == "todo" for n in saved["needs"])
    assert "## To fetch" in (bdir / "b.md").read_text(encoding="utf-8")


def test_run_does_not_mark_done_when_a_sheet_fails(tmp_path):
    (tmp_path / "todo").mkdir()
    (tmp_path / "todo" / "state.json").write_text(json.dumps({"armor/old": {"status": "todo", "since": "x"}}),
                                                  encoding="utf-8")
    doc, tdir, _ = _run(tmp_path, {"b": SHEET, "broken": "{"})
    st = json.loads((tdir / "state.json").read_text(encoding="utf-8"))
    assert st["armor/old"]["status"] == "todo"
    assert any(w.startswith("broken: ") for w in doc["warnings"])


def test_run_includes_extra_needs(tmp_path):
    extra = [{"id": "aegis/celestial-nighthawk", "kind": "aegis", "label": "Aegis: Celestial Nighthawk",
              "target": {"name": "Celestial Nighthawk", "type": "exotic", "source": "Rahool"},
              "builds": [{"build": "aegis", "gain": {"stats": {}, "effects": [], "score": 0.1}}]}]
    bdir, tdir = tmp_path / "builds", tmp_path / "todo"
    bdir.mkdir()
    doc = needs.run(bdir, tdir, [], {}, COSTS, lambda cls: {}, "2026-10-09", extra=extra, extra_warnings=["w"])
    assert [n["id"] for n in doc["needs"]] == ["aegis/celestial-nighthawk"] and doc["warnings"] == ["w"]
    assert state_mod.load(tdir / "state.json")["aegis/celestial-nighthawk"]["status"] == "todo"


def test_aegis_needs_reads_shopping_list(aegis_dir):
    assert needs.aegis_needs([], {}, None)[0] == []
    assert needs.aegis_needs([], {}, None)[1] == [
        "Aegis Shopping List missing: call refresh_references(source='aegis') (or farm_needs(no_aegis=true))"]
    write_aegis(aegis_dir, "endgame", "shopping-list", [
        {"_name": "Celestial Nighthawk", "Role": "hunter DPS", "Priority": "high"},
        {"_name": "Gjallarhorn", "Role": "exotic DPS buff", "Priority": "high"}])
    write_aegis(aegis_dir, "endgame", "exotic-weapons", [{"_name": "Gjallarhorn", "Tier": "S"}])
    armor = [{"name": "X", "slot": "Helmet", "classType": "Hunter", "itemHash": 1, "characterId": "c", "plugs": []}]
    found, warnings, _ = needs.aegis_needs(armor, {}, None)
    assert [n["id"] for n in found] == ["aegis/celestial-nighthawk"] and "1 weapon(s)" in warnings[0]


def _state_with_aegis(tmp_path):
    (tmp_path / "todo").mkdir()
    (tmp_path / "todo" / "state.json").write_text(json.dumps({
        "aegis/truth": {"status": "todo", "since": "x"}, "armor/old": {"status": "todo", "since": "x"}}),
        encoding="utf-8")
    bdir = tmp_path / "builds"
    bdir.mkdir()
    return bdir, tmp_path / "todo"


def test_run_keep_protects_aegis_entries_when_aegis_is_incomplete(tmp_path):
    bdir, tdir = _state_with_aegis(tmp_path)
    needs.run(bdir, tdir, [], {}, COSTS, lambda cls: {}, "2026-10-10", keep=("aegis/",))
    st = state_mod.load(tdir / "state.json")
    assert st["aegis/truth"]["status"] == "todo" and st["armor/old"]["status"] == "done"


def test_run_marks_aegis_done_when_aegis_is_complete(tmp_path):
    bdir, tdir = _state_with_aegis(tmp_path)
    needs.run(bdir, tdir, [], {}, COSTS, lambda cls: {}, "2026-10-10")
    assert state_mod.load(tdir / "state.json")["aegis/truth"]["status"] == "done"


def test_partial_run_keeps_existing_aegis_todos(tmp_path, aegis_dir):
    # no weapon snapshot: the Shopping List weapons are skipped, so existing aegis/ todos must not turn done
    write_aegis(aegis_dir, "endgame", "shopping-list", [
        {"_name": "Gjallarhorn", "Role": "exotic DPS buff", "Priority": "high"}])
    write_aegis(aegis_dir, "endgame", "exotic-weapons", [{"_name": "Gjallarhorn", "Tier": "S"}])
    bdir, tdir = _state_with_aegis(tmp_path)
    extra, warnings, keep = needs.extra_needs([], {}, None)
    assert keep == ("aegis/",) and "1 weapon(s)" in warnings[0]
    needs.run(bdir, tdir, [], {}, COSTS, lambda cls: {}, "2026-10-10", extra=extra, extra_warnings=warnings,
              keep=keep)
    st = state_mod.load(tdir / "state.json")
    assert st["aegis/truth"]["status"] == "todo" and st["armor/old"]["status"] == "done"
    # with a weapon snapshot the list is complete: nothing is kept
    assert needs.extra_needs([], {}, [])[2] == ()
    # no_aegis: no Aegis needs, and the existing ones are kept
    assert needs.extra_needs([], {}, [], no_aegis=True) == ([], [], ("aegis/",))


def test_aegis_needs_reports_completeness(aegis_dir):
    assert needs.aegis_needs([], {}, None)[2] is False   # Shopping List missing
    write_aegis(aegis_dir, "endgame", "shopping-list", [
        {"_name": "Gjallarhorn", "Role": "exotic DPS buff", "Priority": "high"}])
    write_aegis(aegis_dir, "endgame", "exotic-weapons", [{"_name": "Gjallarhorn", "Tier": "S"}])
    assert needs.aegis_needs([], {}, None)[2] is False   # weapons skipped without a snapshot
    assert needs.aegis_needs([], {}, [])[2] is True


def test_aegis_needs_warns_when_weapon_tabs_are_missing(aegis_dir):
    write_aegis(aegis_dir, "endgame", "shopping-list", [
        {"_name": "Celestial Nighthawk", "Role": "hunter DPS", "Priority": "high"}])
    armor = [{"name": "X", "slot": "Helmet", "classType": "Hunter", "itemHash": 1, "characterId": "c", "plugs": []}]
    _, warnings, complete = needs.aegis_needs(armor, {}, [])
    assert warnings == ["Aegis weapon tabs missing: Shopping List weapons may be taken for exotic armor "
                        "(call refresh_references(source='aegis'))"]
    assert complete is False


def test_run_skips_scratch_sheets(tmp_path):
    doc, _, bdir = _run(tmp_path, {"bravery": {**SHEET, "scratch": True}})
    assert doc["needs"] == [] and not (bdir / "bravery.md").exists()
