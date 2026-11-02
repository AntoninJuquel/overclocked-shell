"""Markdown view of a build sheet (regenerated on every save; the JSON is the source of truth)."""
import re

from shell.engines.builds.stats import STATS


def _oneline(value):
    return re.sub(r"\s*\n\s*", " ", str(value)).strip()


def _cell(value):
    return _oneline(value).replace("|", "\\|")


def _escape(text):
    """Keeps a free-text line from passing for a Markdown heading, quote, list or table."""
    return re.sub(r"^( {0,3})(#|>|\||-)", r"\1\\\2", text, flags=re.M)


def _sets_text(sets):
    return ", ".join(f"{e['pieces']} × {e['set']}" for e in sets) or "—"


def _weapon_line(w):
    setup = []
    if w.get("perks"):
        setup.append(f"perks: {', '.join(w['perks'])}")
    if w.get("mod"):
        setup.append(f"mod: {w['mod']}")
    text = f"- {w['slot']}: {_oneline(w['name'])}"
    if setup:
        text += f" ({_oneline(' · '.join(setup))})"
    return text + (f" — {_oneline(w['why'])}" if w.get("why") else "")


def render(s, source="the JSON sheet", needs=(), tr=None):
    """`needs`: [(need, gain)] from `sheet.needs_for`. tr: str → str in the player's language (`lexicon.translator`)."""
    sub, intent = s["subclass"], s["intent"]
    st = intent.get("stats", {})
    lines = [f"# {_oneline(s['name'])}", "",
             f"Class: {s['class']} · Activity: {_oneline(s.get('activity') or '—')}", ""]
    if s.get("concept"):
        lines += [_escape(s["concept"]), ""]
    lines += ["## Subclass", "", f"- Element: {sub['element']}"]
    if sub.get("super"):
        lines.append(f"- Super: {_oneline(sub['super'])}")
    for kind, name in sub.get("abilities", {}).items():
        lines.append(f"- {kind}: {_oneline(name)}")
    lines.append(f"- Aspects: {_oneline(', '.join(sub.get('aspects', []))) or '—'}")
    lines.append(f"- Fragments: {_oneline(', '.join(sub.get('fragments', []))) or '—'}")
    exotic = intent["exotic"]
    perks = f" ({', '.join(exotic['perks'])})" if exotic.get("perks") else ""
    mins = ", ".join(f"{k} ≥ {v}" for k, v in st.get("minimums", {}).items()) or "—"
    prio = " > ".join(st.get("priority", [])) or "—"
    sets_txt = _sets_text(intent.get("sets", []))
    lines += ["", "## Intent", "", f"- Exotic: {_oneline(exotic['name'] + perks)}",
              f"- Minimums: {mins}", f"- Priorities: {prio}", f"- Sets: {_oneline(sets_txt)}"]
    mods = [f"{slot}: {', '.join(names)}" for slot, names in intent.get("armor_mods", {}).items() if names]
    lines.append(f"- Utility mods: {_oneline('; '.join(mods)) or '—'}")
    fill = [f"{slot}: {', '.join(names)}" for slot, names in intent.get("armor_mods_fill", {}).items() if names]
    if fill:
        lines.append(f"- Filler mods (energy left): {_oneline('; '.join(fill))}")
    art = intent.get("artifact")
    if art:
        lines.append(f"- Artifact: {_oneline(art['name'])} — {_oneline(', '.join(art.get('perks', []))) or '—'}")
    for w in intent.get("weapons", []):
        named = [" / ".join(o["name"] for o in w.get("items") or []),
                 ", ".join(" / ".join(o["name"] for o in c) for c in w.get("perks") or []),
                 " / ".join(o["name"] for o in w.get("mods") or []),
                 " / ".join(o["name"] for o in w.get("masterworks") or []), w.get("wanted")]
        named = "; ".join(_oneline(x) for x in named if x)
        wanted = f" ({named})" if named else ""
        spec = [w.get("element"), w.get("type"), w.get("ammo"), "exotic" if w.get("exotic") else None]
        spec = " · ".join(_oneline(x) for x in spec if x)
        lines.append(f"- Weapon {w['slot']}: {_oneline(w.get('role') or '—')}{' — ' + spec if spec else ''}{wanted}")
    res = s.get("resolved")
    if res:
        lines += ["", f"## Result ({_oneline(res.get('date') or '?')})", "",
                  "| Slot | Piece | Masterwork | Stat mod | Tuning | Mods |",
                  "|---|---|---|---|---|---|"]
        for a in res.get("armor", []):
            lines.append(f"| {_cell(a['slot'])} | {_cell(a['name'])} | {_cell(a.get('masterwork') or '—')} | "
                         f"{_cell(a.get('stat_mod') or '—')} | {_cell(a.get('tuning') or '—')} | "
                         f"{_cell(', '.join(a.get('mods') or []) or '—')} |")
        if "sets" in res:
            lines += ["", f"Sets applied: {_oneline(_sets_text(res['sets']))} (intent: {_oneline(sets_txt)})"]
        if res.get("stats"):
            lines += ["", "Stats: " + " · ".join(f"{k} {res['stats'][k]}" for k in STATS if k in res["stats"])]
        if res.get("weapons"):
            lines += ["", "Weapons:"] + [_weapon_line(w) for w in res["weapons"]]
        if res.get("rationale"):
            lines += ["", "Rationale:"] + [f"- {_escape(_oneline(r))}" for r in res["rationale"]]
    if needs:
        lines += ["", "## To fetch", ""]
        for n, gain in needs:
            parts = [" · ".join(f"{k} {v:+d}" for k, v in gain["stats"].items())] + list(gain["effects"])
            detail = "; ".join(_oneline(x) for x in parts if x)
            lines.append(f"- {_escape(_oneline(n['label']))}" + (f" — {detail}" if detail else ""))
    lines += ["", f"_View generated from {source}: do not edit by hand; edit the JSON, then run check_build._", ""]
    return (tr or (lambda t: t))("\n".join(lines))
