"""Icon paths for what a build sheet names (items, subclass, plugs, mods, weapon perks, artifact, stats), reusing the
DIM link's name resolution (`share`). Keys are "<kind>:<name>"; values are manifest paths
("/common/destiny2_content/icons/x.jpg")."""
from shell.engines import share
from shell.engines.share import _category, _copy_key, _is_armor_mod, _name


def _icon(d):
    return (d.get("displayProperties") or {}).get("icon")


def _index(defs, pred, key=lambda h, d: int(h)):
    """{name: definition} of the definitions `pred` accepts, one per name (smallest `key`)."""
    best = {}
    for h, d in defs.items():
        n = _name(d)
        if n and pred(d) and (n not in best or key(h, d) < best[n][0]):
            best[n] = (key(h, d), d)
    return {n: d for n, (_, d) in best.items()}


def refs(s: dict, defs: dict, socket_types: dict, stat_defs: dict, armor_items: list[dict],
         weapon_items: list[dict]) -> tuple[dict[str, str], list[str]]:
    """({key: icon path}, warnings). `defs`: DestinyInventoryItemDefinition, `stat_defs`: DestinyStatDefinition,
    both by hash string."""
    intent, res = s["intent"], s.get("resolved") or {}
    out, warnings = {}, []

    def add(key, d):
        if d is None:
            warnings.append(f"icon not found: {key}")
        elif _icon(d):
            out[key] = _icon(d)
        else:
            warnings.append(f"no icon: {key}")

    cls = share.CLASS_TYPES[s["class"]]
    by_name = {2: _index(defs, lambda d: d.get("itemType") == 2 and d.get("classType") == cls, _copy_key),
               3: _index(defs, lambda d: d.get("itemType") == 3, _copy_key)}
    known = {i["itemId"]: i for i in [*armor_items, *weapon_items]}
    for kind, entries in ((2, res.get("armor") or []), (3, res.get("weapons") or [])):
        for e in entries:
            row = known.get(e["itemId"])
            if row is None:
                warnings.append(f"{e['slot']}: {e['name']} not in the inventory snapshot: icon by name")
            add(f"item:{e['name']}", defs.get(str(row["itemHash"])) if row else by_name[kind].get(e["name"]))
    exotic = intent["exotic"]["name"]
    if f"item:{exotic}" not in out:
        add(f"item:{exotic}", by_name[2].get(exotic))

    sub = share.subclass_item(s, defs, socket_types, [], warnings)
    if sub:
        d = defs[str(sub["hash"])]
        add(f"subclass:{_name(d)}", d)
        for h in sub["socketOverrides"].values():
            add(f"plug:{_name(defs[str(h)])}", defs[str(h)])

    if res.get("armor"):
        mods = [n for a in res["armor"] for n in [a.get("stat_mod"), a.get("tuning"), *(a.get("mods") or [])] if n]
    else:
        mods = [n for key in ("armor_mods", "armor_mods_fill") for m in (intent.get(key) or {}).values() for n in m]
    index = share.mod_index(defs)
    for n in dict.fromkeys(mods):
        add(f"mod:{n}", defs.get(str(index[n])) if n in index else None)

    plugs = _index(defs, lambda d: d.get("plug") and not _is_armor_mod(_category(d)))
    for w in res.get("weapons") or []:
        for n in dict.fromkeys([*(w.get("perks") or []), *([w["mod"]] if w.get("mod") else [])]):
            add(f"perk:{n}", plugs.get(n))

    art = intent.get("artifact")
    if art:
        for kind, names in (("Artifact", [art["name"]]), ("Artifact Perk", art.get("perks") or [])):
            found = _index(defs, lambda d: d.get("itemTypeDisplayName") == kind)
            for n in names:
                add(f"artifact:{n}", found.get(n))

    for n, h in share.STAT_HASHES.items():
        add(f"stat:{n}", stat_defs.get(str(h)))
    return out, warnings
