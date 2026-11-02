"""Share a build sheet: a PDF of its view, a DIM loadout link. Read-only for the account."""
from pathlib import PurePosixPath

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.core.bungie import BungieApiError
from shell.engines import build_icons, lexicon, share
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
        """PDF of build sheet `slug` (profile/builds/<slug>.pdf), A4 landscape in the in-game layout, showing the build
as designed, never what the inventory reached (subclass, wanted weapons and armor, artifact, stat targets, set bonus
as the game's tooltip), with the manifest icons, cached in cache/icons/ (the first export downloads them; later ones work
offline), each item's icon linking to its light.gg page (not offline). The Markdown view is regenerated first. Returns pdf (path) and warnings (Bungie unreachable, missing icons,
no Unicode font: symbols simplified)."""
        path, s = _load(slug)
        language = "en"
        try:
            language = ctx.settings.language
            ctx.lexicon   # the player's language for the .md and the PDF
        except (BungieApiError, httpx.HTTPError, OSError, ValueError) as e:
            warnings_lexicon = [f"names stay in the last cached language ({e})"]
        else:
            warnings_lexicon = []
        sheet_mod.save(path, s)   # regenerates the .md view
        warnings, hashes = warnings_lexicon, {}
        try:
            tables = [ctx.manifest.table(name, keep=False) for name in (
                "DestinyInventoryItemDefinition", "DestinySocketTypeDefinition", "DestinyStatDefinition",
                "DestinyEquipableItemSetDefinition", "DestinySandboxPerkDefinition")]
            local_perks = lexicon.local_table(ctx.manifest, language, "DestinySandboxPerkDefinition")
        except (BungieApiError, httpx.HTTPError, OSError, ValueError):   # ValueError: corrupt cached table
            tables, armor, set_perks = None, None, None   # shortcut: no set perk lines or links offline; cache them if players ask
            refs = {k: r for k, r in icons.indexed().items() if (icons.folder() / PurePosixPath(r).name).is_file()}
            warnings.append("Bungie unreachable: icons from the cache only")
        if tables:
            refs, more = build_icons.refs(s, *tables, hashes=hashes)
            armor = build_icons.intent_armor(s, tables[0], tables[3])
            set_perks = build_icons.set_perks(s, *tables[3:], local_perks)[0]   # its warnings come with refs
            warnings += [w for w in more if not w.startswith(("icon not found:", "no icon:"))]  # reported collapsed
        files, more = icons.local(refs)
        warnings += more
        pdf = path.with_suffix(".pdf")
        missing = []
        links = {k: pdf_out.LIGHT_GG.format(lang=language, hash=h) for k, h in hashes.items()}
        for w in pdf_out.write(pdf, s, files, armor, set_perks, lexicon.current(), links):
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
