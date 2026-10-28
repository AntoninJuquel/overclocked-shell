"""Exotic Armors tab: three blocks side by side (Hunter / Titan / Warlock)."""
from ..model import Entry
from ._common import banner, find_row, first_line, other_lines

ANCHORS = ("Armor", "Icon", "Notes", "Hunters", "Titans", "Warlocks")
MIN_ENTRIES = 100
CLASSES = {"Hunters": "Hunter", "Titans": "Titan", "Warlocks": "Warlock"}


def parse(grid):
    header = find_row(grid, ["Armor", "Icon", "Notes"])
    starts = [c for c, t in grid.cells(header) if t == "Armor"]
    classes = {c: CLASSES.get(grid.cell(header - 1, c).text, grid.cell(header - 1, c).text)
               for c in starts}
    entries = []
    section = None  # current banner (e.g. "Aeon Sects"), None before the first
    for r in range(header + 1, grid.height):
        text = banner(grid, r)
        if text is not None:
            section = first_line(text)
            continue
        for c in starts:
            name, notes = grid.text(r, c), grid.text(r, c + 2)
            if not name or not notes:  # perk row, empty cell
                continue
            if section is not None:
                extra = other_lines(name)
                attrs = {"perk": " · ".join(extra)} if extra else {}
                entries.append(Entry(first_line(name), section, attrs, notes))
                continue
            height = grid.span(r, c + 2)[0]
            perks = [grid.text(k, c) for k in range(r + 1, r + height) if grid.text(k, c)]
            attrs = {"perk": perks[-1]} if perks else {}
            entries.append(Entry(first_line(name), classes[c], attrs, notes))
    return entries
