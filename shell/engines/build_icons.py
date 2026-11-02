"""Icon paths for what a build sheet's intent names (items, subclass, plugs, mods, artifact, stats, set perks),
reusing the DIM link's name resolution (`share`). Keys are "<kind>:<name>"; values are manifest paths
("/common/destiny2_content/icons/x.jpg")."""
from shell.engines import share
from shell.engines.builds import weapon_intent
from shell.engines.share import _category, _copy_key, _is_armor_mod, _name
from shell.engines.todo.catalog import SUBTYPE_SLOTS


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


def set_perks(s: dict, set_defs: dict, perk_defs: dict, local_perks: dict | None = None
              ) -> tuple[dict[str, list[dict]], list[str]]:
    """({set: [{pieces, name, icon, description}]} of the perks the sheet's piece count activates, by piece count;
    warnings), for `intent.sets` (the build as designed). `set_defs`: DestinyEquipableItemSetDefinition, `perk_defs`:
    DestinySandboxPerkDefinition, both by hash string; `local_perks`: the latter in the player's language, for the
    descriptions (the lexicon only translates names)."""
    by_name = {_name(d): d for d in set_defs.values() if _name(d)}
    out, warnings = {}, []
    for e in s["intent"].get("sets") or []:
        d = by_name.get(e["set"])
        if d is None:
            warnings.append(f"set not found: {e['set']}")
            continue
        out[e["set"]] = [{"pieces": p["requiredSetCount"], "name": _name(perk), "icon": _icon(perk),
                          "description": ((local_perks or perk_defs).get(str(p["sandboxPerkHash"]), {})
                                          .get("displayProperties") or {}).get("description") or ""}
                         for p in sorted(d.get("setPerks") or [], key=lambda p: p["requiredSetCount"])
                         if p["requiredSetCount"] <= e["pieces"]
                         for perk in [perk_defs.get(str(p["sandboxPerkHash"])) or {}] if _name(perk)]
    return out, warnings


def intent_armor(s: dict, defs: dict, set_defs: dict) -> dict[str, str]:
    """{slot: piece name} the intent fixes: the exotic's slot, and the other four when a single set fills them (with
    2 + 2 or free pieces, which slot wears what is the player's call). `defs`:
    DestinyInventoryItemDefinition, `set_defs`: DestinyEquipableItemSetDefinition, both by hash string."""
    cls, intent = share.CLASS_TYPES[s["class"]], s["intent"]
    exotic = intent["exotic"]["name"]
    found = _index(defs, lambda d: d.get("itemType") == 2 and d.get("classType") == cls, _copy_key).get(exotic) or {}
    slot = SUBTYPE_SLOTS.get(found.get("itemSubType"))
    if not slot:
        return {}
    out = {slot: exotic}
    sets = intent.get("sets") or []
    if len(sets) == 1 and sets[0]["pieces"] == 4:
        d = next((d for d in set_defs.values() if _name(d) == sets[0]["set"]), {})
        for h in sorted(d.get("setItems") or []):
            piece = defs.get(str(h)) or {}
            if piece.get("classType") == cls and SUBTYPE_SLOTS.get(piece.get("itemSubType")) and _name(piece):
                out.setdefault(SUBTYPE_SLOTS[piece["itemSubType"]], _name(piece))
    return out


def refs(s: dict, defs: dict, socket_types: dict, stat_defs: dict, set_defs: dict | None = None,
         perk_defs: dict | None = None, hashes: dict | None = None) -> tuple[dict[str, str], list[str]]:
    """({key: icon path}, warnings). `defs`: DestinyInventoryItemDefinition, `stat_defs`: DestinyStatDefinition,
    both by hash string; set pieces with `set_defs`, set perks when `perk_defs` is given too (see `set_perks`).
    `hashes`, when given, is filled with {key: hash}; the sheet's own table says which copy of a weapon or plug."""
    intent, known = s["intent"], s.get("hashes") or {}
    out, warnings = {}, []

    def add(key, d):
        if d is None:
            warnings.append(f"icon not found: {key}")
        elif _icon(d):
            out[key] = _icon(d)
        else:
            warnings.append(f"no icon: {key}")
        if hashes is not None and d and d.get("hash"):
            hashes.setdefault(key, d["hash"])

    cls = share.CLASS_TYPES[s["class"]]
    armor = _index(defs, lambda d: d.get("itemType") == 2 and d.get("classType") == cls, _copy_key)
    weapons = _index(defs, lambda d: d.get("itemType") == 3, _copy_key)
    for n in {intent["exotic"]["name"], *intent_armor(s, defs, set_defs or {}).values()}:
        add(f"item:{n}", armor.get(n))
    plugs = _index(defs, lambda d: d.get("plug") and not _is_armor_mod(_category(d)))
    for w in intent.get("weapons") or []:
        for n in (w.get("items") or [])[:1]:
            add(f"item:{n}", defs.get(str(known.get(f"item:{n}"))) or weapons.get(n))
        for n in weapon_intent.options(w):
            add(f"perk:{n}", defs.get(str(known.get(f"perk:{n}"))) or plugs.get(n))

    sub = share.subclass_item(s, defs, socket_types, [], warnings)
    if sub:
        for h in sub["socketOverrides"].values():
            add(f"plug:{_name(defs[str(h)])}", defs[str(h)])

    mods = [n for m in (intent.get("armor_mods") or {}).values() for n in m]
    index = share.mod_index(defs)
    for n in dict.fromkeys(mods):
        add(f"mod:{n}", defs.get(str(index[n])) if n in index else None)

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
