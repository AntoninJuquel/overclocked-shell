"""Reads Aegis data (cache/aegis/<sheet>/<slug>.json) for build scripts and the TODO.
Without data: empty lists and a single warning on stderr, never an error."""
import json
import re
import sys
from pathlib import Path

from shell.core import paths
from shell.sources.aegis import config
from shell.sources.aegis.names import norm

DATA = None  # None: paths.cache_dir() / "aegis", resolved at call time (tests may set a folder)
TIERS = "SABCDEF"
PERK_COLUMNS = ("Barrel", "Mag", "Perk 1", "Perk 2", "Origin Trait")
_warned = False
_cache = {}  # path -> (st_mtime_ns, document, index by name): a file is only reread when it changed


def data_dir() -> Path:
    return Path(DATA) if DATA is not None else paths.cache_dir() / "aegis"


def _warn(message):
    global _warned
    if not _warned:
        print(f"warning: {message}: run refresh_references(source='aegis')", file=sys.stderr)
        _warned = True


def _entry(sheet, slug):
    """(document, index {normalized name: rows with `_tab`}) of a tab, or None (warning) if it is missing or
    unreadable. The index is built once per version of the file."""
    path = data_dir() / sheet / f"{slug}.json"
    try:
        key = str(path)  # no resolve(): slow on Windows, and called once per weapon and per tab
        mtime = path.stat().st_mtime_ns
        if key in _cache and _cache[key][0] == mtime:
            return _cache[key][1:]
        doc = json.loads(path.read_text(encoding="utf-8"))
        index = {}
        for r in doc.get("rows", []):
            index.setdefault(norm(r["_name"]), []).append({**r, "_tab": doc.get("tab", slug)})
        _cache[key] = (mtime, doc, index)
        return doc, index
    except FileNotFoundError:
        _warn("Aegis data missing")
    except (OSError, ValueError):
        _warn(f"{sheet}/{path.name} unreadable")
    return None


def load_tab(sheet, slug):
    """Content of a tab's .json, or None (warning) if it is missing or unreadable."""
    entry = _entry(sheet, slug)
    return None if entry is None else entry[0]


def rows(sheet, slug):
    """Rows of a tab, each with `_tab` (tab name); [] without data."""
    doc = load_tab(sheet, slug)
    return [] if doc is None else [{**r, "_tab": doc.get("tab", slug)} for r in doc.get("rows", [])]


def find(sheet, slug, name):
    """Rows of a tab carrying this name (normalized comparison, all variants)."""
    entry = _entry(sheet, slug)
    return [] if entry is None else [dict(r) for r in entry[1].get(norm(name), [])]


def weapon_rows(name):
    """Rows of a weapon in the legendary weapon tabs and in Exotic Weapons."""
    out = []
    for spec in config.weapon_tabs():
        out += find("endgame", spec.slug, name)
    return out + find("endgame", "exotic-weapons", name)


def tier_key(row, tier="Tier", rank="#"):
    """Sort key: tier (S first, unknown last) then rank."""
    t = (row.get(tier) or "").strip()
    i = TIERS.index(t[0]) if t and t[0] in TIERS else len(TIERS)
    m = re.search(r"\d+", row.get(rank) or "")
    return i, int(m.group()) if m else 10 ** 9


def tier_label(row, tier="Tier", rank="#"):
    """"S #1", "B", or "" without tier or rank."""
    t, n = (row.get(tier) or "").strip(), (row.get(rank) or "").strip()
    return " ".join(x for x in (t, f"#{n}" if n else "") if x)


def best(found, tier="Tier", rank="#"):
    """The best ranked row, or None."""
    return min(found, key=lambda r: tier_key(r, tier, rank)) if found else None


def perk_names(row, columns=PERK_COLUMNS):
    """Normalized names of the perks Aegis recommends (one option per cell line)."""
    return {norm(line) for c in columns for line in (row.get(c) or "").split("\n") if line.strip()}
