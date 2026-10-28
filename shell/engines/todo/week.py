"""The week's context for the TODO: focused or bonus activities, gear on sale, the reset window.

Input: the raw context refresh_context saves in profile/context/<date>.json (destiny-zen's zen-context shape).
Names are resolved in the manifest, profile/todo/overrides.json applied, the result written to
profile/todo/week/<date>.json.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from shell.engines.todo import catalog, state

# Activity modifier that raises rewards; NOT_BONUS is excluded first (the raids' permanent
# "Exotic Drop Rate Boosts Gained" counter is not a bonus of the week).
BONUS = re.compile(r"\bdouble\b|\bbonus\b|increased rewards?", re.IGNORECASE)
NOT_BONUS = re.compile(r"exotic drop rate", re.IGNORECASE)
PERMANENT = "9999"   # nextRefreshDate of a vendor without rotation (9999-12-31)
# Kiosks: the API gives them the weekly reset as nextRefreshDate, but their stock does not rotate.
KIOSK = re.compile(r"^(.+ Exotics|Legacy Gear|Season of .+|Episode: .+|Strange Gear Offers)$")
ITEM_TYPES = {2: "armor", 3: "weapon"}
CLASS_NAMES = {v: k for k, v in catalog.CLASS_TYPES.items()}
TABLES = {"milestones": "DestinyMilestoneDefinition", "activities": "DestinyActivityDefinition",
          "modifiers": "DestinyActivityModifierDefinition", "vendors": "DestinyVendorDefinition",
          "items": "DestinyInventoryItemDefinition"}
DATE_ONLY = re.compile(r"\d{4}-\d{2}-\d{2}")
BOOSTS = ("focus", "bonus")


def folder() -> Path:
    """profile/todo/week/, resolved at call time."""
    return state.folder() / "week"


def name(table, item_hash):
    return ((table.get(str(item_hash)) or {}).get("displayProperties") or {}).get("name") or ""


def item_info(items, sets_by_hash, item_hash):
    """Weapon or armor: {hash, name, type, class, slot, set, tier}; None for anything else (materials, bounties…).
    `slot`: slot for armor, weapon type for a weapon; `tier`: rarity (Legendary, Exotic…)."""
    d = items.get(str(item_hash)) or {}
    kind = ITEM_TYPES.get(d.get("itemType"))
    if kind is None:
        return None
    armor = kind == "armor"
    return {"hash": item_hash, "name": name(items, item_hash), "type": kind,
            "class": CLASS_NAMES.get(d.get("classType")) if armor else None,
            "slot": catalog.SUBTYPE_SLOTS.get(d.get("itemSubType")) if armor else d.get("itemTypeDisplayName"),
            "set": (sets_by_hash.get(item_hash) or {}).get("set"),
            "tier": (d.get("inventory") or {}).get("tierTypeName") or None}


def _for_class(info, cls):
    """True if class `cls` can use the item (None: no filter); armor without a class is kept."""
    return cls is None or info["type"] != "armor" or info["class"] in (None, cls)


def _iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(text):
    """ISO date → aware UTC datetime. A bare `YYYY-MM-DD` = the end of that day (23:59:59 UTC); a date without a
    time zone is UTC. ValueError if the text is not a date."""
    if not isinstance(text, str):
        raise ValueError(f"invalid date {text!r}")
    if DATE_ONLY.fullmatch(text):
        return datetime.fromisoformat(text).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _norm(text):
    """Normalised date (`…Z` without milliseconds); None if missing or invalid."""
    try:
        return _iso(parse_time(text))
    except ValueError:
        return None


def _most_common(values):
    """Most frequent value (the earliest on a tie)."""
    return max(sorted(set(values)), key=values.count)


def reset_window(milestones, now):
    """(start, end) of the weekly reset: the milestones' most frequent end, then the most frequent start among the
    milestones with that end (a seasonal milestone does not give the start); otherwise Tuesday 17:00 UTC."""
    pairs = [(_norm(m.get("startDate")), _norm(m.get("endDate"))) for m in milestones]
    ends = [e for _, e in pairs if e]
    if ends:
        end = _most_common(ends)
        starts = [s for s, e in pairs if s and e == end]
        if starts:
            return _most_common(starts), end
    last = (now - timedelta(days=(now.weekday() - 1) % 7)).replace(hour=17, minute=0, second=0, microsecond=0)
    if last > now:
        last -= timedelta(days=7)
    return _iso(last), _iso(last + timedelta(days=7))


def boosts(focused, modifiers):
    """["focus"] if the activity is in the Portal's focus, ["bonus"] if a modifier raises rewards."""
    out = ["focus"] if focused else []
    if any(BONUS.search(m) and not NOT_BONUS.search(m) for m in modifiers):
        out.append("bonus")
    return out


def _add_activity(acts, tables, activity_hash, source, modifier_hashes, focused, rewards, until):
    """Adds or completes an activity's entry (one entry per hash, sources accumulated)."""
    mods = [n for n in (name(tables["modifiers"], h) for h in modifier_hashes) if n]
    e = acts.setdefault(activity_hash, {"hash": activity_hash, "name": name(tables["activities"], activity_hash),
                                        "sources": [], "boosts": [], "modifiers": [], "rewards": [],
                                        "until": until})
    for key, values in (("sources", [source]), ("boosts", boosts(focused, mods)), ("modifiers", mods),
                        ("rewards", rewards)):
        e[key] += [v for v in values if v not in e[key]]
    return e


def build_context(raw, tables, sets_by_hash, now):
    """The day's context from the raw context: milestone activities (all) and Portal ones (focused, bonus or giving
    gear), vendors' gear with its price (`until` None for a permanent vendor or a kiosk), the reset window. Armor
    for a class other than the raw context's character is left out."""
    milestones = raw.get("milestones", [])
    start, end = reset_window(milestones, now)
    cls = (raw.get("character") or "").capitalize()
    cls = cls if cls in catalog.CLASS_TYPES else None

    def gear(hashes):
        infos = (item_info(tables["items"], sets_by_hash, h) for h in hashes)
        return [i for i in infos if i and _for_class(i, cls)]

    acts, warnings = {}, []
    for m in milestones:
        for a in m.get("activities", []):
            e = _add_activity(acts, tables, a["activityHash"], "milestone", a["modifierHashes"], False, [],
                              m.get("endDate") or end)
            e["milestone"] = name(tables["milestones"], m["milestoneHash"])
    for a in raw.get("activities", []):
        mods = [name(tables["modifiers"], h) for h in a["modifierHashes"]]
        rewards = gear(a["rewardItemHashes"])
        if a["activityHash"] in acts or boosts(a["focused"], mods) or rewards:
            _add_activity(acts, tables, a["activityHash"], "portal", a["modifierHashes"], a["focused"], rewards,
                          end)
    vendors = []
    for v in raw.get("vendors", []):
        items = []
        for s in v["sales"]:
            for info in gear([s["itemHash"]]):
                items.append({**info, "costs": [{"name": name(tables["items"], c["itemHash"]),
                                                 "quantity": c.get("quantity")} for c in s.get("costs") or []]})
        if not items:
            continue
        refresh = v.get("nextRefreshDate")
        vendor_name = name(tables["vendors"], v["vendorHash"])
        permanent = not refresh or refresh.startswith(PERMANENT) or KIOSK.match(vendor_name)
        vendors.append({"hash": v["vendorHash"], "name": vendor_name, "until": None if permanent else refresh,
                        "items": items})
    generated = raw.get("generated")
    if parse_time(end) <= now:
        warnings.append(f"context from {(generated or '?')[:10]}: week ended {end[:10]}, call refresh_context")
    elif generated and parse_time(generated) < parse_time(start):
        warnings.append(f"context from {generated[:10]} is before the {start[:10]} reset: call refresh_context")
    return {"date": now.date().isoformat(), "generated": generated, "character": raw.get("character"),
            "reset": {"start": start, "end": end},
            "activities": sorted(acts.values(), key=lambda a: (not a["boosts"], a["name"])),
            "vendors": sorted(vendors, key=lambda v: v["name"]), "notes": [], "warnings": warnings}


def load_overrides(path=None):
    """profile/todo/overrides.json by default ({"activities": [], "notes": []} if missing); ValueError if the JSON
    is invalid or `activities` / `notes` is not a list of objects."""
    path = Path(path) if path is not None else state.folder() / "overrides.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: JSON object expected")
    out = {}
    for key in ("activities", "notes"):
        values = data.get(key, [])
        if not isinstance(values, list):
            raise ValueError(f'{path.name}: "{key}" must be a list')
        for i, v in enumerate(values):
            if not isinstance(v, dict):
                raise ValueError(f"{path.name}: {key}[{i}] must be an object")
        out[key] = values
    return out


def apply_overrides(ctx, overrides, now):
    """Applies the manual corrections, which win over the API. Returns a new context.
    A correction by name (case-insensitive) applies to every activity with that name; a missing `boost` keeps the
    boosts, `null` removes them; an invalid `until` date skips the entry with a warning."""
    out = json.loads(json.dumps(ctx))
    end = out["reset"]["end"]
    by_name = {}
    for a in out["activities"]:
        if a["name"]:
            by_name.setdefault(a["name"].lower(), []).append(a)
    for i, o in enumerate(overrides.get("activities", [])):
        try:
            until = _iso(parse_time(o.get("until") or end))
        except ValueError:
            out["warnings"].append(f"overrides.activities[{i}]: invalid date {o.get('until')!r}, skipped")
            continue
        if parse_time(until) < now:
            continue
        if not o.get("name"):
            out["warnings"].append(f"overrides.activities[{i}]: missing name, skipped")
            continue
        boost = o.get("boost")
        if boost is not None and boost not in BOOSTS:
            out["warnings"].append(f"overrides.activities[{i}]: unknown boost {boost!r} ({', '.join(BOOSTS)} or null)")
            continue
        entries = by_name.get(o["name"].lower())
        if not entries:
            entries = [{"hash": None, "name": o["name"], "sources": [], "boosts": [], "modifiers": [],
                        "rewards": [], "until": until}]
            out["activities"] += entries
            by_name[o["name"].lower()] = entries
        for e in entries:
            if "override" not in e["sources"]:
                e["sources"].append("override")
            if "boost" in o:
                e["boosts"] = [boost] if boost else []
            e["until"] = until
            if o.get("note"):
                e["note"] = o["note"]
    for i, n in enumerate(overrides.get("notes", [])):
        try:
            until = _iso(parse_time(n.get("until") or end))
        except ValueError:
            out["warnings"].append(f"overrides.notes[{i}]: invalid date {n.get('until')!r}, skipped")
            continue
        if n.get("text") and parse_time(until) >= now:
            out["notes"].append({"text": n["text"], "until": until})
    out["activities"].sort(key=lambda a: (not a["boosts"], a["name"]))
    return out


def run(raw, tables, sets_by_hash, overrides, now, out_dir=None):
    """Builds the context, applies the corrections and writes it to <out_dir or folder()>/<date>.json."""
    ctx = apply_overrides(build_context(raw, tables, sets_by_hash, now), overrides, now)
    state.write_json(Path(out_dir or folder()) / f"{ctx['date']}.json", ctx)
    return ctx


def summary(ctx):
    """Readable summary of the context (lines)."""
    end = ctx["reset"]["end"]
    lines = [f"Week until {end[:10]} (reset {end[11:16]} UTC)"]
    for boost, label in (("focus", "Focus"), ("bonus", "Bonus")):
        names = [a["name"] for a in ctx["activities"] if boost in a["boosts"]]
        if names:
            lines.append(f"{label}: {', '.join(names)}")
    weekly = sum(1 for v in ctx["vendors"] if v["until"] and v["until"][:10] == end[:10])
    lines.append(f"Vendors: {len(ctx['vendors'])} with gear ({weekly} until the reset)")
    lines += [f"Note: {n['text']}" for n in ctx["notes"]]
    return lines
