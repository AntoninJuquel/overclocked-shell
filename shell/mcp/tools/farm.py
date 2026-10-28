"""farm_plan and set_need_status: the dated TODO from profile/todo/needs.json, and the player's statuses."""
import json
from datetime import datetime, timezone

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.engines.builds.catalog import load_catalog
from shell.engines.todo import plan, sources, state, week
from shell.mcp import tool


def _needs():
    path = state.folder() / "needs.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _compact(e):
    out = {"id": e["id"], "label": e["label"], "priority": e["priority"],
           "builds": [b["build"] for b in e["builds"]],
           "where": [plan.format_source(s) for s in plan.display_sources(e["sources"])]}
    if e.get("note"):
        out["note"] = e["note"]
    return out


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def farm_plan(build: str | None = None, top: int = 10) -> dict:
        """Today's farm TODO: every need from profile/todo/needs.json still todo, ranked by gain × availability
(boosted this week 1.5, known source 1, unknown 0.3) into the sections "This week", "When you can" and "Later".
Uses the newest week context (profile/todo/week/, from week_context; ignored once its week has ended) and the
manual sources in profile/todo/sources.json. `build`: one build sheet's needs only ("aegis" = the Aegis
Shopping List). Call farm_needs first. Writes profile/todo/<date>[-<build>].json and .md; returns the top
`top` entries per section (id, label, priority, builds, where), each section's count, the week banner, hidden
(done / ignored) counts, warnings and saved_to (the Markdown)."""
        needs_doc = _needs()
        if needs_doc is None:
            raise ToolError("Call farm_needs first.")
        try:
            if build is not None:
                builds = sorted({b["build"] for n in needs_doc.get("needs", []) for b in n["builds"]})
                if build not in builds:
                    raise ToolError(f"unknown build {build!r}; builds in needs.json: {', '.join(builds) or 'none'}")
            manual = sources.load_sources()
            index = sources.build_index(ctx.manifest.table("DestinyInventoryItemDefinition", keep=False),
                                        ctx.manifest.table("DestinyCollectibleDefinition", keep=False),
                                        load_catalog(ctx.manifest)["sets"])
            doc = plan.run(state.folder(), week.folder(), index, manual, datetime.now(timezone.utc), build)
        except ValueError as e:
            raise ToolError(str(e)) from e
        except (KeyError, TypeError) as e:   # malformed input JSON (needs, statuses, week)
            raise ToolError(f"malformed input file ({type(e).__name__}: {e})") from e
        sections = {}
        for section in plan.SECTIONS:
            entries = [e for e in doc["entries"] if e["section"] == section]
            if entries:
                sections[section] = {"count": len(entries), "entries": [_compact(e) for e in entries[:top]]}
        return {"sections": sections, "week": doc["context"], "hidden": doc["hidden"], "warnings": doc["warnings"],
                "saved_to": str(state.folder() / f"{plan.file_stem(doc)}.md")}

    @tool(mcp)
    def set_need_status(need_id: str, status: str, note: str | None = None) -> dict:
        """Set a TODO need's status: "todo", "done" or "ignored" (ignored needs stay hidden until set back to todo).
`note` replaces the note, "" clears it, omitted keeps it. The id must be in profile/todo/needs.json or
state.json (as farm_plan shows it). Writes profile/todo/state.json; returns the entry."""
        if status not in state.STATUSES:
            raise ToolError(f"unknown status {status!r} ({', '.join(state.STATUSES)}): nothing changed")
        current = state.load()
        known = {n["id"] for n in (_needs() or {}).get("needs", [])} | current.keys()
        if need_id not in known:
            raise ToolError(f"unknown need id {need_id!r} (not in needs.json nor state.json): nothing changed")
        state.set_status(current, need_id, status, datetime.now(timezone.utc).date().isoformat(), note)
        state.save(state.folder() / "state.json", current)
        return {"id": need_id, **current[need_id]}
