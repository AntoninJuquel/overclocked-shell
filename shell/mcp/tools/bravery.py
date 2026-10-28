"""Ultimate Bravery: roll a random build from the player's items into the build sheet `bravery`, which the usual
equip flow (check_build, equip_plan, previews) applies. Nothing here writes to the account."""
import random
from datetime import date

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.engines import bravery
from shell.engines.account import character_id, get_profile, primary_membership
from shell.engines.builds import catalog, sheet
from shell.engines.builds.equip_plan import SUBCLASS_ITEMS
from shell.engines.builds.snapshot import read_snapshot
from shell.engines.loadout import equipped
from shell.mcp import tool

SLUG = "bravery"
PARTS = ("all", "subclass", "weapons", "armor", "mods")
RNG = random.Random()


def owned_elements(ctx: Context, cls: str) -> list[str]:
    """Elements of the subclasses the character owns (live, as get_equipped reads them)."""
    account = primary_membership(ctx.client)
    profile = get_profile(ctx.client, account, [200, 201, 205, 300, 304, 305])
    worn = equipped(profile, ctx.defs, character_id(profile, cls.lower()))
    names = {s["name"] for s in [worn.get("subclass") or {}, *worn.get("other_subclasses", [])] if s.get("name")}
    return [el for el, name in SUBCLASS_ITEMS[cls].items() if name in names]


def _mods(ctx, armor_entries, armor_items):
    pool = bravery.slot_mods(ctx.manifest.table("DestinyInventoryItemDefinition", keep=False))
    return bravery.roll_mods(armor_entries, armor_items, pool, RNG)


def _exotic(armor_entries, armor_items):
    exotic = {x["itemId"] for x in armor_items if x.get("rarity") == "Exotic"}
    return next(e["name"] for e in armor_entries if e["itemId"] in exotic)


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def roll_bravery(character: str, part: str = "all") -> dict:
        """Ultimate Bravery: a random build from the character's own items (titan, hunter or warlock) — random owned
subclass, super, abilities, aspects and as many fragments as they allow; one random weapon per slot (at most one
exotic); one random armor piece per slot (exactly one exotic); random slot mods that fit. part: all, subclass,
weapons, armor (re-rolls mods too) or mods, keeping the rest of the last roll. Writes build sheet "bravery"
(profile/builds/bravery.json + .md, overwritten each roll); equip it with the equip-build flow (equip_plan,
previews). Reads the inventory snapshot: refresh_inventory first."""
        cls = next((c for c in SUBCLASS_ITEMS if c.lower() == (character or "").strip().lower()), None)
        if cls is None:
            raise ToolError("character is titan, hunter or warlock")
        if part not in PARTS:
            raise ToolError(f"part is one of {', '.join(PARTS)}")
        path = sheet.path_for(SLUG)
        try:
            armor_items, taken = read_snapshot("armor")
            weapon_items, _ = read_snapshot("weapons")
            if part == "all":
                s = {"name": f"Ultimate Bravery — {date.today().isoformat()}", "class": cls,
                     "activity": "Ultimate Bravery", "concept": "Random build, chaos on purpose.",
                     "subclass": None, "intent": {"exotic": {"name": "?"}}, "resolved": {}}
            else:
                if not path.exists():
                    raise ToolError("roll a build first (part=all)")
                s = sheet.load(path)
                if s["class"] != cls:
                    raise ToolError(f"the last roll is for {s['class']}: roll a new one with part=all")
            res = s["resolved"]
            res["date"] = date.today().isoformat()
            if part in ("all", "subclass"):
                elements = owned_elements(ctx, cls)
                if not elements:
                    raise ToolError(f"no subclass found for {cls}")
                s["subclass"] = bravery.roll_subclass(cls, elements, catalog.load_catalog(ctx.manifest)["subclass"],
                                                      RNG)
            if part in ("all", "weapons"):
                res["weapons"] = bravery.roll_weapons(weapon_items, RNG, cls)
            if part in ("all", "armor"):
                res["armor"] = bravery.roll_armor(armor_items, cls, RNG)
                s["intent"]["exotic"] = {"name": _exotic(res["armor"], armor_items)}
            if part in ("all", "armor", "mods"):
                mods = _mods(ctx, res["armor"], armor_items)
                for a in res["armor"]:
                    a["mods"] = mods.get(a["slot"], [])
                s["intent"]["armor_mods"] = {slot: m for slot, m in mods.items() if m}
            sheet.save(path, s)
        except (FileNotFoundError, ValueError) as e:   # SheetError included
            raise ToolError(str(e)) from e
        return {"slug": SLUG, "subclass": s["subclass"], "weapons": res["weapons"], "armor": res["armor"],
                "mods": s["intent"].get("armor_mods", {}), "md": str(path.with_suffix(".md")), "snapshot": taken}
