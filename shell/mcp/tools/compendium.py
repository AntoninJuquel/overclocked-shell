"""Exact game values: Compendium entries by name."""
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.mcp import tool
from shell.sources.compendium import folder, lookup

MAX_LIMIT = 30


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def compendium_lookup(name: str, file: str | None = None, limit: int = 10) -> dict:
        """Compendium entries by name (case, punctuation and small words ignored; else entries containing it).
matches: {file, section, name, fetched, text}, every copy of the name (compare `section` and the attributes);
partial: true when the matches' names are only part of `name` ("Siphon" for "Arc Siphon"): check they are the right
thing; more: matches left out; suggestions: closest names when nothing matches exactly. file: a tab to search only
(e.g. armor-mods; a section's remarks are its entry "Notes"). limit at most 30."""
        if not (folder() / "index.md").exists():
            raise ToolError("Compendium missing: run refresh_references(source=\"compendium\").")
        if len(name.strip()) < 3:
            raise ToolError("name needs at least 3 characters")
        return lookup.find(name, file, max(1, min(limit, MAX_LIMIT)))
