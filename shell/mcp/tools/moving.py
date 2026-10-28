"""Move items between the vault and characters; pull from the postmaster."""
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.engines.account import character_id
from shell.engines.actions import Actions
from shell.engines.locations import bucket_of, load_locations
from shell.engines.moving import pull_postmaster, transfer
from shell.mcp import tool

MAX_IDS = 25


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def transfer_items(item_ids: list[str], to: str, dry_run: bool = True) -> dict:
        """Move up to 25 items to the vault or a character (to: vault, titan, hunter or warlock). Previews by
        default: show the player the preview, then call again with dry_run=false once they agree. A full
        character bucket gets room by sending one unrequested item of that slot to the vault."""
        if len(item_ids) > MAX_IDS:
            raise ToolError(f"At most {MAX_IDS} items per call.")
        membership, locations, class_of = load_locations(ctx.client, ctx.defs)
        return transfer(Actions(ctx.client, membership), locations, class_of, item_ids, to, dry_run,
                        bucket_of(ctx.defs))

    @tool(mcp)
    def pull_from_postmaster(character: str, item_ids: list[str] | None = None, pull_all: bool = False,
                             dry_run: bool = True) -> dict:
        """Without item_ids or pull_all: list a character's postmaster. Otherwise pull those items (or all).
        Previews by default; call again with dry_run=false once the player agrees."""
        membership, locations, class_of = load_locations(ctx.client, ctx.defs)
        cid = character_id({"characters": {"data": {c: {"classType": t} for c, t in class_of.items()}}}, character)
        return pull_postmaster(Actions(ctx.client, membership), locations, cid, item_ids, pull_all, dry_run)
