"""Share a build sheet: a PDF of its view, a DIM loadout link. Read-only for the account."""
import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.core.bungie import BungieApiError
from shell.engines import build_icons, share
from shell.engines.builds.snapshot import read_snapshot
from shell.engines.builds import sheet as sheet_mod
from shell.mcp import tool
from shell.mcp.tools.builds import sheet_path, snapshot
from shell.outputs import build_pdf as pdf_out, dim_link
from shell.sources import icons


def _load(slug):
    path = sheet_path(slug)
    try:
        return path, sheet_mod.load(path)
    except ValueError as e:   # SheetError included
        raise ToolError(str(e)) from e


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def build_pdf(slug: str) -> dict:
        """PDF of build sheet `slug` (profile/builds/<slug>.pdf), A4 landscape in the in-game layout (subclass,
weapons, armor, artifact, stats, build text) with the manifest icons, cached in cache/icons/ (the first export
downloads them; later ones work offline). The Markdown view is regenerated first. Reads the inventory snapshot
(call refresh_inventory first). Returns pdf (path) and warnings (no snapshot, Bungie unreachable, missing icons,
no Unicode font: symbols simplified)."""
        path, s = _load(slug)
        sheet_mod.save(path, s)   # regenerates the .md view
        warnings, items = [], {}
        for kind in ("armor", "weapons"):
            try:
                items[kind] = read_snapshot(kind)[0]
            except (FileNotFoundError, ValueError):   # absent, or corrupt / partial JSON
                items[kind] = []
                warnings.append(f"no {kind} snapshot: item icons by name (call refresh_inventory)")
        try:
            tables = [ctx.manifest.table(name, keep=False) for name in (
                "DestinyInventoryItemDefinition", "DestinySocketTypeDefinition", "DestinyStatDefinition")]
        except (BungieApiError, httpx.HTTPError, OSError, ValueError):   # ValueError: corrupt cached table
            tables = None
            refs = icons.indexed()
            warnings.append("Bungie unreachable: icons from the cache only")
        if tables:
            refs, more = build_icons.refs(s, *tables, items["armor"], items["weapons"])
            warnings += more
        files, more = icons.local(refs)
        warnings += more
        pdf = path.with_suffix(".pdf")
        missing = []
        for w in pdf_out.write(pdf, s, files):
            (missing if w.startswith("no icon:") else warnings).append(w)
        if missing:   # one line, not one per icon
            names = ", ".join(m.removeprefix("no icon: ") for m in missing[:3])
            warnings.append(f"{len(missing)} icons missing (placeholders): {names}{'...' if len(missing) > 3 else ''}")
        return {"pdf": str(pdf), "warnings": warnings}

    @tool(mcp)
    def build_dim_link(slug: str) -> dict:
        """DIM loadout link for build sheet `slug`: resolved armor and weapons (by instance id and hash: a friend gets
their own copy), subclass with super / abilities / aspects / fragments, armor mods, exotic, stat priorities and
minimums; weapon perks, artifact, sets and unresolved names in the loadout notes. Reads the inventory snapshot
(call refresh_inventory first). Opening the link in DIM applies nothing. Returns url, length, items, mods,
warnings, snapshot."""
        _, s = _load(slug)
        armor, taken = snapshot("armor")
        weapons, _ = snapshot("weapons")
        loadout, warnings = share.loadout(s, armor, weapons,
                                          ctx.manifest.table("DestinyInventoryItemDefinition", keep=False),
                                          ctx.manifest.table("DestinySocketTypeDefinition", keep=False))
        url, more = dim_link.url(loadout)
        return {"url": url, "length": len(url), "items": len(loadout["equipped"]),
                "mods": len(loadout["parameters"]["mods"]), "warnings": warnings + more, "snapshot": taken}
