"""Build views: check a sheet, list subclass and artifact options, Aegis rankings, weapon candidates.

Read-only: nothing here writes to the account; check_build only regenerates the sheet's Markdown view.
"""
import functools

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.engines.builds import artifact, catalog, rankings as rankings_mod, sheet, sheet_hashes, subclass, weapon_intent, weapons
from shell.engines.builds.snapshot import read_snapshot
from shell.engines.builds.stats import CLASSES, ELEMENTS
from shell.mcp import tool


def _player_facing(fn):
    """Missing data and bad arguments (FileNotFoundError, ValueError incl. SheetError) become one-line errors."""
    @functools.wraps(fn)
    def wrapper(*args, **kw):
        try:
            return fn(*args, **kw)
        except (FileNotFoundError, ValueError) as e:
            raise ToolError(str(e)) from e
    return wrapper


def _pick(value, choices, field):
    found = next((c for c in choices if c.lower() == value.strip().lower()), None)
    if found is None:
        raise ValueError(f"{field} is one of {', '.join(choices)}")
    return found


MAX_LIMIT = 200  # keeps a tool result well under Claude Code's MCP output limit


def _bounded(lines: list[str], limit: int) -> list[str]:
    limit = max(1, min(limit, MAX_LIMIT))
    if len(lines) <= limit:
        return lines
    return lines[:limit] + [f"… {len(lines) - limit} more (narrow the filters or raise limit)"]


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    @_player_facing
    def check_build(slug: str) -> dict:
        """Check build sheet profile/builds/<slug>.json: sheet rules, then subclass (aspects, fragments, abilities
against the manifest), artifact perks (compendium) and intent weapons (items, perks per column, mods, masterworks
against the manifest). Rebuilds the sheet's `hashes` table (every name it holds), saves the sheet and regenerates its
.md view when the sheet itself is valid. Problems are prefixed "sheet…", "subclass: …", "artifact: …" or "weapon: …"; ok is true when there is none. warnings (they don't affect ok): a named weapon that
can take a mod but names none."""
        existing = sorted(p.stem for p in sheet.folder().glob("*.json"))
        if slug not in existing:
            raise ToolError(f"Unknown build: {slug}. Existing: {', '.join(existing) or 'none'}")
        path = sheet.path_for(slug)
        ctx.lexicon   # the .md view in the player's language
        try:
            s = sheet.load(path)
        except sheet.SheetError as e:
            return {"ok": False, "problems": [str(e)], "md": None}
        problems = [f"subclass: {p}" for p in subclass.check(s, catalog.load_catalog(ctx.manifest)["subclass"])]
        intent = s["intent"].get("artifact")
        if intent is not None:
            try:
                problems += [f"artifact: {p}" for p in artifact.check(intent, artifact.load())]
            except ValueError as e:
                problems.append(f"artifact: {e}")
        defs, socket_types, stat_defs, set_defs, perk_defs, plug_sets = (ctx.manifest.table(name, keep=False) for name in (
            "DestinyInventoryItemDefinition", "DestinySocketTypeDefinition", "DestinyStatDefinition",
            "DestinyEquipableItemSetDefinition", "DestinySandboxPerkDefinition", "DestinyPlugSetDefinition"))
        problems += [f"weapon: {p}" for p in sheet_hashes.fill(s, defs, socket_types, stat_defs, set_defs, perk_defs,
                                                               plug_sets)]
        warnings = weapon_intent.missing_mods(s["intent"].get("weapons") or [], defs, plug_sets, s["hashes"])
        sheet.save(path, s)
        return {"ok": not problems, "problems": problems, "warnings": warnings, "md": str(path.with_suffix(".md"))}

    @tool(mcp)
    @_player_facing
    def subclass_options(class_type: str, element: str) -> str:
        """Aspects of a class and element (fragment slots, Aegis tier), its supers and abilities, and the element's
fragments (stat bonuses from the compendium, Aegis tier). class_type: Hunter/Titan/Warlock; element:
Arc/Solar/Void/Stasis/Strand/Prismatic."""
        cls, el = _pick(class_type, CLASSES, "class_type"), _pick(element, ELEMENTS, "element")
        return subclass.list_text(catalog.load_catalog(ctx.manifest)["subclass"], cls, el)

    @tool(mcp)
    @_player_facing
    def artifact_options() -> list[str]:
        """Known artifacts and their perks per column, with the Aegis tier in parentheses."""
        return artifact.list_lines(artifact.load())

    @tool(mcp)
    @_player_facing
    def rankings(view: str, type: str | None = None, element: str | None = None, class_type: str | None = None,
                 tag: str | None = None, tier: str | None = None, activity: str | None = None,
                 name: str | None = None, top: int | None = None, limit: int = 25) -> list[str]:
        """Aegis rankings, one line per entry sorted by tier then rank: tier | name | useful columns.
view: weapons (filters type, element, tier), exotic-weapons, perks, origin-traits, sets, artifact, subclasses
(filters class_type, tag, tier), aspects (class_type, element, tier), fragments (element, tier), dps-sustained,
dps-swap (top, default 20), bosses (activity), name (name: every tab, every column). tier keeps that tier and
better. At most `limit` lines (max 200); narrow the filters rather than raising it."""
        if view == "name" and len((name or "").strip()) < 3:
            raise ToolError("the name view needs `name` with at least 3 characters")
        lines = rankings_mod.rank(view, type=type, element=element, class_type=class_type, tag=tag, tier=tier,
                                  activity=activity, name=name, top=top)
        return _bounded(lines, limit)

    @tool(mcp)
    @_player_facing
    def weapon_candidates(slot: str | None = None, element: str | None = None, type: str | None = None,
                          name: str | None = None, perk: str | None = None, limit: int = 40) -> list[str]:
        """Weapons of the inventory snapshot for a build, graded ones first (weapon triage grade, then name). First
line: snapshot time. Then: id | name | type | element | slot | ammo | frame | perks (`selected [alternatives]`,
`*` enhanced) | grade | aegis tier | lock | location [| equipped] [| crafted]. perk searches build perk columns
and the frame. Use weapon_options(item_id) to see every column of one weapon."""
        items, taken = read_snapshot("weapons")
        return [f"snapshot: {taken}", *weapons.candidates(items, weapons.load_grades(), slot, element, type, name,
                                                          perk, max(1, min(limit, MAX_LIMIT)))]

    @tool(mcp)
    @_player_facing
    def weapon_options(item_id: str) -> str:
        """Every column of one weapon of the snapshot, to choose its perks and mod: `(selected)` current option,
`*` enhanced, `✓` cited by the default wishlist, `A` recommended by Aegis, `(not insertable)` refused by Bungie
for now; the header says whether a full wishlist roll is possible, then one line per Aegis rating. `suggested`: one
option per column with choices, from those marks (A and ✓, then A, then ✓, else what is in place)."""
        items, taken = read_snapshot("weapons")
        item_id = item_id.strip('"')
        w = next((x for x in items if x["itemId"] == item_id), None)
        if w is None:
            raise ToolError(f"Weapon not in the weapon snapshot: {item_id}. Call refresh_inventory if it is new.")
        rolls, by_name = weapons.load_wishlist_index({k: v["n"] for k, v in ctx.defs["plugs"].items()})
        wished = weapons.wishlist_perks(w, rolls, by_name) if rolls is not None else None
        return "\n".join([f"snapshot: {taken}", *weapons.detail(w, weapons.load_grades(), wished)])
