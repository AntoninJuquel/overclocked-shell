"""Reference data: refresh the local copies of the sources in shell/sources/."""
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.mcp import tool
from shell.sources import sources


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def refresh_references(source: str | None = None, force: bool = False, tabs: list[str] | None = None) -> dict:
        """Refresh reference data into cache/<source>/ (all sources when source is omitted). Sources:
- compendium: Destiny Data Compendium, exact game values (cache/compendium/<tab>.md, index.md)
- aegis: Aegis Endgame Analysis and Boss Damage sheets, tiers / ranks / DPS / Shopping List
  (cache/aegis/<sheet>/<tab>.md and .json); changes.md lists tier and rank changes and the builds concerned
- bungie-api: Bungie API endpoints and schemas (cache/bungie-api/*.md)
- wishlists: the default DIM weapon wishlist (cache/wishlists/)
Without force, cached downloads are reused and only rendering runs; force re-downloads. tabs limits the
Compendium / Aegis to those tab names. Read or grep the Markdown afterwards to answer questions."""
        found = sources()
        if source is not None and source not in found:
            raise ToolError(f"Unknown source {source!r}. Known: {', '.join(sorted(found))}.")
        names = [source] if source else sorted(found)
        return {"reports": [found[n].refresh(force=force, only=tabs) for n in names]}
