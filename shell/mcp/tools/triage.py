"""Vault triage: decide KEEP / JUNK, save the result to profile/triage/, apply locks, export DIM tags.

Asking for a triage is the go-ahead for its lock / unlock batches (reversible). Nothing is ever dismantled.
"""
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.core import paths
from shell.engines.account import get_profile, primary_membership
from shell.engines.actions import Actions
from shell.engines.armor_triage import armor_sets, lock_plan, triage_armor as decide_armor
from shell.engines.inventory import armor_rows, weapon_rows
from shell.engines.locations import load_locations
from shell.engines.locking import set_lock
from shell.engines.weapon_triage import triage_weapons as decide_weapons
from shell.mcp import tool
from shell.mcp.tools.inventory import COMPONENTS
from shell.outputs import dim_csv, triage_csv
from shell.sources import wishlists

KINDS = ("armor", "weapons")
MAX_REVIEW = 100
DIM_WARNING = ("DIM replaces the tag and note of every imported item; an empty note erases it. Import in DIM: "
               "Settings > Spreadsheets > import tags and notes, then search tag:junk.")


def folder():
    return paths.profile_dir() / "triage"


def read_rows(ctx: Context, kind: str) -> list[dict]:
    profile = get_profile(ctx.client, primary_membership(ctx.client), COMPONENTS)
    return armor_rows(profile, ctx.defs) if kind == "armor" else weapon_rows(profile, ctx.defs)


def _save(kind: str, rows: list[dict]) -> tuple[list[str], list[str]]:
    lock, unlock = lock_plan(rows)
    folder().mkdir(parents=True, exist_ok=True)
    doc = {"made": datetime.now(timezone.utc).isoformat(timespec="seconds"), "lock": lock, "unlock": unlock,
           "items": rows}
    tmp = folder() / f"{kind}.tmp"
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, folder() / f"{kind}.json")
    triage_csv.write(folder() / f"{kind}.csv", kind, rows)
    return lock, unlock


def _reason_kind(reason: str) -> str:
    """'beaten by X T3 — MW …' -> 'beaten', 'wishlist S #2' -> 'wishlist'."""
    return re.sub(r" (by|of) .*|:.*| —.*| [A-Z]+ #\d+$", "", reason)


def _summary(rows: list[dict], lock: list[str], unlock: list[str], review: list[dict]) -> dict:
    keep = [r for r in rows if r["decision"] == "KEEP"]
    junk = [r for r in rows if r["decision"] == "JUNK"]
    return {"keep": len(keep), "junk": len(junk), "to_lock": len(lock), "to_unlock": len(unlock),
            "keep_by_reason": Counter(_reason_kind(r["reason"]) for r in keep).most_common(),
            "junk_by_reason": Counter(_reason_kind(r["reason"]) for r in junk).most_common(),
            "review": [{"itemId": r["itemId"], "name": r["name"], "reason": r["reason"]} for r in review[:MAX_REVIEW]],
            "review_total": len(review), "saved_to": str(folder())}


def apply_plan(actions, locations: dict, class_of: dict, plan: dict) -> dict:
    """Locks then unlocks the saved ids; postmaster items are skipped (the game cannot lock them).
    Every id lands in exactly one of locked / unlocked / already / skipped / failed."""
    result = {"locked": 0, "unlocked": 0, "already": 0, "skipped": [], "failed": []}
    for key, locked in (("lock", True), ("unlock", False)):
        ids = []
        for item_id in plan[key]:
            loc = locations.get(item_id) or {}
            if loc.get("where") == "postmaster":
                result["skipped"].append({"itemId": item_id, "name": loc["name"], "result": "postmaster (skipped)"})
            else:
                ids.append(item_id)
        done = set_lock(actions, locations, class_of, ids, locked, dry_run=False)
        result["locked" if locked else "unlocked"] += done["changed"]
        result["already"] += sum(i["result"].startswith("already") for i in done["items"])
        result["failed"] += [i for i in done["items"] if i["result"] == "not found" or i["result"].startswith("failed")]
    return result


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def triage_armor() -> dict:
        """Armor triage on a fresh read of every piece (vault and all characters): keep the best copy per stat
distribution and set (projected masterwork stats), drop all legacy, ignore the postmaster. Saves
profile/triage/armor.json and armor.csv (one row per piece with its reason). `review` lists pieces now locked
that would be unlocked, excluding legacy. Then call apply_triage("armor")."""
        rows = decide_armor(read_rows(ctx, "armor"), armor_sets(ctx.manifest))
        lock, unlock = _save("armor", rows)
        review = [r for r in rows if r["decision"] == "JUNK" and r["locked"] and r["gearTier"] != 0]
        no_set = sorted({r["name"] for r in rows if r["gearTier"] >= 1 and r["rarity"] == "Legendary" and not r["set"]})
        by_class = lambda d: Counter(r["classType"] for r in rows if r["decision"] == d)  # noqa: E731
        return {**_summary(rows, lock, unlock, review), "keep_by_class": by_class("KEEP"),
                "junk_by_class": by_class("JUNK"), "no_set": no_set}

    @tool(mcp)
    def triage_weapons(wishlist: str | None = None, refresh_wishlist: bool = False) -> dict:
        """Weapon triage against a DIM wishlist (local path or URL; default MrCharles' Aegis list, grade >= B) on a
fresh read of every weapon: keep wishlist rolls (one copy per trait combination), crafted weapons and one copy
per exotic roll. Saves profile/triage/weapons.json and weapons.csv. `review` lists weapons now locked that
would be unlocked. Then call apply_triage("weapons")."""
        try:
            path, stale = wishlists.fetch(wishlist or wishlists.DEFAULT_WISHLIST, force=refresh_wishlist)
        except OSError as e:
            raise ToolError(f"wishlist: {e}") from e
        plug_names = {k: v["n"] for k, v in ctx.defs["plugs"].items()}
        rows = decide_weapons(read_rows(ctx, "weapons"), *wishlists.load(path, plug_names))
        lock, unlock = _save("weapons", rows)
        review = [r for r in rows if r["decision"] == "JUNK" and r["locked"]]
        return {**_summary(rows, lock, unlock, review), "wishlist": str(path), "wishlist_stale": stale}

    @tool(mcp)
    def apply_triage(kind: str) -> dict:
        """Apply the last saved triage of `kind` ("armor" or "weapons"): lock what it keeps, unlock what it drops.
Reads current locations first, so pieces dismantled or moved since are reported, not guessed. Call
refresh_inventory afterwards before reading locks."""
        if kind not in KINDS:
            raise ToolError("kind is 'armor' or 'weapons'.")
        file = folder() / f"{kind}.json"
        if not file.exists():
            raise ToolError(f"No saved {kind} triage. Run triage_{kind} first.")
        plan = json.loads(file.read_text(encoding="utf-8"))
        membership, locations, class_of = load_locations(ctx.client, ctx.defs)
        return apply_plan(Actions(ctx.client, membership), locations, class_of, plan)

    @tool(mcp)
    def export_dim_tags(notes: bool = True) -> dict:
        """Write profile/triage/dim_tags.csv from the saved armor and weapon triages: tag keep / junk and a note with
the reason. Tell the player the warning before they import it."""
        triaged = [item for kind in KINDS if (folder() / f"{kind}.json").exists()
                   for item in json.loads((folder() / f"{kind}.json").read_text(encoding="utf-8"))["items"]]
        if not triaged:
            raise ToolError("No saved triage. Run triage_armor or triage_weapons first.")
        rows = dim_csv.rows(triaged, notes)
        dim_csv.write(folder() / "dim_tags.csv", rows)
        return {"rows": len(rows), "keep": sum(r["Tag"] == "keep" for r in rows),
                "junk": sum(r["Tag"] == "junk" for r in rows), "saved_to": str(folder() / "dim_tags.csv"),
                "warning": DIM_WARNING}
