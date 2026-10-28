import copy

from shell.engines.builds import sheet
from shell.outputs import build_md
from tests.engines.builds.test_sheet import RESOLVED, SHEET, _with


def render(s, needs=()):
    return build_md.render(sheet.validate(s), "w.json", list(needs))


def test_weapon_intent_fields_render():
    s = copy.deepcopy(SHEET)
    s["intent"]["weapons"] = [
        {"slot": "Kinetic", "role": "precision", "element": "Strand", "type": "Sniper Rifle", "ammo": "Special"},
        {"slot": "Energy", "role": "add clear", "element": "Void", "exotic": True, "wanted": "Graviton Spike"}]
    md = render(s)
    assert "- Weapon Kinetic: precision — Strand · Sniper Rifle · Special" in md
    assert "- Weapon Energy: add clear — Void · exotic (Graviton Spike)" in md


def test_artifact_renders():
    s = copy.deepcopy(SHEET)
    s["intent"]["artifact"] = {"name": "Satchel", "perks": ["Weakened Clear", "Void Renewal"]}
    assert "- Artifact: Satchel — Weakened Clear, Void Renewal" in render(s)


def test_resolved_sets_render():
    s = copy.deepcopy(SHEET)
    s["resolved"] = {"sets": []}
    assert "Sets applied: — (intent: 2 × AION Renewal)" in render(s)


def test_markdown_shows_resolved():
    s = copy.deepcopy(SHEET)
    s["resolved"] = {
        "date": "2026-10-07",
        "armor": [{"slot": "Helmet", "itemId": "1", "name": "Hood", "masterwork": "todo",
                   "stat_mod": "Grenade Mod", "tuning": "+Grenade / -Weapons"}],
        "weapons": [{"slot": "Kinetic", "itemId": "9", "name": "Adamantite", "why": "Strand add clear"}],
        "stats": {"Weapons": 5, "Health": 70, "Class": 30, "Grenade": 150, "Super": 40, "Melee": 10},
        "rationale": ["Grenade first."],
    }
    md = render(s)
    assert "## Result (2026-10-07)" in md
    assert "| Slot | Piece | Masterwork | Stat mod | Tuning | Mods |" in md
    assert "| Helmet | Hood | todo | Grenade Mod | +Grenade / -Weapons | — |" in md
    assert "Weapons:\n- Kinetic: Adamantite — Strand add clear" in md
    assert "Stats: Weapons 5 · Health 70 · Class 30 · Grenade 150 · Super 40 · Melee 10" in md
    assert "Rationale:\n- Grenade first." in md


def test_markdown_shows_fill_mods_and_weapon_setup():
    s = copy.deepcopy(SHEET)
    s["intent"]["armor_mods_fill"] = {"Helmet": ["Arc Siphon", "Heavy Ammo Finder"]}
    s["resolved"] = {
        "armor": [{"slot": "Helmet", "itemId": "1", "name": "Hood", "stat_mod": "Grenade Mod",
                   "mods": ["Arc Siphon", "Arc Siphon", "Heavy Ammo Finder"]}],
        "weapons": [{"slot": "Kinetic", "itemId": "9", "name": "Conspiracy Honed",
                     "perks": ["Vorpal Weapon", "Firefly"], "mod": "Targeting Adjuster", "why": "precision"}],
    }
    md = render(s)
    assert "- Filler mods (energy left): Helmet: Arc Siphon, Heavy Ammo Finder" in md
    assert "| Grenade Mod | — | Arc Siphon, Arc Siphon, Heavy Ammo Finder |" in md
    assert ("- Kinetic: Conspiracy Honed (perks: Vorpal Weapon, Firefly · mod: Targeting Adjuster) — precision"
            in md)


def test_minimal_sheet_fallbacks():
    s = {"name": "Min", "class": "Titan", "subclass": {"element": "Void"},
         "intent": {"exotic": {"name": "Peacekeepers"}}}
    md = render(s)
    assert "Class: Titan · Activity: —" in md
    assert "## Subclass" in md and "- Element: Void" in md
    assert "- Aspects: —" in md and "- Fragments: —" in md
    assert "## Intent" in md and "- Exotic: Peacekeepers" in md
    assert "- Minimums: —" in md and "- Priorities: —" in md
    assert "- Sets: —" in md and "- Utility mods: —" in md
    assert "Super" not in md and "Weapon" not in md


def test_markdown_escaping():
    s = _with(("concept",), "# Title\n> quote\n- item", base=None)
    s["resolved"] = copy.deepcopy(RESOLVED)
    s["resolved"]["armor"] = [{"slot": "Helmet", "itemId": "1", "name": "A|B\nC"}]
    s["resolved"]["rationale"] = ["# title", "- bullet"]
    s["resolved"]["weapons"] = [{"slot": "Kinetic", "itemId": "9", "name": "W"}]
    md = render(s)
    assert "\n# Title" not in md and "\\# Title" in md
    assert "\\> quote" in md and "\\- item" in md
    assert "| Helmet | A\\|B C | — | — | — |" in md
    assert "- \\# title" in md and "- \\- bullet" in md
    assert "- Kinetic: W\n" in md


def test_needs_render():
    need = {"label": "Promised Helmet"}
    gain = {"stats": {"Grenade": 12, "Health": -3}, "effects": ["Promised — 2 pieces: Foo"], "score": 0.2}
    md = render(copy.deepcopy(SHEET), [(need, gain), ({"label": "# Bare"}, {"stats": {}, "effects": []})])
    assert "## To fetch" in md
    assert "- Promised Helmet — Grenade +12 · Health -3; Promised — 2 pieces: Foo" in md
    assert "- \\# Bare\n" in md


def test_render_without_needs_has_no_section():
    assert "To fetch" not in render(copy.deepcopy(SHEET))


def test_footer_names_source_and_check_build():
    md = render(copy.deepcopy(SHEET))
    assert md.endswith("\n")
    assert "w.json" in md.splitlines()[-1] and "check_build" in md.splitlines()[-1]
