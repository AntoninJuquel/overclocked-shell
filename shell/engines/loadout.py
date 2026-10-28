"""What a character is wearing: equipped items, subclass, artifact, armor stat totals."""
import re

from shell.engines.inventory import ARMOR_BUCKETS, ARMOR_STATS, _components, plug_list, stat_map

SUBCLASS_BUCKET = 3284755031
ARTIFACT_BUCKET = 1506418338
SKIPPED_TYPES = re.compile(r"emblem|ship|sparrow|vehicle|finisher|emote|clan banner|ghost", re.I)


def equipped(profile: dict, defs: dict, cid: str) -> dict:
    out = {"items": [], "subclass": None, "artifact": None, "armor_totals": dict.fromkeys(ARMOR_STATS, 0),
           "other_subclasses": [], "other_artifacts": []}
    for item in profile["characterEquipment"]["data"][cid]["items"]:
        item_id, h = item.get("itemInstanceId"), str(item["itemHash"])
        weapon, gear = defs["weapons"].get(h), defs["gear"].get(h)
        if not item_id or not (weapon or gear):
            continue
        name, type_name = (weapon["n"], weapon["t"]) if weapon else (gear[0], gear[1])
        if SKIPPED_TYPES.search(type_name or ""):
            continue
        plugs = plug_list(_components(profile, "sockets", item_id).get("sockets", []), defs)
        if gear and gear[3] == SUBCLASS_BUCKET:
            out["subclass"] = {"itemId": item_id, "name": name, "plugs": plugs}
        elif re.search("artifact", type_name or "", re.I):
            out["artifact"] = {"itemId": item_id, "name": name}
        else:
            entry = {"itemId": item_id, "name": name, "type": type_name,
                     "exotic": (weapon["r"] if weapon else gear[4]) == "Exotic"}
            if gear and gear[3] in ARMOR_BUCKETS:
                live = stat_map(_components(profile, "stats", item_id), defs)
                entry["stats"] = {k: live.get(k, 0) for k in ARMOR_STATS}
                for k, v in entry["stats"].items():
                    out["armor_totals"][k] += v
            entry["plugs"] = plugs
            out["items"].append(entry)
    for item in profile.get("characterInventories", {}).get("data", {}).get(cid, {}).get("items", []):
        gear = defs["gear"].get(str(item["itemHash"]))
        # ids of the subclasses and artifacts not equipped, for equip_items / set_sockets
        others = {SUBCLASS_BUCKET: "other_subclasses", ARTIFACT_BUCKET: "other_artifacts"}
        if gear and gear[3] in others and item.get("itemInstanceId"):
            out[others[gear[3]]].append({"itemId": item["itemInstanceId"], "name": gear[0]})
    return out


def item_name(defs: dict, h) -> str:
    """Any definition's name (artifact perks are indexed as gear, not plugs), `#hash` when unknown."""
    h = str(h)
    found = (defs["weapons"].get(h, {}).get("n") or (defs["gear"].get(h) or [None])[0]
             or defs["plugs"].get(h, {}).get("n") or defs["misc"].get(h) or defs.get("names", {}).get(h))
    return found or f"#{h}"


def artifact_perks(item: dict, defs: dict) -> list[str]:
    """Active perks from an artifact item response (component 305)."""
    names = (item_name(defs, s["plugHash"]) for s in item.get("sockets", {}).get("data", {}).get("sockets", [])
             if s.get("plugHash"))
    return [n for n in names if not re.match(r"^(empty|#)", n, re.I)]
