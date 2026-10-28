"""Game Mechanics tab: chapters (table of contents), terms, paragraphs and number tables."""
import re

from ..model import Entry
from ._common import first_line, is_section_title, other_lines

ANCHORS = ("Table of Contents",)
MIN_ENTRIES = 40


def _chapter(text, toc):
    """Table of contents title matching `text` (one starts with the other), else None.
    At least 8 characters, so that an "Armor" cell is not taken for "Armor Charge", and a short
    title: an "Armor Charges are a resource…" paragraph is not the "Armor Charge" chapter."""
    head = first_line(text)
    if len(head) < 8 or not is_section_title(head):
        return None
    return next((t for t in toc if t.startswith(head) or head.startswith(t)), None)


def _words(text):
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= 4}


def _next_chapter(texts, toc, chapter):
    """NEXT table of contents title if it shares a word (≥ 4 letters) with the header:
    "Character Attributes" -> "Armor & Character Stats". Only the next one is a candidate, so
    that a subpart does not jump to a farther chapter that would share a word."""
    i = toc.index(chapter)
    words = set().union(*(_words(t) for t in texts))
    return next((t for t in toc[i + 1:i + 2] if _words(t) & words), None)


def _resolve_header(cells, toc, nav, chapter, after_blank):
    """(chapter, header) for a row of cells `cells`.
    chapter: table of contents title the row opens, else None. A single cell is compared
    directly to the table; a two-cell row only if it starts in the table's column (a
    "term | definition" row does not change chapter).
    header: label in the table's column + short title, after a blank row (chapter missing
    from the table, or subpart)."""
    texts = [t for _, t in cells]
    header = len(cells) == 2 and cells[0][0] == nav and after_blank and is_section_title(texts[1])
    title = None
    if len(cells) == 1 or (len(cells) == 2 and cells[0][0] == nav):
        title = next((c for c in (_chapter(t, toc) for t in texts) if c), None)
    if not title and header and chapter is not None:
        title = _next_chapter(texts, toc, chapter)
    return title, header


def _add_paragraph(entry, text):
    entry.text = f"{entry.text}\n\n{text}".strip()


def _cell(text):
    return text.replace("|", "\\|").replace("\n", "<br>")


class _Table:
    """Current table: columns (start, width) of its header row."""

    def __init__(self, grid, r, cells):
        self.cols = [(c, grid.span(r, c)[1]) for c, _ in cells]

    def accepts(self, grid, r, cells):
        """The row continues the table: its cells start on header columns, and either it
        starts on the first column, or no cell overflows onto the next one."""
        starts = [c for c, _ in self.cols]
        if len(cells) < 2 or any(c not in starts for c, _ in cells):
            return False
        if cells[0][0] == starts[0]:
            return True
        return not any(c < s < c + grid.span(r, c)[1] for c, _ in cells for s in starts)

    def row(self, cells):
        values = [""] * len(self.cols)
        for c, text in cells:
            i = max(i for i, (s, _) in enumerate(self.cols) if s <= c) if c >= self.cols[0][0] else 0
            values[i] = f"{values[i]} / {_cell(text)}" if values[i] else _cell(text)
        return "| " + " | ".join(values) + " |"


def _start_table(entry, grid, r, cells):
    table = _Table(grid, r, cells)
    header = table.row(cells) + "\n|" + "---|" * len(table.cols)
    entry.text = (entry.text + "\n\n" if entry.text else "") + header
    return table


def _side_by_side(grid, r, cells):
    """Two titles side by side with the same width ("Balanced Weapons Info | Dynamic Weapons Info"):
    header of a two-column table, not a term followed by its definition."""
    (c1, t1), (c2, t2) = cells
    return (grid.span(r, c1)[1] == grid.span(r, c2)[1] and is_section_title(t1) and is_section_title(t2)
            and not t2.endswith((".", ":", "!", "?")))


def _group(text):
    """Group subheading "Name | description" (activity modifiers), else None."""
    name, sep, rest = first_line(text).partition(" | ")
    return name.strip() if sep and 0 < len(name.strip()) <= 40 and rest.strip() else None


def parse(grid):
    toc_row = next(r for r in range(grid.height) if any(t == "Table of Contents" for _, t in grid.cells(r)))
    nav = next(c for c, t in grid.cells(toc_row) if t == "Table of Contents")  # labels column
    toc, r = [], toc_row + 1
    while r < grid.height and len(grid.cells(r)) == 1:
        toc.append(grid.cells(r)[0][1])
        r += 1
    entries, chapter, current, group, table = [], None, None, None, None
    blank_before = True

    def new(name, attrs=None, text=""):
        nonlocal current, table
        current, table = Entry(name, first_line(chapter), attrs or {}, text), None
        entries.append(current)
        return current

    def ensure_current():
        if current is None:
            new(first_line(chapter))
        return current

    for r in range(r, grid.height):
        cells = grid.cells(r)
        if not cells:
            blank_before = True
            continue
        after_blank, blank_before = blank_before, False
        texts = [t for _, t in cells]
        # Order of cases: chapter -> subpart (header) -> continuation of the current table ->
        # new table (≥ 3 cells, or two titles side by side) -> term | definition (or
        # paragraphs) -> group "Name | description" -> subheading -> paragraph.
        title, header = _resolve_header(cells, toc, nav, chapter, after_blank)
        if title:
            chapter, group = title, None
            label = first_line(texts[0])
            new(label)
            for t in texts[1:]:
                if not (t.startswith(label) or label.startswith(t)):  # "Armor Charges" / "Armor Charge"
                    _add_paragraph(current, t)
            continue
        if chapter is None:
            continue
        # Subparts and subheadings: their name becomes the "group" of the terms that follow
        # ("Armor Stats" -> Health, Melee…; "Combatant Banes" -> Caltrops, Cascade…).
        if header:
            label, heading = first_line(texts[0]), texts[1]
            if any(e.name == label and e.section == first_line(chapter) for e in entries):
                new(heading)
            else:
                new(label, text="" if heading == label else heading)
            group = current.name
            continue
        if table is not None and table.accepts(grid, r, cells):
            current.text += "\n" + table.row(cells)
        elif len(cells) >= 3:
            table = _start_table(ensure_current(), grid, r, cells)
        elif len(cells) == 2 and _side_by_side(grid, r, cells):
            table = _start_table(ensure_current(), grid, r, cells)
        elif len(cells) == 2:
            name = texts[0]
            if is_section_title(first_line(name)) and grid.span(r, cells[0][0])[1] <= grid.span(r, cells[1][0])[1]:
                attrs = {"detail": " · ".join(other_lines(name))} if other_lines(name) else {}
                if group:
                    attrs["group"] = group
                new(first_line(name), attrs, texts[1])
            else:
                ensure_current()
                for t in texts:
                    _add_paragraph(current, t)
                table = None
        elif _group(texts[0]):
            group = _group(texts[0])
            rest = first_line(texts[0]).partition(" | ")[2].strip()
            details = other_lines(texts[0])
            new(group, {"detail": " · ".join(details)} if details else {}, rest)
        elif is_section_title(texts[0]):
            group = texts[0]
            new(texts[0])
        else:
            _add_paragraph(ensure_current(), texts[0])
            table = None
    return [e for e in entries if e.text or e.attrs]
