"""Helpers shared by the tab parsers."""

from ..model import Entry


def first_line(text):
    return text.split("\n", 1)[0].strip()


def other_lines(text):
    """Non-empty lines after the first."""
    return [line.strip() for line in text.split("\n")[1:] if line.strip()]


def banner(grid, r):
    """Text of a banner row: a single non-empty cell, at least half the grid wide."""
    cells = grid.cells(r)
    if len(cells) == 1:
        c, text = cells[0]
        w = grid.span(r, c)[1]
        if w * 2 >= grid.width and all(
                grid.cell(r, k).text == "" for k in range(grid.width) if not c <= k < c + w):
            return text
    return None


def find_row(grid, labels, start=0):
    """First row (>= start) whose origin cells start with `labels`."""
    labels = list(labels)
    for r in range(start, grid.height):
        if [t for _, t in grid.cells(r)][:len(labels)] == labels:
            return r
    raise ValueError(f"row not found: {labels}")


def is_section_title(text):
    """A real section title (short, one line) as opposed to an author's note."""
    return len(text) <= 60 and "\n" not in text


class Notes:
    """A single "Notes" entry per section, created at the first note, texts separated by a blank line."""

    def __init__(self, entries):
        self.entries = entries
        self.by_section = {}

    def add(self, section, text):
        if section in self.by_section:
            self.by_section[section].text += "\n\n" + text
        else:
            entry = Entry("Notes", section, {}, text)
            self.by_section[section] = entry
            self.entries.append(entry)
