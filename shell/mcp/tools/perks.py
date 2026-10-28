"""Select weapon perks."""
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.engines.account import get_profile, primary_membership
from shell.engines.actions import Actions
from shell.engines.inventory import weapon_rows
from shell.engines.locking import clean_ids
from shell.engines.perks import plan_perks
from shell.engines.sockets import apply
from shell.mcp import tool
from shell.mcp.tools.inventory import COMPONENTS

MAX_CHANGES, MAX_APPLIED = 50, 30


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def set_perks(changes: list[dict], dry_run: bool = True) -> dict:
        """Select perks on weapons among the options each column rolled. changes: up to 50
        [{"itemId": "...", "select": ["Perk name", ...]}]; at most 30 applied per call, the rest come back as
        deferred. Previews by default: show the player, then call again with dry_run=false once they agree."""
        if len(changes) > MAX_CHANGES:
            raise ToolError(f"At most {MAX_CHANGES} weapons per call.")
        membership = primary_membership(ctx.client)
        profile = get_profile(ctx.client, membership, COMPONENTS)
        rows = {r["itemId"]: r for r in weapon_rows(profile, ctx.defs)}
        first_character = next(iter(profile["characters"]["data"]))
        plans, notes = [], []
        for change in changes:
            row = rows.get(clean_ids([change["itemId"]])[0])
            if not row:
                notes.append(f"{change['itemId']}: weapon not found")
                continue
            weapon_plans, weapon_notes = plan_perks(row, row["characterId"] or first_character, change["select"])
            plans += weapon_plans
            notes += [f"{row['name']}: {n}" for n in weapon_notes]
        now, later = plans[:MAX_APPLIED], plans[MAX_APPLIED:]
        results = ["would change"] * len(now) if dry_run else apply(Actions(ctx.client, membership), now)
        results += ["deferred: call again"] * len(later)
        return {"dry_run": dry_run, "applied": results.count("done"), "notes": notes,
                "changes": [{"itemId": p["itemId"], "name": p["name"], "column": p["column"], "from": p["from"],
                             "to": p["to"], "result": r} for p, r in zip(plans, results)]}
