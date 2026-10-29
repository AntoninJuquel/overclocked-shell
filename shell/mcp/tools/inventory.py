"""Inventory snapshot (armor and weapons) kept in-process; Claude gets filtered, size-limited views."""
import json
import os
import threading

from mcp.server.mcpserver import MCPServer

from shell.context import Context
from shell.core import paths
from shell.engines.account import get_profile, primary_membership
from shell.engines.inventory import armor_rows, weapon_rows
from shell.mcp import tool

COMPONENTS = [102, 200, 201, 205, 300, 304, 305, 310]
ARMOR_FIELDS = ("itemId", "name", "slot", "classType", "rarity", "location", "locked", "gearTier", "stats", "total",
                "tunedStat", "plugs")
MAX_LIMIT = 100


def _has(value: str | None, wanted: str | None, exact: bool = True) -> bool:
    if not wanted:
        return True
    value, wanted = (value or "").casefold(), wanted.casefold()
    return value == wanted if exact else wanted in value


def _page(items: list[dict], limit: int, offset: int) -> dict:
    limit, offset = max(1, min(limit, MAX_LIMIT)), max(0, offset)
    return {"total": len(items), "offset": offset, "truncated": offset + limit < len(items),
            "items": items[offset:offset + limit]}


def register(mcp: MCPServer, ctx: Context) -> None:
    snapshot: dict[str, list[dict]] = {}
    lock = threading.Lock()  # parallel first calls must share one profile fetch

    def refresh() -> dict:
        with lock:
            return _refresh()

    def _refresh() -> dict:
        profile = get_profile(ctx.client, primary_membership(ctx.client), COMPONENTS)
        snapshot["armor"], snapshot["weapons"] = armor_rows(profile, ctx.defs), weapon_rows(profile, ctx.defs)
        folder = paths.profile_dir() / "inventory"
        folder.mkdir(parents=True, exist_ok=True)
        for kind, rows in snapshot.items():
            tmp = folder / f"{kind}.tmp"
            tmp.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, folder / f"{kind}.json")
        return {"armor": len(snapshot["armor"]), "weapons": len(snapshot["weapons"]), "saved_to": str(folder)}

    def rows(kind: str) -> list[dict]:
        with lock:
            if not snapshot:
                _refresh()
            return snapshot[kind]

    @tool(mcp)
    def refresh_inventory() -> dict:
        """Re-read every armor piece and weapon (vault and all characters) from Bungie. Use after the player
        changed their inventory in game; other inventory tools read the last snapshot."""
        return refresh()

    @tool(mcp)
    def find_armor(class_type: str | None = None, slot: str | None = None, name: str | None = None,
                   rarity: str | None = None, limit: int = 25, offset: int = 0) -> dict:
        """Search the armor snapshot. class_type: Titan/Hunter/Warlock (class-agnostic pieces included);
        slot: Helmet/Gauntlets/Chest/Legs/Class Item; rarity: Exotic/Legendary; name: substring. Stats are live
        values (mods and masterwork included). limit at most 100; page with offset."""
        found = [{k: r[k] for k in ARMOR_FIELDS} for r in rows("armor")
                 if (r["classType"] == "Any" or _has(r["classType"], class_type)) and _has(r["slot"], slot) and _has(r["rarity"], rarity)
                 and _has(r["name"], name, exact=False)]
        return _page(found, limit, offset)

    @tool(mcp)
    def find_weapons(type: str | None = None, element: str | None = None, name: str | None = None,
                     perk: str | None = None, limit: int = 25, offset: int = 0) -> dict:
        """Search the weapon snapshot. type: e.g. Auto Rifle; element: Kinetic/Arc/Solar/Void/Stasis/Strand;
        name: substring; perk: substring matched against every perk option the weapon can roll in its columns.
        limit at most 100; page with offset."""
        found = []
        for r in rows("weapons"):
            options = (o["name"] for c in r["columns"] for o in c["options"])
            if (_has(r["type"], type) and _has(r["element"], element) and _has(r["name"], name, exact=False)
                    and (not perk or any(_has(o, perk, exact=False) for o in options))):
                found.append({"itemId": r["itemId"], "name": r["name"], "type": r["type"], "element": r["element"],
                              "rarity": r["rarity"], "location": r["location"], "locked": r["locked"],
                              "crafted": r["crafted"], "frame": r["frame"],
                              "perks": [c["selected"] for c in r["columns"]],
                              "masterwork": r["masterwork"], "mod": r["mod"]})
        return _page(found, limit, offset)
