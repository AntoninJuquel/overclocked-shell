"""Compact definitions index (weapons, gear, plugs, misc, stats, socket categories), one file per manifest version.

Same shape as destiny-zen's ZenDefs, so ported consumers keep reading `defs["plugs"][hash]["n"]`.
"""
import json
import os
import re
from pathlib import Path

from shell.core import paths

GEAR_TYPES = {2, 14, 16, 21, 22, 24, 28}
MISC_TYPES = {1, 9}
MISC_BUCKET = 1469714392


def build_defs(items: dict, stats: dict, socket_categories: dict) -> dict:
    weapons, gear, plugs, misc = {}, {}, {}, {}
    for h, d in items.items():
        name = d.get("displayProperties", {}).get("name")
        if not name:
            continue
        item_type, type_name = d.get("itemType"), d.get("itemTypeDisplayName")
        inv = d.get("inventory", {})
        if item_type == 3:
            weapons[h] = {"n": name, "t": type_name, "r": inv.get("tierTypeName"),
                          "a": d.get("equippingBlock", {}).get("ammoType") or 0, "b": inv.get("bucketTypeHash") or 0,
                          "sc": [[c["socketCategoryHash"], c["socketIndexes"]]
                                 for c in d.get("sockets", {}).get("socketCategories", [])]}
        elif item_type in GEAR_TYPES or re.search("artifact", type_name or "", re.I):
            gear[h] = [name, type_name, d.get("classType", 3), inv.get("bucketTypeHash") or 0,
                       inv.get("tierTypeName") or ""]
        elif "plug" not in d and (item_type in MISC_TYPES or inv.get("bucketTypeHash") == MISC_BUCKET):
            misc[h] = name
        elif "plug" in d:
            plugs[h] = {"n": name, "t": type_name or "", "p": d["plug"].get("plugCategoryIdentifier") or ""}
    names = lambda table: {h: d["displayProperties"]["name"] for h, d in table.items()  # noqa: E731
                           if d.get("displayProperties", {}).get("name")}
    return {"weapons": weapons, "gear": gear, "plugs": plugs, "misc": misc,
            "stats": names(stats), "socketCategories": names(socket_categories)}


def load_defs(manifest, cache_dir: Path | None = None) -> dict:
    root = (cache_dir or paths.cache_dir()) / "defs"
    file = root / f"{re.sub(r'[^\w.-]', '_', manifest.version())}.json"
    if file.exists():
        return json.loads(file.read_text(encoding="utf-8"))
    defs = build_defs(manifest.table("DestinyInventoryItemDefinition", keep=False),
                      manifest.table("DestinyStatDefinition", keep=False),
                      manifest.table("DestinySocketCategoryDefinition", keep=False))
    root.mkdir(parents=True, exist_ok=True)
    tmp = file.with_suffix(".tmp")
    tmp.write_text(json.dumps(defs, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, file)
    for old in root.iterdir():
        if old != file:
            old.unlink(missing_ok=True)
    return defs
