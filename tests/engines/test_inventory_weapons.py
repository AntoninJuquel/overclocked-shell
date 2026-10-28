from shell.engines.inventory import weapon_rows

from .fixtures import DEFS, profile


def rows(p=None):
    return weapon_rows(p or profile(), DEFS)


def by_id(p=None):
    return {r["itemId"]: r for r in rows(p)}


def test_weapon_row_fields():
    r = by_id()["g1"]
    assert {k: v for k, v in r.items() if k != "columns"} == {
        "itemId": "g1", "itemHash": 100, "name": "Gun", "type": "Auto Rifle", "rarity": "Legendary",
        "element": "Strand", "slot": "Kinetic", "ammo": "Primary", "power": 550, "gearTier": 2, "locked": True,
        "crafted": True, "equipped": False, "location": "Vault", "characterId": None, "frame": "Rapid-Fire Frame",
        "masterwork": "Masterworked: Handling", "mod": "Backup Mag", "stats": {"Handling": 90},
    }


def test_columns_flags_and_tracker_skipped():
    assert by_id()["g1"]["columns"] == [
        {"socketIndex": 1, "label": "Barrel", "selected": "Arrowhead Brake", "selectedHash": 11, "options": [
            {"name": "Corkscrew Rifling", "hash": 12, "enhanced": False, "canInsert": True},
            {"name": "Arrowhead Brake", "hash": 11, "enhanced": False, "canInsert": True}]},
        {"socketIndex": 2, "label": "Trait", "selected": "Kill Clip", "selectedHash": 13, "options": [
            {"name": "Kill Clip", "hash": 13, "enhanced": True, "canInsert": True}]},
    ]


def test_selected_prepended_and_cannot_insert_kept():
    p = profile()
    p["itemComponents"]["sockets"]["data"]["g1"]["sockets"][1] = {"plugHash": 12}
    options = by_id(p)["g1"]["columns"][0]["options"]
    assert [(o["hash"], o["canInsert"]) for o in options] == [(12, True), (11, False)]
    p["itemComponents"]["reusablePlugs"]["data"]["g1"]["plugs"]["1"] = [{"plugItemHash": 12, "canInsert": True}]
    p["itemComponents"]["sockets"]["data"]["g1"]["sockets"][1] = {"plugHash": 11}
    assert [o["hash"] for o in by_id(p)["g1"]["columns"][0]["options"]] == [11, 12]


def test_postmaster_weapon_keeps_class_name_and_empty_mod_ignored():
    r = by_id()["g3"]
    assert r["location"] == "Warlock" and r["characterId"] == "w" and r["mod"] == "" and r["element"] == "Kinetic"


def test_equipped_from_instance_flag():
    r = by_id()["g2"]
    assert r["equipped"] is True and r["slot"] == "Energy" and r["element"] == "Solar" and r["columns"] == []


def test_sorted_by_type_then_name():
    assert [r["name"] for r in rows()] == ["Axe", "Gun", "Bow"]
