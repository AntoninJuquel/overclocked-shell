import pytest
from tests.sources.conftest import sheet_html
from shell.sources.sheets.grid import parse_grid


def test_colspan_and_rowspan_are_unfolded(sheet):
    g = sheet([
        [("Title", 1, 3)],
        ["Nom", ("Text over two rows", 2, 1), "x"],
        ["Next", "y"],
    ])
    assert g.width == 3 and g.height == 3
    assert [g.cell(0, c).text for c in range(3)] == ["Title"] * 3
    assert g.cells(0) == [(0, "Title")]                 # only the merge origin counts
    assert g.text(2, 1) == ""                           # covered cell: not an origin
    assert g.cell(2, 1).text == "Text over two rows"  # but its text is still readable
    assert g.cells(2) == [(0, "Next"), (2, "y")]       # "y" lands in column 2
    assert g.span(1, 1) == (2, 1)
    assert g.span(0, 0) == (1, 3)


def test_fully_covered_row_is_kept(sheet):
    g = sheet([
        [("A", 2, 1), ("B", 2, 1)],
        [],
        ["C", "D"],
    ])
    assert g.height == 3
    assert g.cells(1) == []
    assert g.cells(2) == [(0, "C"), (1, "D")]


def test_line_breaks_and_spaces(sheet):
    g = sheet([["  Ligne 1 \n\n\n\nLigne\u00a0  2  "]])
    assert g.text(0, 0) == "Ligne 1\n\nLigne 2"


def test_freezebar_row_is_ignored(sheet):
    g = sheet([["top"], ["bottom"]])
    assert [g.text(r, 0) for r in range(g.height)] == ["top", "bottom"]


def test_hidden_rows_are_counted():
    g = parse_grid(sheet_html([["a"], ["b"], ["c"]], gid="42", hidden={1, 2, 5}))
    # emitted numbers 0, 3, 4 -> a 2-row gap (1, 2); row 5 is past the end
    assert g.hidden_rows == 2


def test_out_of_range_cell_is_empty(sheet):
    g = sheet([["a"]])
    assert g.cell(5, 5).text == "" and g.text(-1, 0) == ""


def test_hidden_rows_at_the_top_are_counted():
    g = parse_grid(sheet_html([["a"], ["b"]], gid="7", hidden={0, 1}))
    assert g.hidden_rows == 2


def test_rowspan_past_the_last_row_is_clipped(sheet):
    g = sheet([[("a", 5, 1), "b"]])
    assert g.height == 1
    assert g.span(0, 0) == (1, 1)


def test_colspan_after_cell_covered_from_above(sheet):
    g = sheet([[("A", 2, 1), "B", "C"], [("D", 1, 2)]])
    assert g.cells(1) == [(1, "D")]
    assert g.span(1, 1) == (1, 2)


def test_overlapping_merges_raise():
    with pytest.raises(ValueError):
        parse_grid(sheet_html([["A", ("B", 2, 1)], [("X", 1, 2)]]))
