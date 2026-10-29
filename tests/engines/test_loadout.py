import copy

from shell.engines.loadout import artifact_perks, equipped

from .fixtures import DEFS, profile, stats


def setup():
    defs = copy.deepcopy(DEFS)
    defs["gear"].update({"300": ["Prismatic", "Warlock Subclass", 2, 3284755031, "Common"],
                         "301": ["Broodweaver", "Warlock Subclass", 2, 3284755031, "Common"],
                         "302": ["Seasonal Artifact", "Artifact", 3, 1506418338, "Exotic"],
                         "303": ["Hunter's Journal", "Artifact", 3, 1506418338, "Exotic"]})
    defs["plugs"]["20"] = {"n": "Feed the Void", "t": "Aspect", "p": "warlock.prism.aspects"}
    p = profile()
    p["characterEquipment"]["data"]["w"]["items"] += [
        {"itemHash": 300, "itemInstanceId": "sc"}, {"itemHash": 302, "itemInstanceId": "art"}]
    p["characterInventories"]["data"]["w"]["items"] += [{"itemHash": 301, "itemInstanceId": "sc2"},
                                                        {"itemHash": 303, "itemInstanceId": "art2"}]
    comps = p["itemComponents"]
    comps["sockets"]["data"]["sc"] = {"sockets": [{"plugHash": 20}]}
    comps["sockets"]["data"]["a3"] = {"sockets": [{"plugHash": 1}]}
    comps["stats"]["data"]["a3"] = stats(Weapons=10, Health=5, Class=1, Grenade=2, Super=3, Melee=4)
    return equipped(p, defs, "w")


def test_equipped_items_and_totals():
    e = setup()
    assert e["items"] == [
        {"itemId": "a3", "name": "Bond", "type": "Warlock Bond", "exotic": False,
         "stats": {"Weapons": 10, "Health": 5, "Class": 1, "Grenade": 2, "Super": 3, "Melee": 4},
         "plugs": ["General Armor Mod: Weapons Mod"]},
        {"itemId": "g2", "name": "Bow", "type": "Combat Bow", "exotic": False, "plugs": []},
    ]
    assert e["armor_totals"] == {"Weapons": 10, "Health": 5, "Class": 1, "Grenade": 2, "Super": 3, "Melee": 4}


def test_subclass_and_artifact_separated():
    e = setup()
    assert e["subclass"] == {"itemId": "sc", "name": "Prismatic", "plugs": ["Aspect: Feed the Void"]}
    assert e["artifact"] == {"itemId": "art", "name": "Seasonal Artifact"}


def test_cosmetic_types_skipped():
    assert "gh" not in {i["itemId"] for i in setup()["items"]}


def test_other_subclasses_from_inventory():
    assert setup()["other_subclasses"] == [{"itemId": "sc2", "name": "Broodweaver"}]


def test_other_artifacts_from_inventory():
    assert setup()["other_artifacts"] == [{"itemId": "art2", "name": "Hunter's Journal"}]


def test_artifact_perks_named_from_any_category():
    defs = copy.deepcopy(DEFS)
    defs["gear"]["400"] = ["Refresh Threads", "Artifact Perk", 3, 2422292810, "Legendary"]
    item = {"sockets": {"data": {"sockets": [{"plugHash": 400}, {"plugHash": 2}, {}, {"plugHash": 999}]}}}
    assert artifact_perks(item, defs) == ["Refresh Threads"]
