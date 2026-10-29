"""PDF of a build sheet: its Markdown view (build_md) printed — headings, paragraphs, bullets, the Result table.

Same content as the .md by construction. Font: the first Unicode TTF found (Arial on Windows / macOS, DejaVu Sans
on Linux); without one, Helvetica with the symbols outside Latin-1 simplified (≥ -> >=, — -> -).
"""
import re
from pathlib import Path

from fpdf import FPDF
from fpdf.fonts import FontFace

FONT_CANDIDATES = [  # (regular, bold)
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
]
NO_FONT = "no Unicode font found (Arial, DejaVu Sans): some symbols were simplified"
NOT_IN_ARIAL = {"✓": "v", "★": "*"}  # simplified on both font paths
# shortcut: Latin-1 fallback for machines without those fonts; bundle a free font if a template user hits it.
SIMPLER = str.maketrans({"≥": ">=", "≤": "<=", "—": "-", "–": "-", "’": "'", "‘": "'", "“": '"', "”": '"',
                         "•": "-", "…": "...", "→": "->", **NOT_IN_ARIAL})
CELL = re.compile(r"(?<!\\)\|")
SEPARATOR = re.compile(r"\|[\s|:-]+\|")
UNESCAPE = re.compile(r"^( {0,3})\\([#>|-])")  # build_md escapes a leading #, >, | or -


def find_fonts():
    """(regular, bold) TTF paths of the first available candidate, or None."""
    return next(((r, b) for r, b in FONT_CANDIDATES if Path(r).exists() and Path(b).exists()), None)


def _cells(line):
    return [c.strip().replace("\\|", "|") for c in CELL.split(line.strip().strip("|"))]


def render(md_text: str, fonts="auto", compress=True) -> tuple[bytes, list[str]]:
    """(PDF bytes, warnings). fonts: "auto" (find_fonts), None (Helvetica) or (regular, bold) paths."""
    fonts = find_fonts() if fonts == "auto" else fonts
    pdf = FPDF(format="A4")
    pdf.compress = compress
    pdf.set_margins(15, 15)
    pdf.set_auto_page_break(True, 15)
    if fonts:
        pdf.add_font("body", "", fonts[0])
        pdf.add_font("body", "B", fonts[1])
        family, bullet, warnings, missing = "body", "•", [], str.maketrans(NOT_IN_ARIAL)

        def clean(t):
            return t.translate(missing)
    else:
        family, bullet, warnings = "helvetica", "-", [NO_FONT]

        def clean(t):
            return t.translate(SIMPLER).encode("latin-1", "replace").decode("latin-1")

    pdf.add_page()

    def text(t, size=10, style="", gap=1.5):
        pdf.set_font(family, style, size)
        pdf.multi_cell(0, size * 0.5, clean(t), align="L", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(gap)

    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        j = i
        while j < len(lines) and lines[j].startswith("|"):
            j += 1
        if any(SEPARATOR.fullmatch(x.strip()) for x in lines[i:j]):  # else plain lines that start with |
            rows = [_cells(x) for x in lines[i:j] if not SEPARATOR.fullmatch(x.strip())]
            i = j
            pdf.set_font(family, "", 8)
            with pdf.table(headings_style=FontFace(emphasis="BOLD"), line_height=4, text_align="LEFT") as table:
                for cells in rows:
                    row = table.row()
                    for c in cells:
                        row.cell(clean(c))
            pdf.ln(2)
            continue
        if line.startswith("# "):
            text(line[2:], 16, "B", 3)
        elif line.startswith("## "):
            pdf.ln(2)
            text(line[3:], 13, "B", 2)
        elif line.startswith("- "):
            text(f"{bullet} {UNESCAPE.sub(r'\1\2', line[2:])}", gap=0.5)
        elif line.strip():
            t = UNESCAPE.sub(r"\1\2", line)
            text(t[1:-1] if t.startswith("_") and t.endswith("_") else t)
        i += 1
    return bytes(pdf.output()), warnings


def write(path: Path, md_text: str) -> list[str]:
    """Writes the PDF; returns the warnings."""
    data, warnings = render(md_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return warnings
