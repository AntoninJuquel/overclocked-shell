"""Situational recommender: the player's best weapons for a role, compared with what a character is wearing.

Read-only: reads the inventory snapshot and Aegis, never the account.
"""
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.engines import recommend
from shell.engines.builds import weapons
from shell.engines.builds.snapshot import read_snapshot
from shell.mcp import tool


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def recommend_weapons(character: str, role: str = "general", slot: str | None = None,
                          element: str | None = None, type: str | None = None, top: int = 5) -> dict:
        """Owned weapons ranked for a role, from the inventory snapshot (call refresh_inventory first).
role: general (Aegis Endgame tier, then wishlist grade) or dps (Aegis sustained DPS of the matching archetype or
exotic; unmatched weapons named in warnings). Filters slot (Kinetic/Energy/Power), element, type. character
(titan, hunter or warlock): whose equipped weapons the picks are compared with. Returns snapshot time, equipped
("slot | name | type | element [| exotic]"), picks ("rank | id | name | type | element | slot | ammo | Aegis tier
or DPS (setup) | grade | where · swap: replaces X · second exotic: unequip Y", one line per weapon name, at most
top), not_owned (general with a type: up to 3 better Aegis entries the player lacks), warnings."""
        try:
            items, taken = read_snapshot("weapons")
            result = recommend.recommend(items, weapons.load_grades(), character, role, slot, element, type,
                                         max(1, min(top, 20)))
        except (FileNotFoundError, ValueError) as e:
            raise ToolError(str(e)) from e
        return {"snapshot": taken, **result}
