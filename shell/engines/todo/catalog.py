"""Existing set pieces per class and slot (Bungie manifest)."""
CLASS_TYPES = {"Titan": 0, "Hunter": 1, "Warlock": 2}
SUBTYPE_SLOTS = {26: "Helmet", 27: "Gauntlets", 28: "Chest", 29: "Legs", 30: "Class Item"}


def set_slots(sets_by_hash, item_defs, cls):
    """{set: {slots}} of the set pieces that exist for class `cls`.

    `sets_by_hash`: armor sets by item hash (int keys); `item_defs`: DestinyInventoryItemDefinition (str keys)."""
    out = {}
    for item_hash, info in sets_by_hash.items():
        d = item_defs.get(str(item_hash))
        if not d or d.get("classType") != CLASS_TYPES[cls]:
            continue
        slot = SUBTYPE_SLOTS.get(d.get("itemSubType"))
        if slot:
            out.setdefault(info["set"], set()).add(slot)
    return out
