"""Artifact Perks tab: per artifact, rows of names (col. 2/5/8) followed by their descriptions (col. 1/4/7).

Each artifact: a title (single cell in column 3), an optional "elements ⯁ weapon types" row
(single cell in column 3, with no title of its own), then pairs of name / description rows. The
"⯁ / ⯁ ⯁ / ⯁ ⯁ ⯁" header labels the three perk columns: it is ignored, the column (1 to 3) is kept
in the "column" attribute. Any text that does not fit this layout (author's notes, description
without a name) goes into "Notes".

The tab has no explicit current-artifact marker. The author lists the current season's artifact
first: the "order" attribute (1 = first artifact of the tab) therefore most likely marks the current one.
"""
from ..model import Entry
from ._common import Notes, is_section_title

ANCHORS = ("Artifact Perks",)
MIN_ENTRIES = 25
DIAMOND = "⯁"


def _is_diamond_header(cells):
    return all(t.replace(DIAMOND, "").strip() == "" for _, t in cells)


def parse(grid):
    entries = []
    notes = Notes(entries)
    section, attrs, names = "Artifact Perks", {}, {}
    order, seen_perk = 0, False

    def add(k, name, text):
        nonlocal seen_perk
        seen_perk = True
        entries.append(Entry(name, section, {**attrs, "order": str(order), "column": str(k + 1)}, text))

    def flush():
        # names left without a description: kept, with an empty text
        for k in sorted(names):
            add(k, names[k], "")
        names.clear()

    for r in range(grid.height):
        cells = grid.cells(r)
        if not cells or _is_diamond_header(cells):
            continue
        positions = {c % 3 for c, _ in cells}
        if len(cells) == 1 and positions == {0}:
            text = cells[0][1]
            if DIAMOND in text and not seen_perk:    # elements ⯁ weapon types
                elements, _, weapons = text.partition(DIAMOND)
                attrs.update({"elements": elements.strip(), "weapons": weapons.strip()})
            elif not is_section_title(text):           # author's note
                flush()
                notes.add(section, text)
            else:                                       # artifact title
                flush()
                section, attrs, seen_perk = text, {}, False
                if text not in ANCHORS:                 # the tab title is not an artifact
                    order += 1
        elif positions == {2}:                          # names row
            flush()
            names.update({c // 3: t for c, t in cells})
        elif positions == {1}:                          # descriptions row
            for c, text in cells:
                if c // 3 in names:
                    add(c // 3, names.pop(c // 3), text)
                else:
                    notes.add(section, text)
            flush()
        else:                                           # unexpected row: nothing is lost
            flush()
            for _, text in cells:
                notes.add(section, text)
    flush()
    return entries
