import copy
import json
from datetime import date

from shell.engines.builds import equip_plan

SHEET = {
    "name": "T", "class": "Warlock",
    "subclass": {"element": "Arc", "super": "Stormtrance",
                 "abilities": {"melee": "Chain Lightning", "grenade": "Storm Grenade"},
                 "aspects": ["Electrostatic Mind", "Lightning Surge"],
                 "fragments": ["Spark of Shock", "Spark of Volts"]},
    "intent": {"exotic": {"name": "Getaway Artist"}, "armor_mods": {"Helmet": ["Arc Siphon"]}},
    "resolved": {
        "date": "2026-10-05",
        "armor": [
            {"slot": "Helmet", "itemId": "h", "name": "Hood", "masterwork": "todo",
             "stat_mod": "Grenade Mod", "tuning": "+Grenade / -Weapons"},
            {"slot": "Gauntlets", "itemId": "g", "name": "Getaway Artist", "masterwork": "done",
             "stat_mod": None, "tuning": None},
            {"slot": "Chest", "itemId": "c", "name": "Robes", "masterwork": "done", "stat_mod": "Class Mod",
             "tuning": None},
            {"slot": "Legs", "itemId": "l", "name": "Boots", "masterwork": "done", "stat_mod": None,
             "tuning": "Balanced Tuning"},
            {"slot": "Class Item", "itemId": "b", "name": "Bond", "masterwork": "done", "stat_mod": None,
             "tuning": None},
        ],
        "weapons": [{"slot": "Kinetic", "itemId": "w1", "name": "Adamantite"}],
        "stats": {"Weapons": 20, "Health": 70, "Class": 40, "Grenade": 140, "Super": 30, "Melee": 10},
    },
}


IDX = {"Arc": {"aspects": {"Warlock": {"Electrostatic Mind": 2, "Lightning Surge": 3}},
               "fragments": {"Spark of Shock", "Spark of Volts"},
               "abilities": {"Warlock": {"super": {"Stormtrance"}, "grenade": {"Storm Grenade"},
                                         "melee": {"Chain Lightning"}, "class": set(), "jump": set()}},
               "fragment_sockets": {"Warlock": [7, 8, 9, 10, 11, 12]}}}
COSTS = {"Grenade Mod": 3, "Class Mod": 3, "Arc Siphon": 2, "Harmonic Targeting": 1, "Ashes to Assets": 4,
         "Heavy Ammo Finder": 2}


def armor(item_id, location="Warlock", locked=True, **kw):
    return {"itemId": item_id, "name": item_id, "location": location, "locked": locked, "gearTier": 5,
            "equipped": False, "plugs": [], "tunedStat": None, **kw}


ARMOR = [armor("h", "Vault", locked=False), armor("g"), armor("c"), armor("l"), armor("b")]
WEAPONS = [{"itemId": "w1", "name": "Adamantite", "location": "Vault", "locked": True, "mod": "Backup Mag"}]
FRAG = {"Grenade": -10, "Class": 10}
TODAY = date(2026, 10, 7)


def plan(sheet=SHEET, arm=ARMOR, weap=WEAPONS, frag=FRAG, today=TODAY):
    return equip_plan.build_plan(sheet, arm, weap, frag, today, IDX, COSTS)


def test_ready_plan():
    p = plan()
    assert p["ready"] and p["problems"] == []
    assert p["warnings"] == [
        "fewer fragments than slots: the remaining slots are emptied",
        "expected stats after masterworking: Hood, lower until then"]
    assert p["character"] == "warlock"
    assert p["equip"] == ["h", "g", "c", "l", "b", "w1"]
    assert p["subclass"] == {"element": "Arc", "item": "Stormcaller",
                             "plugs": ["Stormtrance", "Storm Grenade", "Chain Lightning", "Electrostatic Mind",
                                       "Lightning Surge", {"name": "Spark of Shock", "socketIndex": 7},
                                       {"name": "Spark of Volts", "socketIndex": 8}]
                             + [{"name": "Empty Fragment Socket", "socketIndex": k} for k in (9, 10, 11)]}
    assert p["armor_sockets"] == [
        {"itemId": "h", "slot": "Helmet", "name": "Hood", "plugs": ["Grenade Mod", "+Grenade / -Weapons", "Arc Siphon"]},
        {"itemId": "c", "slot": "Chest", "name": "Robes", "plugs": ["Class Mod"]},
        {"itemId": "l", "slot": "Legs", "name": "Boots", "plugs": ["Balanced Tuning"]},
    ]
    assert p["lock"] == ["h"]
    assert p["masterwork_todo"] == ["Hood"]
    assert p["transfers"] == [{"name": "Hood", "from": "Vault"}, {"name": "Adamantite", "from": "Vault"}]
    assert p["expected_armor_stats"] == {"Weapons": 20, "Health": 70, "Class": 30, "Grenade": 150, "Super": 30,
                                         "Melee": 10}


def test_missing_item_blocks():
    p = plan(arm=ARMOR[1:])
    assert not p["ready"]
    assert "Helmet: Hood (h) not in the inventory" in p["problems"]


def test_missing_weapon_blocks():
    p = plan(weap=[])
    assert "Kinetic: Adamantite (w1) not in the inventory" in p["problems"]


def test_postmaster_blocks():
    p = plan(arm=[armor("h", "Warlock (Postmaster)")] + ARMOR[1:])
    assert "Helmet: Hood (h) in the postmaster" in p["problems"]


def test_no_resolved_armor_blocks():
    s = {**SHEET, "resolved": {}}
    p = plan(sheet=s)
    assert not p["ready"] and p["problems"] == ["no resolved armor: run optimize-build"]


def test_warnings_stale_and_no_weapons():
    s = json.loads(json.dumps(SHEET))
    s["resolved"]["date"] = "2026-09-01"
    del s["resolved"]["weapons"]
    p = plan(sheet=s)
    assert p["ready"]
    assert "result from 2026-09-01 (over 7 days old): offer optimize-build" in p["warnings"]
    assert "no resolved weapons" in p["warnings"]
    assert p["equip"] == ["h", "g", "c", "l", "b"]


def stat_sheet(**armor_fields):
    """Sheet with a single piece (Helmet) whose fields are overridden."""
    s = json.loads(json.dumps(SHEET))
    s["intent"]["armor_mods"] = armor_fields.pop("mods", {})
    s["resolved"]["armor"] = [{**s["resolved"]["armor"][0], "stat_mod": None, "tuning": None, **armor_fields}]
    return s


def helmet_plugs(sheet, **item):
    p = plan(sheet=sheet, arm=[armor("h", **item)])
    return p["armor_sockets"][0]["plugs"] if p["armor_sockets"] else None


def test_stat_mod_none_clears_installed():
    s = stat_sheet()
    assert helmet_plugs(s, plugs=["General Armor Mod: Minor Class Mod"]) == [
        {"name": "Empty Mod Socket", "socketIndex": 0}]
    assert helmet_plugs(s, plugs=["General Armor Mod: Weapons Mod"]) == [{"name": "Empty Mod Socket", "socketIndex": 0}]


def test_stat_mod_none_nothing_installed():
    assert helmet_plugs(stat_sheet(), plugs=["Upgrade Armor", "Artifice Armor Mod: Locked Artifice Socket"]) is None


def test_tuning_none_clears_installed_tuning():
    s = stat_sheet()
    assert helmet_plugs(s, plugs=["General Armor Mod: +Melee / -Health"]) == ["Empty Tuning Mod Socket"]
    assert helmet_plugs(s, plugs=["General Armor Mod: Balanced Tuning"]) == ["Empty Tuning Mod Socket"]


def test_set_stat_mod_and_tuning_kept_in_order():
    s = stat_sheet(stat_mod="Class Mod", tuning="Balanced Tuning")
    assert helmet_plugs(s, plugs=["General Armor Mod: Weapons Mod"]) == ["Class Mod", "Balanced Tuning"]


def util(*names):
    return [f"Helmet Armor Mod: {n}" for n in names]


E = [{"name": "Empty Mod Socket", "socketIndex": k} for k in (1, 2, 3)]


def test_utility_wanted_by_name_then_empties():
    s = stat_sheet(mods={"Helmet": ["Arc Siphon", "Harmonic Targeting"]})
    assert helmet_plugs(s, plugs=util("Harmonic Targeting", "Ashes to Assets", "Arc Siphon")) == [
        "Arc Siphon", "Harmonic Targeting"] + E


def test_utility_already_fitting_not_cleared():
    s = stat_sheet(mods={"Helmet": ["Arc Siphon"]})
    assert helmet_plugs(s, plugs=util("Arc Siphon")) == ["Arc Siphon"]


def test_utility_duplicates_kept():
    s = stat_sheet(mods={"Helmet": ["Arc Siphon", "Arc Siphon"]})
    assert helmet_plugs(s, plugs=util("Harmonic Targeting", "Arc Siphon", "Arc Siphon")) == [
        "Arc Siphon", "Arc Siphon"] + E
    assert helmet_plugs(s, plugs=util("Arc Siphon", "Arc Siphon")) == ["Arc Siphon", "Arc Siphon"]


def test_utility_legacy_same_rule():
    s = stat_sheet(mods={"Helmet": ["Arc Siphon"]})
    p = plan(sheet=s, arm=[armor("h", gearTier=0, plugs=util("Harmonic Targeting") * 3)])
    assert p["armor_sockets"][0]["plugs"] == ["Arc Siphon"] + E


def test_explicit_empty_clears_all():
    s = stat_sheet(mods={"Helmet": []})
    assert helmet_plugs(s, plugs=util("Arc Siphon", "Harmonic Targeting")) == E
    assert helmet_plugs(s, plugs=[]) is None


def test_absent_slot_keeps_what_fits():
    s = stat_sheet(stat_mod="Grenade Mod")          # 3 + 2 + 1 <= 10
    p = plan(sheet=s, arm=[armor("h", energy="3/10", plugs=util("Arc Siphon", "Harmonic Targeting"))])
    assert p["armor_sockets"][0]["plugs"] == ["Grenade Mod"]
    assert "Helmet: Hood: slot mods kept: Arc Siphon, Harmonic Targeting" in p["warnings"]


def test_absent_slot_removes_most_expensive_when_too_big():
    s = stat_sheet(stat_mod="Grenade Mod")          # 3 + 4 + 2 = 9 > 7
    p = plan(sheet=s, arm=[armor("h", energy="3/7", plugs=util("Arc Siphon", "Ashes to Assets"))])
    assert p["armor_sockets"][0]["plugs"] == ["Grenade Mod", "Arc Siphon"] + E
    assert "Helmet: Hood: slot mods kept: Arc Siphon; removed (energy 7 exceeded): Ashes to Assets" in p["warnings"]


def test_absent_slot_legacy_capacity_projected():
    s = stat_sheet(stat_mod="Grenade Mod")          # 3 + 4 + 2 = 9 <= 10 (legacy piece still to masterwork)
    p = plan(sheet=s, arm=[armor("h", gearTier=0, masterworked=False, energy="3/7",
                                 plugs=util("Arc Siphon", "Ashes to Assets"))])
    assert p["armor_sockets"][0]["plugs"] == ["Grenade Mod"]


def test_unknown_utility_cost_warns():
    p = plan(sheet=stat_sheet(), arm=[armor("h", energy="3/10", plugs=util("Mystery Mod"))])
    assert "Helmet: unknown cost of mod Mystery Mod (counted 0)" in p["warnings"]


def test_subclass_check_blocks():
    s = json.loads(json.dumps(SHEET))
    s["subclass"]["super"] = "Nowhere"
    p = plan(sheet=s)
    assert not p["ready"]
    assert "subclass: unknown super for Warlock Arc: Nowhere" in p["problems"]


def test_equipped_elsewhere_blocks():
    p = plan(arm=[armor("h", "Hunter", equipped=True)] + ARMOR[1:])
    assert "Helmet: Hood (h) equipped on Hunter: unequip it first" in p["problems"]
    assert not p["ready"]
    w = [{"itemId": "w1", "name": "Adamantite", "location": "Titan", "locked": True, "equipped": True}]
    assert "Kinetic: Adamantite (w1) equipped on Titan: unequip it first" in plan(weap=w)["problems"]


def test_equipped_on_own_class_is_fine():
    assert plan(arm=[armor("h", equipped=True)] + ARMOR[1:])["ready"]


def test_unreadable_date_warns():
    s = json.loads(json.dumps(SHEET))
    s["resolved"]["date"] = "yesterday"
    p = plan(sheet=s)
    assert p["ready"] and "unreadable result date: yesterday" in p["warnings"]
    del s["resolved"]["date"]
    assert not any("date" in w for w in plan(sheet=s)["warnings"])


def test_exotic_weapon_warning():
    w = [{**WEAPONS[0], "rarity": "Exotic"}]
    assert ("exotic weapon resolved with fewer than 3 weapons: an exotic equipped in another slot can block "
            "the change") in plan(weap=w)["warnings"]
    assert not any("exotic" in x for x in plan()["warnings"])


ARTIFACTS = {"Satchel": {"Wind Chill": 1, "Weakened Clear": 2, "Old God's Rite": 3}}


def test_artifact_plan():
    s = copy.deepcopy(SHEET)
    assert plan(sheet=s)["artifact"] is None
    s["intent"]["artifact"] = {"name": "Satchel", "perks": ["Wind Chill", "Weakened Clear", "Old God's Rite"]}
    p = equip_plan.build_plan(s, ARMOR, WEAPONS, FRAG, TODAY, IDX, COSTS, ARTIFACTS)
    assert p["ready"]
    assert p["artifact"]["name"] == "Satchel"
    assert [x["name"] for x in p["artifact"]["plugs"]] == [
        "Wind Chill", "Empty Artifact Mod", "Weakened Clear", "Empty Artifact Mod", "Empty Artifact Mod",
        "Old God's Rite", "Empty Artifact Mod"]
    assert "artifact: fewer perks than sockets, the remaining sockets are emptied" in p["warnings"]
    s["intent"]["artifact"]["perks"] = ["Brain Freeze"]
    p = equip_plan.build_plan(s, ARMOR, WEAPONS, FRAG, TODAY, IDX, COSTS, ARTIFACTS)
    assert not p["ready"] and p["artifact"] is None
    assert "artifact: Brain Freeze is not a perk of Satchel" in p["problems"]


def test_fragments_by_name_without_socket_layout():
    idx = copy.deepcopy(IDX)
    del idx["Arc"]["fragment_sockets"]
    p = equip_plan.build_plan(SHEET, ARMOR, WEAPONS, FRAG, TODAY, idx, COSTS)
    assert "Spark of Shock" in p["subclass"]["plugs"]
    assert ("unknown fragment sockets: a fragment may target a disabled socket; check fragment slots in game"
            in p["warnings"])


def test_no_padding_when_fragments_fill_slots():
    s = json.loads(json.dumps(SHEET))
    s["subclass"]["fragments"] = ["a", "b", "c", "d", "e"]
    p = plan(sheet=s)
    assert "Empty Fragment Socket" not in p["subclass"]["plugs"]
    assert not any("fewer fragments" in x for x in p["warnings"])


NO_TUNING_WARNING = ("snapshot without the tuning stat: installed tunings kept, real stats differ from the sheet; "
                     "refresh_inventory then re-optimize")


def test_no_tuning_data_keeps_installed_tuning():
    item = armor("h", plugs=["General Armor Mod: +Melee / -Health"])
    del item["tunedStat"]
    p = plan(sheet=stat_sheet(), arm=[item])
    assert p["armor_sockets"] == []
    assert NO_TUNING_WARNING in p["warnings"]


def test_tuning_data_clears_installed_tuning_without_warning():
    p = plan(sheet=stat_sheet(), arm=[armor("h", plugs=["General Armor Mod: +Melee / -Health"])])
    assert p["armor_sockets"][0]["plugs"] == ["Empty Tuning Mod Socket"]
    assert NO_TUNING_WARNING not in p["warnings"]


# ---- energy filling, weapon perks and mods --------------------------------------------------------------

def test_resolved_mods_override_intent_and_allow_duplicates():
    s = stat_sheet(stat_mod="Grenade Mod", mods={"Helmet": ["Arc Siphon"]})
    s["resolved"]["armor"][0]["mods"] = ["Arc Siphon", "Arc Siphon", "Heavy Ammo Finder"]
    p = plan(sheet=s, arm=[armor("h", energy="3/9", plugs=util("Harmonic Targeting"))])
    assert p["armor_sockets"][0]["plugs"] == ["Grenade Mod", "Arc Siphon", "Arc Siphon", "Heavy Ammo Finder"] + E
    assert not any("free energy" in w for w in p["warnings"])     # 3 + 2 + 2 + 2 = 9 of 9


def test_left_energy_warns():
    s = stat_sheet(stat_mod="Grenade Mod", mods={"Helmet": ["Arc Siphon"]})     # 3 + 2 = 5 of 11
    p = plan(sheet=s, arm=[armor("h", energy="0/11")])
    assert ("Helmet: Hood: 6 free energy of 11: add mods to intent.armor_mods_fill (the same mod can be used "
            "more than once) then re-optimize") in p["warnings"]
    cheap = stat_sheet(stat_mod="Grenade Mod", mods={"Helmet": ["Harmonic Targeting"] * 3})    # 3 + 3 of 11
    assert ("Helmet: Hood: 5 free energy of 11: all 3 slots are taken: replace a cheap mod in "
            "intent.armor_mods with a costlier one, then re-optimize"
            in plan(sheet=cheap, arm=[armor("h", energy="0/11")])["warnings"])
    full = stat_sheet(stat_mod="Grenade Mod", mods={"Helmet": ["Ashes to Assets", "Ashes to Assets"]})
    assert not any("free energy" in w for w in plan(sheet=full, arm=[armor("h", energy="0/11")])["warnings"])


def weapon(**kw):
    cols = [{"socketIndex": 1, "label": "Barrel", "selected": "Full Bore",
             "options": [{"name": "Full Bore"}, {"name": "Corkscrew Rifling"}]},
            {"socketIndex": 3, "label": "Trait", "selected": "Lone Wolf",
             "options": [{"name": "Lone Wolf"}, {"name": "Vorpal Weapon"}, {"name": "Snapshot Sights"}]},
            {"socketIndex": 8, "label": "Origin Trait", "selected": "Imperial Allegiance",
             "options": [{"name": "Imperial Allegiance"}]}]
    return {"itemId": "w1", "name": "Adamantite", "location": "Warlock", "locked": True, "mod": "", "columns": cols,
            **kw}


def weapon_sheet(**fields):
    s = copy.deepcopy(SHEET)
    s["resolved"]["weapons"] = [{"slot": "Kinetic", "itemId": "w1", "name": "Adamantite", **fields}]
    return s


def test_weapon_perks_and_mod_planned():
    p = plan(sheet=weapon_sheet(perks=["Full Bore", "Vorpal Weapon"], mod="Targeting Adjuster"), weap=[weapon()])
    assert p["ready"]
    assert p["weapon_perks"] == [{"itemId": "w1", "name": "Adamantite", "select": ["Vorpal Weapon"]}]
    assert p["weapon_sockets"] == [{"itemId": "w1", "name": "Adamantite", "plugs": ["Targeting Adjuster"]}]
    assert not any("Kinetic: Adamantite" in w for w in p["warnings"])


def test_weapon_already_set_up_needs_nothing():
    p = plan(sheet=weapon_sheet(perks=["Full Bore", "Lone Wolf"], mod="Backup Mag"),
             weap=[weapon(mod="Backup Mag")])
    assert p["weapon_perks"] == [] and p["weapon_sockets"] == []


def test_weapon_without_choices_warns():
    p = plan(sheet=weapon_sheet(), weap=[weapon()])
    assert ("Kinetic: Adamantite: perks to choose (columns with options: Barrel, Trait): "
            "set resolved.weapons[].perks") in p["warnings"]
    assert "Kinetic: Adamantite: no weapon mod: set resolved.weapons[].mod" in p["warnings"]
    # mod explicitly empty: no warning
    assert not any("no weapon mod" in w for w in plan(sheet=weapon_sheet(mod=None), weap=[weapon()])["warnings"])


def test_unknown_weapon_perk_blocks():
    p = plan(sheet=weapon_sheet(perks=["Firefly"], mod="Backup Mag"), weap=[weapon()])
    assert not p["ready"]
    assert "Kinetic: Adamantite: perks not in the weapon's options: Firefly" in p["problems"]


def test_more_slot_mods_than_sockets_warns():
    s = stat_sheet()
    s["resolved"]["armor"][0]["mods"] = ["Arc Siphon"] * 4
    assert "Helmet: more than 3 slot mods wanted" in plan(sheet=s, arm=[armor("h")])["warnings"]
