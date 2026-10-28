"""Sources of a need: where to get it at any time (manifest, profile/todo/sources.json) and this week (context)."""
import json
import re
from pathlib import Path

from shell.engines.todo import catalog, state
from shell.sources.aegis.names import norm, strip_set

SOURCE_TYPES = ("activity", "vendor", "craft", "world")
CLASS_NAMES = {v: k for k, v in catalog.CLASS_TYPES.items()}
_QUOTED = re.compile(r'"(?P<name>[^"]+)"')
_NOT_A_SOURCE = re.compile(r"cannot be reacquired", re.IGNORECASE)
_EVERVERSE = re.compile(r"unlock this in Eververse", re.IGNORECASE)
_ACTIVITY_KIND = re.compile(r"\b(?P<kind>raid|dungeon)\b", re.IGNORECASE)
_SOURCE_PREFIX = re.compile(r"^Source:\s*", re.IGNORECASE)
_LEAD = re.compile(r"^(?:Source:|Complete the)\s*", re.IGNORECASE)
_PUNCT = " .,;:!\"'"


def parse_source_string(text):
    """A collectible's source string → source, from its first line only:
    raid or dungeon ("Source: Last Wish raid.", 'Source: Dungeon "Duality"') → activity
    `{type: activity, kind: raid|dungeon, name, detail}`; other text (quest, triumph, "Source: Pantheon",
    Eververse unlock) → free source `{type: world, name}` without "Source:"; empty or "cannot be
    reacquired" → None."""
    text = (text or "").strip()
    if not text or _NOT_A_SOURCE.search(text):
        return None
    line = text.splitlines()[0].strip()
    shown = _SOURCE_PREFIX.sub("", line).strip()
    if not shown:
        return None
    m = _ACTIVITY_KIND.search(line)
    if m is None or _EVERVERSE.search(text):
        return {"type": "world", "name": shown}
    quoted = _QUOTED.search(line)
    if quoted:
        name = quoted["name"].strip(" .,;:!")
    else:
        rest = _LEAD.sub("", line)
        km = _ACTIVITY_KIND.search(rest)
        before, after = rest[:km.start()].strip(_PUNCT), rest[km.end():].strip(_PUNCT)
        name = before or after
    if not name:
        return {"type": "world", "name": shown}
    return {"type": "activity", "kind": m["kind"].lower(), "name": name, "detail": line}


def _add(index, key, source):
    lst = index.setdefault(key, [])
    if source not in lst:
        lst.append(source)


def build_index(items, collectibles, sets_by_hash):
    """Manifest sources: {"by_set": {(set, class, slot): [source]}, "by_name": {name: [source]}}."""
    by_set, by_name = {}, {}
    for item_hash, d in items.items():
        c = collectibles.get(str(d.get("collectibleHash"))) if d.get("collectibleHash") else None
        source = parse_source_string((c or {}).get("sourceString"))
        if source is None:
            continue
        name = (d.get("displayProperties") or {}).get("name")
        if name:
            _add(by_name, name, source)
        info = sets_by_hash.get(int(item_hash))
        slot = catalog.SUBTYPE_SLOTS.get(d.get("itemSubType"))
        if info and slot:
            _add(by_set, (info["set"], CLASS_NAMES.get(d.get("classType")), slot), source)
    return {"by_set": by_set, "by_name": by_name}


def load_sources(path=None):
    """profile/todo/sources.json: {key: [{type, name, detail?}]} ({} when missing); ValueError when malformed."""
    path = Path(path) if path is not None else state.folder() / "sources.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    ok = isinstance(data, dict) and all(
        isinstance(v, list) and all(isinstance(s, dict) and s.get("type") in SOURCE_TYPES and s.get("name")
                                    for s in v)
        for v in data.values())
    if not ok:
        raise ValueError(f"{path.name}: expected {{key: [{{\"type\": {'|'.join(SOURCE_TYPES)}, \"name\": …}}]}}")
    return data


ANY_LEGENDARY = {"type": "world", "name": "any activity that gives legendary armor"}
MASTERWORK = {"type": "craft", "name": "masterwork in game"}
BOOSTED = ("focus", "bonus", "sale")
AVAILABILITY = {"boosted": 1.5, "known": 1.0, "unknown": 0.3}


def _named(index, name):
    """Manifest sources for this name, compared in normalized form (curly apostrophes, case, variant suffix);
    the normalized dictionary is built once and kept in the index."""
    if "by_norm" not in index:
        by_norm = {}
        for n, lst in index["by_name"].items():
            for s in lst:
                _add(by_norm, norm(n), s)
        index["by_norm"] = by_norm
    return list(index["by_norm"].get(norm(name), []))


def _aegis_sources(t, index):
    """Sources of an Aegis Shopping List item: manifest (by name, or by set), then each part of Aegis's Source
    column missing from those ("Vault of Glass", "Rahool"…)."""
    if t.get("type") == "set":
        key, out = strip_set(norm(t["name"])), []
        for (set_name, _, _), lst in sorted(index["by_set"].items(), key=lambda kv: tuple(map(str, kv[0]))):
            if strip_set(norm(set_name)) == key:
                out += [s for s in lst if s not in out]
    else:
        out = _named(index, t["name"])
    for part in (t.get("source") or "").split(","):
        part = part.strip()
        if part and part.lower() != "n/a" and all(s["name"].lower() != part.lower() for s in out):
            out.append({"type": "activity", "name": part, "detail": "Aegis Shopping List"})
    return out


def permanent_sources(need, index, manual):
    """Always-valid sources of a need. An entry of profile/todo/sources.json (key: the need id, then
    `set:<set>` for armor, `item:<name>` for a weapon) replaces the manifest's."""
    kind, t = need["kind"], need["target"]
    keys = [need["id"]]
    if kind == "armor" and t.get("set"):
        keys.append(f"set:{t['set']}")
    if kind == "weapon":
        keys.append(f"item:{t['name']}")
    if kind == "aegis":
        keys.append(f"set:{t['name']}" if t.get("type") == "set" else f"item:{t['name']}")
    for key in keys:
        if manual.get(key):
            return list(manual[key])
    if kind == "aegis":
        return _aegis_sources(t, index)
    if kind == "masterwork":
        return [MASTERWORK]
    if kind == "weapon":
        return list(index["by_name"].get(t["name"], []))
    if kind != "armor":
        return []   # catalysts and upgrades: no reliable source in the manifest
    if not t.get("set"):
        return [ANY_LEGENDARY]
    exact = index["by_set"].get((t["set"], t["class"], t["slot"]))
    if exact:
        return list(exact)
    out = []
    for (set_name, cls, _), lst in sorted(index["by_set"].items(), key=lambda kv: tuple(map(str, kv[0]))):
        if set_name == t["set"] and cls == t["class"]:
            out += [s for s in lst if s not in out]
    return out


def _matches(need, item):
    t = need["target"]
    if need["kind"] == "armor":
        return (t.get("set") is not None and item["type"] == "armor" and item["set"] == t["set"]
                and item["class"] == t["class"] and item["slot"] == t["slot"])
    if need["kind"] == "weapon":   # a catalyst bears its weapon's name but is not sold with it
        return item.get("name") == t.get("name")
    if need["kind"] == "aegis":
        if t.get("type") == "set":
            return item.get("type") == "armor" and strip_set(norm(item.get("set") or "")) == strip_set(norm(t["name"]))
        return norm(item.get("name") or "") == norm(t["name"])
    return False


def dated_sources(need, ctx, permanent):
    """This week's sources: context activities that reward the target or whose name starts with a raid or
    dungeon of the permanent sources (type `activity`), and vendors that sell it. A vendor without an end date
    (kiosk, permanent vendor) is not a boost. Without a context: []."""
    if not ctx:
        return []
    prefixes = [p["name"].lower() for p in permanent if p["type"] == "activity"]
    out = []

    def add(source):
        if source not in out:
            out.append(source)

    for a in ctx.get("activities", []):
        name = a.get("name") or ""
        if any(_matches(need, r) for r in a.get("rewards", [])) or any(name.lower().startswith(p) for p in prefixes):
            boosts = a.get("boosts", [])
            add({"type": "activity", "name": name, "boost": boosts[0] if boosts else None,
                 "until": a.get("until")})
    for v in ctx.get("vendors", []):
        item = next((i for i in v.get("items", []) if _matches(need, i)), None)
        if item:
            add({"type": "vendor", "name": v.get("name"), "boost": "sale" if v.get("until") else None,
                 "until": v.get("until"), "costs": item.get("costs", [])})
    return out


def availability(found):
    """1.5 when a source is boosted (focus, bonus, on sale for a limited time), 1.0 when a source is known,
    0.3 otherwise."""
    if any(s.get("boost") in BOOSTED for s in found):
        return AVAILABILITY["boosted"]
    return AVAILABILITY["known"] if found else AVAILABILITY["unknown"]
