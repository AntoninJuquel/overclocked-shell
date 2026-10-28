"""Exotic Class tab: spirits of the exotic class items (two columns per row)."""
from ..model import Entry
from ._common import Notes, banner

ANCHORS = ("Class-agnostic Perks", "Hunter-exclusive Perks", "Titan-exclusive Perks", "Warlock-exclusive Perks")
MIN_ENTRIES = 30
COLUMNS = {0: "left (archetype)", 3: "right (tertiary stats)"}  # name column -> role


def parse(grid):
    entries, section = [], None
    notes, note_section = Notes(entries), "Exotic Class Perks"
    for r in range(grid.height):
        title = banner(grid, r)
        if title is not None:
            if title.endswith("Perks"):
                section = note_section = title
            else:  # author's note: kept, and it closes the perk section
                notes.add(note_section, title)
                section = None
            continue
        if section is None:
            continue
        for c, column in COLUMNS.items():
            name, text = grid.text(r, c), grid.text(r, c + 2)
            if bool(name) != bool(text):
                raise ValueError(f"incomplete spirit row {r}, column {c}")
            if name and text:
                entries.append(Entry(name, section, {"role": column}, text))
    return entries
