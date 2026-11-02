"""An intent's weapons checked against the manifest: every named option is one the weapon can roll, perks per column.

Fields of `intent.weapons[]`, exact manifest names, alternatives best first: `items`, `perks` (one list per column),
`mods`, `masterworks`. Their hashes go in the sheet's `hashes` table ("item:<name>", "perk:<name>").
"""
from shell.engines.share import _copy_key, _is_armor_mod, _category, _name
from shell.engines.sockets import candidates

FLAT_FIELDS = ("mods", "masterworks")


def options(w: dict) -> list[str]:
    """Every plug option an intent weapon names (perks, mods, masterworks)."""
    return [*(o for column in w.get("perks") or [] for o in column), *(o for k in FLAT_FIELDS for o in w.get(k) or [])]


def is_named(w: dict) -> bool:
    return bool(w.get("items") or options(w))


def missing_mods(weapons: list[dict], defs: dict, plug_sets: dict, hashes: dict) -> list[str]:
    """One line per checked weapon that can take a mod but names none (exotics have no mod socket)."""
    out = []
    for w in weapons:
        item = next((n for n in w.get("items") or [] if f"item:{n}" in hashes), None)
        if item and not w.get("mods") and any(
                (defs.get(str(h)) or {}).get("itemTypeDisplayName") == "Weapon Mod"
                for socket in candidates(defs.get(str(hashes[f"item:{item}"])) or {}, {}, {},
                                         lambda p: plug_sets.get(str(p)))
                for h in socket):
            out.append(f"{w['slot']}: {item} has a mod socket but no mod is chosen")
    return out


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
    """({option: hash} of `w`'s options found in the sockets `tables` of `weapon`, problems)."""
    found, problems, used = {}, [], set()
    slot = w["slot"]

    def sockets_of(option):
        where = {i for i, t in enumerate(tables) if option in t}
        if not where:
            problems.append(f"{slot}: {option} is not an option of {weapon}")
        return where

    for column in w.get("perks") or []:
        where = [sockets_of(o) for o in column]
        if not all(where):
            continue
        free = set.intersection(*where) - used
        if not free:
            problems.append(f"{slot}: {' / '.join(column)}: no free column of {weapon} has them all")
            continue
        used.add(min(free))
        found.update({o: tables[min(free)][o] for o in column})
    for o in (o for k in FLAT_FIELDS for o in w.get(k) or []):
        where = sockets_of(o)
        if where:
            found[o] = tables[min(where)][o]
    return found, problems


def normalize(weapons: list[dict], defs: dict, plug_sets: dict, hashes: dict) -> list[str]:
    """Writes the hashes of `intent.weapons` in `hashes`; returns the problems (unknown name, option the weapon cannot
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
        for n in w.get("items") or []:
            if n in copies:
                hashes[f"item:{n}"] = int(min(copies[n], key=lambda hd: _copy_key(*hd))[0])
            else:
                problems.append(f"{w['slot']}: unknown weapon: {n}")
        known = next((n for n in w.get("items") or [] if n in copies), None)
        if known is None:
            if not w.get("items"):
                for o in options(w):
                    if o in plugs:
                        hashes[f"perk:{o}"] = plugs[o]
                    else:
                        problems.append(f"{w['slot']}: unknown perk or mod: {o}")
            continue
        fits = []
        # several copies of a name (reissues): the first that can roll everything the intent names
        for h, d in sorted(copies[known], key=lambda hd: _copy_key(*hd)):
            tables = [_by_name(socket, defs) for socket in candidates(d, {}, {}, lambda p: plug_sets.get(str(p)))]
            fits.append((h, *_fit(w, known, tables)))
            if not fits[-1][2]:
                break
        h, found, misfit = next((f for f in fits if not f[2]), fits[0])
        hashes[f"item:{known}"] = int(h)
        hashes.update({f"perk:{o}": v for o, v in found.items()})
        problems += misfit
    return problems
