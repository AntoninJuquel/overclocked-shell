"""DIM weapon wishlists (default: MrCharles' Aegis list, grade >= B), cached in cache/wishlists/.

DIM matching rule: a roll matches a line when every perk of the line is among the weapon's options
(all columns). Enhanced perks compare by name, so "Enhanced X" == "X".
"""
import re
from collections import defaultdict
from pathlib import Path

from shell.core import paths
from shell.sources import report
from shell.sources.sheets.fetch import cached

NAME = "wishlists"
DEFAULT_WISHLIST = "https://raw.githubusercontent.com/charlesxcaliber/DIMAegisWeaponWishlist/main/MrCharlesWishlist_MRB_PPC1.txt"


def folder() -> Path:
    return paths.cache_dir() / "wishlists"


def cache_name(url: str) -> str:
    return re.sub(r"[^\w.-]", "_", url.rsplit("/", 1)[-1])


def _download(url: str, force: bool) -> tuple[Path, bool, bool]:
    """(path, stale, changed)."""
    path = folder() / cache_name(url)
    before = path.read_text(encoding="utf-8") if path.exists() else None
    text, stale = cached(url, path, force, validate=lambda t: "dimwishlist:" in t)
    return path, stale, text != before


def fetch(source: str = DEFAULT_WISHLIST, force: bool = False) -> tuple[Path, bool]:
    """(path, stale): a local path, or a URL cached under its sanitised file name. Raises OSError when a URL
    cannot be downloaded (or is not a wishlist) and nothing is cached."""
    if not re.match(r"https?://", source):
        return Path(source), False
    path = folder() / cache_name(source)
    if path.exists() and not force:   # no read here: the list is 23 MB
        return path, False
    path, stale, _ = _download(source, force)
    return path, stale


def refresh(force: bool = False, only: list[str] | None = None) -> dict:
    try:
        path, stale, changed = _download(DEFAULT_WISHLIST, force)
    except OSError as e:
        return report(NAME, folder(), errors=[str(e)])
    return report(NAME, folder(), changed=[path.name] if changed else [], stale=[path.name] if stale else [])


def norm_perk(name):
    return re.sub(r"^Enhanced ", "", name or "").strip().lower()


def norm_weapon(name):
    return re.sub(r"\s*\((Adept|Timelost|Harrowed|Baroque)\)$", "", name).strip().lower()


def load(path, plug_names):
    """-> {itemHash: [frozenset(perk names)]}, {itemHash: "tier #rank"}, {itemHash: name}"""
    rolls, notes, names = defaultdict(list), {}, {}
    current, note = None, ""
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line.startswith("//notes:"):
            m = re.search(r"Tier: (\w+)\. Rank: (\d+)", line)
            note = f"{m.group(1)} #{m.group(2)}" if m else ""
        elif line.startswith("//"):
            current, note = line[2:].strip(), ""
        elif line.startswith("dimwishlist:"):
            m = re.match(r"dimwishlist:item=(-?\d+)(?:&perks=([\d,]*))?", line)
            if not m:
                continue
            h = int(m.group(1))
            perks = frozenset(norm_perk(plug_names.get(p, p)) for p in (m.group(2) or "").split(",") if p)
            rolls[h].append(perks)
            names[h] = current
            if note:
                notes.setdefault(h, note)
    return rolls, notes, names
