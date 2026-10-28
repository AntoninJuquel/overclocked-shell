"""Changes of an Aegis tab from one version to the next, and the build sheets they concern."""
import json
import re
from collections import Counter
from pathlib import Path

from shell.sources.aegis.names import norm, strip_set


def _index(rows):
    out, seen = {}, Counter()
    for r in rows:
        k = norm(r["_name"])
        out[(k, seen[k])] = r
        seen[k] += 1
    return out


def changes(old_rows, new_rows, tier="Tier", rank=None):
    """[{name, kind, col, old, new}]: tier or rank changed, row added or removed. Rows are matched
    by normalized name, then by order of appearance (several versions of the same name)."""
    old, new = _index(old_rows), _index(new_rows)
    out = []
    for k, r in new.items():
        if k not in old:
            out.append({"name": r["_name"], "kind": "added", "col": tier, "old": None,
                        "new": r.get(tier) if tier else None})
            continue
        for kind, col in (("tier", tier), ("rank", rank)):
            if col and (old[k].get(col) or "") != (r.get(col) or ""):
                out.append({"name": r["_name"], "kind": kind, "col": col, "old": old[k].get(col), "new": r.get(col)})
    out += [{"name": r["_name"], "kind": "removed", "col": tier, "old": r.get(tier) if tier else None, "new": None}
            for k, r in old.items() if k not in new]
    return out


def build_names(builds_dir):
    """{slug: (normalized exact names, normalized `wanted` texts)} of the readable builds/*.json sheets."""
    out = {}
    for path in sorted(Path(builds_dir).glob("*.json")):
        try:
            s = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(s, dict):
            continue
        intent, sub, res = s.get("intent") or {}, s.get("subclass") or {}, s.get("resolved") or {}
        names = [(intent.get("exotic") or {}).get("name"), *(sub.get("aspects") or []), *(sub.get("fragments") or []),
                 *(x.get("set") for x in intent.get("sets") or []),
                 *((intent.get("artifact") or {}).get("perks") or []),
                 *(w.get("name") for w in res.get("weapons") or [])]
        wanted = [norm(w["wanted"]) for w in intent.get("weapons") or [] if w.get("wanted")]
        out[path.stem] = ({strip_set(norm(n)) for n in names if n}, wanted)
    return out


def concerned(name, names):
    """Slugs of the sheets that use this name (exact, or whole word in a `wanted`)."""
    key = strip_set(norm(name))
    pattern = re.compile(rf"(?<![\w']){re.escape(key)}(?![\w'])")
    return [slug for slug, (exact, wanted) in names.items()
            if key in exact or any(pattern.search(w) for w in wanted)]


def describe(e):
    """"Tier A → S", "new (Tier B)", "removed (was Tier C)"."""
    if e["kind"] == "added":
        return "new" + (f" ({e['col']} {e['new']})" if e["new"] else "")
    if e["kind"] == "removed":
        return "removed" + (f" (was {e['col']} {e['old']})" if e["old"] else "")
    if e["kind"] == "rank":
        return " → ".join(f"#{v}" if v else "—" for v in (e["old"], e["new"]))
    return f"{e['col']} {e['old'] or '—'} → {e['new'] or '—'}"


def render_changes(entries, today):
    lines = [f"# Aegis changes on {today}", ""]
    if not entries:
        return "\n".join(lines + ["No changes.", ""])
    lines += ["## Builds concerned", ""]
    hits = [(slug, e) for e in entries for slug in e["builds"]]
    lines += [f"- {slug}: {e['tab']} — {e['name']}: {describe(e)}" for slug, e in sorted(hits, key=lambda h: h[0])]
    if not hits:
        lines.append("None.")
    lines += ["", "## All changes"]
    for group in dict.fromkeys((e["sheet"], e["tab"]) for e in entries):
        lines += ["", f"### {group[0]} — {group[1]}", ""]
        lines += [f"- {e['name']}: {describe(e)}" for e in entries if (e["sheet"], e["tab"]) == group]
    return "\n".join(lines) + "\n"
