"""An Aegis tab's grid -> Table: band, headers, one entry per row, legend (KEY block)."""
import re
from collections import Counter

from shell.sources.aegis.model import Table
from shell.sources.aegis.names import first_line
from shell.sources.sheets.errors import ParseError  # noqa: F401 (re-exported for callers)

IGNORED_HEADERS = {"🖼️", "🖼", "icon"}
KEY_BAND = "KEY"


def clean_header(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _header_row(grid, anchors):
    want = {a.lower() for a in anchors}
    for r in range(grid.height):
        if want <= {clean_header(t).lower() for _, t in grid.cells(r)}:
            return r
    return None


def _has_band(grid, hr):
    """The row above the headers is a band if one of its cells merges several columns
    (otherwise it is just a tab title)."""
    return hr > 0 and any(grid.span(hr - 1, c)[1] > 1 for c, _ in grid.cells(hr - 1))


def _columns(grid, hr):
    """([(column, name, band)] of the data, {legend columns})."""
    raw, legend = [], set()
    banded = _has_band(grid, hr)
    for c in range(grid.width):
        band = clean_header(grid.cell(hr - 1, c).text) if banded else ""
        head = clean_header(grid.text(hr, c))
        cell = grid.cell(hr, c)
        merged = clean_header(cell.text) if cell.top == hr and cell.left < c else ""
        if merged:
            # continuation of a header merged over several columns: "Explosion 2", not the band name
            head = f"{merged} {c - cell.left + 1}"
        if band.upper() == KEY_BAND:
            legend.add(c)
            continue
        if head.lower() in IGNORED_HEADERS or merged.lower() in IGNORED_HEADERS:
            continue
        raw.append([c, head or band or f"col{c}", band])
    counts = Counter(name for _, name, _ in raw)
    for col in raw:
        if counts[col[1]] > 1 and col[2]:
            col[1] = f"{col[1]} ({col[2]})"
    seen = Counter()
    for col in raw:
        seen[col[1]] += 1
        if seen[col[1]] > 1:
            col[1] = f"{col[1]} {seen[col[1]]}"
    return [tuple(col) for col in raw], legend


def parse_table(grid, spec):
    hr = _header_row(grid, spec.anchors)
    if hr is None:
        raise ParseError(spec.name, f"headers not found: {', '.join(spec.anchors)}")
    cols, legend_cols = _columns(grid, hr)
    names = [name for _, name, _ in cols]
    missing = [k for k in spec.key if k not in names]
    if missing:
        raise ParseError(spec.name, f"key column not found: {', '.join(missing)}")
    rows, legend, section = [], {}, ""
    for r in range(hr + 1, grid.height):
        key_values = [v for v in (grid.text(r, c) for c in sorted(legend_cols)) if v]
        if len(key_values) >= 2:
            legend.setdefault(key_values[0], " — ".join(key_values[1:]))
        filled = [(c, t) for c, t in grid.cells(r) if c not in legend_cols]  # the legend is not content
        if len(filled) == 1 and grid.span(r, filled[0][0])[1] > 1:
            section = first_line(filled[0][1])  # title merged over several columns
            continue
        values = {}
        for c, name, _ in cols:
            cell = grid.cell(r, c)
            if cell.left == c and cell.text:
                values[name] = cell.text
        parts = [first_line(values.get(k, "")) for k in spec.key]
        if not any(parts):
            continue
        if all(p.lower() == k.lower() for p, k in zip(parts, spec.key)):
            continue  # headers repeated further down the tab
        rows.append({"_name": " — ".join(p for p in parts if p), "_section": section, **values})
    if len(rows) < spec.min_rows:
        n = len(rows)
        raise ParseError(spec.name, f"{n} row{'s' if n > 1 else ''} found, at least {spec.min_rows} expected")
    used = [n for n in names if any(n in row for row in rows)]
    groups = {name: band for _, name, band in cols if name in used}
    return Table(spec.name, used, groups, rows, legend, grid.hidden_rows)
