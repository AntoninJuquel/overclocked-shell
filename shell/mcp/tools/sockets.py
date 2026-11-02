"""Change sockets: armor / weapon mods, subclass super, abilities, aspects, fragments, artifact perks."""
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.engines.account import get_profile, primary_membership
from shell.engines.actions import Actions
from shell.engines.locking import clean_ids
from shell.engines.sockets import apply, candidates, plan_item
from shell.mcp import tool

MAX_CHANGES, MAX_ACTIONS = 10, 30


def plan_sockets(ctx: Context, changes: list[dict], definitions: dict, force: bool = False) -> tuple:
    """(plans, notes, membership). `definitions`: memo of the manifest definitions, read one by one."""
    def definition(kind: str, h: int) -> dict:
        if (kind, h) not in definitions:
            definitions[kind, h] = ctx.client.get(f"/Destiny2/Manifest/{kind}/{h}/") or {}
        return definitions[kind, h]

    membership = primary_membership(ctx.client)
    base = f"/Destiny2/{membership['membershipType']}/Profile/{membership['membershipId']}"
    profile = get_profile(ctx.client, membership, [200, 305])
    first_character = next(iter(profile["characters"]["data"]))
    profile_sets = profile.get("profilePlugSets", {}).get("data", {}).get("plugs", {})
    character_sets = profile.get("characterPlugSets", {}).get("data", {})
    plans, notes = [], []
    for change in changes:
        item_id = clean_ids([change["itemId"]])[0]
        if not item_id.isdigit():  # ids go into the request path
            notes.append(f"{item_id}: not an item id")
            continue
        item = ctx.client.get(f"{base}/Item/{item_id}/", params={"components": "305,307,310"}, auth=True)
        item_hash = item.get("item", {}).get("data", {}).get("itemHash")
        if not item_hash:
            notes.append(f"{item_id}: item not found")
            continue
        cid = item.get("characterId") or first_character
        plug_sets = {k: v + character_sets.get(cid, {}).get("plugs", {}).get(k, []) for k, v in profile_sets.items()}
        for k, v in character_sets.get(cid, {}).get("plugs", {}).items():
            plug_sets.setdefault(k, v)
        reusable = item.get("reusablePlugs", {}).get("data", {}).get("plugs", {})
        item_def = definition("DestinyInventoryItemDefinition", item_hash)
        cands = candidates(item_def, reusable, plug_sets,
                           lambda ps: definition("DestinyPlugSetDefinition", ps))
        current = [s.get("plugHash") or 0 for s in item.get("sockets", {}).get("data", {}).get("sockets", [])]
        current += [0] * (len(cands) - len(current))
        name = item_def.get("displayProperties", {}).get("name", item_id)
        item_plans, item_notes = plan_item(item_id, cid, name, current, cands, reusable, change["plugs"],
                                           ctx.defs, force)
        plans += item_plans
        notes += [f"{name}: {n}" for n in item_notes]
    return plans, notes, membership


def run_sockets(ctx: Context, planned: tuple, dry_run: bool) -> dict:
    plans, notes, membership = planned
    results = ["would change"] * len(plans) if dry_run else apply(Actions(ctx.client, membership), plans)
    return {"dry_run": dry_run, "applied": results.count("done"), "notes": notes,
            "changes": [{"itemId": p["itemId"], "name": p["name"], "socketIndex": p["socketIndex"],
                         "from": p["from"], "to": p["to"], "result": r} for p, r in zip(plans, results)]}


def register(mcp: MCPServer, ctx: Context) -> None:
    definitions: dict[tuple[str, int], dict] = {}

    @tool(mcp)
    def set_sockets(changes: list[dict], dry_run: bool = True, force: bool = False) -> dict:
        """Insert plugs by name. changes: up to 10 [{"itemId": "...", "plugs": ["Name" | {"name": "Name",
        "socketIndex": n}]}], 30 socket actions at most. Plugs already installed are kept; "Empty ..." names free
        a socket. Works for armor and weapon mods, subclass items (super, abilities, aspects, fragments) and the
        artifact. Previews by default: show the player, then call again with dry_run=false once they agree.
        force re-inserts plugs that look installed (avoid)."""
        if len(changes) > MAX_CHANGES:
            raise ToolError(f"At most {MAX_CHANGES} items per call.")
        planned = plan_sockets(ctx, changes, definitions, force)
        if len(planned[0]) > MAX_ACTIONS:
            raise ToolError(f"That is {len(planned[0])} socket changes; split it into batches of {MAX_ACTIONS} or fewer.")
        return run_sockets(ctx, planned, dry_run)
