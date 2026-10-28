"""This week's context: milestones, Portal / focused activities with rewards, vendor sales."""
import json
import os
from datetime import datetime, timezone

from mcp.server.mcpserver import MCPServer

from shell.context import Context
from shell.core import paths
from shell.engines.account import character_id, get_profile, primary_membership
from shell.engines.context import build_context
from shell.mcp import tool


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def refresh_context(character: str) -> dict:
        """Read this week's milestones, available activities (focused ones and their rewards) and vendor sales for
        one character (titan, hunter or warlock), and save them to profile/context/<UTC date>.json for the TODO."""
        account = primary_membership(ctx.client)
        profile = get_profile(ctx.client, account, [200, 204])
        cid = character_id(profile, character)
        milestones = ctx.client.get("/Destiny2/Milestones/")
        vendors = ctx.client.get(f"/Destiny2/{account['membershipType']}/Profile/{account['membershipId']}/"
                                 f"Character/{cid}/Vendors/", params={"components": "400,402"}, auth=True)
        generated = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        context = build_context(character, cid, milestones, profile, vendors, generated)
        folder = paths.profile_dir() / "context"
        folder.mkdir(parents=True, exist_ok=True)
        file = folder / f"{generated[:10]}.json"
        tmp = file.with_suffix(".tmp")
        tmp.write_text(json.dumps(context, indent=1), encoding="utf-8")
        os.replace(tmp, file)
        return {"milestones": len(context["milestones"]), "activities": len(context["activities"]),
                "focused": sum(a["focused"] for a in context["activities"]), "vendors": len(context["vendors"]),
                "saved_to": str(file)}
