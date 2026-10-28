"""Build tools on the sheets in profile/builds/ and the inventory snapshot refresh_inventory saves."""
from datetime import date

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.engines.builds import artifact, equip_plan as equip_mod, inventory, optimize, sheet as sheet_mod
from shell.engines.builds.catalog import load_catalog
from shell.engines.builds.snapshot import read_snapshot
from shell.engines.builds.stats import fragment_stats
from shell.mcp import tool


def sheet_path(slug: str):
    """Path of an existing sheet; ToolError listing the sheets otherwise (also refuses paths outside the folder)."""
    slugs = sorted(p.stem for p in sheet_mod.folder().glob("*.json"))
    if slug not in slugs:
        raise ToolError(f"unknown build: {slug} (sheets: {', '.join(slugs) or 'none'})")
    return sheet_mod.path_for(slug)


def snapshot(kind: str) -> tuple[list[dict], str]:
    try:
        return read_snapshot(kind)
    except FileNotFoundError as e:
        raise ToolError(str(e)) from e


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def optimize_build(slug: str, top: int = 5, sets: list[str] | None = None, no_sets: bool = False,
                       write: bool = False, pick: int = 1, force: bool = False) -> dict:
        """Armor optimizer for build sheet `slug`: the exotic + 4 legendaries and their stat, tuning and filler
mods that meet the intent's minimums, then its priorities, then fewest masterworks and transfers. Reads the
armor snapshot: call refresh_inventory first when the player changed gear. `sets` ["Name:2", ...] or `no_sets`
replace the intent's sets (recorded in resolved.sets). `write` saves result `pick` into the sheet's `resolved`
(refused when it misses a minimum unless `force`). `complete: false` = search stopped early, results may not
be optimal; `feasible: false` = best 3 shown with their `deficit`."""
        if top < 1:
            raise ToolError("top must be >= 1")
        path = sheet_path(slug)
        items, taken = snapshot("armor")
        warnings = []
        if not inventory.has_tuning_data(items):
            warnings.append("snapshot without the tuning stat: tuning mods are ignored")
        try:
            override = optimize.parse_set_override(sets, no_sets)
            s = sheet_mod.load(path)
            intent, sub = s["intent"], s["subclass"]
            if override is not None:
                intent = {**intent, "sets": override}
            catalog = load_catalog(ctx.manifest)
            optimize.check_sets(intent, {v["set"] for v in catalog["sets"].values()})
            pieces = inventory.load_pieces(items, s["class"], intent["exotic"], catalog["sets"])
            frag = fragment_stats(sub.get("fragments", []), sub["element"], s["class"])
            out = optimize.optimize(pieces, intent, frag, catalog["costs"], s["class"], top)
        except ValueError as e:   # SheetError included
            raise ToolError(str(e)) from e
        if not out["complete"]:
            warnings.append(f"search stopped after {optimize.MAX_EVALS} combinations: results may not be optimal")
        if not out["results"]:
            warnings.append("no valid combination (set requirement impossible to meet, or utility mods over "
                            "the pieces' energy)")
        if write:
            if not 1 <= pick <= len(out["results"]):
                raise ToolError(f"pick {pick} out of 1..{len(out['results'])}")
            chosen = out["results"][pick - 1]
            if not chosen["feasible"] and not force:
                raise ToolError("this result misses the minimums; force=true writes it anyway")
            try:
                optimize.write_result(path, chosen, sets=override)
            except (ValueError, OSError) as e:
                raise ToolError(str(e)) from e
            out["written"] = pick
        return {**out, "snapshot": taken, "warnings": warnings}

    @tool(mcp)
    def equip_plan(slug: str) -> dict:
        """Equip plan for build sheet `slug`: the write calls to make (equip, subclass / armor / weapon / artifact
sockets, perks, locks, transfers) without running any. Reads the armor and weapon snapshots: call
refresh_inventory first. `ready: false` = blocking `problems` (item missing, in the postmaster, equipped on another
class, invalid subclass or artifact, no resolved armor: re-optimize); `warnings` do not block.
`expected_armor_stats` = armor totals to check with get_equipped after equipping."""
        path = sheet_path(slug)
        armor_items, taken = snapshot("armor")
        weapon_items, _ = snapshot("weapons")
        try:
            s = sheet_mod.load(path)
            sub = s["subclass"]
            frag = fragment_stats(sub.get("fragments", []), sub["element"], s["class"])
            catalog = load_catalog(ctx.manifest)
            artifacts = artifact.load() if s["intent"].get("artifact") else None
            plan = equip_mod.build_plan(s, armor_items, weapon_items, frag, date.today(), catalog["subclass"],
                                        catalog["costs"], artifacts)
        except ValueError as e:   # SheetError included, missing compendium
            raise ToolError(str(e)) from e
        except (KeyError, TypeError, AttributeError) as e:   # malformed snapshot
            raise ToolError(f"malformed snapshot: {type(e).__name__}: {e}") from e
        return {**plan, "snapshot": taken}
