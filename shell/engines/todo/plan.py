"""Dated TODO: build needs × sources × the week's context, ranked by priority.

Reads profile/todo/needs.json, state.json, sources.json and the newest profile/todo/week/<date>.json, writes
profile/todo/<date>.json and .md (<date>-<build>.* for a single build). Aegis Shopping List needs have the build
`aegis`.
"""
import json
import re
from pathlib import Path

from shell.engines import distortions
from shell.engines.todo import shopping, sources, state as state_mod, week
from shell.sources import distortions as distortions_source

SECTIONS = ("This week", "When you can", "Later")
SECTION_BY_AVAILABILITY = {sources.AVAILABILITY["boosted"]: SECTIONS[0], sources.AVAILABILITY["known"]: SECTIONS[1],
                           sources.AVAILABILITY["unknown"]: SECTIONS[2]}
# Variant of one activity ("Salvation's Edge: Master", "Astral Alignment: Matchmade"…).
VARIANT = re.compile(r": (?:Customize|Matchmade|Normal|Master|Standard)$")


def group_name(name):
    """Activity name without its variant: "Salvation's Edge: Standard" → "Salvation's Edge"."""
    return VARIANT.sub("", name or "")


def load_context(week_dir, now):
    """(context, warnings): the newest <week_dir>/<date>.json (week_dir None = profile/todo/week), or None if
    missing or its week has ended."""
    week_dir = Path(week_dir) if week_dir is not None else week.folder()
    files = sorted(week_dir.glob("????-??-??.json"))
    if not files:
        return None, ["week context unavailable: call refresh_context then week_context"]
    ctx = json.loads(files[-1].read_text(encoding="utf-8"))
    end = (ctx.get("reset") or {}).get("end")
    if not end or week.parse_time(end) <= now:
        return None, [f"week context from {files[-1].stem} is out of date (week ended): call refresh_context "
                      "then week_context"]
    return ctx, list(ctx.get("warnings", []))


def _context_summary(ctx):
    """Week banner: reset end, focused / bonus activities (variants grouped), notes."""
    if not ctx:
        return None
    acts = ctx.get("activities", [])
    names = lambda boost: list(dict.fromkeys(group_name(a.get("name")) for a in acts
                                             if boost in a.get("boosts", [])))
    return {"end": ctx["reset"]["end"], "focus": names("focus"), "bonus": names("bonus"),
            "notes": [n["text"] for n in ctx.get("notes", [])]}


def _annotate_masterworks(entries):
    """A masterwork is useless if an armor need of the same build targets the same slot."""
    armor = [e for e in entries if e["kind"] == "armor"]
    for e in entries:
        if e["kind"] != "masterwork":
            continue
        builds = {b["build"] for b in e["builds"]}
        hit = next((a for a in armor if a["target"]["slot"] == e["target"]["slot"]
                    and builds & {b["build"] for b in a["builds"]}), None)
        if hit:
            e["note"] = f"useless if you replace the piece with: {hit['label']}"


def build_plan(needs_doc, state, ctx, index, manual, today, build=None):
    """TODO entries (status todo only), sorted by section then decreasing priority.
    `build`: keep only that build's needs (and count only its gain and hidden entries)."""
    entries, hidden = [], {"done": 0, "ignored": 0}
    for n in needs_doc.get("needs", []):
        builds = [b for b in n["builds"] if build is None or b["build"] == build]
        if not builds:
            continue
        status = state.get(n["id"], {}).get("status", "todo")
        if status in hidden:
            hidden[status] += 1
            continue
        permanent = sources.permanent_sources(n, index, manual)
        found = sources.dated_sources(n, ctx, permanent) + permanent
        avail = sources.availability(found)
        score = sum(b["gain"]["score"] for b in builds)
        entries.append({**n, "builds": builds, "sources": found, "availability": avail,
                        "priority": round(score * avail, 4), "section": SECTION_BY_AVAILABILITY[avail]})
    _annotate_masterworks(entries)
    entries.sort(key=lambda e: (SECTIONS.index(e["section"]), -e["priority"], e["id"]))
    return {"date": today, "build": build, "reset": ctx["reset"] if ctx else None, "context": _context_summary(ctx),
            "entries": entries, "hidden": hidden, "warnings": []}


def _num(value):
    """Three significant figures: 0.007 · 0.15 · 0.098."""
    return f"{value:.3g}"


def _names(names, limit=5):
    return ", ".join(names[:limit]) + (f" (+{len(names) - limit})" if len(names) > limit else "")


def format_source(s):
    """One source on one line: "name (boost, until …)", "raid (raid)", "vendor (on sale until … · cost)";
    zero costs are left out."""
    until = f"until {s['until'][:10]}" if s.get("until") else None
    if s["type"] == "vendor":
        costs = " + ".join(f"{c['quantity']} {c['name']}" for c in s.get("costs", []) if c.get("quantity"))
        inner = " · ".join(x for x in ("on sale" + (f" {until}" if until else ""), costs) if x)
        return f"{s['name']} ({inner})"
    kind = s.get("kind") if s["type"] == "activity" and s.get("kind") in ("raid", "dungeon") else None
    extra = [x for x in (kind, s.get("boost"), until) if x]
    return s["name"] + (f" ({', '.join(extra)})" if extra else "")


def display_sources(found):
    """Sources to show: the week's activities (with `boost`) are grouped by name without variant, boost and date;
    a permanent activity is left out when a week activity of the same name exists."""
    dated = {group_name(s["name"]).lower() for s in found if s["type"] == "activity" and "boost" in s}
    out, seen = [], set()
    for s in found:
        if s["type"] == "activity":
            name = group_name(s["name"])
            if "boost" in s:
                key = (name.lower(), s.get("boost"), s.get("until"))
                if key in seen:
                    continue
                seen.add(key)
                s = {**s, "name": name}
            elif name.lower() in dated:
                continue
        out.append(s)
    return out


def render_md(doc):
    title = f"# TODO for {doc['date']}" + (f" — {doc['build']}" if doc.get("build") else "")
    lines = [title, ""]
    c = doc["context"]
    if c:
        parts = [f"Week until {c['end'][:10]} {c['end'][11:16]} UTC"]
        parts += [f"{label}: {_names(c[key])}" for key, label in (("focus", "Focus"), ("bonus", "Bonus")) if c[key]]
        lines.append(" · ".join(parts))
        lines += [f"- Note: {n}" for n in c["notes"]]
    lines += [f"> {w}" for w in doc["warnings"]]
    for section in SECTIONS:
        entries = [e for e in doc["entries"] if e["section"] == section]
        if not entries:
            continue
        lines += ["", f"## {section}", ""]
        for i, e in enumerate(entries, 1):
            lines.append(f"{i}. **{e['label']}** · priority {_num(e['priority'])}")
            for b in e["builds"]:
                g = b["gain"]
                parts = [" · ".join(f"{k} {v:+d}" for k, v in g["stats"].items())] + list(g["effects"])
                detail = "; ".join(x for x in parts if x)
                who = shopping.LABEL if b["build"] == shopping.BUILD else b["build"]
                lines.append(f"   For: {who}" + (f" ({detail})" if detail else ""))
            if e["sources"]:
                lines.append("   Where: " + "; ".join(format_source(s) for s in display_sources(e["sources"])))
            else:
                lines.append(f"   Where: unknown source, add it to profile/todo/sources.json (key \"{e['id']}\")")
            if e.get("distorted"):
                lines.append(f"   Distorted: {e['distorted']}")
            if e.get("note"):
                lines.append(f"   Note: {e['note']}")
    h = doc["hidden"]
    lines += ["", f"_Ignored: {h['ignored']} · Done: {h['done']}_", ""]
    return "\n".join(lines)


def summary(doc, top=10):
    """First entries on one line each: section · label · priority · best source."""
    out = []
    for e in doc["entries"][:top]:
        shown = display_sources(e["sources"])
        best = next((s for s in shown if s.get("boost") in sources.BOOSTED), shown[0] if shown else None)
        out.append(" · ".join([e["section"], e["label"], _num(e["priority"]),
                               format_source(best) if best else "unknown source"]))
    return out


def file_stem(doc):
    """File name of the TODO: <date>, or <date>-<build> for a filtered TODO."""
    return doc["date"] + (f"-{doc['build']}" if doc.get("build") else "")


NO_ROTATION = 'no Distortion rotation cached: refresh_references(source="distortions") to see farming times'


def _add_distortions(doc, now):
    """Each entry with a destination among its sources gets `distorted`: its next Distorted window."""
    rot = distortions_source.load()
    if rot is None:   # destinations are only known from the rotation itself: warn whenever there is a TODO
        if doc["entries"]:
            doc["warnings"].append(NO_ROTATION)
        return
    for e in doc["entries"]:
        line = distortions.todo_line(rot, [s["name"] for s in e["sources"]], now)
        if line:
            e["distorted"] = line
    stale = distortions.stale_warning(rot, now)
    if stale and any("distorted" in e for e in doc["entries"]):
        doc["warnings"].append(stale)


def run(todo_dir, week_dir, index, manual, now, build=None):
    """Computes today's TODO and writes it to <todo_dir>/<date>.json and .md (<date>-<build>.* with `build`, so the
    full TODO is not overwritten)."""
    todo_dir = Path(todo_dir)
    needs_path = todo_dir / "needs.json"
    if not needs_path.exists():
        raise ValueError("No needs.json. Call farm_needs first.")
    needs_doc = json.loads(needs_path.read_text(encoding="utf-8"))
    ctx, warnings = load_context(week_dir, now)
    doc = build_plan(needs_doc, state_mod.load(todo_dir / "state.json"), ctx, index, manual,
                     now.date().isoformat(), build)
    doc["warnings"] = warnings + list(needs_doc.get("warnings", []))
    _add_distortions(doc, now)
    state_mod.write_json(todo_dir / f"{file_stem(doc)}.json", doc)
    (todo_dir / f"{file_stem(doc)}.md").write_text(render_md(doc), encoding="utf-8")
    return doc
