import copy

from shell.engines import build_icons
from tests.engines.test_share import DEFS, SHEET, SOCKET_TYPES, plug


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


def run(s=SHEET, defs=None):
    return build_icons.refs(s, defs or fixture(), SOCKET_TYPES, STATS)


def test_subclass_and_plugs():
    out, _ = run()
    assert out["plug:Storm Grenade"] == icon("Storm Grenade")
    assert out["plug:Song of Flame"] == icon("Song of Flame-P")        # Prismatic copy (11), not Solar (10)


def test_items_come_from_the_intent_not_the_resolved_ones():
    s = copy.deepcopy(SHEET)
    s["intent"]["weapons"] = [{"slot": "Kinetic", "items": [{"name": "DECATUR 02", "hash": 2001}],
                               "perks": [[{"name": "Physic", "hash": 60}]]}]
    s["resolved"]["weapons"] = [{"slot": "Kinetic", "itemId": "w", "name": "Stand-in", "mod": "Other"}]
    out, warnings = run(s)
    assert out["item:DECATUR 02"] == "/icons/decatur.jpg" and out["perk:Physic"] == "/icons/physic.jpg"
    assert "item:Hood" not in out and "item:Stand-in" not in out and "perk:Other" not in out


def test_hashes_of_what_has_a_page():
    s = copy.deepcopy(SHEET)
    s["intent"]["weapons"] = [{"slot": "Kinetic", "items": [{"name": "DECATUR 02", "hash": 2001}]}]
    defs = fixture()
    defs["2001"]["hash"] = 2001
    stats = {"1735777505": {**STATS["1735777505"], "hash": 1735777505}}
    hashes = {}
    build_icons.refs(s, defs, SOCKET_TYPES, stats, hashes=hashes)
    assert hashes == {"item:DECATUR 02": 2001}


def test_weapon_options_without_a_hash_are_found_by_name():
    s = copy.deepcopy(SHEET)
    s["intent"]["weapons"] = [{"slot": "Kinetic", "items": [{"name": "DECATUR 02"}], "mods": [{"name": "Physic"}]}]
    out, _ = run(s)
    assert out["item:DECATUR 02"] == "/icons/decatur.jpg" and out["perk:Physic"] == "/icons/physic.jpg"


def test_mods_come_from_the_intent():
    s = copy.deepcopy(SHEET)
    s["intent"]["armor_mods"] = {"Class Item": ["Time Dilation"]}
    out, _ = run(s)
    assert out["mod:Time Dilation"] == "/icons/mod.jpg"               # the mod, not the emblem of the same name
    assert "mod:Grenade Mod" not in out and "mod:Ashes to Assets" not in out


def test_artifact_and_stats():
    out, _ = run()
    assert out["artifact:Hunter's Journal"] == "/icons/journal.jpg"
    assert out["artifact:Shieldcrush"] == "/icons/shieldcrush.jpg"
    assert out["stat:Grenade"] == "/icons/grenade_stat.jpg"


def test_unknown_names_warn():
    s = copy.deepcopy(SHEET)
    s["subclass"]["fragments"] = ["Facet of Nothing"]
    out, warnings = run(s)
    assert "plug:Facet of Nothing" not in out and any("Facet of Nothing" in w for w in warnings)


SETS = {"7": {"displayProperties": {"name": "Great Hunt"},
              "setPerks": [{"requiredSetCount": 4, "sandboxPerkHash": 72}, {"requiredSetCount": 2, "sandboxPerkHash": 71}]}}
PERKS = {"71": {"displayProperties": {"name": "Taken Barrier", "icon": "/icons/barrier.png",
                                      "description": "Grenade final blows reduce damage."}},
         "72": {"displayProperties": {"name": "Taken Armaments", "icon": "/icons/armaments.png"}}}


def test_set_perks_by_piece_count():
    perks, warnings = build_icons.set_perks(SHEET, SETS, PERKS)
    assert perks == {"Great Hunt": [{"pieces": 2, "name": "Taken Barrier", "icon": "/icons/barrier.png",
                                     "description": "Grenade final blows reduce damage."},
                                    {"pieces": 4, "name": "Taken Armaments", "icon": "/icons/armaments.png",
                                     "description": ""}]}
    assert warnings == []


def test_set_perk_description_in_the_player_language():
    local = {"71": {"displayProperties": {"name": "Barriere", "description": "Moins de degats."}}}
    perks, _ = build_icons.set_perks(SHEET, SETS, PERKS, local)
    assert perks["Great Hunt"][0]["name"] == "Taken Barrier"           # names stay English: the lexicon translates
    assert perks["Great Hunt"][0]["description"] == "Moins de degats."


def test_set_perks_two_pieces_and_unknown_set():
    s = copy.deepcopy(SHEET)
    s["intent"]["sets"] = [{"set": "Great Hunt", "pieces": 2}, {"set": "Nowhere", "pieces": 2}]
    perks, warnings = build_icons.set_perks(s, SETS, PERKS)
    assert [p["name"] for p in perks["Great Hunt"]] == ["Taken Barrier"]
    assert warnings == ["set not found: Nowhere"]


def test_set_perks_follow_the_intent_not_the_resolved_sets():
    s = copy.deepcopy(SHEET)
    s["intent"]["sets"] = [{"set": "Great Hunt", "pieces": 2}]
    s["resolved"] = {"sets": []}   # the inventory reached no set
    perks, _ = build_icons.set_perks(s, SETS, PERKS)
    assert [p["name"] for p in perks["Great Hunt"]] == ["Taken Barrier"]


def test_set_perk_refs():
    out, _ = build_icons.refs(SHEET, fixture(), SOCKET_TYPES, STATS, SETS, PERKS)
    assert out["setperk:Taken Barrier"] == "/icons/barrier.png"
    assert out["setperk:Taken Armaments"] == "/icons/armaments.png"


def armor_defs():
    def piece(name, subtype, cls=2):
        return {"displayProperties": {"name": name, "icon": f"/icons/{name}.jpg"}, "itemType": 2, "classType": cls,
                "itemSubType": subtype}
    defs = fixture()
    defs["50"]["itemSubType"] = 27
    defs.update({"3001": piece("Hood of the Great Hunt", 26), "3002": piece("Gloves of the Great Hunt", 27),
                 "3003": piece("Robes of the Great Hunt", 28), "3004": piece("Boots of the Great Hunt", 29),
                 "3005": piece("Bond of the Great Hunt", 30), "3006": piece("Titan Helm of the Great Hunt", 26, 0)})
    return defs


PIECES = {**SETS["7"], "setItems": [3006, 3001, 3002, 3003, 3004, 3005]}


def test_intent_armor_exotic_and_full_set():
    assert build_icons.intent_armor(SHEET, armor_defs(), {"7": PIECES}) == {
        "Gauntlets": "Getaway Artist", "Helmet": "Hood of the Great Hunt", "Chest": "Robes of the Great Hunt",
        "Legs": "Boots of the Great Hunt", "Class Item": "Bond of the Great Hunt"}


def test_intent_armor_two_sets_leave_the_slots_free():
    s = copy.deepcopy(SHEET)
    s["intent"]["sets"] = [{"set": "Great Hunt", "pieces": 2}, {"set": "Other", "pieces": 2}]
    assert build_icons.intent_armor(s, armor_defs(), {"7": PIECES}) == {"Gauntlets": "Getaway Artist"}


def test_intent_armor_unknown_exotic():
    assert build_icons.intent_armor(SHEET, fixture(), {"7": PIECES}) == {}   # no itemSubType: slot unknown


def test_set_piece_icons():
    out, _ = build_icons.refs(SHEET, armor_defs(), SOCKET_TYPES, STATS, {"7": PIECES}, PERKS)
    assert out["item:Hood of the Great Hunt"] == "/icons/Hood of the Great Hunt.jpg"
