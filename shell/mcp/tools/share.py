"""Share a build sheet: a PDF of its view, a DIM loadout link. Read-only for the account."""
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.engines import share
from shell.engines.builds import sheet as sheet_mod
from shell.mcp import tool
from shell.mcp.tools.builds import sheet_path, snapshot
from shell.outputs import build_pdf as pdf_out, dim_link


def _load(slug):
    path = sheet_path(slug)
    try:
        return path, sheet_mod.load(path)
    except ValueError as e:   # SheetError included
        raise ToolError(str(e)) from e


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def build_pdf(slug: str) -> dict:
        """PDF of build sheet `slug` (profile/builds/<slug>.pdf): its Markdown view, regenerated first, printed.
Returns pdf (path) and warnings (e.g. no Unicode font: symbols simplified)."""
        path, s = _load(slug)
        sheet_mod.save(path, s)   # regenerates the .md view
        pdf = path.with_suffix(".pdf")
        warnings = pdf_out.write(pdf, s, {})  # icons wired by S-026 task 4
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
