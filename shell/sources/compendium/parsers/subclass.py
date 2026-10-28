"""Subclass tabs (Arc, Solar, Void, Stasis, Strand, Prismatic); same layout as Class Abilities.
Name in column 1, description in column 3, info in column 13.

The aspects' "Fragment Slots" column holds an image, not text: nothing to get from it."""
from ..model import Entry
from ._common import Notes, other_lines

ANCHORS = ("Glossary", "Fragments")
MIN_ENTRIES = 20
NAME, TEXT, EXTRA = 1, 3, 13
CLASS_COL = 6  # class block: the class is repeated there (only useful cell of Void's Titan block)
CLASSES = {"Hunter": "Hunter", "Hunters": "Hunter", "Titan": "Titan", "Titans": "Titan",
           "Warlock": "Warlock", "Warlocks": "Warlock"}
SECTIONS = {"Glossary": "Glossary", "Fragments": "Fragments", "Aspect": "Aspects", "Aspects": "Aspects",
            "Grenade Abilities": "Grenade Abilities", "Melee Abilities": "Melee Abilities",
            "Super Abilities": "Super Abilities", "Class Abilities": "Class Abilities"}
# Aspect effects listed under the grenade they modify (one variant per grenade).
VARIANTS = ("Touch of Thunder", "Touch of Flame", "Touch of Winter", "Chaos Accelerant", "Mindspun Invocation")


def _label(cls, section):
    return f"{cls} — {section}" if cls else section


def _class_block(grid, r):
    """Class of a class block row, None otherwise (the navigation bar has the class in column 1)."""
    head = grid.text(r, 0)
    if head in CLASSES:
        return CLASSES[head]
    if head and grid.text(r, CLASS_COL) in CLASSES and grid.text(r, NAME) not in CLASSES:
        return CLASSES[grid.text(r, CLASS_COL)]
    return None


def _name_parts(name):
    """First line of the name, then the details: following lines without their parentheses,
    or the part after ": " ("Nova Bomb: Cataclysm" like "Nova Bomb:\\nVortex")."""
    lines = [line.strip() for line in name.split("\n") if line.strip()]
    first, _, detail = lines[0].partition(": ")
    rest = ([detail.strip()] if detail.strip() else []) + [line.strip("()") for line in lines[1:]]
    return first.rstrip(":").strip(), rest


def _entry_name(name, section, grenade):
    """(displayed name, new current grenade). A variant under a grenade takes that grenade's name."""
    first, rest = _name_parts(name)
    if first in VARIANTS and section == "Grenade Abilities" and grenade:
        return f"{grenade} ({', '.join([first] + rest)})", grenade
    name = f"{first} ({', '.join(rest)})" if rest else first
    # Every non-variant Grenade Abilities row becomes the current grenade, including
    # "Handheld Supernova (Chaos Accelerant)" (Void), which is not a grenade: no variant follows it.
    return name, name if section == "Grenade Abilities" else grenade


def _shared_abilities(grid, r, cls):
    """Prismatic: "Shared Abilities" cell (merged over several rows) and the abilities listed to its right.
    Returns the entry and the first row after the merge."""
    name = grid.text(r, NAME)
    end = r + grid.span(r, NAME)[0]
    items = [t for k in range(r, end) for c, t in grid.cells(k) if c > NAME + 1]
    note = " ".join(other_lines(name))
    entry = Entry("Shared Abilities", _label(cls, "Abilities"), {"note": note} if note else {},
                  "\n".join(f"- {t}" for t in items))
    return entry, end


def _info(extra):
    """Lines of the info column joined by "·"; a line ending with ":" absorbs the next one."""
    lines = []
    for line in (line.strip() for line in extra.split("\n")):
        if not line:
            continue
        if lines and lines[-1].endswith(":"):
            lines[-1] += " " + line
        else:
            lines.append(line)
    return " · ".join(lines)


def parse(grid):
    entries, cls, section, grenade, shared_end = [], None, None, None, 0
    notes = Notes(entries)
    for r in range(grid.height):
        if r < shared_end:  # ability rows covered by the "Shared Abilities" cell
            continue
        block = _class_block(grid, r)
        if block:
            cls, section = block, None
            continue
        if grid.text(r, 0):  # title row ("Go back to the top!" / tab title)
            continue
        name, text = grid.text(r, NAME), grid.text(r, TEXT)
        if name in CLASSES:  # navigation bar
            continue
        if name in SECTIONS:
            section = SECTIONS[name]
            continue
        if name.startswith("Shared Abilities"):
            entry, shared_end = _shared_abilities(grid, r, cls)
            entries.append(entry)
            continue
        if not name or not text:  # author's note (or name replaced by an image)
            if name or text:
                notes.add(_label(cls, section or "Abilities"), name or text)
            continue
        sec = section or ("Grenade Abilities" if text.startswith("Prismatic Grenade") else "Abilities")
        name, grenade = _entry_name(name, sec, grenade)
        attrs = {}
        extra = grid.text(r, EXTRA)
        if extra and extra != "-":
            attrs["stats" if sec == "Fragments" else "info"] = _info(extra)
        entries.append(Entry(name, _label(cls, sec), attrs, text))
    return entries
