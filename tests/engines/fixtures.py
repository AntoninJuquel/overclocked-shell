"""Small fake defs and profile shared by inventory tests."""

DEFS = {
    "weapons": {
        "100": {"n": "Gun", "t": "Auto Rifle", "r": "Legendary", "a": 1, "b": 1498876634,
                "sc": [[3956125808, [0]], [4241085061, [1, 2, 3]], [999, [4, 5]]]},
        "101": {"n": "Bow", "t": "Combat Bow", "r": "Legendary", "a": 1, "b": 2465295065, "sc": []},
        "102": {"n": "Axe", "t": "Auto Rifle", "r": "Legendary", "a": 1, "b": 1498876634, "sc": []},
    },
    "gear": {
        "200": ["Star-Eater Scales", "Leg Armor", 1, 20886954, "Exotic"],
        "201": ["Bond", "Warlock Bond", 2, 1585787867, "Legendary"],
        "202": ["Ghost Shell", "Ghost Shell", 3, 4023194814, "Legendary"],
    },
    "plugs": {
        "1": {"n": "Weapons Mod", "t": "General Armor Mod", "p": "enhancements.v2_general"},
        "2": {"n": "Empty Mod Socket", "t": "General Armor Mod", "p": "enhancements.v2_general"},
        "3": {"n": "Shader", "t": "Shader", "p": "shader"},
        "4": {"n": "Upgrade Armor", "t": "", "p": "v400.plugs.armor.masterworks"},
        "5": {"n": "Balanced Tuning", "t": "General Armor Mod", "p": "core.gear_systems.armor_tiering.plugs.tuning.mods"},
        "6": {"n": "+Super / -Melee", "t": "General Armor Mod", "p": "core.gear_systems.armor_tiering.plugs.tuning.mods"},
        "7": {"n": "+Grenade / -Class", "t": "General Armor Mod", "p": "enhancements.v2_general"},
        "10": {"n": "Rapid-Fire Frame", "t": "Intrinsic", "p": "intrinsics"},
        "11": {"n": "Arrowhead Brake", "t": "Barrel", "p": "barrels"},
        "12": {"n": "Corkscrew Rifling", "t": "Barrel", "p": "barrels"},
        "13": {"n": "Kill Clip", "t": "Enhanced Trait", "p": "frames"},
        "14": {"n": "Kill Tracker", "t": "Tracker", "p": "v400.plugs.weapons.masterworks.trackers"},
        "15": {"n": "Masterworked: Handling", "t": "Masterwork", "p": "v400.weapon.mod_masterwork"},
        "16": {"n": "Backup Mag", "t": "Weapon Mod", "p": "v400.weapon.mod_magazine"},
        "17": {"n": "Empty Mod Socket", "t": "Weapon Mod", "p": "v400.weapon.mod_empty"},
    },
    "misc": {},
    "stats": {"1": "Weapons", "2": "Health", "3": "Class", "4": "Grenade", "5": "Super", "6": "Melee",
              "7": "Defense", "8": "Handling", "9": "Attack"},
    "socketCategories": {"3956125808": "INTRINSIC TRAITS", "4241085061": "WEAPON PERKS", "999": "WEAPON MODS"},
}


def stats(**values):
    ids = {name: h for h, name in DEFS["stats"].items()}
    return {"stats": {ids[k]: {"statHash": int(ids[k]), "value": v} for k, v in values.items()}}


def profile():
    return {
        "characters": {"data": {"w": {"classType": 2}}},
        "profileInventory": {"data": {"items": [
            {"itemHash": 200, "itemInstanceId": "a1", "state": 5, "bucketHash": 138197802},
            {"itemHash": 100, "itemInstanceId": "g1", "state": 9, "bucketHash": 138197802},
            {"itemHash": 999, "itemInstanceId": "x1", "state": 0},
            {"itemHash": 201, "state": 0},
        ]}},
        "characterInventories": {"data": {"w": {"items": [
            {"itemHash": 201, "itemInstanceId": "a2", "state": 0, "bucketHash": 215593132},
            {"itemHash": 102, "itemInstanceId": "g3", "state": 0, "bucketHash": 215593132},
        ]}}},
        "characterEquipment": {"data": {"w": {"items": [
            {"itemHash": 201, "itemInstanceId": "a3", "state": 1, "bucketHash": 1585787867},
            {"itemHash": 101, "itemInstanceId": "g2", "state": 0, "bucketHash": 2465295065},
            {"itemHash": 202, "itemInstanceId": "gh", "state": 0},
        ]}}},
        "itemComponents": {
            "instances": {"data": {
                "a1": {"primaryStat": {"value": 10}, "gearTier": 3, "energy": {"energyUsed": 9, "energyCapacity": 10}},
                "a2": {"gearTier": 0}, "a3": {},
                "g1": {"primaryStat": {"value": 550}, "damageType": 7, "gearTier": 2},
                "g2": {"damageType": 3, "isEquipped": True}, "g3": {"damageType": 1},
            }},
            "stats": {"data": {
                "a1": stats(Weapons=20, Health=23, Class=4, Grenade=15, Super=17, Melee=4, Defense=10),
                "a2": stats(Health=30),
                "g1": stats(Handling=90, Attack=550),
            }},
            "sockets": {"data": {
                "a1": {"sockets": [{"plugHash": 1}, {"plugHash": 2}, {"plugHash": 3}, {}, {"plugHash": 4},
                                   {"plugHash": 1}, {"plugHash": 5}]},
                "g1": {"sockets": [{"plugHash": 10}, {"plugHash": 11}, {"plugHash": 13}, {"plugHash": 14},
                                   {"plugHash": 15}, {"plugHash": 16}]},
                "g3": {"sockets": [{}, {}, {}, {}, {"plugHash": 17}]},
            }},
            "reusablePlugs": {"data": {
                "a1": {"plugs": {"10": [{"plugItemHash": 7, "canInsert": True}],
                                 "6": [{"plugItemHash": 5, "canInsert": True}, {"plugItemHash": 6, "canInsert": True}]}},
                "a2": {"plugs": {"3": [{"plugItemHash": 7, "canInsert": True}]}},
                "g1": {"plugs": {"1": [{"plugItemHash": 12, "canInsert": True},
                                       {"plugItemHash": 11, "canInsert": False}]}},
            }},
        },
    }
