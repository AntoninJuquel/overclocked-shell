import copy

from shell.engines import share


def plug(name, category, coll=1, type_name="Armor Mod"):
    return {"displayProperties": {"name": name}, "itemType": 19, "itemTypeDisplayName": type_name,
            "collectibleHash": coll, "plug": {"plugCategoryIdentifier": category}}


DEFS = {
    "100": {"displayProperties": {"name": "Prismatic Warlock"}, "itemType": 16, "classType": 2,
            "sockets": {"socketEntries": [{"singleInitialItemHash": h, "socketTypeHash": t} for h, t in
                                          ((900, 1), (0, 2), (902, 1), (903, 1), (904, 1), (907, 1),
                                           (908, 3), (908, 3), (906, 1), (906, 1), (906, 1))]}},
    "101": {"displayProperties": {"name": "Prismatic Warlock"}, "itemType": 20, "classType": 3},   # not a subclass
    "900": plug("Empty Super Socket", "warlock.prism.supers"),
    "901": plug("Empty Grenade Socket", "warlock.prism.grenades"),
    "902": plug("Empty Melee Socket", "warlock.prism.melee"),
    "903": plug("Empty Class Socket", "warlock.prism.class_abilities"),
    "904": plug("Empty Jump Socket", "warlock.prism.movement"),
    "905": plug("Empty Aspect Socket", "warlock.prism.aspects"),
    "906": plug("Empty Fragment Socket", "shared.prism.fragments"),
    "907": plug("Transcendence", "warlock.prism.transcendence"),
    "908": plug("Empty Aspect Socket", "warlock.shared.aspects"),     # the real plugs are in the socket whitelist
    "10": plug("Song of Flame", "warlock.solar.supers"),
    "11": plug("Song of Flame", "warlock.prism.supers"),
    "12": plug("Storm Grenade", "warlock.prism.grenades"),
    "13": plug("Arcane Needle", "warlock.prism.melee"),
    "14": plug("Phoenix Dive", "warlock.prism.class_abilities"),
    "15": plug("Burst Glide", "warlock.prism.movement"),
    "16": plug("Feed the Void", "warlock.prism.aspects"),
    "17": plug("Bleak Watcher", "warlock.prism.aspects"),
    "18": plug("Facet of Purpose", "shared.prism.fragments"),
    "19": plug("Facet of Courage", "shared.prism.fragments"),
    "20": plug("Ashes to Assets", "enhancements.v2_head"),
    "21": plug("Ashes to Assets", "enhancements.v2_head", coll=None),         # artifact-discounted copy
    "22": plug("Grenade Mod", "enhancements.v2_general"),
    "23": plug("Balanced Tuning", "core.gear_systems.armor_tiering.plugs.tuning.mods"),
    "24": plug("Firepower", "enhancements.v2_arms"),
    "50": {"displayProperties": {"name": "Getaway Artist"}, "itemType": 2, "inventory": {"tierType": 6},
           "classType": 2, "collectibleHash": 1},
}
# Real manifest: a Void grenade socket has no initial plug, Stasis aspect sockets start on a shared empty plug;
# the allowed categories come from the socket type's whitelist (2, 3). 1 has no whitelist: the initial plug decides.
SOCKET_TYPES = {"1": {"plugWhitelist": []},
                "2": {"plugWhitelist": [{"categoryIdentifier": "warlock.prism.grenades"}]},
                "3": {"plugWhitelist": [{"categoryIdentifier": "warlock.prism.aspects"},
                                        {"categoryIdentifier": "warlock.shared.aspects"}]}}
SHEET = {
    "name": "Getaway Buddy", "class": "Warlock", "concept": "Storm Grenade spam.",
    "subclass": {"element": "Prismatic", "super": "Song of Flame",
                 "abilities": {"grenade": "Storm Grenade", "melee": "Arcane Needle", "class": "Phoenix Dive",
                               "jump": "Burst Glide"},
                 "aspects": ["Feed the Void", "Bleak Watcher"], "fragments": ["Facet of Purpose", "Facet of Courage"]},
    "intent": {"exotic": {"name": "Getaway Artist"},
               "stats": {"minimums": {"Grenade": 150, "Weapons": 100}, "priority": ["Grenade", "Super"]},
               "sets": [{"set": "Great Hunt", "pieces": 4}],
               "armor_mods": {"Helmet": ["Ashes to Assets"], "Gauntlets": ["Firepower"]},
               "artifact": {"name": "Hunter's Journal", "perks": ["Shieldcrush"]}},
    "resolved": {
        "armor": [{"slot": "Helmet", "itemId": "a1", "name": "Hood", "stat_mod": "Grenade Mod",
                   "tuning": "Balanced Tuning", "mods": ["Ashes to Assets", "Mystery Mod"]},
                  {"slot": "Gauntlets", "itemId": "a2", "name": "Getaway Artist", "stat_mod": "Grenade Mod",
                   "tuning": "Balanced Tuning", "mods": ["Firepower"]},
                  {"slot": "Chest", "itemId": "gone", "name": "Robes", "mods": []}],
        "weapons": [{"slot": "Kinetic", "itemId": "w1", "name": "DECATUR 02", "perks": ["Physic", "Master of Arms"]}],
        "stats": {"Grenade": 171, "Weapons": 100}},
}
ARMOR = [{"itemId": "a1", "itemHash": 1001, "name": "Hood", "rarity": "Legendary"},
         {"itemId": "a2", "itemHash": 50, "name": "Getaway Artist", "rarity": "Exotic"}]
WEAPONS = [{"itemId": "w1", "itemHash": 2001, "name": "DECATUR 02"}]


def test_loadout_from_resolved_sheet():
    lo, warnings = share.loadout(SHEET, ARMOR, WEAPONS, DEFS, SOCKET_TYPES)
    assert lo["name"] == "Getaway Buddy" and lo["classType"] == 2 and lo["unequipped"] == [] and lo["id"]
    assert lo["equipped"][:3] == [{"id": "a1", "hash": 1001}, {"id": "a2", "hash": 50}, {"id": "w1", "hash": 2001}]
    assert lo["equipped"][3] == {"hash": 100, "socketOverrides": {
        "0": 11, "1": 12, "2": 13, "3": 14, "4": 15, "6": 16, "7": 17, "8": 18, "9": 19}}
    p = lo["parameters"]
    assert p["mods"] == [22, 23, 20, 22, 23, 24] and p["exoticArmorHash"] == 50
    assert p["statConstraints"] == [{"statHash": share.STAT_HASHES["Grenade"], "minStat": 150},
                                    {"statHash": share.STAT_HASHES["Super"]},
                                    {"statHash": share.STAT_HASHES["Weapons"], "minStat": 100}]
    assert warnings == ["Chest: Robes (gone) not in the inventory: left out", "unknown mod: Mystery Mod"]
    notes = lo["notes"]
    assert "Storm Grenade spam." in notes and "Kinetic: DECATUR 02 (Physic, Master of Arms)" in notes
    assert "Artifact: Hunter's Journal — Shieldcrush" in notes and "Sets: 4 × Great Hunt" in notes
    assert "Not in DIM slots: Mystery Mod" in notes


def test_loadout_without_resolved_uses_intent():
    s = copy.deepcopy(SHEET)
    del s["resolved"]
    lo, warnings = share.loadout(s, ARMOR, WEAPONS, DEFS, SOCKET_TYPES)
    assert [e.get("id") for e in lo["equipped"]] == [None]                 # subclass only
    assert lo["parameters"]["mods"] == [20, 24] and lo["parameters"]["exoticArmorHash"] == 50
    assert warnings == ["no resolved armor or weapons: the link carries the subclass and mods only"]


def test_notes_are_capped():
    s = copy.deepcopy(SHEET)
    s["concept"] = "x" * 3000
    lo, _ = share.loadout(s, ARMOR, WEAPONS, DEFS, SOCKET_TYPES)
    assert len(lo["notes"]) == share.MAX_NOTES and lo["notes"].endswith("…")


def test_unknown_subclass_plug_warns_and_notes_keep_it_first():
    s = copy.deepcopy(SHEET)
    s["subclass"]["aspects"] = ["Feed the Void", "Nope Aspect"]
    s["concept"] = "x" * 3000
    lo, warnings = share.loadout(s, ARMOR, WEAPONS, DEFS, SOCKET_TYPES)
    assert "subclass: Nope Aspect not found: in the notes" in warnings
    assert "Not in DIM slots: Nope Aspect, Mystery Mod" in lo["notes"]


def test_mod_without_collectible_prefers_a_non_deprecated_copy():
    defs = {"30": plug("Old Mod", "enhancements.v2_head", coll=None, type_name="Deprecated Armor Mod"),
            "31": plug("Old Mod", "enhancements.v2_head", coll=None)}
    assert share.mod_index(defs) == {"Old Mod": 31}


def test_exotic_fallback_takes_the_collectible_copy_of_the_sheet_class():
    s = copy.deepcopy(SHEET)
    del s["resolved"]
    exotic = {"displayProperties": {"name": "Getaway Artist"}, "itemType": 2, "inventory": {"tierType": 6}}
    defs = {"40": {**exotic, "classType": 1, "collectibleHash": 1},                  # wrong class
            "45": {**exotic, "classType": 2},                                         # no collectible
            "51": {**exotic, "classType": 2, "collectibleHash": 1, "itemTypeDisplayName": "Deprecated Gauntlets"},
            **DEFS, "50": {**exotic, "classType": 2, "collectibleHash": 1}}
    lo, _ = share.loadout(s, ARMOR, WEAPONS, defs, SOCKET_TYPES)
    assert lo["parameters"]["exoticArmorHash"] == 50
