"""Destiny Data Compendium (Google Sheets) converted to Markdown for the agent.

Output: cache/compendium/index.md + one .md per tab (raw HTML cached in cache/compendium/raw/).
A failing tab keeps its previous .md and is reported in `errors`; the other tabs are unaffected.
"""
import traceback
from datetime import date

from shell.sources import report, write_if_changed
from shell.sources.compendium.fetch import folder, sheet
from shell.sources.compendium.model import ParseError, TabResult
from shell.sources.compendium.parsers import TABS, is_ignored, run
from shell.sources.compendium.render import read_meta, render_index, render_tab
from shell.sources.sheets.grid import parse_grid

NAME = "compendium"


def _previous(tab, slug, path, ok, note):
    """Result of a tab not regenerated: what is already on disk."""
    if path.exists():
        when, count, hidden = read_meta(path.read_text(encoding="utf-8"))
        return TabResult(tab, slug, count, when, ok, hidden, note)
    return TabResult(tab, slug, 0, None, False, 0, note or "not fetched yet")


def refresh(force: bool = False, only: list[str] | None = None) -> dict:
    """`force` re-downloads the tab list and HTML (otherwise raw/ serves); `only` limits to these tabs.
    `changed` lists the tab .md files that changed; index.md is left out since it embeds the run date."""
    only = only or []
    out = folder()
    unknown = [t for t in only if t not in TABS]
    if unknown:
        return report(NAME, out, errors=[f"unknown tab: {', '.join(unknown)} (known: {', '.join(TABS)})"])

    today = date.today().isoformat()
    out.mkdir(parents=True, exist_ok=True)
    src = sheet()
    try:
        sheet_tabs = dict(src.list_tabs(force))
    except OSError as e:
        return report(NAME, out, errors=[f"tab list failed: {e}"])
    stale = ["tab list"] if src.tabs_stale else []
    errors = []  # sheet tabs we do not handle go to "unhandled": informational, like Aegis
    unhandled = [n for n in sheet_tabs if n not in TABS and not is_ignored(n)]

    results, changed = [], []
    for tab, (slug, module) in TABS.items():
        path = out / f"{slug}.md"
        if only and tab not in only:
            results.append(_previous(tab, slug, path, True, ""))
            continue
        try:
            if tab not in sheet_tabs:
                raise ParseError(tab, "tab missing from the Sheet")
            gid = sheet_tabs[tab]
            html, tab_stale = src.tab_html(gid, force)
            try:
                grid = parse_grid(html)
            except ValueError as e:
                raise ParseError(tab, f"unreadable HTML ({e})") from e
            entries = run(tab, module, grid)
            fetched = src.cache_date(gid) or today  # date of the HTML actually used
            if write_if_changed(path, render_tab(tab, entries, fetched, grid.hidden_rows)):
                changed.append(path.name)
            if tab_stale:
                stale.append(tab)
            results.append(TabResult(tab, slug, len(entries), fetched, True, grid.hidden_rows,
                                     "cache (network failed)" if tab_stale else ""))
        except (ParseError, OSError) as e:
            note = str(e) if isinstance(e, ParseError) else f"{tab}: network ({e})"
            errors.append(note)
            results.append(_previous(tab, slug, path, False, note))
        except Exception as e:  # a parser must never bring the other tabs down
            traceback.print_exc()
            note = f"{tab}: unexpected error ({e!r})"
            errors.append(note)
            results.append(_previous(tab, slug, path, False, note))

    write_if_changed(out / "index.md", render_index(results, src.url, today))
    return {**report(NAME, out, changed, stale, errors), "unhandled": unhandled}
