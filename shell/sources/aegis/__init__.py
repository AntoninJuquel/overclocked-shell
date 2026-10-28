"""Aegis's spreadsheets (Endgame Analysis, Boss Damage) as Markdown and JSON in cache/aegis/.

Outputs: cache/aegis/index.md, cache/aegis/<sheet>/<slug>.md and .json, cache/aegis/changes.md (tier and rank
changes since the previous version, and the profile/builds/ sheets they concern). Raw HTML: cache/aegis/raw/<sheet>/.
"""
import json
import traceback
from datetime import date

from shell.core import paths
from shell.sources import report, write_if_changed
from shell.sources.aegis import diff, lookup, render
from shell.sources.aegis.config import SHEETS
from shell.sources.aegis.model import TabResult
from shell.sources.aegis.names import first_line
from shell.sources.aegis.table import ParseError, parse_table
from shell.sources.sheets.fetch import SheetSource
from shell.sources.sheets.grid import parse_grid

NAME = "aegis"


def _previous(sheet, spec, ok, note):
    fetched, updated, n, hidden = render.load_meta(lookup.data_dir() / sheet.key / f"{spec.slug}.json")
    if fetched is None:
        return TabResult(sheet.title, sheet.key, spec.name, spec.slug, 0, None, None, False,
                         0, note or "not fetched yet")
    return TabResult(sheet.title, sheet.key, spec.name, spec.slug, n, fetched, updated, ok, hidden, note)


def _load_rows(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))["rows"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _process(sheet, spec, src, gid, refresh, updated, today, names, changes):
    """Parses and writes one tab; appends its changes to `changes`. Returns (TabResult, table)."""
    if gid is None:
        raise ParseError(spec.name, "tab missing from the Sheet")
    html, stale = src.tab_html(gid, refresh)
    try:
        grid = parse_grid(html)
    except ValueError as e:
        raise ParseError(spec.name, f"unreadable HTML ({e})") from e
    table = parse_table(grid, spec)
    fetched = src.cache_date(gid) or today
    out = lookup.data_dir() / sheet.key
    json_path = out / f"{spec.slug}.json"
    if updated is None:  # Status tab unreadable this time: keep the previous version's date
        upd = render.load_meta(json_path)[1]
    else:
        upd = updated.get(spec.name.lower())
    doc = render.to_json(table, sheet.key, upd, fetched)
    old = _load_rows(json_path)
    if old is not None and spec.slug != "status":  # rows added / removed from Status: noise
        for c in diff.changes(old, doc["rows"], spec.tier, spec.rank):
            changes.append({**c, "sheet": sheet.title, "tab": spec.name, "builds": diff.concerned(c["name"], names)})
    write_if_changed(out / f"{spec.slug}.md", render.render_tab(table, sheet.title, upd, fetched))
    write_if_changed(json_path, json.dumps(doc, ensure_ascii=False, indent=1))
    return TabResult(sheet.title, sheet.key, spec.name, spec.slug, len(table.rows), fetched, upd, True,
                     table.hidden_rows, "cache (network failed)" if stale else ""), table


def refresh(force: bool = False, only: list[str] | None = None, sheet: str | None = None) -> dict:
    """only: tab names (config names); sheet: "endgame" or "boss". The Status tab is always processed.
    Result also carries `unhandled`: Sheet tabs neither configured nor ignored."""
    out = lookup.data_dir()
    only = only or []
    known = {t.name for s in SHEETS.values() for t in s.tabs}
    unknown = [t for t in only if t not in known]
    if unknown:
        return report(NAME, out, errors=[f"unknown tab: {', '.join(unknown)} (known: {', '.join(sorted(known))})"])
    if sheet is not None and sheet not in SHEETS:
        return report(NAME, out, errors=[f"unknown sheet: {sheet} (known: {', '.join(sorted(SHEETS))})"])

    today = date.today().isoformat()
    names = diff.build_names(paths.profile_dir() / "builds")
    results, changes, stale, errors, unhandled = [], [], [], [], []
    for s in SHEETS.values():
        if sheet not in (None, s.key):
            results += [_previous(s, spec, True, "") for spec in s.tabs]
            continue
        src = SheetSource(s.id, out / "raw" / s.key)
        try:
            tabs = src.list_tabs(force)
        except OSError as e:
            errors.append(f"tab list ({s.title}): {e}")
            results += [_previous(s, spec, False, f"{spec.name}: network ({e})") for spec in s.tabs]
            continue
        if src.tabs_stale:
            stale.append(f"{s.title}: tab list")
        unhandled += [f"{s.title}: {n}" for n, _ in tabs if s.spec_for(n) is None and not s.is_ignored(n)]
        updated = None  # {tab: date} once the Status tab is read
        for spec in s.tabs:
            if only and spec.name not in only and spec.slug != "status":
                results.append(_previous(s, spec, True, ""))
                continue
            gid = next((g for n, g in tabs if spec.matches(n)), None)
            try:
                result, table = _process(s, spec, src, gid, force, updated, today, names, changes)
                if spec.slug == "status":
                    updated = {first_line(r["_name"]).lower(): r.get("UPDATED") for r in table.rows}
                if result.note:
                    stale.append(f"{s.title}: {spec.name}")
                results.append(result)
            except (ParseError, OSError) as e:
                note = str(e) if isinstance(e, ParseError) else f"{spec.name}: network ({e})"
                errors.append(f"{s.title}: {note}")
                results.append(_previous(s, spec, False, note))
            except Exception as e:  # one tab must never bring down the others
                traceback.print_exc()
                note = f"{spec.name}: unexpected error ({e!r})"
                errors.append(f"{s.title}: {note}")
                results.append(_previous(s, spec, False, note))

    write_if_changed(out / "index.md", render.render_index(results, today))
    if changes or not (out / "changes.md").exists():  # a no-change run must not erase changes not read yet
        write_if_changed(out / "changes.md", diff.render_changes(changes, today))
    changed = []
    for e in changes:
        line = f"{e['tab']} — {e['name']}: {diff.describe(e)}"
        changed += [f"{slug}: {line}" for slug in e["builds"]] or [line]
    return {**report(NAME, out, changed, stale, errors), "unhandled": unhandled}
