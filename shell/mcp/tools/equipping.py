"""Equip items (weapons, armor, subclass) on a character."""
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.engines.actions import Actions
from shell.engines.equipping import equip
from shell.engines.locations import bucket_of, load_locations
from shell.engines.moving import target_character
from shell.mcp import tool

MAX_IDS = 12


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def equip_items(character: str, item_ids: list[str], dry_run: bool = True) -> dict:
        """Equip up to 12 items (weapons, armor, subclass) on a character (titan, hunter or warlock), moving them
        there first. Previews by default: show the player the preview, then call again with dry_run=false once
        they agree. Call refresh_inventory afterwards."""
        if len(item_ids) > MAX_IDS:
            raise ToolError(f"At most {MAX_IDS} items per call.")
        if character.lower() == "vault":
            raise ToolError("Choose a character: titan, hunter or warlock.")
        membership, locations, class_of = load_locations(ctx.client, ctx.defs)
        cid = target_character(class_of, character)
        return equip(Actions(ctx.client, membership), locations, class_of, cid, item_ids, dry_run,
                     bucket_of(ctx.defs))
