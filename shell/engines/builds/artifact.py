"""Artifact perks of a sheet: check (compendium) and placement in the artifact's sockets."""
import re
from pathlib import Path

from shell.engines.builds.rules import ARTIFACT_SOCKET_COLUMNS
from shell.engines.builds.stats import compendium_dir, entries
from shell.sources.aegis import lookup as aegis
from shell.sources.aegis.names import norm

EMPTY = "Empty Artifact Mod"
AEGIS_TIER = "Tier (ANALYSIS)"
_SEASON = re.compile(r"\s*\([^)]*\)$")


def load(compendium: Path | None = None):
    """{artifact: {perk: column}} from artifact-perks.md (artifact name without the season in parentheses)."""
    path = Path(compendium if compendium is not None else compendium_dir()) / "artifact-perks.md"
    if not path.exists():
        raise ValueError(f"{path.name} missing: run refresh_references(source=\"compendium\")")
    out = {}
    for name, attrs in entries(path):
        col = attrs.get("column", "")
        if not col.isdigit():
            continue
        out.setdefault(_SEASON.sub("", attrs.get("section", "")), {})[name] = int(col)
    return out


def assign(perks, columns):
    """[{name, socketIndex}] for every socket: highest column perks first, each in the first free socket that
    accepts it; the remaining sockets are emptied. ValueError when it cannot be done."""
    placed = {}
    for perk in sorted(perks, key=lambda p: -columns[p]):     # stable sort: the sheet's order is kept
        free = [i for i, top in enumerate(ARTIFACT_SOCKET_COLUMNS) if i not in placed and top >= columns[perk]]
        if not free:
            raise ValueError(f"no room left for {perk} (column {columns[perk]})")
        placed[free[0]] = perk
    return [{"name": placed.get(i, EMPTY), "socketIndex": i} for i in range(len(ARTIFACT_SOCKET_COLUMNS))]


def check(intent, known):
    """Problems of intent.artifact (empty list = valid)."""
    name, perks = intent.get("name"), intent.get("perks", [])
    if name not in known:
        close = [k for k in known if k.lower() == str(name).lower()]
        hint = f" (expected: {close[0]})" if close else f" (known: {', '.join(sorted(known))})"
        return [f"unknown artifact: {name}{hint}"]
    columns = known[name]
    problems = [f"{p} is listed twice" for p in dict.fromkeys(p for p in perks if perks.count(p) > 1)]
    problems += [f"{p} is not a perk of {name}" for p in perks if p not in columns]
    if problems:
        return problems
    n = len(ARTIFACT_SOCKET_COLUMNS)
    top = sum(1 for c in ARTIFACT_SOCKET_COLUMNS if c >= 3)
    mid = sum(1 for c in ARTIFACT_SOCKET_COLUMNS if c >= 2)
    by_col = [columns[p] for p in perks]
    if len(perks) > n:
        problems.append(f"at most {n} perks")
    if sum(1 for c in by_col if c >= 3) > top:
        problems.append(f"at most {top} column 3 perks")
    if sum(1 for c in by_col if c >= 2) > mid:
        problems.append(f"at most {mid} column 2 or 3 perks")
    return problems


def _with_tier(perk, artifact=""):
    """"Supernova (S)": Aegis tier of this perk (Artifact Mods), or the name alone. A mod is rated per artifact:
    rows of this artifact are preferred (normalized name contained in the other or the reverse), otherwise the
    best row whatever its "Artifact" column."""
    found = aegis.find("endgame", "artifact-mods", perk)
    key = norm(artifact)
    mine = [r for r in found if key and norm(r.get("Artifact") or "")
            and (key in norm(r["Artifact"]) or norm(r["Artifact"]) in key)]
    b = aegis.best(mine or found, tier=AEGIS_TIER)
    return f"{perk} ({b[AEGIS_TIER]})" if b and b.get(AEGIS_TIER) else perk


def list_lines(known):
    """Each artifact, then its perks per column with their Aegis tier."""
    out = []
    for art, perks in known.items():
        out.append(f"{art}:")
        for col in sorted(set(perks.values())):
            out.append(f"  column {col}: {', '.join(_with_tier(p, art) for p, c in perks.items() if c == col)}")
    return out
