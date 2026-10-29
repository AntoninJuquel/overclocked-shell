import json
from pathlib import Path

import pytest

from shell.engines.builds import sheet
from shell.outputs import build_md, build_pdf

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "builds" / "example-warlock-prismatic-grenades.json"
MD = """# Warlock Void — Contraverse

Class: Warlock · Activity: Endgame général

\\# not a heading: Grenade ≥ 150 — Super × 2

## Result (2026-10-21)

| Slot | Piece | Mods |
|---|---|---|
| Helmet | Hood \\| of the Great Hunt | Ashes to Assets |

- Kinetic: DECATUR 02 (perks: Physic) — Aegis S #3

_View generated from w.json_
"""


def plain(md):
    """PDF with the core font and uncompressed streams, so the text can be searched in the bytes."""
    data, warnings = build_pdf.render(md, fonts=None, compress=False)
    return data, warnings


def test_fallback_font_renders_markdown_blocks():
    data, warnings = plain(MD)
    assert data.startswith(b"%PDF")
    for text in (b"Warlock Void - Contraverse", rb"Result \(2026-10-21\)", b"Hood | of the Great Hunt",
                 b"# not a heading: Grenade >= 150 - Super \xd7 2", b"Kinetic: DECATUR 02", b"Endgame g\xe9n\xe9ral"):
        assert text in data, text
    assert b"|---|" not in data and b"View generated" in data
    assert warnings == ["no Unicode font found (Arial, DejaVu Sans): some symbols were simplified"]


def test_example_sheet_renders():
    md = build_md.render(sheet.validate(json.loads(EXAMPLE.read_text(encoding="utf-8"))), "example.json", [])
    data, _ = plain(md)
    assert b"Subclass" in data and b"Feed the Void" in data


@pytest.mark.skipif(build_pdf.find_fonts() is None, reason="no Unicode TTF font on this machine")
def test_unicode_font_keeps_symbols():
    data, warnings = build_pdf.render(MD)
    assert data.startswith(b"%PDF") and warnings == []


def test_write(tmp_path):
    path = tmp_path / "builds" / "w.pdf"
    build_pdf.write(path, MD)
    assert path.read_bytes().startswith(b"%PDF")


def test_escaped_bullets_and_indented_escapes_lose_their_backslash():
    data, _ = plain("- \\-10 Weapons\n  \\# indented\n")
    assert b"- -10 Weapons" in data and b"# indented" in data and b"\\\\" not in data


def test_pipe_lines_without_separator_are_paragraphs():
    data, _ = plain("| not a table |\n")
    assert b"| not a table |" in data


@pytest.mark.skipif(build_pdf.find_fonts() is None, reason="no Unicode TTF font on this machine")
def test_unicode_font_maps_glyphs_it_lacks(monkeypatch):
    sent, multi_cell = [], build_pdf.FPDF.multi_cell

    def spy(self, w, h, text, *args, **kwargs):
        sent.append(text)
        return multi_cell(self, w, h, text, *args, **kwargs)
    monkeypatch.setattr(build_pdf.FPDF, "multi_cell", spy)
    build_pdf.render("Done ✓ · Rated ★")
    assert sent and not any(c in t for t in sent for c in "✓★") and "v" in sent[0] and "*" in sent[0]
