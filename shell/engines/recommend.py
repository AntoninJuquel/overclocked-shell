"""Situational recommender: the player's weapons ranked for a role, compared with what a character has equipped.

role "general": best Aegis Endgame row (tier then rank), then wishlist grade. role "dps": Aegis sustained DPS of
the matching row (see `dps_row`); weapons without a row are left out and named in a warning.
One line per weapon name (best copy: wishlist grade, then the copy equipped on the character, then locked):
rank | id | name | type | element | slot | ammo | Aegis tier or DPS (setup) | grade | where / what it replaces.
not_owned (general, with a `type`): up to 3 Aegis rows ranked above the best owned pick, not in the inventory.
"""
import re

from shell.engines.builds import rankings, weapons
from shell.sources.aegis import config, lookup
from shell.sources.aegis.names import first_line, norm

CLASSES = ("Titan", "Hunter", "Warlock")
ROLES = ("general", "dps")
SLOTS = ("Kinetic", "Energy", "Power")
# Aegis DPS `Family` per weapon type (grenade launchers: special or heavy).
FAMILIES = {"Rocket Launcher": {"rocket"}, "Sniper Rifle": {"sniper"}, "Machine Gun": {"LMG"},
            "Combat Bow": {"bow"}, "Linear Fusion Rifle": {"linear"}, "Fusion Rifle": {"fusion"},
            "Sword": {"sword"}, "Glaive": {"glaive"}, "Shotgun": {"shotgun"}, "Grenade Launcher": {"BGL", "HGL"},
            "Trace Rifle": {"trace"}, "Auto Rifle": {"auto"}, "Pulse Rifle": {"pulse"}, "Scout Rifle": {"scout"},
            "Sidearm": {"sidearm"}, "Submachine Gun": {"SMG"}, "Hand Cannon": {"HC"}}
UNRATED = (len(lookup.TIERS), weapons.BIG)


def _words(text):
    """"Rapid-Fire Frame" -> ["rapid", "fire"]: lower case, hyphens split, the word "frame" dropped."""
    return [x for x in re.split(r"[\s-]+", (text or "").lower()) if x and x != "frame"]


def dps_row(w, rows):
    """The DPS row of an owned weapon, or None. Exotics match on their name, preferring rows of their type's family
    and whose setup names their intrinsic (Ergo Sum: The Perfect Fifth vs Unplanned Reprieve).
    A legendary matches an archetype row
    ("Aggressive rocket launcher") when the row's family is its type's, the row name starts with its frame and the
    rest are words of its type; in a family whose rows name no frame ("Trace rifle"), on the family alone. shortcut: the row's perks are shown, not matched; match them if picks mislead."""
    if w.get("rarity") == "Exotic":
        found = [r for r in rows if norm(r["_name"]) == norm(w["name"])]
        found = [r for r in found if r.get("Family") in FAMILIES.get(w["type"], ())] or found
        intrinsic = (w.get("frame") or "").lower()
        found = [r for r in found if intrinsic and intrinsic in (r.get("Name") or "").lower()] or found
    else:
        frame, type_words = _words(w.get("frame")), set(_words(w["type"]))
        found = [r for r in rows if r.get("Family") in FAMILIES.get(w["type"], ())]
        if not all(set(_words(r["_name"])) <= type_words for r in found):
            found = [r for r in found if (name := _words(r["_name"]))[:len(frame)] == frame and frame
                     and set(name[len(frame):]) <= type_words]
    return max(found, key=_dps, default=None)


def _dps(row):
    m = re.search(r"\d[\d,]*(?:\.\d+)?", (row or {}).get("DPS") or "")
    return float(m.group().replace(",", "")) if m else 0.0


def _dps_label(row):
    """"DPS 13,514 (Aggressive rocket launcher: Cluster Bomb + Elemental Honing)": the setup Aegis measured."""
    setup = " / ".join(x.strip() for x in (row.get("Name") or "").split("\n")[1:] if x.strip())
    return f"DPS {row.get('DPS') or '—'} ({': '.join(filter(None, [first_line(row['_name']), setup]))})"


def _note(w, cls, worn):
    if w.get("equipped") and w.get("location") == cls:
        return "equipped"
    parts = ["in vault" if w.get("location") == "Vault" else f"on {w.get('location')}"]
    if w.get("equipped"):
        parts[0] += " (equipped there)"
    if (same := worn.get(w["slot"])) is not None:
        parts.append(f"swap: replaces {same['name']}")
    others = [x["name"] for s, x in worn.items() if s != w["slot"] and x.get("rarity") == "Exotic"]
    if w.get("rarity") == "Exotic" and others:
        parts.append(f"second exotic: unequip {others[0]}")
    return " · ".join(parts)


def _grade(grades, w):
    g = grades.get(w["itemId"])
    return weapons._grade_key(g) if g else UNRATED


def _best_copies(rows, grades, cls, first=lambda w: 0):
    """One copy per weapon: lowest `first` (dps role: its DPS row), then grade, equipped here, locked."""
    def key(w):
        return (first(w), _grade(grades, w), not (w.get("equipped") and w.get("location") == cls),
                not w.get("locked"), w["itemId"])

    best = {}  # by norm(name): "X (Timelost)" and "X (Adept)" are copies of X
    for w in rows:
        n = norm(w["name"])
        if n not in best or key(w) < key(best[n]):
            best[n] = w
    return list(best.values())


def _type_ok(type_, weapon_type):
    """A full type name ("Fusion Rifle") matches exactly, a part of one ("fusion") as a substring."""
    t = type_.lower()
    return t == weapon_type.lower() if t in {x.lower() for x in FAMILIES} else t in weapon_type.lower()


def _not_owned(items, type_, element, above):
    """The Other tab gives no type: its rows come last, marked, as in `rankings`."""
    owned = {norm(w["name"]) for w in items}
    found = [(not spec.weapon_type, r) for spec in config.weapon_tabs()
             if not spec.weapon_type or _type_ok(type_, spec.weapon_type) for r in lookup.rows("endgame", spec.slug)]
    # Exotic rows are left out: their Type column is the ammo (primary / special / power), not a weapon type.
    found = [(u, r) for u, r in found if norm(r["_name"]) not in owned and lookup.tier_key(r) < above
             and (not element or (r.get("Energy") or "").strip().lower() == element.lower())]
    found.sort(key=lambda ur: (ur[0], lookup.tier_key(ur[1])))
    return [" | ".join([lookup.tier_label(r), first_line(r["_name"]), r["_tab"]] + [rankings.UNTYPED_NOTE] * u)
            for u, r in found[:3]]


def recommend(items, grades, character, role="general", slot=None, element=None, type_=None, top=5) -> dict:
    """{equipped, picks, not_owned, warnings} for one character (titan, hunter or warlock). ValueError on a bad
    argument, FileNotFoundError without Aegis data."""
    cls = next((c for c in CLASSES if c.lower() == (character or "").strip().lower()), None)
    if cls is None:
        raise ValueError("character is titan, hunter or warlock")
    if role not in ROLES:
        raise ValueError(f"role is one of {', '.join(ROLES)}")
    if slot and slot.capitalize() not in SLOTS:
        raise ValueError(f"slot is one of {', '.join(SLOTS)}")
    if top < 1:
        raise ValueError("top must be >= 1")
    needed = lookup.data_dir() / ("boss/sustained.json" if role == "dps" else "endgame")
    if not needed.exists():
        raise FileNotFoundError(rankings.MISSING)

    worn = {w["slot"]: w for w in items if w.get("equipped") and w.get("location") == cls}
    equipped = [" | ".join([s, worn[s]["name"], worn[s]["type"], worn[s]["element"]]
                           + (["exotic"] if worn[s].get("rarity") == "Exotic" else [])) for s in SLOTS if s in worn]
    selected = [w for w in weapons.select(items, slot, element, type_) if not type_ or _type_ok(type_, w["type"])]
    warnings, not_owned = [] if selected else ["no owned weapon matches the filters"], []
    if role == "dps":
        rows = lookup.rows("boss", "sustained")
        row_of = {w["itemId"]: dps_row(w, rows) for w in selected}
        matched = [(w, row_of[w["itemId"]])
                   for w in _best_copies(selected, grades, cls, lambda w: -_dps(row_of[w["itemId"]]))]
        missing = [w["name"] for w, r in matched if r is None]
        if missing:
            more = f" … and {len(missing) - 10} more" if len(missing) > 10 else ""
            warnings.append(f"no Aegis DPS row for: {', '.join(missing[:10])}{more}")
        ranked = sorted(((w, r) for w, r in matched if r is not None),
                        key=lambda wr: (-_dps(wr[1]), _grade(grades, wr[0]), wr[0]["name"]))
        label = _dps_label
    else:
        def key(wr):
            return lookup.tier_key(wr[1]) if wr[1] else UNRATED, _grade(grades, wr[0]), wr[0]["name"]

        ranked = sorted(((w, lookup.best(lookup.weapon_rows(w["name"]))) for w in _best_copies(selected, grades, cls)),
                        key=key)
        label = lambda r: f"Aegis {lookup.tier_label(r)} ({r['_tab']})" if r else "Aegis —"  # noqa: E731
        if type_:
            not_owned = _not_owned(items, type_, element, key(ranked[0])[0] if ranked else UNRATED)

    picks = [" | ".join([str(i), w["itemId"], w["name"], w["type"], w["element"], w["slot"], w.get("ammo") or "—",
                         label(r), f"grade {grades.get(w['itemId']) or '—'}", _note(w, cls, worn)])
             for i, (w, r) in enumerate(ranked[:top], 1)]
    return {"equipped": equipped, "picks": picks, "not_owned": not_owned, "warnings": warnings}
