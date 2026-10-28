"""MCP layer. Tool modules in shell/mcp/tools/ define `register(mcp, ctx)` and declare tools with `tool(mcp)`."""
import functools

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.core.auth import NotSignedIn
from shell.core.bungie import BungieApiError
from shell.core.settings import SettingsError

PLAYER_FACING = (NotSignedIn, SettingsError, BungieApiError)


def tool(mcp: MCPServer, **kwargs):
    """Like `mcp.tool()`, but known errors reach Claude as one-line messages (the SDK hides other exceptions)."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kw):
            try:
                return fn(*args, **kw)
            except PLAYER_FACING as e:
                raise ToolError(str(e)) from e
        return mcp.tool(**kwargs)(wrapper)
    return decorator
