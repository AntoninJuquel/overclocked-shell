"""A build sheet as a DIM loadout (dim-api api/shapes/loadouts.ts), to share as a link.

equipped: the resolved armor and weapons ({id, hash}: DIM falls back to the hash for a player without that
instance) and the subclass item with socketOverrides (super, abilities, aspects, fragments). parameters: armor mods
(stat mods, tunings, slot mods), exotic, stat constraints. What has no DIM slot (weapon perks, artifact, sets,
names that could not be resolved) goes in the notes.
"""
import uuid

from shell.engines.builds.equip_plan import SUBCLASS_ITEMS

CLASS_TYPES = {"Titan": 0, "Hunter": 1, "Warlock": 2}
STAT_HASHES = {"Weapons": 2996146975, "Health": 392767087, "Class": 1943323491, "Grenade": 1735777505,
               "Super": 144602215, "Melee": 4244567218}
SUBCLASS_ITEM_TYPE = 16
EXOTIC_TIER = 6
# sheet field -> plug category suffixes of its subclass sockets (Stasis says totems / trinkets)
SOCKET_KINDS = {"super": ("supers",), "grenade": ("grenades",), "melee": ("melee",), "class": ("class_abilities",),
                "jump": ("movement",), "aspects": ("aspects", "totems"), "fragments": ("fragments", "trinkets")}
MAX_NOTES = 1000


def _name(d):
    return (d.get("displayProperties") or {}).get("name", "")


def _category(d):
    return (d.get("plug") or {}).get("plugCategoryIdentifier") or ""


def _is_armor_mod(category):
    return category.startswith("enhancements.") or "armor_tiering.plugs.tuning" in category


def _mod_index(defs):
    """{name: hash} of armor mods. Several definitions of one name: the base mod (it has a collectible; the other
    copies are artifact-discounted), then the lowest hash."""
    best = {}
    for h, d in defs.items():
        if not _is_armor_mod(_category(d)) or not _name(d):
            continue
        key = (d.get("collectibleHash") is None, int(h))
        if _name(d) not in best or key < best[_name(d)][0]:
            best[_name(d)] = (key, int(h))
    return {n: h for n, (_, h) in best.items()}


def _subclass(s, defs, unknown):
    """{hash, socketOverrides} of the sheet's subclass item, or None when the manifest has no such item."""
    cls, sub = s["class"], s["subclass"]
    name = SUBCLASS_ITEMS[cls][sub["element"]]
    item = next(((h, d) for h, d in defs.items() if d.get("itemType") == SUBCLASS_ITEM_TYPE
                 and d.get("classType") == CLASS_TYPES[cls] and _name(d) == name), None)
    if item is None:
        unknown.append(f"subclass {name}")
        return None
    h, d = item
    sockets = {}  # category -> [socket index]
    for i, entry in enumerate((d.get("sockets") or {}).get("socketEntries", [])):
        cat = _category(defs.get(str(entry.get("singleInitialItemHash"))) or {})
        if cat:
            sockets.setdefault(cat, []).append(i)
    plugs = {(_category(p), _name(p)): int(ph) for ph, p in defs.items() if _category(p) in sockets}
    wanted = {"super": [sub["super"]] if sub.get("super") else [],
              **{k: [v] for k, v in (sub.get("abilities") or {}).items()},
              "aspects": sub.get("aspects", []), "fragments": sub.get("fragments", [])}
    overrides = {}
    for kind, names in wanted.items():
        cats = [c for c in sockets if c.rsplit(".", 1)[-1] in SOCKET_KINDS.get(kind, ())]
        for index, n in zip(sockets[cats[0]] if cats else [], names):  # first sockets first: the active ones
            if (cats[0], n) in plugs:
                overrides[str(index)] = plugs[(cats[0], n)]
            else:
                unknown.append(n)
        if not cats:
            unknown += names
    return {"hash": int(h), "socketOverrides": overrides}


def _notes(s, unknown):
    intent, res = s["intent"], s.get("resolved") or {}
    lines = [s.get("concept") or ""]
    lines += [f"{w['slot']}: {w['name']}" + (f" ({', '.join(w['perks'])})" if w.get("perks") else "")
              for w in res.get("weapons") or []]
    if res.get("stats"):
        lines.append("Stats: " + " · ".join(f"{k} {v}" for k, v in res["stats"].items()))
    if intent.get("artifact"):
        art = intent["artifact"]
        lines.append(f"Artifact: {art['name']} — {', '.join(art.get('perks', []))}")
    if intent.get("sets"):
        lines.append("Sets: " + ", ".join(f"{e['pieces']} × {e['set']}" for e in intent["sets"]))
    if unknown:
        lines.append("Not in DIM slots: " + ", ".join(unknown))
    text = "\n".join(x for x in lines if x)
    return text if len(text) <= MAX_NOTES else text[:MAX_NOTES - 1] + "…"


def loadout(s, armor_items, weapon_items, defs) -> tuple[dict, list[str]]:
    """(DIM Loadout, warnings). `defs`: DestinyInventoryItemDefinition by hash string."""
    res, intent = s.get("resolved") or {}, s["intent"]
    known = {i["itemId"]: i for i in [*armor_items, *weapon_items]}
    warnings, unknown, equipped = [], [], []
    entries = (res.get("armor") or []) + (res.get("weapons") or [])
    if not entries:
        warnings.append("no resolved armor or weapons: the link carries the subclass and mods only")
    for e in entries:
        item = known.get(e["itemId"])
        if item is None:
            warnings.append(f"{e['slot']}: {e['name']} ({e['itemId']}) not in the inventory: left out")
        else:
            equipped.append({"id": e["itemId"], "hash": item["itemHash"]})
    sub = _subclass(s, defs, unknown)
    if sub:
        equipped.append(sub)

    if res.get("armor"):
        names = [n for a in res["armor"] for n in [a.get("stat_mod"), a.get("tuning"), *(a.get("mods") or [])] if n]
    else:
        names = [n for slot_mods in (intent.get("armor_mods") or {}).values() for n in slot_mods]
    index, mods = _mod_index(defs), []
    for n in names:
        if n in index:
            mods.append(index[n])
        else:
            unknown.append(n)
            warnings.append(f"unknown mod: {n}")

    exotic = intent["exotic"]["name"]
    exotic_hash = next((known[a["itemId"]]["itemHash"] for a in res.get("armor") or []
                        if a["itemId"] in known and known[a["itemId"]].get("rarity") == "Exotic"), None)
    if exotic_hash is None:
        exotic_hash = next((int(h) for h, d in defs.items() if d.get("itemType") == 2 and _name(d) == exotic
                            and (d.get("inventory") or {}).get("tierType") == EXOTIC_TIER), None)
    stats = intent.get("stats") or {}
    mins, order = stats.get("minimums") or {}, list(stats.get("priority") or [])
    order += [k for k in mins if k not in order]
    constraints = [{"statHash": STAT_HASHES[k], **({"minStat": mins[k]} if k in mins else {})}
                   for k in order if k in STAT_HASHES]
    parameters = {"mods": mods, "statConstraints": constraints}
    if exotic_hash is not None:
        parameters["exoticArmorHash"] = exotic_hash
    return {"id": str(uuid.uuid4()), "name": s["name"], "classType": CLASS_TYPES[s["class"]],
            "notes": _notes(s, unknown), "equipped": equipped, "unequipped": [], "parameters": parameters}, warnings
