"""Overclocked Shell MCP server: every module in shell/mcp/tools/ registers its own tools."""
import importlib
import pkgutil

from mcp.server.mcpserver import MCPServer

from shell.context import Context
from shell.mcp import tools

INSTRUCTIONS = "Destiny 2 companion tools: the player's Bungie account, inventory and game data."


def build_server(ctx: Context) -> MCPServer:
    mcp = MCPServer("overclocked-shell", instructions=INSTRUCTIONS)
    for module in pkgutil.iter_modules(tools.__path__):
        importlib.import_module(f"{tools.__name__}.{module.name}").register(mcp, ctx)
    return mcp


def main() -> None:
    build_server(Context()).run()
