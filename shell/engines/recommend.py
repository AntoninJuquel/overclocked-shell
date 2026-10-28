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
    """The DPS row of an owned weapon, or None. Exotics match on their name. A legendary matches an archetype row
    ("Aggressive rocket launcher") when the row's family is its type's, the row name starts with its frame and the
    rest are words of its type. shortcut: the row's perks are shown, not matched; match them if picks mislead."""
    if w.get("rarity") == "Exotic":
        found = [r for r in rows if norm(r["_name"]) == norm(w["name"])]
    else:
        frame, type_words = _words(w.get("frame")), set(_words(w["type"]))
        found = [r for r in rows if r.get("Family") in FAMILIES.get(w["type"], ())
                 and (name := _words(r["_name"]))[:len(frame)] == frame and frame
                 and set(name[len(frame):]) <= type_words]
    return max(found, key=_dps, default=None)


def _dps(row):
    m = re.search(r"\d[\d,]*(?:\.\d+)?", row.get("DPS") or "")
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


def _best_copies(rows, grades, cls):
    def key(w):
        g = grades.get(w["itemId"])
        return (g is None, *(weapons._grade_key(g) if g else (0, 0)),
                not (w.get("equipped") and w.get("location") == cls), not w.get("locked"), w["itemId"])

    best = {}  # by norm(name): "X (Timelost)" and "X (Adept)" are copies of X
    for w in rows:
        n = norm(w["name"])
        if n not in best or key(w) < key(best[n]):
            best[n] = w
    return list(best.values())


def _not_owned(items, type_, element, above):
    owned = {norm(w["name"]) for w in items}
    found = [r for spec in config.weapon_tabs() if spec.weapon_type and type_.lower() in spec.weapon_type.lower()
             for r in lookup.rows("endgame", spec.slug)]
    found += [r for r in lookup.rows("endgame", "exotic-weapons") if type_.lower() in (r.get("Type") or "").lower()]
    found = [r for r in found if norm(r["_name"]) not in owned and lookup.tier_key(r) < above
             and (not element or (r.get("Energy") or "").strip().lower() == element.lower())]
    found.sort(key=lookup.tier_key)
    return [f"{lookup.tier_label(r)} | {first_line(r['_name'])} | {r['_tab']}" for r in found[:3]]


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
    copies = _best_copies(weapons.select(items, slot, element, type_), grades, cls)
    warnings, not_owned = [], []
    if role == "dps":
        rows = lookup.rows("boss", "sustained")
        matched = [(w, dps_row(w, rows)) for w in copies]
        missing = [w["name"] for w, r in matched if r is None]
        if missing:
            more = f" … and {len(missing) - 10} more" if len(missing) > 10 else ""
            warnings.append(f"no Aegis DPS row for: {', '.join(missing[:10])}{more}")
        ranked = sorted(((w, r) for w, r in matched if r is not None), key=lambda wr: (-_dps(wr[1]), wr[0]["name"]))
        label = _dps_label
    else:
        def key(wr):
            g = grades.get(wr[0]["itemId"])
            return (lookup.tier_key(wr[1]) if wr[1] else UNRATED, weapons._grade_key(g) if g else UNRATED,
                    wr[0]["name"])

        ranked = sorted(((w, lookup.best(lookup.weapon_rows(w["name"]))) for w in copies), key=key)
        label = lambda r: f"Aegis {lookup.tier_label(r) if r else '—'}"  # noqa: E731
        if type_:
            not_owned = _not_owned(items, type_, element, key(ranked[0])[0] if ranked else UNRATED)

    picks = [" | ".join([str(i), w["itemId"], w["name"], w["type"], w["element"], w["slot"], w.get("ammo") or "—",
                         label(r), f"grade {grades.get(w['itemId']) or '—'}", _note(w, cls, worn)])
             for i, (w, r) in enumerate(ranked[:top], 1)]
    return {"equipped": equipped, "picks": picks, "not_owned": not_owned, "warnings": warnings}
