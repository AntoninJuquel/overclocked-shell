"""What is Distorted now and when a destination is next, from the cached rotation. Read-only."""
from datetime import datetime, timezone

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.engines import distortions as engine
from shell.mcp import tool
from shell.sources import distortions as source


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def distortions(hours: int = 24, destination: str | None = None) -> dict:
        """The hourly Distortion rotation (the Distorted destination drops one gear tier higher), in the machine's
local time: now ("now until 22:00: Europa"), schedule (one line per hour for `hours`, 1-168), and with
`destination` (e.g. "Throne World") its next 3 windows. Community-observed order, not published by Bungie:
quote source and fetched. Needs refresh_references(source="distortions") once."""
        if not 1 <= hours <= 168:
            raise ToolError("hours is between 1 and 168")
        rot = source.load()
        if rot is None:
            raise ToolError('No Distortion rotation cached: call refresh_references(source="distortions").')
        now = datetime.now(timezone.utc)
        warnings = []
        if engine.stale(rot, now):
            warnings.append(f"rotation fetched on {rot['fetched'][:10]}: refresh_references(source=\"distortions\", "
                            f"force=true) if the order may have changed")
        schedule = engine.schedule(rot, now, hours)
        result = {"now": schedule[0], "schedule": schedule, "offset": engine.offset(now), "source": rot["source"],
                  "fetched": rot["fetched"], "warnings": warnings}
        if destination:
            found = engine.match(destination, rot)
            if found is None:
                raise ToolError(f"not a Distortion destination: {destination} "
                                f"(destinations: {', '.join(rot['order'])})")
            result.update(destination=found,
                          next=[engine.fmt(h, now) for h in engine.windows(rot, found, now, 3)])
        return result
