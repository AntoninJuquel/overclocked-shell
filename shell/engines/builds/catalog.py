"""Build catalog: armor sets, armor mod energy costs and the subclass index, from the manifest.

One compact file per manifest version in cache/defs/, next to the defs index.
"""
import json
import os
import re
from pathlib import Path

from shell.core import paths
from shell.engines.armor_triage import armor_sets
from shell.engines.builds.stats import CLASSES, ELEMENTS

SCHEMA = 1  # bump when the catalog output changes, so existing caches are rebuilt

_CLASS = {c.lower(): c for c in CLASSES}
_ELEMENT = {"arc": "Arc", "solar": "Solar", "void": "Void", "stasis": "Stasis", "strand": "Strand",
            "prism": "Prismatic"}
ABILITY_KINDS = {"supers": "super", "grenades": "grenade", "prism_grenade": "grenade", "melee": "melee",
                 "class_abilities": "class", "movement": "jump"}
SUBCLASS_ITEM_TYPE = 16
CLASS_TYPES = {0: "Titan", 1: "Hunter", 2: "Warlock"}
KIND_LABELS = {"super": "Supers", "grenade": "Grenades", "melee": "Melee", "class": "Class abilities",
               "jump": "Jumps"}


def load_costs(defs):
    """{mod name: energy cost} for armor mods (`enhancements.*`) that have a cost.
    Several definitions with the same name: keep the highest cost (cautious)."""
    costs = {}
    for d in defs.values():
        plug = d.get("plug") or {}
        cost = (plug.get("energyCost") or {}).get("energyCost")
        if cost is None or not plug.get("plugCategoryIdentifier", "").startswith("enhancements."):
            continue
        name = d["displayProperties"]["name"]
        costs[name] = max(cost, costs.get(name, 0))
    return costs


def build_index(defs):
    """{element: {"aspects": {class: {name: slots}}, "fragments": {names}}} from
    DestinyInventoryItemDefinition (categories `<class>.<element>.aspects|totems`,
    `shared.<element>.fragments|trinkets`), and "fragment_sockets": {class: [indexes]} of the subclass item's
    fragment sockets (the first ones are active, the last ones disabled depending on the aspects)."""
    idx = {e: {"aspects": {c: {} for c in CLASSES}, "fragments": set(), "fragment_sockets": {},
               "abilities": {c: {k: set() for k in KIND_LABELS} for c in CLASSES}} for e in ELEMENTS}
    for d in defs.values():
        plug = d.get("plug") or {}
        parts = plug.get("plugCategoryIdentifier", "").split(".")
        name = (d.get("displayProperties") or {}).get("name", "")
        if len(parts) != 3 or not name or name.startswith("Empty") or parts[1] not in _ELEMENT:
            continue
        element = _ELEMENT[parts[1]]
        if parts[2] in ABILITY_KINDS:
            kind = ABILITY_KINDS[parts[2]]
            for c in (CLASSES if parts[0] == "shared" else [_CLASS[parts[0]]] if parts[0] in _CLASS else []):
                idx[element]["abilities"][c][kind].add(name)
        elif parts[0] in _CLASS and parts[2] in ("aspects", "totems"):
            slots = (plug.get("energyCapacity") or {}).get("capacityValue")
            if slots:
                idx[element]["aspects"][_CLASS[parts[0]]][name] = slots
        elif parts[0] == "shared" and parts[2] in ("fragments", "trinkets"):
            if (plug.get("energyCost") or {}).get("energyCost") is not None:
                idx[element]["fragments"].add(name)
    for d in defs.values():
        cls = CLASS_TYPES.get(d.get("classType"))
        if d.get("itemType") != SUBCLASS_ITEM_TYPE or not cls:
            continue
        # element: the abilities' one (`warlock.void.supers`); fragments: `shared.<element>.fragments`, or
        # `shared.fragments` without element (Stasis)
        elements, sockets = set(), []
        for i, entry in enumerate((d.get("sockets") or {}).get("socketEntries", [])):
            initial = defs.get(str(entry.get("singleInitialItemHash"))) or {}
            parts = ((initial.get("plug") or {}).get("plugCategoryIdentifier") or "").split(".")
            if parts[-1] in ("fragments", "trinkets"):
                sockets.append(i)
            elif len(parts) == 3 and parts[1] in _ELEMENT and parts[2] in ABILITY_KINDS:
                elements.add(_ELEMENT[parts[1]])
        if len(elements) == 1 and sockets:
            element = elements.pop()
            if len(sockets) > len(idx[element]["fragment_sockets"].get(cls, [])):
                idx[element]["fragment_sockets"][cls] = sockets
    return idx


def _dump(cat):
    """JSON-ready copy: name sets become sorted lists."""
    sub = {e: {**v, "fragments": sorted(v["fragments"]),
               "abilities": {c: {k: sorted(n) for k, n in kinds.items()} for c, kinds in v["abilities"].items()}}
           for e, v in cat["subclass"].items()}
    return {**cat, "subclass": sub}


def _restore(data):
    """Back to the in-memory shape: int item hashes, name sets."""
    for v in data["subclass"].values():
        v["fragments"] = set(v["fragments"])
        v["abilities"] = {c: {k: set(n) for k, n in kinds.items()} for c, kinds in v["abilities"].items()}
    data["sets"] = {int(h): s for h, s in data["sets"].items()}
    return data


def load_catalog(manifest, cache_dir: Path | None = None) -> dict:
    """{"sets": {itemHash: {"set", "bonus"}}, "costs": {mod: energy}, "subclass": index}, cached per version."""
    root = (cache_dir or paths.cache_dir()) / "defs"
    file = root / f"builds-s{SCHEMA}-{re.sub(r'[^\w.-]', '_', manifest.version())}.json"
    if file.exists():
        return _restore(json.loads(file.read_text(encoding="utf-8")))
    items = manifest.table("DestinyInventoryItemDefinition", keep=False)
    cat = {"sets": armor_sets(manifest), "costs": load_costs(items), "subclass": build_index(items)}
    del items
    root.mkdir(parents=True, exist_ok=True)
    tmp = file.with_suffix(".tmp")
    tmp.write_text(json.dumps(_dump(cat), separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, file)
    for old in root.glob("builds-*.json"):
        if old != file:
            old.unlink(missing_ok=True)
    return cat
