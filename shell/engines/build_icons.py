"""Icon paths for what a build sheet names (items, subclass, plugs, mods, weapon perks, artifact, stats, set perks),
reusing the
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


def set_perks(s: dict, set_defs: dict, perk_defs: dict) -> tuple[dict[str, list[dict]], list[str]]:
    """({set: [{pieces, name, icon}]} of the perks the sheet's piece count activates, by piece count; warnings), for
    `intent.sets` (the build as designed). `set_defs`: DestinyEquipableItemSetDefinition, `perk_defs`:
    DestinySandboxPerkDefinition, both by hash string."""
    by_name = {_name(d): d for d in set_defs.values() if _name(d)}
    out, warnings = {}, []
    for e in s["intent"].get("sets") or []:
        d = by_name.get(e["set"])
        if d is None:
            warnings.append(f"set not found: {e['set']}")
            continue
        out[e["set"]] = [{"pieces": p["requiredSetCount"], "name": _name(perk), "icon": _icon(perk)}
                         for p in sorted(d.get("setPerks") or [], key=lambda p: p["requiredSetCount"])
                         if p["requiredSetCount"] <= e["pieces"]
                         for perk in [perk_defs.get(str(p["sandboxPerkHash"])) or {}] if _name(perk)]
    return out, warnings


def refs(s: dict, defs: dict, socket_types: dict, stat_defs: dict, armor_items: list[dict],
         weapon_items: list[dict], set_defs: dict | None = None,
         perk_defs: dict | None = None) -> tuple[dict[str, str], list[str]]:
    """({key: icon path}, warnings). `defs`: DestinyInventoryItemDefinition, `stat_defs`: DestinyStatDefinition,
    both by hash string; set perks when `set_defs` and `perk_defs` are given (see `set_perks`)."""
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

    if set_defs is not None and perk_defs is not None:
        perks, more = set_perks(s, set_defs, perk_defs)
        warnings += more
        for p in (p for ps in perks.values() for p in ps):
            add(f"setperk:{p['name']}", {"displayProperties": {"icon": p["icon"]}})
    return out, warnings
