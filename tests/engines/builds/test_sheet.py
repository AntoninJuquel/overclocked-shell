import copy
import json
import re

import pytest

from shell.engines.builds import sheet

SHEET = {
    "name": "Warlock Arc grenades",
    "class": "Warlock",
    "activity": "GM Nightfall",
    "concept": "Arc grenades on a loop.",
    "subclass": {
        "element": "Arc",
        "super": "Stormtrance",
        "abilities": {"grenade": "Storm Grenade"},
        "aspects": ["Electrostatic Mind", "Lightning Surge"],
        "fragments": ["Spark of Shock", "Spark of Magnitude"],
    },
    "intent": {
        "exotic": {"name": "Getaway Artist"},
        "stats": {"minimums": {"Grenade": 150, "Health": 70}, "priority": ["Class", "Super"]},
        "sets": [{"set": "AION Renewal", "pieces": 2}],
        "armor_mods": {"Helmet": ["Arc Siphon"], "Gauntlets": [], "Chest": [], "Legs": [], "Class Item": []},
        "weapons": [{"slot": "Kinetic", "role": "add clear"}],
    },
}


def test_valid_sheet_passes():
    sheet.validate(copy.deepcopy(SHEET))


def test_named_weapon_options():
    s = copy.deepcopy(SHEET)
    w = s["intent"]["weapons"][0]
    w.update(items=[{"name": "DECATUR 02", "hash": 1}], perks=[[{"name": "Physic"}, {"name": "Attrition Orbs"}]],
             mods=[{"name": "Ballistics"}], masterworks=[{"name": "Masterworked: Range"}])
    sheet.validate(s)
    for key, value, field in (("items", [], "items"), ("perks", [[]], "perks[0]"), ("mods", [{"hash": 1}], "mods[0].name"),
                              ("items", [{"name": "x", "hash": "1"}], "items[0].hash")):
        bad = copy.deepcopy(s)
        bad["intent"]["weapons"][0][key] = value
        with pytest.raises(sheet.SheetError, match=rf"intent\.weapons\[0\]\.{re.escape(field)}"):
            sheet.validate(bad)


@pytest.mark.parametrize("path,value,field", [
    (("class",), "Paladin", "class"),
    (("subclass", "element"), "Light", "subclass.element"),
    (("intent", "stats", "minimums"), {"Grenade": 250}, "intent.stats.minimums.Grenade"),
    (("intent", "stats", "minimums"), {"Mobility": 50}, "intent.stats.minimums.Mobility"),
    (("intent", "stats", "priority"), ["Class", "Class"], "intent.stats.priority"),
    (("intent", "sets"), [{"set": "AION Renewal", "pieces": 3}], "intent.sets[0].pieces"),
    (("intent", "armor_mods"), {"Arms": []}, "intent.armor_mods.Arms"),
    (("intent", "weapons"), [{"slot": "Heavy", "role": "x"}], "intent.weapons[0].slot"),
    (("intent", "exotic"), {}, "intent.exotic.name"),
    (("intent", "weapons"), [{"slot": "Kinetic", "element": "Void"}], "intent.weapons[0].element"),
    (("intent", "weapons"), [{"slot": "Kinetic", "element": "Fire"}], "intent.weapons[0].element"),
    (("intent", "weapons"), [{"slot": "Power", "ammo": "Primary"}], "intent.weapons[0].ammo"),
    (("intent", "weapons"), [{"slot": "Kinetic", "exotic": "yes"}], "intent.weapons[0].exotic"),
    (("intent", "weapons"), [{"slot": "Kinetic", "exotic": True}, {"slot": "Power", "exotic": True}],
     "intent.weapons"),
    (("intent", "weapons"), [{"slot": "Power"}, {"slot": "Power"}], "intent.weapons[1].slot"),
    (("intent", "artifact"), {"perks": []}, "intent.artifact.name"),
    (("intent", "artifact"), {"name": "A", "perks": ["p"] * 8}, "intent.artifact.perks"),
    (("intent", "artifact"), {"name": "A", "perks": "p"}, "intent.artifact.perks"),
])
def test_invalid_field_is_named(path, value, field):
    s = copy.deepcopy(SHEET)
    node = s
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(sheet.SheetError, match="^" + re.escape(field) + ": "):
        sheet.validate(s)


def test_messages_are_english():
    s = copy.deepcopy(SHEET)
    s["intent"]["weapons"] = [{"slot": "Kinetic", "element": "Void"}]
    with pytest.raises(sheet.SheetError, match=r"^intent\.weapons\[0\]\.element: not possible in Kinetic "
                                               r"\(possible elements: Kinetic, Stasis, Strand\)$"):
        sheet.validate(s)
    with pytest.raises(sheet.SheetError, match="^sheet: must be a JSON object$"):
        sheet.validate([])


def test_resolved_sets_are_validated():
    s = copy.deepcopy(SHEET)
    s["resolved"] = {"sets": [{"set": "AION Renewal", "pieces": 3}]}
    with pytest.raises(sheet.SheetError, match=r"^resolved\.sets\[0\]\.pieces"):
        sheet.validate(s)


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "warlock-arc.json"
    sheet.save(path, copy.deepcopy(SHEET))
    assert sheet.load(path) == SHEET
    md = (tmp_path / "warlock-arc.md").read_text(encoding="utf-8")
    assert md.startswith("# Warlock Arc grenades")
    assert "Grenade ≥ 150" in md and "Class > Super" in md and "2 × AION Renewal" in md
    assert "Spark of Shock" in md
    assert "warlock-arc.json" in md and "check_build" in md


def test_slug():
    assert sheet.slug("Warlock Arc — grenades !") == "warlock-arc-grenades"


def test_folder_and_path_for(isolated_dirs):
    assert sheet.folder() == isolated_dirs / "profile" / "builds"
    assert sheet.path_for("warlock-arc") == isolated_dirs / "profile" / "builds" / "warlock-arc.json"


RESOLVED = {
    "date": "2026-10-07",
    "armor": [{"slot": "Helmet", "itemId": "1", "name": "Hood", "masterwork": None, "stat_mod": "Grenade Mod", "tuning": None}],
    "weapons": [{"slot": "Kinetic", "itemId": "9", "name": "Adamantite", "why": "x"}],
    "stats": {"Grenade": 150},
    "rationale": ["ok"],
}


def _with(path, value, base=None):
    s = copy.deepcopy(SHEET)
    if base is not None:
        s["resolved"] = copy.deepcopy(base)
    node = s
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return s


def test_valid_resolved_passes():
    s = copy.deepcopy(SHEET)
    s["resolved"] = copy.deepcopy(RESOLVED)
    sheet.validate(s)


@pytest.mark.parametrize("path,value,field", [
    (("resolved",), [], "resolved"),
    (("resolved", "date"), 5, "resolved.date"),
    (("resolved", "armor"), {}, "resolved.armor"),
    (("resolved", "armor"), ["x"], "resolved.armor[0]"),
    (("resolved", "armor"), [{"slot": "Arms", "itemId": "1", "name": "x"}], "resolved.armor[0].slot"),
    (("resolved", "armor"), [{"slot": "Helmet", "itemId": "1", "name": "x"}] * 2, "resolved.armor[1].slot"),
    (("resolved", "armor"), [{"slot": "Helmet", "itemId": "1"}], "resolved.armor[0].name"),
    (("resolved", "armor"), [{"slot": "Helmet", "name": "x"}], "resolved.armor[0].itemId"),
    (("resolved", "armor"), [{"slot": "Helmet", "itemId": "1", "name": "x", "tuning": 3}], "resolved.armor[0].tuning"),
    (("resolved", "weapons"), "x", "resolved.weapons"),
    (("resolved", "weapons"), [{"slot": "Heavy", "name": "x"}], "resolved.weapons[0].slot"),
    (("resolved", "weapons"), [{"slot": "Kinetic"}], "resolved.weapons[0].name"),
    (("resolved", "weapons"), [{"slot": "Kinetic", "itemId": "9", "name": "x", "why": 1}], "resolved.weapons[0].why"),
    (("resolved", "weapons"), [{"slot": "Kinetic", "itemId": "9", "name": "x"}] * 2, "resolved.weapons[1].slot"),
    (("resolved", "weapons"), [{"slot": "Kinetic", "name": "x"}], "resolved.weapons[0].itemId"),
    (("resolved", "weapons"), [{"slot": "Kinetic", "itemId": "9", "name": "x", "mod": 1}], "resolved.weapons[0].mod"),
    (("resolved", "weapons"), [{"slot": "Kinetic", "itemId": "9", "name": "x", "perks": "a"}],
     "resolved.weapons[0].perks"),
    (("resolved", "weapons"), [{"slot": "Kinetic", "itemId": "9", "name": "x", "perks": ["a", "a"]}],
     "resolved.weapons[0].perks"),
    (("resolved", "armor"), [{"slot": "Helmet", "itemId": "1", "name": "x", "mods": "a"}], "resolved.armor[0].mods"),
    (("resolved", "armor"), [{"slot": "Helmet", "itemId": "1", "name": "x", "mods": ["a"] * 4}],
     "resolved.armor[0].mods"),
    (("resolved", "stats"), {"Grenade": -1}, "resolved.stats.Grenade"),
    (("resolved", "stats"), [], "resolved.stats"),
    (("resolved", "stats"), {"Mobility": 5}, "resolved.stats.Mobility"),
    (("resolved", "stats"), {"Grenade": True}, "resolved.stats.Grenade"),
    (("resolved", "stats"), {"Grenade": "5"}, "resolved.stats.Grenade"),
    (("resolved", "rationale"), "x", "resolved.rationale"),
    (("resolved", "rationale"), [1], "resolved.rationale[0]"),
])
def test_invalid_resolved(path, value, field):
    with pytest.raises(sheet.SheetError, match="^" + re.escape(field)):
        sheet.validate(_with(path, value, base=RESOLVED))


@pytest.mark.parametrize("path,value,field", [
    (("intent", "stats"), [], "intent.stats"),
    (("intent", "stats", "minimums"), [], "intent.stats.minimums"),
    (("intent", "stats", "minimums"), {"Grenade": True}, "intent.stats.minimums.Grenade"),
    (("intent", "stats", "priority"), [["Class"]], "intent.stats.priority"),
    (("intent", "sets"), [{"set": "A", "pieces": True}], "intent.sets[0].pieces"),
    (("intent", "sets"), [{"set": "A", "pieces": 2}, {"set": "A", "pieces": 2}], "intent.sets[1].set"),
    (("intent", "sets"), [{"set": "A", "pieces": 4}, {"set": "B", "pieces": 2}], "intent.sets"),
    (("intent", "sets"), "x", "intent.sets"),
    (("intent", "weapons"), {}, "intent.weapons"),
    (("intent", "weapons"), ["x"], "intent.weapons[0]"),
    (("intent", "weapons"), [{"slot": "Kinetic", "role": 3}], "intent.weapons[0].role"),
    (("intent", "weapons"), [{"slot": "Kinetic", "wanted": 3}], "intent.weapons[0].wanted"),
    (("intent", "exotic"), {"name": "X", "perks": [1]}, "intent.exotic.perks"),
    (("intent", "armor_mods"), {"Helmet": "x"}, "intent.armor_mods.Helmet"),
    (("intent", "armor_mods"), {"Helmet": ["x"] * 4}, "intent.armor_mods.Helmet"),
    (("intent", "armor_mods_fill"), {"Arms": ["x"]}, "intent.armor_mods_fill.Arms"),
    (("intent", "armor_mods_fill"), [], "intent.armor_mods_fill"),
    (("subclass", "abilities"), [], "subclass.abilities"),
    (("subclass", "abilities"), {"dash": "x"}, "subclass.abilities.dash"),
    (("subclass", "abilities"), {"grenade": 1}, "subclass.abilities.grenade"),
    (("subclass", "super"), 3, "subclass.super"),
    (("subclass", "aspects"), [1], "subclass.aspects"),
    (("activity",), 3, "activity"),
    (("concept",), 3, "concept"),
])
def test_invalid_types(path, value, field):
    with pytest.raises(sheet.SheetError, match="^" + re.escape(field)):
        sheet.validate(_with(path, value))


def test_invalid_sheet_writes_nothing(tmp_path):
    path = tmp_path / "bad.json"
    with pytest.raises(sheet.SheetError):
        sheet.save(path, _with(("class",), "Paladin"))
    assert list(tmp_path.iterdir()) == []


def test_invalid_sheet_keeps_existing_files(tmp_path):
    path = tmp_path / "w.json"
    sheet.save(path, copy.deepcopy(SHEET))
    before = path.read_text(encoding="utf-8"), path.with_suffix(".md").read_text(encoding="utf-8")
    with pytest.raises(sheet.SheetError, match="^intent.stats.minimums.Mobility"):
        sheet.save(path, _with(("intent", "stats", "minimums"), {"Mobility": 50}))
    assert (path.read_text(encoding="utf-8"), path.with_suffix(".md").read_text(encoding="utf-8")) == before


def test_save_leaves_no_tmp_files(tmp_path):
    sheet.save(tmp_path / "a.json", copy.deepcopy(SHEET))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.json", "a.md"]


def test_load_invalid_json(tmp_path):
    path = tmp_path / "x.json"
    path.write_text("{oops", encoding="utf-8")
    with pytest.raises(sheet.SheetError, match="^sheet: invalid JSON"):
        sheet.load(path)


def test_load_invalid_encoding(tmp_path):
    path = tmp_path / "x.json"
    path.write_bytes(bytes([0xFF, 0xFE, 0x7B]))
    with pytest.raises(sheet.SheetError, match="^sheet: "):
        sheet.load(path)


def test_slug_empty_raises():
    with pytest.raises(ValueError):
        sheet.slug("!!! —")


def test_french_masterwork_values_migrate(tmp_path):
    s = copy.deepcopy(SHEET)
    s["resolved"] = {"armor": [
        {"slot": "Helmet", "itemId": "1", "name": "Hood", "masterwork": "à faire"},
        {"slot": "Chest", "itemId": "2", "name": "Robes", "masterwork": "fait"},
        {"slot": "Legs", "itemId": "3", "name": "Boots", "masterwork": None}],
        "rationale": ["Grenade d'abord, à faire en GM."]}
    path = tmp_path / "fr.json"
    path.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    loaded = sheet.load(path)
    assert [a["masterwork"] for a in loaded["resolved"]["armor"]] == ["todo", "done", None]
    assert loaded["resolved"]["rationale"] == ["Grenade d'abord, à faire en GM."]
    assert loaded["concept"] == SHEET["concept"]


def test_migrate_tolerates_any_shape():
    assert sheet.migrate([]) == []
    assert sheet.migrate({"resolved": "x"}) == {"resolved": "x"}
    assert sheet.migrate({"resolved": {"armor": ["x", {"masterwork": "fait"}]}}) == {
        "resolved": {"armor": ["x", {"masterwork": "done"}]}}


def test_resolved_gaps_valid():
    s = copy.deepcopy(SHEET)
    s["resolved"] = {"gaps": [{"kind": "catalyst", "target": "Collective Obligation",
                               "effects": ["Repulsor Brace: overshield"]}]}
    sheet.validate(s)


@pytest.mark.parametrize("gap, field", [
    ({"kind": "armor", "target": "X"}, "resolved.gaps[0].kind"),
    ({"kind": "weapon", "target": ""}, "resolved.gaps[0].target"),
    ({"kind": "upgrade", "target": "X", "effects": "text"}, "resolved.gaps[0].effects"),
])
def test_resolved_gaps_invalid(gap, field):
    s = copy.deepcopy(SHEET)
    s["resolved"] = {"gaps": [gap]}
    with pytest.raises(sheet.SheetError, match=re.escape(field)):
        sheet.validate(s)


def test_resolved_gaps_target_without_usable_character():
    s = copy.deepcopy(SHEET)
    s["resolved"] = {"gaps": [{"kind": "weapon", "target": "✓"}]}
    with pytest.raises(sheet.SheetError, match=re.escape("resolved.gaps[0].target")):
        sheet.validate(s)


def test_resolved_gaps_duplicate():
    s = copy.deepcopy(SHEET)
    s["resolved"] = {"gaps": [{"kind": "weapon", "target": "Foo Bar"}, {"kind": "weapon", "target": "foo  bar"}]}
    with pytest.raises(sheet.SheetError, match=re.escape("resolved.gaps[1]")) as e:
        sheet.validate(s)
    assert "duplicate gap" in str(e.value)
    s["resolved"]["gaps"][1]["kind"] = "catalyst"   # same target, other kind: not a duplicate
    sheet.validate(s)


def _todo(tmp_path, needs, state=None):
    d = tmp_path / "todo"
    d.mkdir()
    (d / "needs.json").write_text(json.dumps({"date": "2026-10-07", "needs": needs, "warnings": []}), encoding="utf-8")
    if state is not None:
        (d / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return d


def _need(nid, label, build, score, stats=None, effects=()):
    return {"id": nid, "kind": "armor", "label": label, "target": {},
            "builds": [{"build": build, "gain": {"stats": stats or {}, "effects": list(effects), "score": score}}]}


def test_needs_for_filters_build_and_status(tmp_path):
    d = _todo(tmp_path, [_need("a", "A", "mine", 0.1), _need("b", "B", "mine", 0.3), _need("c", "C", "other", 0.5),
                         _need("d", "D", "mine", 0.9)],
              state={"d": {"status": "ignored", "since": "2026-10-07"}})
    assert [n["label"] for n, _ in sheet.needs_for("mine", d)] == ["B", "A"]
    assert sheet.needs_for("mine", tmp_path / "absent") == []


def test_save_with_needs(tmp_path):
    d = _todo(tmp_path, [_need("a", "Promised Helmet", "arc", 0.2, {"Grenade": 12, "Health": -3},
                               ["Promised — 2 pieces: Foo"])])
    path = tmp_path / "arc.json"
    sheet.save(path, copy.deepcopy(SHEET), needs_dir=d)
    md = path.with_suffix(".md").read_text(encoding="utf-8")
    assert "## To fetch" in md
    assert "- Promised Helmet — Grenade +12 · Health -3; Promised — 2 pieces: Foo" in md


@pytest.mark.parametrize("content", ["[]", '{"needs": [{"id": "a"}]}', '{"needs": [{"id": "a", "builds": [{"build": "mine"}]}]}'])
def test_needs_for_malformed_needs_json(tmp_path, content):
    (tmp_path / "needs.json").write_text(content, encoding="utf-8")
    assert sheet.needs_for("mine", tmp_path) == []


def test_default_needs_dir_is_resolved_at_call_time(isolated_dirs, tmp_path):
    d = isolated_dirs / "profile" / "todo"
    d.mkdir(parents=True)
    (d / "needs.json").write_text(json.dumps({"needs": [_need("a", "A", "mine", 0.1)]}), encoding="utf-8")
    assert [n["label"] for n, _ in sheet.needs_for("mine")] == ["A"]
    path = tmp_path / "mine.json"
    sheet.save(path, copy.deepcopy(SHEET))
    assert "## To fetch" in path.with_suffix(".md").read_text(encoding="utf-8")
