"""Inventory rows from a Bungie profile response, in destiny-zen's export shape (ported consumers rely on it)."""
import re

CLASS_NAME = {0: "Titan", 1: "Hunter", 2: "Warlock", 3: "Any"}
POSTMASTER_BUCKET = 215593132
ARMOR_BUCKETS = {3448274439: "Helmet", 3551918588: "Gauntlets", 14239492: "Chest", 20886954: "Legs",
                 1585787867: "Class Item"}
ARMOR_STATS = ("Weapons", "Health", "Class", "Grenade", "Super", "Melee")
COSMETIC = re.compile(r"shader|skins|ornament|transmog|armor_skins|emote|v400\.empty|tracker", re.I)
EMPTY = re.compile(r"^(Empty|Default)", re.I)
TUNING = re.compile(r"^\+(\w+) / -\w+$")


def holdings(profile: dict) -> list[tuple[dict, str, str | None, bool]]:
    """(item, location, characterId, equipped): vault, then character inventories (postmaster marked), then equipment."""
    out = [(item, "Vault", None, False) for item in profile["profileInventory"]["data"]["items"]]
    characters = profile["characters"]["data"]
    name = lambda cid: CLASS_NAME.get(characters.get(cid, {}).get("classType", 3), cid)  # noqa: E731
    for cid, inv in profile.get("characterInventories", {}).get("data", {}).items():
        for item in inv["items"]:
            where = f"{name(cid)} (Postmaster)" if item.get("bucketHash") == POSTMASTER_BUCKET else name(cid)
            out.append((item, where, cid, False))
    for cid, eq in profile.get("characterEquipment", {}).get("data", {}).items():
        out.extend((item, name(cid), cid, True) for item in eq["items"])
    return out


def plug_list(sockets: list[dict], defs: dict) -> list[str]:
    out = []
    for socket in sockets:
        plug = defs["plugs"].get(str(socket.get("plugHash") or ""))
        if not plug or EMPTY.match(plug["n"]) or COSMETIC.search(f"{plug['p']} {plug['t']}"):
            continue
        out.append(f"{plug['t']}: {plug['n']}" if plug["t"] else plug["n"])
    return out


def stat_map(stats: dict, defs: dict) -> dict[str, int]:
    out = {}
    for s in stats.get("stats", {}).values():
        name = defs["stats"].get(str(s["statHash"]))
        if name:
            out[name] = s["value"]
    return out


def tuned_stat(reusable: dict, defs: dict) -> str | None:
    """Stat a tier-5 piece can tune (+X / -Y), read from the offered tuning plugs, so it works with nothing slotted."""
    for index in sorted(reusable.get("plugs", {}), key=int):
        for option in reusable["plugs"][index]:
            plug = defs["plugs"].get(str(option["plugItemHash"]))
            match = plug and "tuning" in plug["p"] and TUNING.match(plug["n"])
            if match:
                return match.group(1)
    return None


def _components(profile: dict, kind: str, item_id: str) -> dict:
    return profile.get("itemComponents", {}).get(kind, {}).get("data", {}).get(item_id, {})


def armor_rows(profile: dict, defs: dict) -> list[dict]:
    rows = []
    for item, location, cid, equipped in holdings(profile):
        item_id = item.get("itemInstanceId")
        gear = defs["gear"].get(str(item["itemHash"]))
        if not item_id or not gear or gear[3] not in ARMOR_BUCKETS:
            continue
        inst = _components(profile, "instances", item_id)
        live = stat_map(_components(profile, "stats", item_id), defs)
        stats = {k: live[k] for k in ARMOR_STATS if k in live}
        energy = inst.get("energy")
        rows.append({
            "itemId": item_id, "itemHash": item["itemHash"], "name": gear[0], "slot": ARMOR_BUCKETS[gear[3]],
            "classType": CLASS_NAME.get(gear[2], "Any"), "rarity": gear[4], "location": location,
            "characterId": cid, "equipped": equipped, "locked": bool(item.get("state", 0) & 1),
            "masterworked": bool(item.get("state", 0) & 4), "power": inst.get("primaryStat", {}).get("value", 0),
            "gearTier": inst.get("gearTier"),
            "energy": f"{energy['energyUsed']}/{energy['energyCapacity']}" if energy else "",
            "stats": stats, "total": sum(stats.values()),
            "plugs": plug_list(_components(profile, "sockets", item_id).get("sockets", []), defs),
            "tunedStat": tuned_stat(_components(profile, "reusablePlugs", item_id), defs),
        })
    return rows
