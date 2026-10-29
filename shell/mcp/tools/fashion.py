"""Fashion: check a look (from a screenshot the Ghost read) against the player's Collections, sources and this week's
Eververse; save looks as wardrobes. Applying goes through get_equipped + set_sockets previews (fashion skill)."""
import json
from datetime import datetime, timezone

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.core import paths
from shell.engines import fashion
from shell.core.bungie import BungieApiError
from shell.engines.account import character_id, get_profile, primary_membership
from shell.engines.builds.sheet import slug
from shell.engines.builds.snapshot import read_snapshot
from shell.mcp import tool
from shell.sources.aegis.names import norm

CLASSES = ("Titan", "Hunter", "Warlock")
SLOTS = ("Helmet", "Gauntlets", "Chest", "Legs", "Class Item")


def collectibles_state(ctx: Context, cls: str) -> tuple[dict[int, int], str | None, dict]:
    """({collectible hash: state}, warning, plugs), profile and the character combined (owned in either scope =
    owned); plugs: the plug sets of both scopes (component 305) for cosmetics without a collectible —
    {"insertable": plug hashes, "listed": plug hashes, "sets": plug set hashes}. No character of the class: the
    profile scope only, with a warning."""
    account = primary_membership(ctx.client)
    profile = get_profile(ctx.client, account, [200, 305, 800])
    scopes = [(profile.get("profileCollectibles") or {}).get("data", {}).get("collectibles", {})]
    plug_scopes = [(profile.get("profilePlugSets") or {}).get("data", {}).get("plugs", {})]
    warning = None
    try:
        cid = character_id(profile, cls.lower())
        scopes.append(((profile.get("characterCollectibles") or {}).get("data", {}).get(cid) or {})
                      .get("collectibles", {}))
        plug_scopes.append(((profile.get("characterPlugSets") or {}).get("data", {}).get(cid) or {})
                           .get("plugs", {}))
    except BungieApiError:
        warning = f"no {cls.lower()} character: character-scoped ownership unknown"
    state = {}
    for scope in scopes:
        for h, c in scope.items():
            state[int(h)] = state.get(int(h), c.get("state", 0)) & c.get("state", 0)
    plugs = {"insertable": set(), "listed": set(), "sets": set()}
    for scope in plug_scopes:
        for s, entries in scope.items():
            plugs["sets"].add(int(s))
            for e in entries:
                plugs["listed"].add(e["plugItemHash"])
                if e.get("canInsert"):
                    plugs["insertable"].add(e["plugItemHash"])
    return state, warning, plugs


def _folder():
    return paths.profile_dir() / "fashion"


def _newest_context():
    files = sorted((paths.profile_dir() / "context").glob("*.json"))
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def fashion_check(character: str, look: list[dict], save_as: str | None = None,
                      credit: str | None = None) -> dict:
        """Check a fashion look for a character (titan, hunter or warlock). look: [{"slot": "Helmet|Gauntlets|Chest|
Legs|Class Item", "ornament": name?, "shader": name?}] (read from the player's screenshot and confirmed with them).
Per piece: owned (Collections, inventory, or the profile's plug sets for cosmetics without a collectible;
null = none of them says), source (collectible source line),
eververse (on sale this week and price, from the newest refresh_context), exotic_for (an exotic ornament's exotic),
problem ("not for <class>", "is a shader" / "is an ornament" / "is an armor piece", "not found (close: …)");
plus a summary and warnings. save_as: save the look as a wardrobe (profile/fashion/<slug>.json) with its credit;
overwrote: true when a wardrobe of that name was replaced."""
        cls = next((c for c in CLASSES if c.lower() == (character or "").strip().lower()), None)
        if cls is None:
            raise ToolError("character is titan, hunter or warlock")
        if not look:
            raise ToolError("empty look: give at least one slot with an ornament or a shader")
        bad = [s.get("slot") for s in look if s.get("slot") not in SLOTS]
        if bad:
            raise ToolError(f"slot is one of {', '.join(SLOTS)} (got {bad[0]!r})")
        items = ctx.manifest.table("DestinyInventoryItemDefinition", keep=False)
        index = fashion.build_index(items, ctx.manifest.table("DestinyCollectibleDefinition", keep=False),
                                    ctx.manifest.table("DestinyPlugSetDefinition", keep=False))
        try:
            snapshot = read_snapshot("armor")[0]
        except FileNotFoundError:
            snapshot = []
        inventory = {x.get("itemHash") for x in snapshot} | {norm(x["name"]) for x in snapshot if x.get("name")}
        state, warning, plugs = collectibles_state(ctx, cls)
        result = fashion.check(look, cls, index, state, inventory, _newest_context(), datetime.now(timezone.utc),
                               items, plugs)
        if warning:
            result["warnings"] = [warning]
        if save_as:
            try:
                path = _folder() / f"{slug(save_as)}.json"
            except ValueError as e:
                raise ToolError(str(e)) from e
            path.parent.mkdir(parents=True, exist_ok=True)
            result["overwrote"] = path.exists()
            path.write_text(json.dumps({"name": save_as, "class": cls, "credit": credit, "look": look,
                                        "saved": datetime.now(timezone.utc).date().isoformat()},
                                       indent=1, ensure_ascii=False), encoding="utf-8")
            result["saved_to"] = str(path)
        return result

    @tool(mcp)
    def wardrobes() -> list[dict]:
        """Saved fashion looks (profile/fashion/*.json): name, class, credit, slots, saved date, file, look."""
        out = []
        for p in sorted(_folder().glob("*.json")) if _folder().exists() else []:
            try:
                w = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            out.append({"name": w.get("name"), "class": w.get("class"), "credit": w.get("credit"),
                        "slots": len(w.get("look") or []), "saved": w.get("saved"), "file": p.name,
                        "look": w.get("look")})
        return out
