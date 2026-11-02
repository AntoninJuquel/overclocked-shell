"""An intent's weapons normalized against the manifest: every named option gets its hash, perks are checked per column.

Fields of `intent.weapons[]`, each option being {"name", "hash"} (the author writes the name, `normalize` the hash),
alternatives best first: `items`, `perks` (one list per column), `mods`, `masterworks`.
"""
from shell.engines.share import _copy_key, _is_armor_mod, _category, _name
from shell.engines.sockets import candidates

FLAT_FIELDS = ("mods", "masterworks")


def options(w: dict) -> list[dict]:
    """Every plug option an intent weapon names (perks, mods, masterworks)."""
    return [*(o for column in w.get("perks") or [] for o in column), *(o for k in FLAT_FIELDS for o in w.get(k) or [])]


def is_named(w: dict) -> bool:
    return bool(w.get("items") or options(w))


def _by_name(hashes, defs):
    """{name: hash}, the plain copy of a perk rather than its enhanced one."""
    out = {}
    for h in hashes:
        d = defs.get(str(h)) or {}
        enhanced = "Enhanced" in (d.get("itemTypeDisplayName") or "")
        if _name(d) and (_name(d) not in out or (out[_name(d)][0] and not enhanced)):
            out[_name(d)] = (enhanced, h)
    return {n: h for n, (_, h) in out.items()}


def _fit(w, weapon, tables):
    """Writes the hashes of `w`'s options found in the sockets `tables` of `weapon`; returns the problems."""
    problems, used = [], set()
    slot = w["slot"]

    def sockets_of(option):
        found = {i for i, t in enumerate(tables) if option["name"] in t}
        if not found:
            problems.append(f"{slot}: {option['name']} is not an option of {weapon}")
        return found

    for column in w.get("perks") or []:
        found = [sockets_of(o) for o in column]
        if not all(found):
            continue
        free = set.intersection(*found) - used
        if not free:
            names = " / ".join(o["name"] for o in column)
            problems.append(f"{slot}: {names}: no free column of {weapon} has them all")
            continue
        used.add(min(free))
        for o in column:
            o["hash"] = tables[min(free)][o["name"]]
    for o in (o for k in FLAT_FIELDS for o in w.get(k) or []):
        found = sockets_of(o)
        if found:
            o["hash"] = tables[min(found)][o["name"]]
    return problems


def normalize(weapons: list[dict], defs: dict, plug_sets: dict) -> list[str]:
    """Fills the hashes of `intent.weapons` in place; returns the problems (unknown name, option the weapon cannot
    roll). A weapon without `items` only names perks: any plug of that name. `defs`: DestinyInventoryItemDefinition,
    `plug_sets`: DestinyPlugSetDefinition, both by hash string."""
    copies, plugs = {}, []
    for h, d in defs.items():
        if d.get("itemType") == 3 and _name(d):
            copies.setdefault(_name(d), []).append((h, d))
        elif d.get("plug") and not _is_armor_mod(_category(d)):
            plugs.append(int(h))
    plugs = _by_name(sorted(plugs), defs)
    problems = []
    for w in weapons:
        for o in w.get("items") or []:
            if o["name"] in copies:
                o["hash"] = int(min(copies[o["name"]], key=lambda hd: _copy_key(*hd))[0])
            else:
                problems.append(f"{w['slot']}: unknown weapon: {o['name']}")
        known = next((o["name"] for o in w.get("items") or [] if o["name"] in copies), None)
        if known is None:
            if not w.get("items"):
                for o in options(w):
                    if o["name"] in plugs:
                        o["hash"] = plugs[o["name"]]
                    else:
                        problems.append(f"{w['slot']}: unknown perk or mod: {o['name']}")
            continue
        fits = []
        # several copies of a name (reissues): the first that can roll everything the intent names
        for h, d in sorted(copies[known], key=lambda hd: _copy_key(*hd)):
            tables = [_by_name(hashes, defs) for hashes in candidates(d, {}, {}, lambda p: plug_sets.get(str(p)))]
            fits.append((h, tables, _fit(w, known, tables)))
            if not fits[-1][2]:
                break
        h, tables, misfit = next((f for f in fits if not f[2]), fits[0])
        _fit(w, known, tables)
        w["items"][[o["name"] for o in w["items"]].index(known)]["hash"] = int(h)
        problems += misfit
    return problems
