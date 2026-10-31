"""PDF of a build sheet laid out like the game's Character and subclass screens: one A4 landscape page.

Top bar (name, class · activity); left: the subclass (emblem, super diamond, abilities, aspects, fragments), the
weapons (perk circles and mod to the left of the icon, as in the inspect screen) and the artifact; middle (where the
Guardian stands): concept, why it works, each weapon's why, the armor set bonus with its perks; right: the stats (the
active set perk icons below) and the armor with its mods (tuning, stat mod, slot mods). Text that doesn't fit the middle continues on page 2.

Pure: the icons come in as local files ({"<kind>:<name>": Path}); a missing or unreadable one is a dark placeholder
with the name in it, plus a warning. Font: the first Unicode TTF found (Arial on Windows / macOS, DejaVu Sans on
Linux); without one, Helvetica with the symbols outside Latin-1 simplified (≥ -> >=, — -> -).
"""
import re
from pathlib import Path

from fpdf import FPDF
from fpdf.image_parsing import preload_image  # semi-internal: why pyproject pins fpdf2 below 2.9
from fpdf.pattern import LinearGradient, RadialGradient

from shell.engines.builds.equip_plan import SUBCLASS_ITEMS
from shell.engines.builds.stats import SLOTS, STATS

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
                         "•": "-", "…": "...", "→": "->", "−": "-", **NOT_IN_ARIAL})
MARKUP = re.compile(r"(\*\*|__|--|~~)")  # fpdf markdown markers, escaped in sheet text

GRADIENTS = {  # centre → middle → edge, by subclass element
    "Prismatic": ("#c46aa6", "#6b3f77", "#2a2433"), "Solar": ("#d9823f", "#6e3a2a", "#2a2226"),
    "Arc": ("#6fb6e0", "#2f5a7a", "#1e2632"), "Void": ("#a36ad6", "#4b2f6e", "#221d2e"),
    "Stasis": ("#7a9ee8", "#34497a", "#1d2233"), "Strand": ("#5fd39a", "#2b6b52", "#1c2a26"),
}
WEAPON_SLOTS = ["Kinetic", "Energy", "Power"]
WHITE, SOFT, LABEL = "#eeeeee", "#cccccc", "#f0e6f4"
GOLD, MOD_GOLD = "#e9cf55", "#c9b46a"
MID_X, MID_W, MID_TOP, MID_BOTTOM = 114, 100, 17, 204


def find_fonts():
    """(regular, bold) TTF paths of the first available candidate, or None."""
    return next(((r, b) for r, b in FONT_CANDIDATES if Path(r).exists() and Path(b).exists()), None)


def _italic(regular):
    stem = regular[:-4]
    return next((p for p in (stem + "i.ttf", stem + " Italic.ttf", stem + "-Oblique.ttf") if Path(p).exists()), None)


def _escape(t):
    """Sheet text as literal fpdf markdown: markers escaped, no [link](url)."""
    return MARKUP.sub(lambda m: "\\" + m.group(1), t).replace("](", "] (")


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


class _Page(FPDF):
    colors = GRADIENTS["Prismatic"]

    def header(self):  # every page: the element's radial gradient, as the in-game background
        with self.use_pattern(RadialGradient(self.w * .55, self.h * .45, 0, self.w * .55, self.h * .45, 160,
                                             list(self.colors), bounds=[.47], extend_after=True)):
            self.rect(0, 0, self.w, self.h, "F")


def render(s: dict, icons: dict[str, Path], fonts="auto", compress=True, needs=(), slug="build",
           set_perks=None) -> tuple[bytes, list[str]]:
    """(PDF bytes, warnings). icons: {"<kind>:<name>": local file}. fonts: "auto" (find_fonts), None (Helvetica) or
    (regular, bold) paths. needs: [(need, gain)] from `sheet.needs_for`, shown as "TO FETCH" on page 2. set_perks:
    {set: [{pieces, name}]} from `build_icons.set_perks`."""
    set_perks = set_perks or {}
    fonts = find_fonts() if fonts == "auto" else fonts
    pdf = _Page(orientation="L", format="A4")
    pdf.compress = compress
    pdf.colors = GRADIENTS.get(s["subclass"]["element"], GRADIENTS["Prismatic"])
    pdf.set_auto_page_break(False)
    warnings, warned = [], set()
    if fonts:
        family, bullet = "body", "•"
        pdf.add_font(family, "", fonts[0])
        pdf.add_font(family, "B", fonts[1])
        italic = _italic(fonts[0])
        if italic:
            pdf.add_font(family, "I", italic)
        missing = str.maketrans(NOT_IN_ARIAL)

        def clean(t):
            return t.translate(missing)
    else:
        family, bullet, italic = "helvetica", "-", True
        warnings.append(NO_FONT)

        def clean(t):
            return t.translate(SIMPLER).encode("latin-1", "replace").decode("latin-1")

    def font(size, style="", color=WHITE):
        pdf.set_font(family, style if italic or style != "I" else "", size)
        pdf.set_text_color(*_rgb(color))

    def text(x, y, t, size, style="", color=WHITE, w=0, align="L"):
        font(size, style, color)
        if w:  # shrink to fit one line
            while size > 5 and pdf.get_string_width(clean(t)) > w:
                size -= .5
                font(size, style, color)
        pdf.set_xy(x, y)
        pdf.cell(w, size * .42, clean(t), align=align)

    def frame(x, y, w, color="#ffffff", alpha=.55, width=.5, round_=False):
        pdf.set_draw_color(*_rgb(color))
        pdf.set_line_width(width)
        with pdf.local_context(stroke_opacity=alpha):
            (pdf.ellipse if round_ else pdf.rect)(x, y, w, w, "D")

    def fill(x, y, w, color, alpha=1, round_=False, h=None):
        pdf.set_fill_color(*_rgb(color))
        with pdf.local_context(fill_opacity=alpha):
            (pdf.ellipse if round_ else pdf.rect)(x, y, w, h or w, "F")

    def icon(key, x, y, w, round_=False, bg=None):
        """The icon of `key` (clipped to a circle when round_), or a placeholder with its name."""
        file = icons.get(key)
        if bg:
            fill(x, y, w, bg, round_=round_)
        if file is not None:
            try:
                preload_image(pdf.image_cache, file)  # raises before elliptic_clip, which would leave its clip open
                if round_:
                    with pdf.elliptic_clip(x, y, w, w):
                        pdf.image(file, x, y, w, w)
                else:
                    pdf.image(file, x, y, w, w)
                return
            except Exception:
                problem = f"bad icon file: {key}"
        else:
            problem = f"no icon: {key}"
        if problem not in warned:
            warned.add(problem)
            warnings.append(problem)
        fill(x, y, w, "#000000", .33, round_)
        font(4, "", SOFT)
        pdf.set_xy(x, y + w / 2 - 2)
        pdf.multi_cell(w, 1.6, clean(key.split(":", 1)[1])[:40], align="C")

    def label(x, y, t, w):
        text(x, y, t.upper(), 6.5, "", LABEL)
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(.3)
        with pdf.local_context(stroke_opacity=.4):
            pdf.line(x, y + 3.4, x + w, y + 3.4)

    pdf.add_page()
    intent, res, sub, cls = s["intent"], s.get("resolved"), s["subclass"], s["class"]

    # top bar
    fill(0, 0, pdf.w, "#111111", .6, h=14)
    text(6, 2.2, s["name"], 16, "B", w=280)
    text(6, 9.2, " · ".join(p for p in (cls, s.get("activity")) if p).upper(), 7, "", SOFT)

    # subclass panel
    emblem = f"subclass:{SUBCLASS_ITEMS[cls][sub['element']]}"
    icon(emblem, 6, 17, 10, round_=True)
    frame(6, 17, 10, alpha=.5, round_=True)
    text(18.5, 17.6, f"{sub['element']} {cls}".upper(), 14, "B")
    text(18.5, 24, f"{cls} subclass · super: {sub['super']}".upper(), 6.5, "", "#dddddd", w=90)
    cx, cy, half = 25, 50, 12
    with pdf.rotation(45, cx, cy):
        with pdf.use_pattern(LinearGradient(cx - half, cy - half, cx + half, cy + half, list(pdf.colors[:2]))):
            pdf.rect(cx - half, cy - half, 2 * half, 2 * half, "F")
        frame(cx - half, cy - half, 2 * half, alpha=.6)
    icon(f"plug:{sub['super']}", cx - 9, cy - 9, 18)
    abilities = sub.get("abilities") or {}
    y = 30
    for title, names in (("Abilities", [abilities.get(k) for k in ("class", "jump", "melee", "grenade")]),
                         ("Aspects", sub.get("aspects") or []), ("Fragments", sub.get("fragments") or [])):
        names = [n for n in names if n]
        label(50, y, title, 60)
        size = min(10, 61 / max(len(names), 1) - 1)
        for i, n in enumerate(names):
            fill(50 + i * (size + 1), y + 4.6, size, "#000000", .2)
            icon(f"plug:{n}", 50 + i * (size + 1), y + 4.6, size)
            frame(50 + i * (size + 1), y + 4.6, size, alpha=.33, width=.25)
        y += 17

    # weapons: perk circles and mod right-aligned toward the icon, icon, name and the two main perks
    intent_weapons = {w["slot"]: w for w in intent.get("weapons") or []}
    weapons = sorted(res.get("weapons") or [] if res else [], key=lambda w: WEAPON_SLOTS.index(w["slot"]))
    for i, w in enumerate(weapons):
        y = 95 + i * 18
        perks, mod = w.get("perks") or [], w.get("mod")
        top = y + (1.1 if mod else 4.5)
        for j, p in enumerate(reversed(perks)):
            icon(f"perk:{p}", 46 - 6 - j * 6.8, top, 6, round_=True, bg="#3d6f93")
        if mod:
            icon(f"perk:{mod}", 40, top + 6.8, 6, bg="#4a4636")
            frame(40, top + 6.8, 6, MOD_GOLD, 1, .25)
        exotic = (intent_weapons.get(w["slot"]) or {}).get("exotic") or w["name"] == intent["exotic"]["name"]
        icon(f"item:{w['name']}", 48, y, 15, bg="#000000")
        frame(48, y, 15, GOLD if exotic else "#ffffff", 1 if exotic else .55)
        text(65, y + 4, w["name"], 8, "B", w=45)
        main = perks[2:4] if len(perks) >= 4 else perks[:2]  # traits (columns 3-4), as the inspect screen shows
        text(65, y + 8, " · ".join(main), 6.5, "", "#dddddd", w=45)
    if not res:  # intent only: the roles in empty frames
        for i, w in enumerate(sorted(intent_weapons.values(), key=lambda w: WEAPON_SLOTS.index(w["slot"]))):
            y = 95 + i * 18
            fill(48, y, 15, "#000000", .33)
            frame(48, y, 15, GOLD if w.get("exotic") else "#ffffff", 1 if w.get("exotic") else .55)
            text(65, y + 1.5, w["slot"], 8, "B")
            font(6.5, "", "#dddddd")
            pdf.set_xy(65, y + 5.5)
            pdf.multi_cell(45, 2.8, clean(w.get("role") or w.get("wanted") or ""), align="L", max_line_height=2.8)

    # artifact
    art = intent.get("artifact")
    if art:
        icon(f"artifact:{art['name']}", 6, 189, 13, bg="#000000")
        frame(6, 189, 13)
        text(21, 189.5, art["name"].upper(), 6.5, "", LABEL)
        for j, p in enumerate(art.get("perks") or []):
            icon(f"artifact:{p}", 21 + j * 7.5, 194.5, 6.5, round_=True, bg="#30534f")

    # stats
    if res:
        top = 70
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(.25)
        with pdf.local_context(stroke_opacity=.27):
            pdf.rect(216, top, 16, 6 * 8 + 3, "D")
        for i, k in enumerate(STATS):
            v = (res.get("stats") or {}).get(k)
            text(216, top + 3 + i * 8, "-" if v is None else str(v), 9, "", WHITE, w=10, align="R")
            icon(f"stat:{k}", 227, top + 2.7 + i * 8, 4)

    # active set perks under the stats column
    for i, p in enumerate(p for ps in set_perks.values() for p in ps):
        icon(f"setperk:{p['name']}", 220, 124 + i * 9.5, 8)

    # armor: one row per slot, item icon then tuning, stat mod, slot mods
    rows = {a["slot"]: a for a in res.get("armor") or []} if res else {}
    pitch = (200 - 18) / len(SLOTS)
    for i, slot in enumerate(SLOTS):
        y = 18 + i * pitch + (pitch - 15) / 2
        a = rows.get(slot)
        if a:
            gold = a["name"] == intent["exotic"]["name"]
            icon(f"item:{a['name']}", 234, y, 15, bg="#000000")
            mods = [(a.get("tuning"), False), (a.get("stat_mod"), True), *((m, False) for m in a.get("mods") or [])]
        else:
            gold = False
            fill(234, y, 15, "#000000", .33)
            text(234, y + 6.5, slot, 5, "", SOFT, w=15, align="C")
            mods = [(m, False) for m in (intent.get("armor_mods") or {}).get(slot) or []]
        frame(234, y, 15, GOLD if gold else "#ffffff", 1 if gold else .55)
        for j, (m, stat) in enumerate(m for m in mods if m[0]):
            icon(f"mod:{m}", 251 + j * 7.8, y + 4, 7, bg="#2c4b52")
            frame(251 + j * 7.8, y + 4, 7, MOD_GOLD if stat else "#ffffff", 1 if stat else .2, .25)
    if not res:  # no slot for the exotic in the intent: shown where the stats would be
        text(216, 86, "EXOTIC", 5, "", LABEL, w=16, align="C")
        icon(f"item:{intent['exotic']['name']}", 216.5, 89, 15, bg="#000000")
        frame(216.5, 89, 15, GOLD, 1)

    _middle(pdf, s, font, clean, bullet, needs, set_perks)
    pdf.set_auto_page_break(False)  # footer on the last page, below the break margin
    font(6, "", SOFT)
    pdf.set_xy(6, 203)
    pdf.cell(0, 3, f"Generated by Overclocked Shell from {slug}.json")
    return bytes(pdf.output()), warnings


def _middle(pdf, s, font, clean, bullet, needs=(), set_perks={}):
    """Concept, WHY IT WORKS, WEAPONS, set box in the middle at 8 / 7.5 / 7 pt; the rest on page 2."""
    res, intent = s.get("resolved") or {}, s["intent"]
    blocks = []  # (kind, text): box (concept), h (heading), li, wli (markdown), set
    if s.get("concept"):
        blocks.append(("box", s["concept"]))
    if res.get("rationale"):
        blocks += [("h", "WHY IT WORKS"), *(("li", r) for r in res["rationale"])]
    whys = [w for w in res.get("weapons") or [] if w.get("why")]
    if whys:
        blocks += [("h", "WEAPONS"), *(("wli", f"**{_escape(w['name'])}**: {_escape(w['why'])}") for w in whys)]
    sets = res.get("sets") or intent.get("sets") or []
    if sets:
        blocks.append(("set", "\n".join(line for e in sets for line in (
            f"ARMOR SET BONUS · {e['set'].upper()} ×{e['pieces']}",
            *(f"{p['pieces']} Piece | {p['name']}" for p in set_perks.get(e["set"]) or [])))))

    tail = []  # page 2 only: after any overflow
    if needs:
        tail.append(("h", "TO FETCH"))
        for n, gain in needs:
            parts = [" · ".join(f"{k} {v:+d}" for k, v in gain["stats"].items())] + list(gain["effects"])
            detail = "; ".join(x for x in parts if x)
            tail.append(("li", n["label"] + (f" — {detail}" if detail else "")))

    def draw(kind, t, x, w, size, dry=False):
        h = size * .45
        style = {"box": "I", "h": "B", "set": "B"}.get(kind, "")
        font(size, style, "#f0e6f4" if kind == "h" else "#eeeeee")
        args = dict(align="L", markdown=kind == "wli", max_line_height=h)
        if kind in ("box", "set"):
            pdf.set_fill_color(*_rgb("#1a1420" if kind == "box" else "#221b27"))
            args.update(fill=True, padding=(1.6, 2.4))
        indent = 3 if kind in ("li", "wli") else 0
        if dry:
            return pdf.multi_cell(w - indent, h, clean(t), dry_run=True, output="HEIGHT", **args) + 1.4
        if indent:
            pdf.set_xy(x, pdf.get_y())
            pdf.cell(indent, h, bullet)
        pdf.set_x(x + indent)
        with pdf.local_context(fill_opacity=.7 if kind == "box" else .9):
            pdf.multi_cell(w - indent, h, clean(t), new_x="LMARGIN", new_y="NEXT", **args)
        pdf.set_y(pdf.get_y() + 1.4)

    room = MID_BOTTOM - MID_TOP
    for size in (8, 7.5, 7):
        heights = [draw(k, t, MID_X, MID_W, size, True) for k, t in blocks]
        if sum(heights) <= room:
            break
    cut, used = len(blocks), 0
    if sum(heights) > room:
        room -= 4  # the "continued" line
        cut = 0
        while used + heights[cut] <= room:
            used += heights[cut]
            cut += 1
        if cut and blocks[cut - 1][0] == "h":  # no heading alone at the bottom
            cut -= 1
    pdf.set_y(MID_TOP)
    for k, t in blocks[:cut]:
        draw(k, t, MID_X, MID_W, size)
    if cut < len(blocks) or tail:
        if cut < len(blocks):
            font(6.5, "I", "#cccccc")
            pdf.set_xy(MID_X, pdf.get_y())
            pdf.cell(MID_W, 3, "(continued on page 2)")
        pdf.set_auto_page_break(True, 12)
        pdf.add_page()
        pdf.set_y(15)
        for k, t in blocks[cut:] + tail:
            draw(k, t, 15, pdf.w - 30, 8)


def write(path: Path, s: dict, icons: dict[str, Path], needs=(), set_perks=None) -> list[str]:
    """Writes the PDF; returns the warnings."""
    data, warnings = render(s, icons, needs=needs, slug=path.stem, set_perks=set_perks)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return warnings
