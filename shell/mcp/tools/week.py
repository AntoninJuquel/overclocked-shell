"""The week's context for the TODO, from the raw context refresh_context saved."""
import json
from datetime import datetime, timezone

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.core import paths
from shell.engines.builds import catalog
from shell.engines.todo import week
from shell.mcp import tool


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def week_context() -> dict:
        """Build this week's context for the TODO from the newest raw context (profile/context/): focused and bonus
activities, vendors' gear, the reset window, with profile/todo/overrides.json applied. Saves
profile/todo/week/<UTC date>.json; returns a readable summary, warnings (e.g. a context from last week) and saved_to."""
        raws = sorted((paths.profile_dir() / "context").glob("*.json"))
        if not raws:
            raise ToolError("Call refresh_context(character) first.")
        try:
            overrides = week.load_overrides()
        except ValueError as e:
            raise ToolError(str(e)) from e
        raw = json.loads(raws[-1].read_text(encoding="utf-8"))
        tables = {key: ctx.manifest.table(table, keep=False) for key, table in week.TABLES.items()}
        sets_by_hash = catalog.load_catalog(ctx.manifest)["sets"]
        result = week.run(raw, tables, sets_by_hash, overrides, datetime.now(timezone.utc))
        return {"summary": week.summary(result), "warnings": result["warnings"],
                "saved_to": str(week.folder() / f"{result['date']}.json")}
