"""PDF of a build sheet laid out like the game's Character and subclass screens: one A4 landscape page.

A sheet to share: it shows the build as designed (the intent), never what the player's inventory reached.
Top bar (name, class · activity); left: the subclass (super diamond, abilities, aspects, fragments), the
weapons (icon, name, perk columns with alternatives, mod, masterwork) and the artifact; middle (where the Guardian
stands): the armor set bonus, as the game's tooltip; right: the stat targets and the armor with its wanted mods.

Pure: the icons come in as local files ({"<kind>:<name>": Path}); a missing or unreadable one is a dark placeholder
with the name in it, plus a warning. Font: the first Unicode TTF found (Arial on Windows / macOS, DejaVu Sans on
Linux); without one, Helvetica with the symbols outside Latin-1 simplified (≥ -> >=, — -> -).
"""
from pathlib import Path

from fpdf import FPDF
from fpdf.image_parsing import preload_image  # semi-internal: why pyproject pins fpdf2 below 2.9
from fpdf.pattern import LinearGradient, RadialGradient

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

GRADIENTS = {  # centre → middle → edge, by subclass element
    "Prismatic": ("#c46aa6", "#6b3f77", "#2a2433"), "Solar": ("#d9823f", "#6e3a2a", "#2a2226"),
    "Arc": ("#6fb6e0", "#2f5a7a", "#1e2632"), "Void": ("#a36ad6", "#4b2f6e", "#221d2e"),
    "Stasis": ("#7a9ee8", "#34497a", "#1d2233"), "Strand": ("#5fd39a", "#2b6b52", "#1c2a26"),
}
WEAPON_SLOTS = ["Kinetic", "Energy", "Power"]
WHITE, SOFT, LABEL = "#eeeeee", "#cccccc", "#f0e6f4"
GOLD, MOD_GOLD = "#e9cf55", "#c9b46a"
MID_X, MID_W, MID_TOP = 113, 120, 90  # the set bonus: below the stats box, right edges aligned
LIGHT_GG = "https://www.light.gg/db/{lang}/items/{hash}"


def find_fonts():
    """(regular, bold) TTF paths of the first available candidate, or None."""
    return next(((r, b) for r, b in FONT_CANDIDATES if Path(r).exists() and Path(b).exists()), None)


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


class _Page(FPDF):
    colors = GRADIENTS["Prismatic"]

    def header(self):  # every page: the element's radial gradient, as the in-game background
        with self.use_pattern(RadialGradient(self.w * .55, self.h * .45, 0, self.w * .55, self.h * .45, 160,
                                             list(self.colors), bounds=[.47], extend_after=True)):
            self.rect(0, 0, self.w, self.h, "F")


def render(s: dict, icons: dict[str, Path], fonts="auto", compress=True, armor=None, slug="build",
           set_perks=None, tr=None, links=None) -> tuple[bytes, list[str]]:
    """(PDF bytes, warnings). icons: {"<kind>:<name>": local file}. fonts: "auto" (find_fonts), None (Helvetica) or
    (regular, bold) paths. armor: {slot: piece} from `build_icons.intent_armor`. set_perks: {set: [{pieces, name, description}]}
    from `build_icons.set_perks`. tr: str → str shown in the player's language (`lexicon.translator`); icons,
    gradients and layout stay keyed by the sheet's English names. links: {"<kind>:<name>": url} makes those
    icons clickable."""
    links = links or {}
    tr = tr or (lambda t: t)
    set_perks = set_perks or {}
    fonts = find_fonts() if fonts == "auto" else fonts
    pdf = _Page(orientation="L", format="A4")
    pdf.compress = compress
    pdf.colors = GRADIENTS.get(s["subclass"]["element"], GRADIENTS["Prismatic"])
    pdf.set_auto_page_break(False)
    warnings, warned = [], set()
    if fonts:
        family = "body"
        pdf.add_font(family, "", fonts[0])
        pdf.add_font(family, "B", fonts[1])
        missing = str.maketrans(NOT_IN_ARIAL)

        def clean(t):
            return tr(t).translate(missing)
    else:
        family = "helvetica"
        warnings.append(NO_FONT)

        def clean(t):
            return tr(t).translate(SIMPLER).encode("latin-1", "replace").decode("latin-1")

    def font(size, style="", color=WHITE):
        pdf.set_font(family, style, size)
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
        if key in links:
            pdf.link(x, y, w, w, links[key])
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
        text(x, y, t.upper(), 9, "", LABEL)
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(.3)
        with pdf.local_context(stroke_opacity=.4):
            pdf.line(x, y + 4.6, x + w, y + 4.6)

    pdf.add_page()
    intent, sub, cls = s["intent"], s["subclass"], s["class"]

    # top bar
    fill(0, 0, pdf.w, "#111111", .6, h=14)
    text(6, 2.2, s["name"], 16, "B", w=280)
    text(6, 9.2, " · ".join(p for p in (cls, s.get("activity")) if p).upper(), 7, "", SOFT)

    # subclass panel
    cx, cy, half = 30, 41, 16.8
    with pdf.rotation(45, cx, cy):
        with pdf.use_pattern(LinearGradient(cx - half, cy - half, cx + half, cy + half, list(pdf.colors[:2]))):
            pdf.rect(cx - half, cy - half, 2 * half, 2 * half, "F")
        frame(cx - half, cy - half, 2 * half, alpha=.6)
    icon(f"plug:{sub['super']}", cx - 12.5, cy - 12.5, 25)
    abilities = sub.get("abilities") or {}
    y = 17
    for title, names in (("Abilities", [abilities.get(k) for k in ("class", "jump", "melee", "grenade")]),
                         ("Aspects", sub.get("aspects") or []), ("Fragments", sub.get("fragments") or [])):
        names = [n for n in names if n]
        label(58, y, title, 84)
        size = min(14, 85 / max(len(names), 1) - 1)
        for i, n in enumerate(names):
            fill(58 + i * (size + 1), y + 6.5, size, "#000000", .2)
            icon(f"plug:{n}", 58 + i * (size + 1), y + 6.5, size)
            frame(58 + i * (size + 1), y + 6.5, size, alpha=.33, width=.25)
        y += 24

    # weapons: icon, name, then the perk columns (alternatives below), mods and masterworks
    y = 90
    for w in sorted(intent.get("weapons") or [], key=lambda w: WEAPON_SLOTS.index(w["slot"])):
        name = (w.get("items") or [{}])[0].get("name")
        if name:
            icon(f"item:{name}", 6, y, 21, bg="#000000")
        else:
            fill(6, y, 21, "#000000", .33)
        frame(6, y, 21, GOLD if w.get("exotic") else "#ffffff", 1 if w.get("exotic") else .55)
        text(30, y, name or w.get("type") or w["slot"], 11, "B", w=80)
        columns = w.get("perks") or []
        if w.get("wanted") and not columns:  # free text: nothing to show as icons
            text(30, y + 5.3, w["wanted"], 9, "", "#dddddd", w=80)
        for j, column in enumerate(columns):
            for k, o in enumerate(column):
                icon(f"perk:{o['name']}", 30 + j * 7.8, y + 6 + k * 7, 6.4, round_=True, bg="#3d6f93" if k == 0 else "#25323d")
        x = 30 + len(columns) * 7.8 + 1.4
        for o in [*(w.get("mods") or []), *(w.get("masterworks") or [])]:
            icon(f"perk:{o['name']}", x, y + 6, 6.4, bg="#4a4636")
            frame(x, y + 6, 6.4, MOD_GOLD, 1, .25)
            x += 7.8
        y += max(21, 6 + 7 * max(map(len, columns), default=0)) + 4  # as tall as its longest perk column

    # artifact
    art = intent.get("artifact")
    if art:
        icon(f"artifact:{art['name']}", 6, y, 18, bg="#000000")
        frame(6, y, 18)
        text(27, y + .5, art["name"].upper(), 9, "", LABEL)
        for j, p in enumerate(art.get("perks") or []):
            icon(f"artifact:{p}", 27 + j * 10.5, y + 7, 9, round_=True, bg="#30534f")

    # stat targets: the minimums, then the other priorities in order
    stats = intent.get("stats") or {}
    mins = stats.get("minimums") or {}
    targets = [*mins, *(k for k in stats.get("priority") or [] if k not in mins)]
    if targets:
        top = 17
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(.25)
        with pdf.local_context(stroke_opacity=.27):
            pdf.rect(211, top, 22, len(targets) * 11 + 4, "D")
        for i, k in enumerate(targets):
            text(211, top + 4 + i * 11, f"≥{mins[k]}" if k in mins else "", 11, "", WHITE, w=14.5, align="R")
            icon(f"stat:{k}", 226.5, top + 3.7 + i * 11, 5.6)

    # armor: one row per slot, the piece when the intent fixes it, then the wanted mods
    armor = armor or {}
    exotic = intent["exotic"]["name"]
    for i, slot in enumerate(SLOTS):
        y = 17 + i * 28
        piece = armor.get(slot)
        if piece == exotic:
            text(258, y + .3, exotic, 10, "B", GOLD, w=38)
        if piece:
            icon(f"item:{piece}", 235, y, 21, bg="#000000")
        else:
            fill(235, y, 21, "#000000", .33)
            text(235, y + 9, slot, 7, "", SOFT, w=21, align="C")
        frame(235, y, 21, GOLD if piece == exotic else "#ffffff", 1 if piece == exotic else .55)
        for j, m in enumerate((intent.get("armor_mods") or {}).get(slot) or []):
            icon(f"mod:{m}", 258 + j * 11, y + 5.5, 10, bg="#2c4b52")
            frame(258 + j * 11, y + 5.5, 10, "#ffffff", .2, .25)
    if exotic not in armor.values():  # slot unknown (exotic not found, offline): below the armor rows
        text(235, 153, "EXOTIC", 7, "", LABEL, w=21, align="C")
        icon(f"item:{exotic}", 235, 157, 21, bg="#000000")
        frame(235, 157, 21, GOLD, 1)

    # armor set bonus, as the game's tooltip: a title band, then each perk's icon, name and effect
    y = MID_TOP
    for e in intent.get("sets") or []:
        perks = set_perks.get(e["set"]) or []
        fill(MID_X, y, MID_W, "#3a3036", .9, h=12)
        text(MID_X + 4, y + 2.8, e["set"].upper() + ("" if perks else f" ×{e['pieces']}"), 15, "B", WHITE, w=MID_W - 8)
        y += 12
        font(10)
        rows = [max(15, 8 + pdf.multi_cell(MID_W - 22, 4.4, clean(p.get("description") or ""), dry_run=True,
                                           output="HEIGHT")) for p in perks]
        if perks:
            fill(MID_X, y, MID_W, "#231d24", .85, h=sum(rows) + 3)
        y += 1.5
        for p, row in zip(perks, rows):
            icon(f"setperk:{p['name']}", MID_X + 4, y + 1.5, 12, round_=True, bg="#6f9fc0")
            text(MID_X + 20, y + 1.2, f"{p['pieces']} Piece | {p['name']}", 11, "B", WHITE, w=MID_W - 22)
            font(10, "", SOFT)
            pdf.set_xy(MID_X + 20, y + 6.5)
            pdf.multi_cell(MID_W - 22, 4.4, clean(p.get("description") or ""), align="L", max_line_height=4.4)
            y += row
        y += 4

    font(6, "", SOFT)
    pdf.set_xy(6, 203)
    pdf.cell(0, 3, clean(f"Generated by Overclocked Shell from {slug}.json"))
    return bytes(pdf.output()), warnings


def write(path: Path, s: dict, icons: dict[str, Path], armor=None, set_perks=None, tr=None, links=None) -> list[str]:
    """Writes the PDF; returns the warnings."""
    data, warnings = render(s, icons, armor=armor, slug=path.stem, set_perks=set_perks, tr=tr, links=links)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return warnings
