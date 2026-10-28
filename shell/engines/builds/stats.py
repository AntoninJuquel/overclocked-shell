"""Armor stat constants (Armor 3.0) and fragment stat bonuses read from the compendium."""
import re
from pathlib import Path

from shell.core import paths

STATS = ["Weapons", "Health", "Class", "Grenade", "Super", "Melee"]
SLOTS = ["Helmet", "Gauntlets", "Chest", "Legs", "Class Item"]
CLASSES = ["Hunter", "Titan", "Warlock"]
ELEMENTS = ["Arc", "Solar", "Void", "Stasis", "Strand", "Prismatic"]
CAP = 200  # points above this are lost

# Armor 3.0 archetypes: (primary stat, secondary stat). A tier 5 piece has 30 / 25 / 20 on primary,
# secondary and tertiary (random), 0 elsewhere. Read from the armor export of 2026-10-07.
ARCHETYPES = {
    "Brawler": ("Melee", "Health"), "Bulwark": ("Health", "Class"), "Colossus": ("Super", "Health"),
    "Demolitionist": ("Grenade", "Class"), "Grenadier": ("Grenade", "Super"), "Gunner": ("Weapons", "Grenade"),
    "Paragon": ("Super", "Melee"), "Powerhouse": ("Weapons", "Super"), "Reaver": ("Class", "Melee"),
    "Siegebreaker": ("Health", "Grenade"), "Skirmisher": ("Melee", "Weapons"), "Specialist": ("Class", "Weapons"),
}

_PART = re.compile(r"([+-]\d+)\s+(\w+)(?:\s+\((\w+)\))?$")
_ALIASES = {"Weapon": "Weapons"}  # typo found in the compendium
_FRAGMENT_PREFIX = re.compile(r"^(?:Spark|Ember|Echo|Whisper|Thread|Facet) of (?:the )?", re.IGNORECASE)


class FragmentNotFound(ValueError):
    """Fragment missing from the compendium."""


def compendium_dir() -> Path:
    return paths.cache_dir() / "compendium"


def fragment_key(name):
    """"Spark of Shock" and "Shock" give the same key (the compendium uses the short name)."""
    return _FRAGMENT_PREFIX.sub("", name.strip())


def parse_stats(text, cls):
    """"+10 Health · -10 Weapons (Hunter)" → {"Health": 10} for a Warlock (other classes' parts ignored)."""
    if cls not in CLASSES:
        raise ValueError(f"unknown class: {cls!r}")
    out = {}
    for part in text.split("·"):
        part = part.strip()
        m = _PART.match(part)
        if not m:
            raise ValueError(f"unreadable stats: {part!r}")
        stat = _ALIASES.get(m.group(2), m.group(2))
        if stat not in STATS:
            raise ValueError(f"unreadable stats: {part!r}")
        if m.group(3) and m.group(3) not in CLASSES:
            raise ValueError(f"unknown class: {m.group(3)!r} in {part!r}")
        if m.group(3) and m.group(3) != cls:
            continue
        out[stat] = out.get(stat, 0) + int(m.group(1))
    return out


def entries(path):
    """[(name, {attribute: value})] of the `### name` entries of a compendium file."""
    found = []
    in_attrs = False  # only the `- k: v` lines right under the heading are attributes
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("### "):
            found.append((line[4:].strip(), {}))
            in_attrs = True
        elif not line.strip() or line.startswith("#"):
            in_attrs = False
        elif in_attrs and line.startswith("- ") and ": " in line:
            key, value = line[2:].split(": ", 1)
            found[-1][1].setdefault(key.strip(), value.strip())
    return found


def fragment_stats(fragments, element, cls, compendium: Path | None = None):
    """Sum of the fragments' stat bonuses (section "Fragments" of subclass-<element>.md)."""
    if element not in ELEMENTS:
        raise ValueError(f"unknown element: {element!r}")
    keys = [fragment_key(f) for f in fragments]
    if len(set(keys)) != len(keys):
        raise ValueError(f"duplicate fragment: {fragments}")
    path = Path(compendium if compendium is not None else compendium_dir()) / f"subclass-{element.lower()}.md"
    if not path.exists():
        raise ValueError(f"{path.name} missing: run refresh_references(source=\"compendium\")")
    known = {fragment_key(name): attrs for name, attrs in entries(path) if attrs.get("section") == "Fragments"}
    total = {}
    for name, key in zip(fragments, keys):
        if key not in known:
            raise FragmentNotFound(f"fragment not found in the compendium: {name} ({path.name})")
        if "stats" not in known[key]:
            continue
        for stat, value in parse_stats(known[key]["stats"], cls).items():
            total[stat] = total.get(stat, 0) + value
    return {stat: value for stat, value in total.items() if value}
