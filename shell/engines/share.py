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


def _subclass(s, defs, socket_types, unknown, warnings):
    """{hash, socketOverrides} of the sheet's subclass item, or None when the manifest has no such item.
    A socket's categories come from its socket type's whitelist (a Void grenade socket has no initial plug,
    Stasis aspect sockets start on a shared empty plug), else from its initial plug."""
    cls, sub = s["class"], s["subclass"]
    name = SUBCLASS_ITEMS[cls][sub["element"]]
    item = next(((h, d) for h, d in defs.items() if d.get("itemType") == SUBCLASS_ITEM_TYPE
                 and d.get("classType") == CLASS_TYPES[cls] and _name(d) == name), None)
    if item is None:
        unknown.append(f"subclass {name}")
        warnings.append(f"subclass: {name} not found: in the notes")
        return None
    h, d = item
    socket_cats = []
    for entry in (d.get("sockets") or {}).get("socketEntries", []):
        whitelist = (socket_types.get(str(entry.get("socketTypeHash"))) or {}).get("plugWhitelist") or []
        cats = [w["categoryIdentifier"] for w in whitelist if w.get("categoryIdentifier")]
        socket_cats.append(cats or [_category(defs.get(str(entry.get("singleInitialItemHash"))) or {})])
    wanted_cats = {c for cats in socket_cats for c in cats if c}
    plugs = {}  # name -> {category: hash}
    for ph, p in defs.items():
        if _category(p) in wanted_cats:
            plugs.setdefault(_name(p), {})[_category(p)] = int(ph)
    wanted = {"super": [sub["super"]] if sub.get("super") else [],
              **{k: [v] for k, v in (sub.get("abilities") or {}).items()},
              "aspects": sub.get("aspects", []), "fragments": sub.get("fragments", [])}
    overrides = {}
    for kind, names in wanted.items():
        suffixes = SOCKET_KINDS.get(kind, ())
        indexes = [i for i, cats in enumerate(socket_cats) if any(c.rsplit(".", 1)[-1] in suffixes for c in cats)]
        for k, n in enumerate(names):  # first sockets first: the active ones
            found = next((plugs[n][c] for c in socket_cats[indexes[k]] if c in plugs.get(n, {})), None)                 if k < len(indexes) else None
            if found is None:
                unknown.append(n)
                warnings.append(f"subclass: {n} not found: in the notes")
            else:
                overrides[str(indexes[k])] = found
    return {"hash": int(h), "socketOverrides": overrides}


def _notes(s, unknown):
    intent, res = s["intent"], s.get("resolved") or {}
    lines = ["Not in DIM slots: " + ", ".join(unknown)] if unknown else []  # first: the cap never cuts it
    lines.append(s.get("concept") or "")
    lines += [f"{w['slot']}: {w['name']}" + (f" ({', '.join(w['perks'])})" if w.get("perks") else "")
              for w in res.get("weapons") or []]
    if res.get("stats"):
        lines.append("Stats: " + " · ".join(f"{k} {v}" for k, v in res["stats"].items()))
    if intent.get("artifact"):
        art = intent["artifact"]
        lines.append(f"Artifact: {art['name']} — {', '.join(art.get('perks', []))}")
    if intent.get("sets"):
        lines.append("Sets: " + ", ".join(f"{e['pieces']} × {e['set']}" for e in intent["sets"]))
    text = "\n".join(x for x in lines if x)
    return text if len(text) <= MAX_NOTES else text[:MAX_NOTES - 1] + "…"


def loadout(s, armor_items, weapon_items, defs, socket_types) -> tuple[dict, list[str]]:
    """(DIM Loadout, warnings). `defs`: DestinyInventoryItemDefinition, `socket_types`: DestinySocketTypeDefinition,
    both by hash string."""
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
    sub = _subclass(s, defs, socket_types, unknown, warnings)
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
