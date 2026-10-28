import random

import pytest

from shell.engines import bravery
from shell.engines.builds import catalog


def make_idx():
    idx = catalog.build_index({})
    arc = idx["Arc"]
    arc["aspects"]["Warlock"] = {"Arc Soul": 2, "Lightning Surge": 3, "Electrostatic Mind": 2}
    arc["fragments"] = {f"Spark {i}" for i in range(8)}
    ab = arc["abilities"]["Warlock"]
    ab["super"], ab["grenade"], ab["melee"] = {"Stormtrance", "Chaos Reach"}, {"Storm Grenade"}, {"Ball Lightning"}
    ab["class"], ab["jump"] = {"Healing Rift"}, {"Burst Glide"}
    void = idx["Void"]
    void["aspects"]["Warlock"] = {"Feed the Void": 0}
    void["fragments"] = {"Echo of Starvation"}
    void["abilities"]["Warlock"]["super"] = {"Nova Bomb"}
    return idx


def w(item_id, slot, rarity="Legendary", location="Vault", equipped=False):
    return {"itemId": item_id, "name": f"W{item_id}", "slot": slot, "rarity": rarity, "location": location,
            "equipped": equipped, "type": "Auto Rifle"}


def a(item_id, slot, cls="Warlock", rarity="Legendary", location="Vault", equipped=False, energy="0/10"):
    return {"itemId": item_id, "name": f"A{item_id}", "slot": slot, "classType": cls, "rarity": rarity,
            "location": location, "equipped": equipped, "energy": energy}


WEAPONS = [w("k1", "Kinetic"), w("k2", "Kinetic", "Exotic"), w("e1", "Energy"), w("e2", "Energy", "Exotic"),
           w("p1", "Power", "Exotic"), w("p2", "Power")]
SLOTS = ("Helmet", "Gauntlets", "Chest", "Legs", "Class Item")
ARMOR = [a(f"{s}-l", s) for s in SLOTS] + [a("helm-x", "Helmet", rarity="Exotic"),
                                           a("legs-x", "Legs", rarity="Exotic"), a("hunter", "Chest", cls="Hunter")]


def test_subclass_uses_owned_elements_and_fragment_slots():
    sub = bravery.roll_subclass("Warlock", ["Arc"], make_idx(), random.Random(1))
    assert sub["element"] == "Arc" and sub["super"] in {"Stormtrance", "Chaos Reach"}
    assert sub["abilities"] == {"grenade": "Storm Grenade", "melee": "Ball Lightning", "class": "Healing Rift",
                                "jump": "Burst Glide"}
    slots = {"Arc Soul": 2, "Lightning Surge": 3, "Electrostatic Mind": 2}
    assert len(set(sub["aspects"])) == len(sub["aspects"]) == 2
    assert len(sub["fragments"]) == len(set(sub["fragments"])) == sum(slots[x] for x in sub["aspects"])


def test_no_fragments_when_aspects_give_none():
    sub = bravery.roll_subclass("Warlock", ["Void"], make_idx(), random.Random(2))
    assert sub["aspects"] == ["Feed the Void"] and sub["fragments"] == [] and "grenade" not in sub["abilities"]


def test_weapons_one_per_slot_at_most_one_exotic():
    for seed in range(100):
        rolled = bravery.roll_weapons(WEAPONS, random.Random(seed))
        assert [x["slot"] for x in rolled] == ["Kinetic", "Energy", "Power"]
        exotics = [x for x in rolled if x["itemId"] in {"k2", "e2", "p1"}]
        assert len(exotics) <= 1


def test_armor_exactly_one_exotic_and_class_only():
    for seed in range(50):
        rolled = bravery.roll_armor(ARMOR, "Warlock", random.Random(seed))
        assert [x["slot"] for x in rolled] == list(SLOTS)
        assert sum(x["itemId"] in {"helm-x", "legs-x"} for x in rolled) == 1 and "hunter" not in str(rolled)


def test_no_exotic_armor_raises():
    with pytest.raises(ValueError, match="no exotic armor for Titan"):
        bravery.roll_armor([a("t", "Helmet", cls="Titan")], "Titan", random.Random(0))


def test_postmaster_and_other_class_equipped_skipped():
    weapons = [w("pm", "Kinetic", location="Hunter (Postmaster)"), w("eq", "Kinetic", location="Hunter",
                                                                     equipped=True), w("ok", "Kinetic")]
    for seed in range(20):
        assert bravery.roll_weapons(weapons, random.Random(seed), "Warlock")[0]["itemId"] == "ok"


MODS = {"Helmet": {"Ashes to Assets": 3, "Heavy Ammo Finder": 2, "Hands-On": 1},
        "Legs": {"Recuperation": 1, "Void Weapon Surge": 3}}


def test_mods_fit_energy_and_slot():
    entries = [{"slot": "Helmet", "itemId": "h"}, {"slot": "Legs", "itemId": "l"}, {"slot": "Chest", "itemId": "c"}]
    items = [a("h", "Helmet", energy="3/10"), a("l", "Legs", energy="0/2"), a("c", "Chest")]
    for seed in range(30):
        mods = bravery.roll_mods(entries, items, MODS, random.Random(seed))
        assert len(mods["Helmet"]) <= 3 and sum(MODS["Helmet"][m] for m in mods["Helmet"]) <= 10
        assert all(m == "Recuperation" for m in mods["Legs"]) and sum(1 for _ in mods["Legs"]) <= 2
        assert mods.get("Chest", []) == []


def test_unknown_energy_gives_no_mods():
    entries = [{"slot": "Helmet", "itemId": "h"}]
    assert bravery.roll_mods(entries, [a("h", "Helmet", energy="?/?")], MODS, random.Random(0)) == {"Helmet": []}


def test_slot_mods_base_copy():
    def mod(name, cat, cost, coll):
        return {"displayProperties": {"name": name}, "collectibleHash": coll,
                "plug": {"plugCategoryIdentifier": cat, "energyCost": {"energyCost": cost}}}
    defs = {"1": mod("Ashes to Assets", "enhancements.v2_head", 3, 9), "2": mod("Ashes to Assets",
                                                                                  "enhancements.v2_head", 1, None),
            "3": mod("Grenade Mod", "enhancements.v2_general", 3, 9), "4": mod("Recuperation",
                                                                               "enhancements.v2_legs", 1, 7)}
    assert bravery.slot_mods(defs) == {"Helmet": {"Ashes to Assets": 3}, "Legs": {"Recuperation": 1}}


def test_mods_budget_keeps_room_for_the_installed_stat_mod():
    entries = [{"slot": "Helmet", "itemId": "h"}]
    for seed in range(30):
        mods = bravery.roll_mods(entries, [a("h", "Helmet", energy="5/4")], MODS, random.Random(seed), {"h": 3})
        assert sum(MODS["Helmet"][m] for m in mods["Helmet"]) <= 1
