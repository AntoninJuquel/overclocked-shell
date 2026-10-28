"""Entries -> Markdown: one file per tab, and the index."""
import re


def _escape(text):
    """Keeps a description line from passing for a Markdown heading."""
    return re.sub(r"^( {0,3})(#|[-=]+\s*$)", r"\1\\\2", text, flags=re.M)


def _oneline(value):
    return re.sub(r"\s*\n\s*", " / ", str(value))


def render_tab(tab, entries, fetched, hidden_rows=0):
    lines = [f"# {tab}", "", f'Source: Destiny Data Compendium, tab "{tab}", fetched on {fetched}.']
    if hidden_rows:
        lines.append(f"Rows hidden by the author (missing from this version): {hidden_rows}.")
    lines.append("")
    order = list(dict.fromkeys(e.section for e in entries))  # sections in order of appearance
    for section in order:
        lines += [f"## {section}", ""]
        for e in (e for e in entries if e.section == section):
            lines.append(f"### {e.name}")
            attrs = {"section": e.section, **e.attrs}
            lines += [f"- {k}: {_oneline(v)}" for k, v in attrs.items()]
            lines.append("")
            if e.text:
                lines += [_escape(e.text), ""]
    return "\n".join(lines).rstrip("\n") + "\n"


def read_meta(md):
    """(date, entry count, hidden rows) of an already written .md."""
    date = re.search(r"^Source: .*fetched on (\d{4}-\d{2}-\d{2})", md, flags=re.M)
    hidden = re.search(r"^Rows hidden by the author \(missing from this version\): (\d+)", md, flags=re.M)
    count = len(re.findall(r"^### ", md, flags=re.M))
    return (date.group(1) if date else None), count, (int(hidden.group(1)) if hidden else 0)


def _status(r):
    if r.ok:
        parts = ["ok"]
        if r.hidden_rows:
            parts.append(f"{r.hidden_rows} hidden row" if r.hidden_rows == 1 else f"{r.hidden_rows} hidden rows")
        if r.note:
            parts.append(r.note)
        return " · ".join(parts)
    return f"⚠ {r.note} — " + (f"data from {r.date}" if r.date else "no data")


def render_index(results, source, now):
    oldest = min((r.date for r in results if r.date), default="none")
    lines = [
        "# Destiny Data Compendium (Markdown)",
        "",
        f"Source: {source}",
        f"Last run: {now}",
        f"Oldest data: {oldest}",
        "",
        "Compendium conventions, kept as is:",
        "- `X [Y]`: usually PvE value [PvP value]; `{Z}`: third variant when the tab says so.",
        "- `↑`: value of the enhanced version; `?`: value not confirmed by the author.",
        "- Hidden rows: the author hides some rows, missing from the public view and so from here.",
        "",
        "Find an entry: `grep -n -e \"^## \" -e \"^### <name>\" cache/compendium/<file>.md`, then read only its section.",
        "The same name can appear in several sections (artifacts, classes, variants) and can also repeat within one section "
        "(e.g. \"Aggressive Frame\" ×5, told apart by `detail`): check `section` and the other attributes.",
        "",
        "| Tab | File | Entries | Status |",
        "|---|---|---|---|",
    ]
    for r in results:
        file = f"[{r.slug}.md]({r.slug}.md)" if r.date else f"{r.slug}.md"
        lines.append(f"| {r.tab} | {file} | {r.entries} | {_status(r)} |")
    return "\n".join(lines) + "\n"
