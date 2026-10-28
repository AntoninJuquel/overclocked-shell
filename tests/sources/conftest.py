import html

import pytest


def sheet_html(rows, gid="0", hidden=()):
    """HTML shaped like the public Google Sheets view (htmlview/sheet).

    rows   : list of rows; a cell is a text or a tuple (text, rowspan, colspan).
             A cell covered by a merge from a row above must not be listed (Google emits no <td> for it);
             a fully covered row is an empty list.
    hidden : sheet row numbers missing from the HTML (rows hidden by the author).
    A "freezebar" row is inserted after the first row, as in the real HTML.
    """
    out = ['<table class="waffle" cellspacing="0" cellpadding="0"><tbody>']
    n = 0
    for i, row in enumerate(rows):
        while n in hidden:
            n += 1
        out.append(f'<tr style="height: 20px"><th id="{gid}R{n}" class="row-headers-background">'
                   f'<div>{n + 1}</div></th>')
        for cell in row:
            text, rs, cs = (cell, 1, 1) if isinstance(cell, str) else cell
            attrs = (f' rowspan="{rs}"' if rs > 1 else "") + (f' colspan="{cs}"' if cs > 1 else "")
            out.append(f'<td class="s0"{attrs}>{html.escape(text).replace(chr(10), "<br>")}</td>')
        out.append("</tr>")
        if i == 0:
            out.append('<tr><th style="height:3px;" class="freezebar-cell freezebar-horizontal-handle"></th>'
                       '<td class="freezebar-cell"></td></tr>')
        n += 1
    out.append("</tbody></table>")
    return "".join(out)


@pytest.fixture
def sheet():
    """sheet(rows, **kw) -> Grid, from rows described as for sheet_html."""
    from shell.sources.sheets.grid import parse_grid
    return lambda rows, **kw: parse_grid(sheet_html(rows, **kw))


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Sources never read or write the real cache/ or profile/."""
    from shell.core import paths
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(paths, "profile_dir", lambda: tmp_path / "profile")
    return tmp_path
