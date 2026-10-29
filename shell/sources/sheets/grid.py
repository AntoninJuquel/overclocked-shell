"""Public Google Sheets view HTML -> 2D grid, merged cells unfolded."""
import re
from dataclasses import dataclass
from html.parser import HTMLParser


@dataclass(frozen=True, eq=False)
class Cell:
    """One grid cell. Every cell of a merge shares the same Cell object,
    whose (top, left) is the merge origin (top-left)."""
    text: str
    top: int
    left: int


class Grid:
    def __init__(self, rows, hidden_rows=0):
        self.rows = rows                # list[list[Cell]], all the same width
        self.hidden_rows = hidden_rows  # rows hidden by the author (missing from the HTML)

    @property
    def height(self):
        return len(self.rows)

    @property
    def width(self):
        return len(self.rows[0]) if self.rows else 0

    def cell(self, r, c):
        if 0 <= r < self.height and 0 <= c < self.width:
            return self.rows[r][c]
        return Cell("", r, c)

    def is_origin(self, r, c):
        cell = self.cell(r, c)
        return cell.top == r and cell.left == c

    def text(self, r, c):
        """The cell text only when it is the origin of its merge, else ""."""
        return self.cell(r, c).text if self.is_origin(r, c) else ""

    def cells(self, r):
        """[(column, text)] of the non-empty origin cells of row r."""
        if not 0 <= r < self.height:
            return []
        return [(c, cell.text) for c, cell in enumerate(self.rows[r])
                if cell.text and cell.top == r and cell.left == c]

    def span(self, r, c):
        """(rows, columns) of the merge (r, c) belongs to.
        An out-of-grid cell returns a new Cell object, so the loops stop at the edge."""
        cell = self.cell(r, c)
        rows = cols = 0
        while self.cell(cell.top + rows, cell.left) is cell:
            rows += 1
        while self.cell(cell.top, cell.left + cols) is cell:
            cols += 1
        return max(rows, 1), max(cols, 1)


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []      # list[list[(raw text, rowspan, colspan)]]
        self.numbers = []   # sheet row number (id="<gid>R<n>") of each row, or None
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class") or ""
        if tag == "tr":
            self._row = []
            self.rows.append(self._row)
            self.numbers.append(None)
        elif tag == "th" and self._row is not None:
            if "freezebar" in cls:  # frozen-pane bar: not a sheet row
                self.rows.pop()
                self.numbers.pop()
                self._row = None
            else:
                m = re.search(r"R(\d+)$", a.get("id") or "")
                if m:
                    self.numbers[-1] = int(m.group(1))
        elif tag == "td" and self._row is not None and "freezebar" not in cls:
            self._cell = ([], int(a.get("rowspan") or 1), int(a.get("colspan") or 1))
        elif tag == "br" and self._cell is not None:
            self._cell[0].append("\n")

    def handle_endtag(self, tag):
        if tag == "td" and self._cell is not None:
            parts, rs, cs = self._cell
            self._row.append(("".join(parts), rs, cs))
            self._cell = None
        elif tag == "tr":
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell[0].append(data)


def _clean(text):
    lines = [re.sub(r"[ \t\xa0]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def parse_grid(html):
    p = _TableParser()
    p.feed(html)
    taken = {}  # (row, column) -> Cell
    for r, raw in enumerate(p.rows):
        c = 0
        for text, rs, cs in raw:
            while (r, c) in taken:  # cell already covered by a merge from above
                c += 1
            cell = Cell(_clean(text), r, c)
            for dr in range(rs):
                for dc in range(cs):
                    if (r + dr, c + dc) in taken:
                        raise ValueError(f"overlapping merges at row {r + dr}, column {c + dc}")
                    taken[(r + dr, c + dc)] = cell
            c += cs
    height = len(p.rows)
    width = max((c + 1 for (r, c) in taken if r < height), default=0)
    rows = [[taken.get((r, c)) or Cell("", r, c) for c in range(width)] for r in range(height)]
    nums = [n for n in p.numbers if n is not None]
    hidden = (nums[0] if nums else 0) + sum(b - a - 1 for a, b in zip(nums, nums[1:]) if b > a + 1)
    return Grid(rows, hidden)
