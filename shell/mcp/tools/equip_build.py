"""Equip a whole build sheet: every write of its equip plan, in order, from one previewed plan."""
import hashlib
import json
from datetime import datetime, timezone

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.core.bungie import BungieApiError
from shell.engines.account import character_id, get_profile, primary_membership
from shell.engines.loadout import equipped
from shell.mcp import tool
from shell.mcp.tools.builds import plan_for
from shell.mcp.tools.equipping import equip_on
from shell.mcp.tools.locking import change_locks
from shell.mcp.tools.perks import change_perks
from shell.mcp.tools.sockets import plan_sockets, run_sockets

MAX_SNAPSHOT_MINUTES = 15   # mod removals are computed from the snapshot
PLANNED = ("equip", "subclass", "armor_sockets", "weapon_perks", "weapon_sockets", "artifact", "lock")
REFUSED = ("no socket takes", "can't take", "no free socket", "not one of", "can't be selected", "not found",
           "not an item id", "shares the", "more than one column")


def _confirm_code(plan: dict) -> str:
    return hashlib.sha1(json.dumps({k: plan[k] for k in PLANNED}, sort_keys=True).encode()).hexdigest()[:12]


def _snapshot_minutes(taken: str) -> float:
    return (datetime.now(timezone.utc) - datetime.fromisoformat(taken)).total_seconds() / 60


def _item_ids(ctx: Context, plan: dict) -> tuple[str | None, str | None, bool, list[str]]:
    """(subclass id, artifact id, artifact already equipped, problems), read live on the character."""
    profile = get_profile(ctx.client, primary_membership(ctx.client), [200, 201, 205, 300, 304, 305])
    worn = equipped(profile, ctx.defs, character_id(profile, plan["character"]))

    def find(name, current, others):
        return next((x["itemId"] for x in [worn[current] or {}, *worn[others]] if x.get("name") == name), None)

    sub = find(plan["subclass"]["item"], "subclass", "other_subclasses")
    art = find(plan["artifact"]["name"], "artifact", "other_artifacts") if plan["artifact"] else None
    problems = [] if sub else [f"subclass {plan['subclass']['item']} not found on {plan['character']}"]
    if plan["artifact"] and not art:
        problems.append(f"artifact {plan['artifact']['name']} not found on {plan['character']}")
    return sub, art, bool(art) and (worn["artifact"] or {}).get("itemId") == art, problems


def _blocked(step: str, result: dict, dry_run: bool) -> list[str]:
    """What must stop the sequence in this step's result. A failed "Empty ..." frees nothing that matters."""
    if step == "equip":
        out = [f"{m['name'] or m['itemId']}: {m['result']}" for m in result["moves"]
               if not m["result"].startswith(("would move", "moved", "already on"))]
        if not dry_run:
            out += [f"{e['name']}: {e['result']}" for e in result["equip"] if e["result"] != "equipped"]
        return out
    if step == "lock":
        return []   # the gear is on: a lock that failed is only reported
    return [f"{c['name']}: {c['to']}: {c['result']}" for c in result["changes"]
            if c["result"].startswith(("failed", "not attempted")) and not c["to"].lower().startswith("empty")]


def register(mcp: MCPServer, ctx: Context) -> None:
    definitions: dict[tuple[str, int], dict] = {}

    @tool(mcp)
    def equip_build(slug: str, dry_run: bool = True, confirm: str | None = None) -> dict:
        """Equip build sheet `slug`: items, subclass, artifact, armor mods, weapon perks, weapon mods, then locks, in
that order. Call refresh_inventory right before (refused when the snapshot is over 15 minutes old). Previews by
default and returns `confirm`: show the player the preview, then after their yes call again with dry_run=false and
that `confirm` (refused if the plan changed since: preview again). `ready: false` = blocking `problems`, nothing done.
`steps`: each step's result; `stopped_at`: the step that stopped the sequence (`blocked` says why), later steps not
run. `refused`: plugs or perks Bungie would not take, skipped. `warnings`, `masterwork_todo`, `transfers`,
`expected_armor_stats` as in equip_plan. Call refresh_inventory afterwards."""
        plan = plan_for(ctx, slug)
        summary = {k: plan[k] for k in ("warnings", "character", "masterwork_todo", "transfers",
                                        "expected_armor_stats", "snapshot")}
        if not plan["ready"]:
            return {"dry_run": dry_run, "ready": False, "problems": plan["problems"], **summary}
        if _snapshot_minutes(plan["snapshot"]) > MAX_SNAPSHOT_MINUTES:
            raise ToolError(f"Snapshot of {plan['snapshot']} is over {MAX_SNAPSHOT_MINUTES} minutes old: "
                            "call refresh_inventory, then preview again.")
        code = _confirm_code(plan)
        if not dry_run and confirm != code:
            raise ToolError("No preview of this plan: call equip_build with dry_run=true, show it to the player, "
                            "then pass its `confirm`.")
        sub_id, art_id, art_worn, problems = _item_ids(ctx, plan)
        if problems:
            return {"dry_run": dry_run, "ready": False, "problems": problems, **summary}

        def sockets(changes):
            return lambda: run_sockets(ctx, plan_sockets(ctx, changes, definitions), dry_run)

        strip = lambda entries: [{"itemId": e["itemId"], "plugs": e["plugs"]} for e in entries]  # noqa: E731
        ids = [*plan["equip"], sub_id, *([art_id] if art_id and not art_worn else [])]
        stages = [("equip", lambda: equip_on(ctx, plan["character"], ids, dry_run)),
                  ("subclass", sockets([{"itemId": sub_id, "plugs": plan["subclass"]["plugs"]}]))]
        if plan["artifact"]:
            stages.append(("artifact", sockets([{"itemId": art_id, "plugs": plan["artifact"]["plugs"]}])))
        if plan["armor_sockets"]:
            stages.append(("armor", sockets(strip(plan["armor_sockets"]))))
        if plan["weapon_perks"]:
            stages.append(("perks", lambda: change_perks(ctx, plan["weapon_perks"], dry_run)))
        if plan["weapon_sockets"]:
            stages.append(("weapon mods", sockets(strip(plan["weapon_sockets"]))))
        if plan["lock"]:
            stages.append(("lock", lambda: change_locks(ctx, plan["lock"], True, dry_run)))

        steps, refused, stopped, blocked = [], [], None, []
        for name, run in stages:
            try:
                result = run()
            except BungieApiError as e:   # what was done so far must still reach the player
                stopped, blocked = stopped or name, [*blocked, str(e)]
                break
            steps.append({"step": name, **result})
            refused += [n for n in result.get("notes", []) if any(r in n for r in REFUSED)]
            found = _blocked(name, result, dry_run)
            if found:
                stopped, blocked = stopped or name, [*blocked, *found]
                if not dry_run:
                    break
        out = {"dry_run": dry_run, "ready": True, **summary, "refused": refused, "stopped_at": stopped,
               "blocked": blocked, "steps": steps}
        return {**out, "confirm": code} if dry_run and not stopped else out
