"""Aegis rankings (Endgame Analysis, Boss Damage) to choose the parts of a build.

One line per entry, sorted by tier then rank (dps views: by DPS, highest first): tier and rank | name | useful
columns, texts cut at `width`. With `type`, the Other tab's weapons (type not given by Aegis) come last, marked.
"""
import re
from dataclasses import dataclass
from types import SimpleNamespace

from shell.sources.aegis import config, lookup
from shell.sources.aegis.names import norm


@dataclass(frozen=True)
class View:
    slugs: tuple
    columns: tuple
    tier: str = "Tier"
    sheet: str = "endgame"


VIEWS = {
    "weapons": View(tuple(t.slug for t in config.weapon_tabs()),
                    ("Energy", "Frame", "Perk 1", "Perk 2", "Origin Trait", "Notes")),
    "exotic-weapons": View(("exotic-weapons",), ("Type", "Tags", "Usage")),
    "perks": View(("perks",), ("Tags", "Effect", "Usage")),
    "origin-traits": View(("origin-traits",), ("Tags", "Effect", "Description")),
    "sets": View(("set-bonuses",), ("Bonus", "Pcs", "Tags", "Description")),
    "artifact": View(("artifact-mods",), ("Artifact", "Tags", "Description"), tier="Tier (ANALYSIS)"),
    "subclasses": View(("subclasses",), ("Usage",)),
    "aspects": View(("aspects",), ("Subclass", "Class", "Fragments", "Usage")),
    "fragments": View(("fragments",), ("Subclass", "Stats", "Usage")),
}
WEAPON_TYPES = {t.slug: t.weapon_type or "" for t in config.weapon_tabs()}
CLASS_LETTER = {"hunter": "H", "titan": "T", "warlock": "W"}
DPS = {"sustained": ("sustained", "DPS", ("Type",)), "swap": ("swap", "true DPS", ("Type", "swap DPS"))}
UNTYPED_NOTE = "type not given by Aegis (Other tab)"
BOSS_COLUMNS = ("effective Health", "Mechanics", "Phase", "1 phase DPS")
ALL_VIEWS = (*VIEWS, *(f"dps-{k}" for k in DPS), "bosses", "name")
MISSING = "Aegis data missing: run refresh_references(source=\"aegis\")"


def _short(text, width):
    t = re.sub(r"\s*\n\s*", " / ", text or "")
    return t if len(t) <= width else t[:width - 1] + "…"


def _number(text):
    m = re.search(r"\d[\d,]*(?:\.\d+)?", text or "")
    return float(m.group().replace(",", "")) if m else 0.0


def _available(sheet, slugs):
    return any((lookup.data_dir() / sheet / f"{s}.json").exists() for s in slugs)


def _keep(r, slug, a):
    eq = lambda col, value: (r.get(col) or "").strip().lower() == value.lower()  # noqa: E731
    if a.type and slug in WEAPON_TYPES and WEAPON_TYPES[slug] and a.type.lower() not in WEAPON_TYPES[slug].lower():
        return False
    if a.type and slug not in WEAPON_TYPES:
        return False
    if a.element and not (eq("Energy", a.element) or eq("Subclass", a.element)):
        return False
    if a.cls:
        letter = CLASS_LETTER[a.cls.lower()]
        if letter not in (r.get("Class") or "") and not r["_name"].startswith(f"{letter} — "):
            return False
    if a.tag and a.tag.lower() not in (r.get("Tags") or "").lower():
        return False
    return True


def view_lines(name, a):
    v = VIEWS[name]
    found = [(slug, r) for slug in v.slugs for r in lookup.rows(v.sheet, slug) if _keep(r, slug, a)]
    if a.tier:
        found = [(s, r) for s, r in found if lookup.tier_key(r, v.tier)[0] <= lookup.TIERS.index(a.tier)]
    found.sort(key=lambda sr: lookup.tier_key(sr[1], v.tier))
    # type filter: the Other tab has no type (no column gives it); its rows pass the filter, last and marked,
    # so a weapon of the wanted type is not dropped by mistake.
    untyped = lambda slug: bool(a.type) and name == "weapons" and not WEAPON_TYPES.get(slug)  # noqa: E731
    found = [sr for sr in found if not untyped(sr[0])] + [sr for sr in found if untyped(sr[0])]
    lines = []
    for slug, r in found:
        parts = [lookup.tier_label(r, v.tier) or "—", _short(r["_name"], 40)]
        if name == "weapons":
            parts.append(r["_tab"])
        parts += [f"{c}: {_short(r.get(c), a.width)}" for c in v.columns if r.get(c)]
        if untyped(slug):
            parts.append(UNTYPED_NOTE)
        lines.append(" | ".join(parts))
    return lines


def dps_lines(kind, a):
    slug, col, extra = DPS[kind]
    found = sorted(lookup.rows("boss", slug), key=lambda r: -_number(r.get(col)))[:a.top]
    return [" | ".join([r.get(col) or "—", _short(r.get("Name") or r["_name"], 60),
                        *(f"{c}: {_short(r.get(c), a.width)}" for c in extra
                          if r.get(c) and not (c == "swap DPS" and r.get(c) == r.get(col)))]) for r in found]


def boss_lines(a):
    found = [r for r in lookup.rows("boss", "bosses")
             if not a.activity or a.activity.lower() in (r.get("Activity") or "").lower()]
    return [" | ".join([r["_name"], *(f"{c}: {_short(r.get(c), a.width)}" for c in BOSS_COLUMNS if r.get(c))])
            for r in found]


def name_lines(query, a):
    key, lines = norm(query), []
    for sheet in config.SHEETS.values():
        for spec in sheet.tabs:
            for r in lookup.rows(sheet.key, spec.slug):
                if key not in norm(r["_name"]):
                    continue
                lines.append(f"{sheet.key}/{spec.slug} | {lookup.tier_label(r, spec.tier or 'Tier') or '—'} | {r['_name']}")
                lines += [f"    {k}: {_short(v, a.width)}" for k, v in r.items() if not k.startswith("_") and v]
    return lines


def rank(view: str, type=None, element=None, class_type=None, tag=None, tier=None, activity=None, name=None,
         top=None, width=80) -> list[str]:
    """Lines of a view (see ALL_VIEWS). ValueError on a bad argument, FileNotFoundError without Aegis data."""
    if view not in ALL_VIEWS:
        raise ValueError(f"unknown view: {view} (views: {', '.join(ALL_VIEWS)})")
    top = 20 if top is None else top
    if top < 1:
        raise ValueError("top must be >= 1")
    tier = tier.upper() if tier else None
    if tier and tier not in lookup.TIERS:
        raise ValueError(f"tier is one of {', '.join(lookup.TIERS)}")
    if class_type and class_type.lower() not in CLASS_LETTER:
        raise ValueError("class_type is Hunter, Titan or Warlock")
    if view == "name" and not name:
        raise ValueError("the name view needs `name`")
    a = SimpleNamespace(type=type, element=element, cls=class_type, tag=tag, tier=tier, activity=activity,
                        top=top, width=width)
    if view in VIEWS:
        sheet, slugs = VIEWS[view].sheet, VIEWS[view].slugs
    elif view.startswith("dps-"):
        sheet, slugs = "boss", (DPS[view[4:]][0],)
    elif view == "bosses":
        sheet, slugs = "boss", ("bosses",)
    else:
        sheet, slugs = None, ()
    if sheet and not _available(sheet, slugs) or view == "name" and not lookup.data_dir().exists():
        raise FileNotFoundError(MISSING)
    if view in VIEWS:
        lines = view_lines(view, a)
    elif view.startswith("dps-"):
        lines = dps_lines(view[4:], a)
    elif view == "bosses":
        lines = boss_lines(a)
    else:
        lines = name_lines(name, a)
    return lines or ["no matching entry"]
