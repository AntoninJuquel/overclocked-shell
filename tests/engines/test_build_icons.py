import copy

from shell.engines import build_icons
from tests.engines.test_share import ARMOR, DEFS, SHEET, SOCKET_TYPES, WEAPONS, plug


def icon(name):
    return f"/icons/{name.replace(' ', '_')}.jpg"


def fixture():
    defs = copy.deepcopy(DEFS)
    for h, d in defs.items():
        d["displayProperties"]["icon"] = icon(d["displayProperties"]["name"] + ("-P" if h == "11" else ""))
    defs.update({
        "1001": {"displayProperties": {"name": "Hood", "icon": "/icons/hood_a.jpg"}, "itemType": 2, "classType": 2},
        "1002": {"displayProperties": {"name": "Hood", "icon": "/icons/hood_b.jpg"}, "itemType": 2, "classType": 2},
        "2001": {"displayProperties": {"name": "DECATUR 02", "icon": "/icons/decatur.jpg"}, "itemType": 3},
        "60": {**plug("Physic", "frames"), "displayProperties": {"name": "Physic", "icon": "/icons/physic.jpg"}},
        "61": {"displayProperties": {"name": "Hunter's Journal", "icon": "/icons/journal.jpg"},
               "itemTypeDisplayName": "Artifact"},
        "62": {"displayProperties": {"name": "Shieldcrush", "icon": "/icons/shieldcrush.jpg"},
               "itemTypeDisplayName": "Artifact Perk"},
        "63": {"displayProperties": {"name": "Time Dilation", "icon": "/icons/emblem.jpg"}, "itemType": 14},
        "64": {**plug("Time Dilation", "enhancements.v2_class_item"),
               "displayProperties": {"name": "Time Dilation", "icon": "/icons/mod.jpg"}},
        "65": {**plug("+Grenade / -Weapons", "core.gear_systems.armor_tiering.plugs.tuning.mods"),
               "displayProperties": {"name": "+Grenade / -Weapons", "icon": "/icons/tuning.jpg"}},
    })
    return defs


STATS = {"1735777505": {"displayProperties": {"name": "Grenade", "icon": "/icons/grenade_stat.jpg"}}}


def run(s=SHEET, defs=None, armor=ARMOR, weapons=WEAPONS):
    return build_icons.refs(s, defs or fixture(), SOCKET_TYPES, STATS, armor, weapons)


def test_subclass_and_plugs():
    out, _ = run()
    assert out["plug:Storm Grenade"] == icon("Storm Grenade")
    assert out["plug:Song of Flame"] == icon("Song of Flame-P")        # Prismatic copy (11), not Solar (10)
    assert out["subclass:Prismatic Warlock"] == icon("Prismatic Warlock")


def test_item_icon_from_snapshot_hash():
    armor = [{"itemId": "a1", "itemHash": 1002, "name": "Hood"}, ARMOR[1]]
    out, warnings = run(armor=armor)
    assert out["item:Hood"] == "/icons/hood_b.jpg"                     # the snapshot hash, not the lowest hash
    assert not any("Hood" in w for w in warnings)


def test_item_without_snapshot_falls_back_to_name():
    out, warnings = run(armor=[], weapons=[])
    assert out["item:Hood"] == "/icons/hood_a.jpg" and out["item:DECATUR 02"] == "/icons/decatur.jpg"
    assert "Helmet: Hood not in the inventory snapshot: icon by name" in warnings


def test_mod_kind_filter():
    s = copy.deepcopy(SHEET)
    s["resolved"]["armor"][0]["mods"] = ["Time Dilation"]
    out, _ = run(s)
    assert out["mod:Time Dilation"] == "/icons/mod.jpg"


def test_tuning_label_maps():
    s = copy.deepcopy(SHEET)
    s["resolved"]["armor"][0]["tuning"] = "+Grenade / -Weapons"
    assert "mod:+Grenade / -Weapons" in run(s)[0]


def test_weapon_perk_artifact_and_stats():
    out, _ = run()
    assert out["perk:Physic"] == "/icons/physic.jpg"
    assert out["artifact:Hunter's Journal"] == "/icons/journal.jpg"
    assert out["artifact:Shieldcrush"] == "/icons/shieldcrush.jpg"
    assert out["stat:Grenade"] == "/icons/grenade_stat.jpg"


def test_unknown_names_warn():
    s = copy.deepcopy(SHEET)
    s["subclass"]["fragments"] = ["Facet of Nothing"]
    out, warnings = run(s)
    assert "plug:Facet of Nothing" not in out and any("Facet of Nothing" in w for w in warnings)
