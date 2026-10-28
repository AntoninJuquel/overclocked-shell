"""Weapon triage against a DIM wishlist: KEEP / JUNK with a reason for each weapon.

Only roll quality counts: neither loadouts nor what is equipped protect a weapon.
"""
from collections import defaultdict

from shell.sources.wishlists import norm_perk, norm_weapon


def rank(w):
    """Bigger = better copy."""
    return (w["crafted"], w["wish"], w["gearTier"], w["enhanced"], w["locked"], w["power"])


def _decide(w, keep, reason):
    w["decision"], w["reason"] = ("KEEP" if keep else "JUNK"), reason


def triage_weapons(rows: list[dict], rolls: dict, notes: dict, names: dict) -> list[dict]:
    """rolls / notes / names as returned by `shell.sources.wishlists.load`."""
    by_name = defaultdict(list)  # name fallback (reissues / adepts under another hash)
    for h, n in names.items():
        if n:
            by_name[norm_weapon(n)].append(h)

    weapons = [dict(r) for r in rows]
    for w in weapons:
        opts = {norm_perk(o["name"]) for c in w["columns"] for o in c["options"]}
        w["traits"] = tuple(sorted(norm_perk(o["name"]) for c in w["columns"] if c["label"] == "Trait"
                                   for o in c["options"]))
        # `frame` also carries the random exotic perk (e.g. Ergo Sum: Stormbringer, Wolfpack Rounds…),
        # missing from the perk columns.
        w["roll"] = (w["frame"],) + tuple(sorted(norm_perk(o["name"]) for c in w["columns"] for o in c["options"]))
        w["enhanced"] = sum(o["enhanced"] for c in w["columns"] for o in c["options"])
        hashes = [w["itemHash"]] if w["itemHash"] in rolls else by_name.get(norm_weapon(w["name"]), [])
        w["listed"] = bool(hashes)
        w["grade"] = next((notes[h] for h in hashes if h in notes), "")
        best = 0
        for h in hashes:
            for perks in rolls[h]:
                if perks <= opts:
                    best = max(best, len(perks) or 1)
        w["wish"] = best  # 0 = no wishlist roll matches

    groups = defaultdict(list)
    for w in weapons:
        # Exotics: grouped by full roll (Ergo Sum & co have random perks).
        groups[(norm_weapon(w["name"]), w["roll"]) if w["rarity"] == "Exotic" else w["name"]].append(w)

    for grp in groups.values():
        grp.sort(key=rank, reverse=True)
        if grp[0]["rarity"] == "Exotic":
            # Exotics: one copy per roll is enough.
            _decide(grp[0], True, "exotic (best copy)")
            for w in grp[1:]:
                _decide(w, False, "duplicate exotic")
            continue
        kept_traits = set()
        for w in grp:
            if w["crafted"]:
                _decide(w, True, "crafted (pattern)")
            elif w["wish"]:
                if w["traits"] in kept_traits:
                    _decide(w, False, "duplicate god roll (same traits, worse tier/enhanced)")
                else:
                    _decide(w, True, f"wishlist {w['grade']}".strip())
                kept_traits.add(w["traits"])
            elif not w["listed"]:
                _decide(w, False, "weapon not on the wishlist")
            else:
                _decide(w, False, "roll not on the wishlist")
    return weapons
