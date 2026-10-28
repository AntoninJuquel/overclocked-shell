"""Exotic Weapons tab: one weapon per row, perks and catalyst under the name.

Column 0: `Name[\nSubtitle]\n\nPerk 1\nPerk 2\n↑Catalyst[\n\nNote]`; column 3: description;
columns 1-2 ("PvP-Specific") and 6+ ("PvE-Specific"): specific notes, kept with their label.
"""
from ..model import Entry
from ._common import Notes

ANCHORS = ("Kinetic Slot Weapons",)
MIN_ENTRIES = 100
TAB = "Exotic Weapons"


def _lines(block):
    return [line.strip() for line in block.split("\n") if line.strip()]


def _split_name(text):
    """(name, subtitle, perks, catalysts, note) of a weapon name cell."""
    blocks = [b for b in text.strip().split("\n\n") if b.strip()]
    head = _lines(blocks[0])
    subtitle = head[1:]
    perk_lines = _lines(blocks[1]) if len(blocks) > 1 else []
    note = "\n\n".join(b.strip() for b in blocks[2:])
    if len(blocks) == 1 and len(head) > 1:
        # no blank line: only the exact shape (name, alias, 3 perk lines, 1 catalyst line) gives an alias;
        # any other shape: everything is a perk (an extra visible perk beats a lost perk)
        rest = head[1:]
        n_cat = len([line for line in rest if line.startswith("↑")])
        if n_cat == 1 and len(rest) - n_cat == 3:
            subtitle, perk_lines = rest[:1], rest[1:]
        else:
            subtitle, perk_lines = [], rest
    perks = [line for line in perk_lines if not line.startswith("↑")]
    catalyst = [line[1:].strip() for line in perk_lines if line.startswith("↑")]
    return head[0].rstrip(":").strip(), subtitle, perks, catalyst, note


def parse(grid):
    entries, section = [], None
    notes = Notes(entries)
    last = None
    for r in range(grid.height):
        cells = grid.cells(r)
        if not cells:
            continue
        if len(cells) == 1 and cells[0][0] == 0 and cells[0][1].endswith("Weapons") and len(cells[0][1]) <= 40:
            section, last = cells[0][1], None
            continue
        if section is None:
            # before the first banner: headers and navigation bar (several cells) ignored;
            # a lone cell is a general note from the author, kept
            if len(cells) == 1:
                notes.add(TAB, cells[0][1])
            continue
        if cells[0][0] != 0:
            notes.add(section, "\n\n".join(t for _, t in cells))  # author's note in the middle of a section
            continue
        if not cells[0][1].strip():
            continue
        name, subtitle, perks, catalyst, note = _split_name(cells[0][1])
        attrs = {}
        if (last is not None and name == last and not catalyst and len(perks) == 1 and not subtitle):
            # variant of a weapon listed just before (e.g. Ergo Sum / Arc Element): not a perk
            name, perks = f"{name} ({perks[0]})", []
        last = cells[0][1].split("\n", 1)[0].strip()
        if subtitle:
            attrs["subtitle"] = " · ".join(subtitle)
        if perks:
            attrs["perks"] = " · ".join(perks)
        if catalyst:
            attrs["catalyst"] = " · ".join(catalyst)
        if note:
            attrs["note"] = note
        parts, pvp, pve = [], [], []
        for c, text in cells[1:]:
            (pvp if c < 3 else pve if c >= 6 else parts).append(text)
        if pvp:
            parts.append("PvP-specific:\n" + "\n\n".join(pvp))
        if pve:
            parts.append("PvE-specific:\n" + "\n\n".join(pve))
        entries.append(Entry(name, section, attrs, "\n\n".join(parts)))
    return entries
