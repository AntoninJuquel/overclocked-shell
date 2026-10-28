"""farm_needs: what each build sheet and Aegis's Shopping List still need, into profile/todo/needs.json."""
from datetime import datetime, timezone

from mcp.server.mcpserver import MCPServer

from shell.context import Context
from shell.engines.builds import sheet as sheet_mod
from shell.engines.builds.catalog import load_catalog
from shell.engines.builds.snapshot import read_snapshot
from shell.engines.todo import catalog as todo_catalog, needs, state
from shell.mcp import tool
from shell.mcp.tools.builds import snapshot


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def farm_needs(no_aegis: bool = False) -> dict:
        """Farm needs of every build sheet (better armor pieces, set pieces, masterworks, weapon / catalyst /
upgrade gaps, each with its score gain) plus the Aegis Shopping List items the player lacks (skipped with
`no_aegis`). Reads the armor snapshot (required) and the weapon snapshot (optional: without it the Shopping List
weapons are skipped): call refresh_inventory first. Writes profile/todo/needs.json, syncs the statuses in
profile/todo/state.json (a need no longer found turns done, unless something could not be checked) and
regenerates every sheet's "To fetch" section. Returns the need count per kind, the total and the warnings."""
        armor, taken = snapshot("armor")
        warnings = []
        try:
            weapons, _ = read_snapshot("weapons")
        except FileNotFoundError:
            weapons = None   # shopping_needs warns about the skipped weapons
        except (OSError, ValueError) as e:
            weapons = None
            warnings.append(f"unreadable weapon snapshot ({e}): the Shopping List weapons are skipped")
        cat = load_catalog(ctx.manifest)
        sets = cat["sets"]
        defs = ctx.manifest.table("DestinyInventoryItemDefinition", keep=False)
        extra, extra_warnings, keep = needs.extra_needs(armor, sets, weapons, no_aegis)
        todo_dir = state.folder()
        doc = needs.run(sheet_mod.folder(), todo_dir, armor, sets, cat["costs"],
                        lambda cls: todo_catalog.set_slots(sets, defs, cls),
                        datetime.now(timezone.utc).date().isoformat(),
                        extra=extra, extra_warnings=warnings + extra_warnings, keep=keep)
        counts = {}
        for n in doc["needs"]:
            counts[n["kind"]] = counts.get(n["kind"], 0) + 1
        return {"counts": dict(sorted(counts.items())), "total": len(doc["needs"]), "warnings": doc["warnings"],
                "snapshot": taken, "saved_to": str(todo_dir / "needs.json")}
