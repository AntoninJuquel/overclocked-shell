"""Fashion: for each piece of a look (ornaments and shaders per armor slot, read from a screenshot by the Ghost),
whether the player owns it (Collections), where it comes from (its collectible's source line) and whether Eververse
sells it this week. Pure: manifest tables, the collectibles state and the raw weekly context come in as data.

Manifest shapes (checked 2026-10-29): shaders have plug category `shader`; ornaments `armor_skins_<class>_<slot>`,
exotic ones `armor_skins_<class>_exotic_<slot>`. Every exotic of a class and slot shares one ornament plug set, so
the exotic an ornament fits comes from its description ("change the appearance of Nothing Manacles").
"""
import difflib
import re
from datetime import datetime

from shell.sources.aegis.names import norm

EVERVERSE = 3361454721
NOT_ACQUIRED = 1  # DestinyCollectibleState bit
SLOTS = {"head": "Helmet", "arms": "Gauntlets", "chest": "Chest", "legs": "Legs", "class": "Class Item"}
CLASSES = {0: "Titan", 1: "Hunter", 2: "Warlock"}
EXOTIC_TIER = 6
PACKAGE = 25  # itemType of an Eververse pack
ARTICLED = {"shader": "a shader", "ornament": "an ornament", "armor": "an armor piece"}
FOR_EXOTIC = re.compile(r"appearance of (?:the |your )?([^.\n]+)", re.I)


def _name(d):
    return (d.get("displayProperties") or {}).get("name") or ""


def _source(collectibles, d):
    text = (collectibles.get(str(d.get("collectibleHash"))) or {}).get("sourceString") or ""
    line = text.split("\n", 1)[0].strip()
    return line.removeprefix("Source:").strip() or None


def _exotic_names(items):
    """{lowercase name: name} of exotic armor."""
    return {_name(d).lower(): _name(d) for d in items.values()
            if d.get("itemType") == 2 and (d.get("inventory") or {}).get("tierType") == EXOTIC_TIER and _name(d)}


def _exotic_for(d, exotics):
    m = FOR_EXOTIC.search((d.get("displayProperties") or {}).get("description") or "")
    return exotics.get(m.group(1).strip().lower()) if m else None


def build_index(items: dict, collectibles: dict) -> dict:
    """{normalized name: [entry]} of shaders, ornaments and armor pieces."""
    exotics = _exotic_names(items)
    index = {}
    for h, d in items.items():
        name, cat = _name(d), (d.get("plug") or {}).get("plugCategoryIdentifier") or ""
        if not name:
            continue
        if cat == "shader":
            e = {"kind": "shader", "cls": None}
        elif cat.startswith("armor_skins_"):
            parts = cat.split("_")
            if len(parts) < 4 or parts[-1] not in SLOTS:
                continue
            e = {"kind": "ornament", "cls": parts[2].capitalize(), "slot": SLOTS[parts[-1]]}
            if parts[3] == "exotic":
                e["exotic_for"] = _exotic_for(d, exotics)
        elif d.get("itemType") == 2:
            e = {"kind": "armor", "cls": CLASSES.get(d.get("classType"))}
        else:
            continue
        e.update(hash=int(h), name=name, collectible=d.get("collectibleHash"), source=_source(collectibles, d))
        index.setdefault(norm(name), []).append(e)
    return index


def resolve(name: str, kind: str, cls: str, index: dict, slot: str | None = None) -> tuple[dict | None, str | None]:
    """(entry, problem). kind "ornament" also accepts an armor piece (some looks use the base armor); `slot`: the
    look's row, an ornament of another slot is refused."""
    kinds = ("ornament", "armor") if kind == "ornament" else (kind,)
    found = [e for e in index.get(norm(name), []) if e["kind"] in kinds]
    other = index.get(norm(name))
    if not found and other:
        return None, f"is {ARTICLED[other[0]['kind']]}"
    if not found:
        close = difflib.get_close_matches(norm(name), list(index), n=3, cutoff=0.85)
        names = [index[c][0]["name"] for c in close]
        return None, f"not found (close: {', '.join(names)})" if names else "not found"
    mine = [e for e in found if e["cls"] in (None, cls)]
    if not mine:
        return None, f"not for {cls}"
    if slot and any(e.get("slot") for e in mine):
        fitting = [e for e in mine if e.get("slot") in (None, slot)]
        if not fitting:
            return None, f"is a {mine[0]['slot']} ornament"
        mine = fitting
    # the ornament before the armor piece, then one with a collectible
    return sorted(mine, key=lambda e: (kinds.index(e["kind"]), e["collectible"] is None))[0], None


def owned(entry: dict, state: dict, inventory: set) -> bool | None:
    """True / False from Collections (or the inventory: item hashes, and normalized armor names since a copy of an
    armor piece can have another hash); None when the profile doesn't say."""
    if entry["hash"] in inventory or (entry["kind"] == "armor" and norm(entry["name"]) in inventory):
        return True
    if entry.get("collectible") is None or entry["collectible"] not in state:
        return None
    return not state[entry["collectible"]] & NOT_ACQUIRED


def _price(sale, items):
    return " + ".join(f"{c['quantity']} {_name(items.get(str(c['itemHash'])) or {}) or '?'}"
                      for c in sale.get("costs", []) if c.get("quantity")) or "free"


def _in_package(sale, entry, items):
    d = items.get(str(sale.get("itemHash"))) or {}
    if d.get("itemType") != PACKAGE:
        return None
    inside = {i.get("itemHash") for cat in (d.get("preview") or {}).get("derivedItemCategories", [])
              for i in cat.get("items", [])}
    return _name(d) if entry["hash"] in inside else None


def eververse(entry: dict, raw_context: dict | None, now: datetime, items: dict) -> str:
    unknown = "stock unknown (refresh_context)"
    vendor = next((v for v in (raw_context or {}).get("vendors", []) if v.get("vendorHash") == EVERVERSE), None)
    if vendor is None:
        return unknown
    until = vendor.get("nextRefreshDate") or ""
    try:
        if datetime.fromisoformat(until.replace("Z", "+00:00")) < now:
            return unknown
    except ValueError:
        return unknown
    seen_for = (raw_context.get("character") or "").capitalize()
    if entry.get("cls") and seen_for and entry["cls"] != seen_for:   # Eververse's stock differs per class
        return f"stock unknown (this week's data is for {seen_for}: refresh_context({entry['cls'].lower()}))"
    sales = vendor.get("sales", [])
    direct = [_price(x, items) for x in sales if x.get("itemHash") == entry["hash"]]
    if direct:
        return f"on sale: {' or '.join(direct)} until {until[:10]}"
    packs = [(name, _price(x, items)) for x in sales if (name := _in_package(x, entry, items))]
    if packs:
        return "on sale " + " or ".join(f"in {n}: {p}" for n, p in packs) + f" until {until[:10]}"
    return "not on sale this week"


def check(look, cls, index, state, inventory, raw_context, now, items) -> dict:
    """{rows: one per slot and kind, summary}."""
    rows = []
    for slot in look:
        for kind in ("ornament", "shader"):
            name = slot.get(kind)
            if not name:
                continue
            entry, problem = resolve(name, kind, cls, index, slot.get("slot"))
            row = {"slot": slot.get("slot"), "kind": kind, "name": name, "owned": None}
            if problem:
                row["problem"] = problem
            else:
                row.update(name=entry["name"], owned=owned(entry, state, inventory),
                           source=entry.get("source"), eververse=eververse(entry, raw_context, now, items))
                if entry.get("exotic_for"):
                    row["exotic_for"] = entry["exotic_for"]
            rows.append(row)
    missing = list(dict.fromkeys(f"{r['name']} ({r.get('source') or 'source unknown'})" for r in rows
                                 if r["owned"] is False))
    unknown = list(dict.fromkeys(r["name"] for r in rows if r["owned"] is None and "problem" not in r))
    lost = list(dict.fromkeys(r["name"] for r in rows if "problem" in r))
    parts = [f"{sum(r['owned'] is True for r in rows)} of {len(rows)} owned"]
    parts += [f"{label}: {', '.join(xs)}" for label, xs in (("missing", missing), ("unknown", unknown),
                                                           ("not found", lost)) if xs]
    return {"rows": rows, "summary": "; ".join(parts)}
