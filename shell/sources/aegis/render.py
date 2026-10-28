"""Table -> .json (scripts) and .md (agent, same format as the compendium); index.md."""
import json
import re

from shell.sources.aegis.config import SHEETS


def _oneline(value):
    return re.sub(r"\s*\n\s*", " / ", str(value))


def to_json(table, sheet_key, updated, fetched):
    return {"sheet": sheet_key, "tab": table.tab, "updated": updated, "fetched": fetched,
            "hidden_rows": table.hidden_rows, "columns": table.columns, "groups": table.groups,
            "legend": table.legend, "rows": table.rows}


def load_meta(path):
    """(fetched on, updated on, rows, hidden rows) of an already written .json; (None, None, 0, 0) otherwise."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc.get("fetched"), doc.get("updated"), len(doc.get("rows", [])), doc.get("hidden_rows", 0)
    except (OSError, ValueError, AttributeError):
        return None, None, 0, 0


def render_tab(table, sheet_title, updated, fetched):
    when = (f"updated by Aegis on {updated}, " if updated else "") + f"fetched on {fetched}."
    lines = [f"# {table.tab}", "", f'Source: Aegis — {sheet_title}, tab "{table.tab}", {when}']
    if table.hidden_rows:
        lines.append(f"Rows hidden by the author (missing from this version): {table.hidden_rows}.")
    lines.append("")
    if table.legend:
        lines += ["## Legend", ""] + [f"- {k}: {_oneline(v)}" for k, v in table.legend.items()] + [""]
    for section in dict.fromkeys(r["_section"] for r in table.rows):
        lines += [f"## {section or table.tab}", ""]
        for row in (r for r in table.rows if r["_section"] == section):
            lines.append(f"### {_oneline(row['_name'])}")
            lines += [f"- {c}: {_oneline(row[c])}" for c in table.columns if row.get(c)]
            lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def _status(r):
    if r.ok:
        parts = ["ok"]
        if r.hidden_rows:
            parts.append(f"{r.hidden_rows} hidden row" if r.hidden_rows == 1 else f"{r.hidden_rows} hidden rows")
        if r.note:
            parts.append(r.note)
        return " · ".join(parts)
    return f"⚠ {r.note} — " + (f"data from {r.fetched}" if r.fetched else "no data")


def render_index(results, now):
    oldest = min((r.fetched for r in results if r.fetched), default="none")
    lines = ["# Aegis spreadsheets (Markdown)", "", "Sources:"]
    lines += [f"- {s.title}: https://docs.google.com/spreadsheets/d/{s.id}" for s in SHEETS.values()]
    lines += [
        "",
        f"Last run: {now}",
        f"Oldest data: {oldest}",
        "",
        "Aegis's ratings (endgame PvE): tiers, ranks, measured DPS, recommended perks, farming priorities. "
        "Exact game values come from the compendium (cache/compendium/).",
        "Tiers: S (best) > A > B > C > D > E > F; `#`: rank within the tab. A tab's own legend: "
        "the \"Legend\" section of its file.",
        "",
        "Find an entry: `grep -n -e \"^## \" -e \"^### <name>\" cache/aegis/<folder>/<file>.md`, then read "
        "only its section. A name can repeat (weapon versions, firing modes): compare the attributes.",
        "",
        "| Spreadsheet | Tab | File | Rows | Updated by Aegis | Fetched | Status |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        rel = f"{r.sheet_key}/{r.slug}.md"
        file = f"[{rel}]({rel})" if r.fetched else rel
        lines.append(f"| {r.sheet} | {r.tab} | {file} | {r.rows} | {r.updated or '—'} | {r.fetched or '—'} | {_status(r)} |")
    return "\n".join(lines) + "\n"
