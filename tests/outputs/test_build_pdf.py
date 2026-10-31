import base64
import copy
import re

import pytest

from shell.outputs import build_pdf
from tests.engines.builds.test_sheet import SHEET

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5E"
                       "rkJggg==")  # 1×1 pixel
RESOLVED = {
    "date": "2026-10-21",
    "armor": [{"slot": "Gauntlets", "itemId": "1", "name": "Getaway Artist", "stat_mod": "Grenade Mod",
               "tuning": "Balanced Tuning", "mods": ["Firepower"]}],
    "weapons": [{"slot": "Kinetic", "itemId": "9", "name": "DECATUR 02", "perks": ["Physic", "Master of Arms"],
                 "mod": "Ballistics", "why": "Add clear."}],
    "stats": {"Weapons": 100, "Grenade": 171},
    "rationale": ["Feed the Void heals on grenade kills."],
}
KEYS = ["item:Getaway Artist", "item:DECATUR 02", "subclass:Stormcaller", "plug:Stormtrance", "plug:Storm Grenade",
        "plug:Electrostatic Mind", "mod:Grenade Mod", "perk:Physic", "stat:Grenade"]


def resolved_sheet():
    s = copy.deepcopy(SHEET)
    s["subclass"]["aspects"] = ["Feed the Void", "Lightning Surge"]
    s["resolved"] = copy.deepcopy(RESOLVED)
    return s


@pytest.fixture
def icons(tmp_path):
    out = {}
    for i, key in enumerate(KEYS):
        out[key] = tmp_path / f"{i}.png"
        out[key].write_bytes(PNG)
    return out


def plain(s, icons):
    return build_pdf.render(s, icons, fonts=None, compress=False)


def test_page_one_is_landscape_with_images(icons):
    data, _ = plain(resolved_sheet(), icons)
    assert data.startswith(b"%PDF") and b"/MediaBox [0 0 841.89 595.28]" in data
    assert b"/Subtype /Image" in data and b"Warlock Arc grenades" in data


def test_missing_icons_are_placeholders():
    data, warnings = plain(resolved_sheet(), {})
    assert data.startswith(b"%PDF")
    assert "no icon: plug:Feed the Void" in warnings and len(warnings) == len(set(warnings))


def test_bad_icon_file(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"<html>nope</html>")
    data, warnings = plain(resolved_sheet(), {"plug:Feed the Void": bad})
    assert data.startswith(b"%PDF") and "bad icon file: plug:Feed the Void" in warnings


def test_bad_round_icon_leaves_no_clip_open(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"<html>nope</html>")
    data, warnings = plain(resolved_sheet(), {"perk:Physic": bad})
    assert "bad icon file: perk:Physic" in warnings
    for page in re.findall(rb"stream\n(.*?)endstream", data, re.S):
        assert len(re.findall(rb"(?<!\S)q(?!\S)", page)) == len(re.findall(rb"(?<!\S)Q(?!\S)", page))


def test_long_text_overflows_to_page_two(icons):
    s = resolved_sheet()
    s["resolved"]["rationale"] = [f"{i:02} " + "grenade " * 25 for i in range(30)]  # 30 × 200 chars
    data, _ = plain(s, icons)
    assert b"/Count 2" in data and b"continued on page 2" in data


def test_short_text_single_page(icons):
    data, _ = plain(resolved_sheet(), icons)
    assert b"/Count 1" in data


def test_intent_only_sheet(icons):
    data, _ = plain(copy.deepcopy(SHEET), icons)
    assert data.startswith(b"%PDF") and b"add clear" in data


def test_fallback_font_simplifies_symbols(icons):
    s = resolved_sheet()
    s["name"] = "Warlock — Grenade ≥ 150"
    data, warnings = plain(s, icons)
    assert b"Warlock - Grenade >= 150" in data
    assert "no Unicode font found (Arial, DejaVu Sans): some symbols were simplified" in warnings


@pytest.mark.skipif(build_pdf.find_fonts() is None, reason="no Unicode TTF font on this machine")
def test_unicode_font_keeps_symbols(icons):
    s = resolved_sheet()
    s["concept"] = "Grenade ≥ 150 — Super × 2 ✓ ★"
    data, warnings = build_pdf.render(s, icons)
    assert data.startswith(b"%PDF") and not any(w.startswith("no Unicode") for w in warnings)


def test_write(tmp_path, icons):
    path = tmp_path / "builds" / "w.pdf"
    build_pdf.write(path, resolved_sheet(), icons)
    assert path.read_bytes().startswith(b"%PDF")
    assert len(re.findall(rb"/Type /Page\b", path.read_bytes())) == 1
