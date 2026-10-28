"""The live raid page for the player's second monitor: map first, then their role's steps for the phase, the
whole fireteam's split, what the guides don't place or disagree on, and the guides' dates. Reloads itself."""
from html import escape
from pathlib import Path

from shell.outputs import raid_map

REFRESH_SECONDS = 3
STYLE = """
:root { --bg: #0f1318; --panel: #1a212b; --line: #33414f; --text: #d8e0e8; --muted: #8a99a8; --accent: #3fb27f;
        --spot: #5a8fd8; --warn: #e0a83a; }
body { background: var(--bg); color: var(--text); font: 15px/1.45 system-ui, sans-serif; margin: 16px; }
h1 { font-size: 20px; margin: 0 0 4px; } h2 { font-size: 16px; margin: 18px 0 6px; } .muted { color: var(--muted); }
.maps { display: flex; flex-wrap: wrap; gap: 12px; } .maps svg { flex: 1 1 380px; max-width: 640px; }
svg .area { fill: var(--panel); stroke: var(--line); } svg .room { fill: none; stroke: var(--line); }
svg text { fill: var(--muted); font: 11px system-ui, sans-serif; } svg .floor { fill: var(--text); font-weight: 600; }
svg .spot circle { fill: var(--spot); } svg .spot text { fill: var(--text); }
svg .hl circle { fill: var(--accent); } svg .hl text { fill: var(--accent); font-weight: 600; }
svg .note { font-size: 9px; } ol.steps li { margin: 4px 0; font-size: 17px; }
table { border-collapse: collapse; } td, th { border: 1px solid var(--line); padding: 4px 8px; text-align: left; }
tr.me td { color: var(--accent); } .warn { color: var(--warn); }
"""


def _by_id(items, key):
    return next(i for i in items if i["id"] == key)


def render(enc: dict, names: dict, role_id: str, phase_id: str) -> str:
    role, phase = _by_id(enc["roles"], role_id), _by_id(enc["phases"], phase_id)
    spots = {s["id"]: s for s in enc["spots"]}
    used = [spots[s] for s in phase.get("spots", []) if s in spots]
    placed_floors = {s["floor"] for s in used if s.get("pos") is not None}
    floors = [f for f in enc["floors"] if f["id"] in placed_floors] or enc["floors"]
    floor_names = {f["id"]: f["name"] for f in enc["floors"]}
    e = escape
    steps = phase.get("steps", {}).get(role_id) or []
    out = [f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
           f'<meta http-equiv="refresh" content="{REFRESH_SECONDS}">'
           f'<title>{e(enc["name"])} — {e(phase["name"])} — {e(role["name"])}</title><style>{STYLE}</style></head>'
           f'<body><h1>{e(enc["name"])} · {e(phase["name"])} · <span style="color:var(--accent)">'
           f'{e(role["name"])}</span></h1><p class="muted">{e(phase.get("summary", ""))}</p><div class="maps">']
    out += [raid_map.svg(enc, f["id"], names, {s["id"] for s in used}) for f in floors]
    out.append("</div><h2>Your steps</h2>")
    out.append("<ol class=\"steps\">" + "".join(f"<li>{e(s)}</li>" for s in steps) + "</ol>" if steps else
               f'<p class="warn">No steps for {e(role["name"])} in the guides.</p>')
    unplaced = [s for s in used if s.get("pos") is None]
    if unplaced:
        out.append("<h2>Not on the map</h2><ul>" + "".join(
            f"<li>{e(names.get(s['id'], s['name']))} — {e(floor_names.get(s.get('floor'), '?'))}</li>"
            for s in unplaced) + "</ul><p class=\"muted\">No guide says where these are.</p>")
    out.append("<h2>Fireteam</h2><table><tr><th>Role</th><th>Players</th><th>Steps</th></tr>")
    for r in enc["roles"]:
        mine = ' class="me"' if r["id"] == role_id else ""
        out.append(f"<tr{mine}><td>{e(r['name'])}</td><td>{r.get('count', '')}</td><td>"
                   f"{e(' '.join(phase.get('steps', {}).get(r['id'], [])) or '—')}</td></tr>")
    out.append("</table>")
    for title, items in (("Guides disagree", enc.get("conflicts", [])), ("Not in the guides", enc.get("gaps", []))):
        if items:
            out.append(f'<h2 class="warn">{title}</h2><ul>' + "".join(f"<li>{e(i)}</li>" for i in items) + "</ul>")
    out.append('<p class="muted">Sources: ' + ", ".join(f"{e(s['guide'])} ({e(s.get('updated') or '?')})"
                                                       for s in enc["sources"]) + "</p></body></html>")
    return "".join(out)


def write(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
