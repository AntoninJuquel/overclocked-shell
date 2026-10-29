from datetime import datetime, timezone

from shell.engines import fashion


def orn(name, cat, coll):
    return {"displayProperties": {"name": name}, "itemType": 19, "collectibleHash": coll,
            "plug": {"plugCategoryIdentifier": cat}}


ITEMS = {
    "1": orn("Vigil of the Seraph", "armor_skins_hunter_head", 11),
    "2": orn("Vigil of the Seraph", "armor_skins_titan_head", 12),
    "3": orn("Vigil of the Seraph", "armor_skins_warlock_head", 13),
    "4": orn("Electro-Brass", "armor_skins_warlock_exotic_arms", 14),
    "5": orn("Ceramic Alloy", "shader", 15),
    "6": orn("Jade Rabbit Robes", "armor_skins_warlock_chest", 16),
    "7": orn("Tyrian Abyss", "shader", 17),
    "8": {"displayProperties": {"name": "Sunbracers"}, "itemType": 2, "classType": 2, "inventory": {"tierType": 6},
          "collectibleHash": 18, "sockets": {"socketEntries": [{"reusablePlugSetHash": 900}]}},
    "9": {"displayProperties": {"name": "Hood of the Great Hunt"}, "itemType": 2, "classType": 2,
          "collectibleHash": 19},
    "3373582085": {"displayProperties": {"name": "Bright Dust"}},
}
COLLECTIBLES = {str(c): {"sourceString": s} for c, s in (
    (11, "Source: Rewards Pass"), (12, "Source: Rewards Pass"), (13, "Source: Rewards Pass\nmore"),
    (14, "Source: Eververse"), (15, "Source: Eververse"), (16, "Source: Eververse"), (17, ""),
    (18, "Source: Exotic engrams"), (19, ""))}
PLUG_SETS = {"900": {"reusablePlugItems": [{"plugItemHash": 4}]}}
INDEX = fashion.build_index(ITEMS, COLLECTIBLES, PLUG_SETS)
NOW = datetime(2026, 10, 29, tzinfo=timezone.utc)
CTX = {"vendors": [{"vendorHash": fashion.EVERVERSE, "nextRefreshDate": "2026-11-03T17:00:00Z",
                    "sales": [{"itemHash": 6, "costs": [{"itemHash": 3373582085, "quantity": 1500}]}]}]}
LOOK = [{"slot": "Helmet", "ornament": "Vigil of the Seraph", "shader": "Ceramic Alloy"},
        {"slot": "Gauntlets", "ornament": "Electro-Brass", "shader": "Ceramic Alloy"},
        {"slot": "Chest", "ornament": "Jade Rabbit Robes", "shader": "Ceramic Alloy"},
        {"slot": "Class Item", "ornament": "Painted Kitsune Bnod", "shader": "Tyrian Abyss"}]
STATE = {13: 0, 14: 1, 15: 0, 16: 1, 18: 0}     # bit 1 = not acquired; 17 (Tyrian Abyss) absent: unknown


def test_index_kinds_classes_slots():
    vigil = INDEX["vigil of the seraph"]
    assert {(e["cls"], e["slot"], e["kind"]) for e in vigil} == {("Hunter", "Helmet", "ornament"),
                                                               ("Titan", "Helmet", "ornament"),
                                                               ("Warlock", "Helmet", "ornament")}
    assert INDEX["ceramic alloy"][0]["kind"] == "shader" and INDEX["ceramic alloy"][0]["cls"] is None
    assert INDEX["vigil of the seraph"][2]["source"] == "Rewards Pass"
    assert INDEX["hood of the great hunt"][0]["kind"] == "armor"


def test_same_name_three_classes_picks_the_character_class():
    entry, problem = fashion.resolve("Vigil of the Seraph", "ornament", "Warlock", INDEX)
    assert entry["hash"] == 3 and problem is None
    entry, problem = fashion.resolve("Jade Rabbit Robes", "ornament", "Hunter", INDEX)
    assert entry is None and problem == "not for Hunter"


def test_exotic_ornament_names_its_exotic():
    entry, _ = fashion.resolve("electro-brass", "ornament", "Warlock", INDEX)
    assert entry["exotic_for"] == "Sunbracers"


def test_armor_piece_accepted_as_ornament():
    entry, problem = fashion.resolve("Hood of the Great Hunt", "ornament", "Warlock", INDEX)
    assert entry["kind"] == "armor" and problem is None


def test_unknown_name_suggests_close_names():
    entry, problem = fashion.resolve("Painted Kitsune Bnod", "ornament", "Warlock", INDEX)
    assert entry is None and problem == "not found"
    _, problem = fashion.resolve("Jade Rabit Robes", "ornament", "Warlock", INDEX)
    assert problem == "not found (close: Jade Rabbit Robes)"


def test_owned_unknown_and_inventory():
    e = lambda n: fashion.resolve(n, "shader", "Warlock", INDEX)[0]  # noqa: E731
    assert fashion.owned(e("Ceramic Alloy"), STATE, set()) is True
    assert fashion.owned(e("Tyrian Abyss"), STATE, set()) is None              # not in the profile response
    jade = fashion.resolve("Jade Rabbit Robes", "ornament", "Warlock", INDEX)[0]
    assert fashion.owned(jade, STATE, set()) is False and fashion.owned(jade, STATE, {6}) is True


def test_eververse_lines():
    jade = fashion.resolve("Jade Rabbit Robes", "ornament", "Warlock", INDEX)[0]
    ceramic = fashion.resolve("Ceramic Alloy", "shader", "Warlock", INDEX)[0]
    assert fashion.eververse(jade, CTX, NOW, ITEMS) == "on sale: 1500 Bright Dust until 2026-11-03"
    assert fashion.eververse(ceramic, CTX, NOW, ITEMS) == "not on sale this week"
    assert fashion.eververse(jade, None, NOW, ITEMS) == "stock unknown (refresh_context)"
    assert fashion.eververse(jade, CTX, datetime(2026, 11, 5, tzinfo=timezone.utc), ITEMS) == \
        "stock unknown (refresh_context)"


def test_check_rows_per_slot_and_summary():
    r = fashion.check(LOOK, "Warlock", INDEX, STATE, set(), CTX, NOW, ITEMS)
    ceramic = [x for x in r["rows"] if x["name"] == "Ceramic Alloy"]
    assert [x["slot"] for x in ceramic] == ["Helmet", "Gauntlets", "Chest"] and all(x["owned"] for x in ceramic)
    brass = next(x for x in r["rows"] if x["name"] == "Electro-Brass")
    assert brass["owned"] is False and brass["exotic_for"] == "Sunbracers" and brass["source"] == "Eververse"
    bad = next(x for x in r["rows"] if x["name"] == "Painted Kitsune Bnod")
    assert bad["problem"].startswith("not found") and bad["owned"] is None
    assert r["summary"] == ("4 of 8 owned; missing: Electro-Brass (Eververse), Jade Rabbit Robes (Eververse); "
                            "unknown: Tyrian Abyss; not found: Painted Kitsune Bnod")
