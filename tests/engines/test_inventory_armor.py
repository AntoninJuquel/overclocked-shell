from shell.engines.inventory import armor_rows, tuned_stat

from .fixtures import DEFS, profile


def rows():
    return {r["itemId"]: r for r in armor_rows(profile(), DEFS)}


def test_armor_row_fields():
    assert rows()["a1"] == {
        "itemId": "a1", "itemHash": 200, "name": "Star-Eater Scales", "slot": "Legs", "classType": "Hunter",
        "rarity": "Exotic", "location": "Vault", "characterId": None, "equipped": False, "locked": True,
        "masterworked": True, "power": 10, "gearTier": 3, "energy": "9/10",
        "stats": {"Weapons": 20, "Health": 23, "Class": 4, "Grenade": 15, "Super": 17, "Melee": 4}, "total": 83,
        "plugs": ["General Armor Mod: Weapons Mod", "Upgrade Armor", "General Armor Mod: Weapons Mod",
                  "General Armor Mod: Balanced Tuning"],
        "tunedStat": "Super",
    }


def test_postmaster_location():
    r = rows()["a2"]
    assert r["location"] == "Warlock (Postmaster)" and r["characterId"] == "w" and r["equipped"] is False
    assert r["stats"] == {"Health": 30} and r["energy"] == "" and r["power"] == 0


def test_equipped_from_equipment():
    r = rows()["a3"]
    assert r["equipped"] is True and r["location"] == "Warlock" and r["gearTier"] is None
    assert r["tunedStat"] is None and r["plugs"] == []


def test_unknown_or_non_armor_items_skipped():
    assert set(rows()) == {"a1", "a2", "a3"}


def test_tuned_stat_none_without_tuning_socket():
    assert tuned_stat({}, DEFS) is None


def test_tuned_stat_ignores_non_tuning_category():
    assert tuned_stat({"plugs": {"3": [{"plugItemHash": 7, "canInsert": True}]}}, DEFS) is None
