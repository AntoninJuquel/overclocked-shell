"""Game names in the player's language (SHELL_LANGUAGE), from the Bungie manifest, as the game and DIM show them."""
from mcp.server.mcpserver import MCPServer

from shell.context import Context
from shell.engines import lexicon
from shell.mcp import tool


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def game_terms(names: list[str]) -> dict:
        """Localized in-game names for English game names (weapons, armor, exotics, perks, mods, aspects, fragments,
abilities, supers, sets, set perks, stats, slots, elements, weapon types, activities), from the manifest in the
player's language. Use before writing a game name to the player in their language; never translate one by hand.
Returns language, names ({English: localized}) and unchanged (same name in that language, or unknown to the
manifest: keep it as is)."""
        found, unchanged = lexicon.lookup(ctx.lexicon, names)
        return {"language": ctx.settings.language, "names": found, "unchanged": unchanged}
