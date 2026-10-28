"""Armor Perks tab: armor set bonuses (2 and 4 pieces), one entry per set."""
import re

from ..model import Entry
from ._common import Notes, banner, find_row, first_line, is_section_title, other_lines

ANCHORS = ("Armor Set Bonuses", "Armor Set", "Description")
MIN_ENTRIES = 20
DEFAULT_SECTION = "Armor Set Bonuses"
DISABLED = ">>DISABLED IN CRUCIBLE<<"
BONUS = re.compile(r"^(\d) Piece \| ([^\n]+)\n?(.*)$", re.S)


def parse(grid):
    start = find_row(grid, ["Armor Set", "Description"]) + 1
    entries, section, by_origin = [], DEFAULT_SECTION, {}
    notes = Notes(entries)

    for r in range(start, grid.height):
        title = banner(grid, r)
        if title is not None:
            if is_section_title(title):
                section = title
            else:  # author's note: does not change the section
                notes.add(section, title)
            continue
        name_cell = grid.cell(r, 0)
        desc = [t for c, t in grid.cells(r) if c > 0]
        if not name_cell.text or not desc:
            leftovers = [t for _, t in grid.cells(r)]
            if leftovers:  # unexpected row: kept as a note rather than lost
                notes.add(section, "\n\n".join(leftovers))
            continue
        entry = by_origin.get(name_cell.top)
        if entry is None:
            entry = Entry(first_line(name_cell.text), section)
            source = other_lines(name_cell.text)
            if source:
                entry.attrs["source"] = " · ".join(source)
            by_origin[name_cell.top] = entry
            entries.append(entry)
        m = BONUS.match(desc[0])
        if m:
            pieces, perk, body = m.group(1), m.group(2).strip(), m.group(3).strip()
            entry.attrs[f"{pieces} pieces"] = perk
            block = f"{pieces} pieces — {perk}:\n{body}"
            if body.startswith(DISABLED):
                flag = f"{pieces} pieces disabled"
                previous = entry.attrs.get("crucible")
                entry.attrs["crucible"] = f"{previous} · {flag}" if previous else flag
        else:
            block = desc[0]
        entry.text = f"{entry.text}\n\n{block}".strip()
    return entries
