"""Raid companion: check an encounter file, show it on the live page, rename callouts. Read-only for the account."""
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.core import paths
from shell.engines import raids
from shell.mcp import tool
from shell.outputs import raid_page
from shell.sources import guides


def _cached_guides(raid):
    return {p.stem for p in (guides.folder() / raid).glob("*.md") if p.stem != "index"}


def _problems(raid, enc):
    try:
        return raids.check(enc, _cached_guides(raid))
    except (KeyError, TypeError, AttributeError) as e:
        return [f"malformed encounter file: {type(e).__name__}: {e}"]


def _load(raid, encounter):
    try:
        return raids.load(raid, encounter)
    except (FileNotFoundError, ValueError) as e:
        raise ToolError(str(e)) from e


def _pick(items, wanted, label):
    w = (wanted or "").strip().casefold()
    found = next((i for i in items if w in (i["id"].casefold(), i["name"].casefold())), None)
    if found is None:
        raise ToolError(f"unknown {label} {wanted!r}; {label}s: {', '.join(i['name'] for i in items)}")
    return found


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def raid_check(raid: str, encounter: str) -> dict:
        """Check encounter file profile/raids/<raid>/<encounter>.json (written by the raid-companion skill from the
cached guides): ids, references, 6 players, every spot and phase sourced, no position without pos_source.
Returns ok, problems, file."""
        enc = _load(raid, encounter)
        problems = _problems(raid, enc)
        return {"ok": not problems, "problems": problems, "file": str(raids.folder(raid) / f"{encounter}.json")}

    @tool(mcp)
    def raid_show(raid: str, encounter: str, role: str, phase: str | None = None) -> dict:
        """Write the live raid page (profile/raids/live.html, reloads itself: the player keeps it open on a second
monitor) for an encounter, a role and a phase (default: the first), and return the same as text: steps for the
role, spots of the phase, not_on_map (no guide places them), conflicts between guides, gaps, the encounter's
phases and roles, warnings. role / phase: id or name."""
        enc = _load(raid, encounter)
        problems = _problems(raid, enc)
        if problems:
            raise ToolError(f"{raid}/{encounter} is invalid: {'; '.join(problems[:5])}. Fix it, then raid_check.")
        r = _pick(enc["roles"], role, "role")
        p = _pick(enc["phases"], phase, "phase") if phase else enc["phases"][0]
        names = raids.names(enc, raids.load_renames(raid))
        page = paths.profile_dir() / "raids" / "live.html"
        raid_page.write(page, raid_page.render(enc, names, r["id"], p["id"]))
        spots = {s["id"]: s for s in enc["spots"]}
        used = [s for s in p.get("spots", []) if s in spots]
        return {"page": str(page), "encounter": enc["name"], "phase": p["name"], "role": r["name"],
                "steps": p.get("steps", {}).get(r["id"], []), "spots": [names[s] for s in used],
                "not_on_map": [names[s] for s in used if spots[s].get("pos") is None],
                "conflicts": enc.get("conflicts", []), "gaps": enc.get("gaps", []),
                "phases": [x["name"] for x in enc["phases"]], "roles": [x["name"] for x in enc["roles"]],
                "warnings": raids.orphan_renames(raid)}

    @tool(mcp)
    def raid_rename(raid: str, spot_id: str, name: str | None = None) -> dict:
        """Rename a spot's callout to what the player's groups say (shown on every page of the raid, kept when an
encounter file is rebuilt); without name, back to the guides' label. Returns every rename of the raid."""
        try:
            known = {s["id"] for e in raids.encounters(raid) for s in raids.load(raid, e).get("spots", [])}
        except (FileNotFoundError, ValueError, KeyError, TypeError) as e:
            raise ToolError(f"cannot read the encounter files: {e}") from e
        if name and spot_id not in known:
            raise ToolError(f"unknown spot {spot_id!r} in {raid}; spots: {', '.join(sorted(known)) or 'none'}")
        return {"renames": raids.save_rename(raid, spot_id, name)}
