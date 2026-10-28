"""Lock / unlock items."""
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.engines.account import get_profile, primary_membership
from shell.engines.actions import Actions
from shell.engines.locations import LOCATION_COMPONENTS, read_locations
from shell.engines.locking import set_lock as lock_items
from shell.mcp import tool

MAX_IDS = 50


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def set_lock(item_ids: list[str], locked: bool, dry_run: bool = False) -> dict:
        """Lock (locked=true) or unlock up to 50 items by instance id. Reversible, so it acts unless dry_run.
        Items already in that state are left alone. Call refresh_inventory afterwards before reading locks."""
        if len(item_ids) > MAX_IDS:
            raise ToolError(f"At most {MAX_IDS} items per call.")
        membership = primary_membership(ctx.client)
        locations, class_of = read_locations(get_profile(ctx.client, membership, LOCATION_COMPONENTS), ctx.defs)
        return lock_items(Actions(ctx.client, membership), locations, class_of, item_ids, locked, dry_run)
