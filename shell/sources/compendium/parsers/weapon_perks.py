"""Weapon Perks tab: traits, mods, intrinsics and origins, one entry per row."""
from ..model import Entry
from ._common import Notes, banner, find_row, first_line, is_section_title

ANCHORS = ("Perk", "Description", "Weapon Traits")
MIN_ENTRIES = 300
DEFAULT_NOTE_SECTION = "Weapon Traits"  # legend placed before the first section banner


def _extra(name):
    """Lines after the first: "·" within a paragraph, "/" between paragraphs (separated by a blank line)."""
    paragraphs, current = [], []
    for line in name.split("\n")[1:]:
        line = line.strip()
        if line:
            current.append(line)
        elif current:
            paragraphs.append(current)
            current = []
    if current:
        paragraphs.append(current)
    return " / ".join(" · ".join(p) for p in paragraphs)


def parse(grid):
    start = find_row(grid, ["Perk", "Description"]) + 1
    entries, section = [], None
    notes = Notes(entries)

    for r in range(start, grid.height):
        title = banner(grid, r)
        if title is not None:
            if is_section_title(title):
                section = title
            else:  # author's note: does not change the section
                notes.add(section or DEFAULT_NOTE_SECTION, title)
            continue
        cells = grid.cells(r)
        if section is None or len(cells) < 2:
            continue
        name = cells[0][1]
        if len(first_line(name)) > 60:  # section footnote (column 0 = sentence), not a perk
            notes.add(section, "\n\n".join(t for _, t in cells))
            continue
        extra = _extra(name)
        attrs = {("source" if section == "Origin Traits" else "detail"): extra} if extra else {}
        entries.append(Entry(first_line(name), section, attrs, "\n\n".join(t for _, t in cells[1:])))
    return entries
