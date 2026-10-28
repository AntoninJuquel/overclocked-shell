"""Raid encounter files (profile/raids/<raid>/<encounter>.json), written by the Ghost from the cached guides:
check them against the rules that keep them honest, and apply the player's callout renames
(profile/raids/<raid>/callouts.json, spot id -> name, shared by every encounter of the raid).

A position on the map needs a pos_source (a guide's text or image): the map never shows an invented spot.
"""
import json
import re
from pathlib import Path

from shell.core import paths

REQUIRED = ("raid", "encounter", "name", "sources", "floors", "spots", "roles", "phases")
KINDS = {"plate", "panel", "terminal", "bucket", "zone", "spawn", "door", "other"}
FIRETEAM = 6
SLUG = re.compile(r"^[a-z0-9-]+$")


def _slug(value):
    if not SLUG.fullmatch(value or ""):
        raise ValueError(f"not a slug: {value!r} (lowercase letters, digits and dashes)")
    return value


def folder(raid: str) -> Path:
    return paths.profile_dir() / "raids" / _slug(raid)


def encounters(raid: str) -> list[str]:
    f = folder(raid)
    return sorted(p.stem for p in f.glob("*.json") if p.stem != "callouts") if f.exists() else []


def load(raid: str, encounter: str) -> dict:
    path = folder(raid) / f"{_slug(encounter)}.json"
    if not path.exists():
        raise FileNotFoundError(f"no encounter file {raid}/{encounter}: build it with the raid-companion skill")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise ValueError(f"{raid}/{encounter}: invalid JSON: {e}") from e


def _dupes(kind, ids):
    seen, out = set(), []
    for i in ids:
        if i in seen:
            out.append(f"duplicate {kind} id: {i}")
        seen.add(i)
    return out


def _sourced(label, item, guides):
    found = item.get("sources") or []
    return [f"{label}: no source"] if not found else [f"{label}: unknown guide {g}" for g in found if g not in guides]


def _names_a_guide(pos_source, guides):
    """ "shacknews image 4", "grindout text: left of the door": a cached guide, then its image or its text."""
    first, _, rest = pos_source.partition(" ")
    return first in guides and (rest.startswith("text") or re.fullmatch(r"image \d+.*", rest) is not None)


def shared_ids(raid: str, encounter: str, enc: dict) -> list[str]:
    """Problems for spot ids another encounter of the raid also uses: renames are per raid, so ids must be unique."""
    out = []
    others = {e: {s.get("id") for s in load(raid, e).get("spots", [])} for e in encounters(raid) if e != encounter}
    for s in enc["spots"]:
        found = [e for e, ids in others.items() if s["id"] in ids]
        if found:
            out.append(f"spot {s['id']}: also in {', '.join(found)} (prefix spot ids with the encounter)")
    return out


def check(enc: dict, guides: set[str]) -> list[str]:
    """Problems of an encounter file; [] when valid. `guides`: the guides cached for its raid."""
    missing = [f"missing key: {k}" for k in REQUIRED if k not in enc]
    if missing:
        return missing
    floors = {f["id"]: {r["id"] for r in f.get("rooms", [])} for f in enc["floors"]}
    spots, roles = {s["id"] for s in enc["spots"]}, {r["id"] for r in enc["roles"]}
    problems = [f"sources: unknown guide {s['guide']}" for s in enc["sources"] if s["guide"] not in guides]
    problems += _dupes("floor", [f["id"] for f in enc["floors"]])
    problems += _dupes("room", [r["id"] for f in enc["floors"] for r in f.get("rooms", [])])
    problems += _dupes("spot", [s["id"] for s in enc["spots"]])
    problems += _dupes("role", [r["id"] for r in enc["roles"]])
    problems += _dupes("phase", [p["id"] for p in enc["phases"]])
    if not enc["phases"]:
        problems.append("phases: none")
    total = sum(r.get("count", 0) for r in enc["roles"])
    if total != FIRETEAM:
        problems.append(f"roles: counts sum to {total}, not {FIRETEAM}")
    for s in enc["spots"]:
        label = f"spot {s['id']}"
        if s.get("kind") not in KINDS:
            problems.append(f"{label}: unknown kind {s.get('kind')}")
        if s.get("floor") not in floors:
            problems.append(f"{label}: unknown floor {s.get('floor')}")
        elif s.get("room") and s["room"] not in floors[s["floor"]]:
            problems.append(f"{label}: unknown room {s['room']}")
        pos = s.get("pos")
        if pos is not None:
            if not (isinstance(pos, list) and len(pos) == 2 and all(isinstance(v, (int, float)) and 0 <= v <= 100
                                                                    for v in pos)):
                problems.append(f"{label}: position out of 0-100")
            if not s.get("pos_source"):
                problems.append(f"{label}: position without pos_source")
            elif not _names_a_guide(s["pos_source"], guides):
                problems.append(f"{label}: pos_source must name a guide's image or text")
        problems += _sourced(label, s, guides)
    for p in enc["phases"]:
        label = f"phase {p['id']}"
        problems += [f"{label}: steps for unknown role {r}" for r in p.get("steps", {}) if r not in roles]
        problems += [f"{label}: unknown spot {s}" for s in p.get("spots", []) if s not in spots]
        problems += _sourced(label, p, guides)
    return problems


def names(enc: dict, renames: dict) -> dict[str, str]:
    """Spot id -> name shown: the player's rename, else the guides' label."""
    return {s["id"]: renames.get(s["id"]) or s["name"] for s in enc["spots"]}


def _renames_path(raid):
    return folder(raid) / "callouts.json"


def load_renames(raid: str) -> dict:
    path = _renames_path(raid)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_rename(raid: str, spot_id: str, name: str | None) -> dict:
    """Sets (or with None removes) a rename; returns every rename of the raid."""
    renames = load_renames(raid)
    if name:
        renames[spot_id] = name
    else:
        renames.pop(spot_id, None)
    path = _renames_path(raid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(renames, indent=1, ensure_ascii=False), encoding="utf-8")
    return renames


def orphan_renames(raid: str) -> list[str]:
    """Warnings for renames whose spot no encounter of the raid has any more (rebuilt files)."""
    known = set()
    for e in encounters(raid):
        try:
            known |= {s["id"] for s in load(raid, e).get("spots", [])}
        except (ValueError, KeyError, TypeError):
            continue
    return [f"rename for unknown spot {i} ignored" for i in load_renames(raid) if i not in known]
