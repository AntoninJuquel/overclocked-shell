"""What a character is wearing right now."""
from mcp.server.mcpserver import MCPServer

from shell.context import Context
from shell.engines.account import character_id, get_profile, primary_membership
from shell.engines.loadout import artifact_perks, equipped
from shell.mcp import tool


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def get_equipped(character: str) -> dict:
        """Equipped weapons and armor (live stats, mods), subclass (super, abilities, aspects, fragments), active
        artifact perks and armor stat totals for one character: titan, hunter or warlock."""
        account = primary_membership(ctx.client)
        profile = get_profile(ctx.client, account, [200, 201, 205, 300, 304, 305])
        result = equipped(profile, ctx.defs, character_id(profile, character))
        if result["artifact"]:
            item = ctx.client.get(f"/Destiny2/{account['membershipType']}/Profile/{account['membershipId']}/Item/"
                                  f"{result['artifact']['itemId']}/", params={"components": "305"}, auth=True)
            result["artifact"]["perks"] = artifact_perks(item, ctx.defs)
        return result
