"""Share a build sheet: a PDF of its view, a DIM loadout link. Read-only for the account."""
from pathlib import PurePosixPath

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.core.bungie import BungieApiError
from shell.engines import build_icons, lexicon, share
from shell.engines.builds import sheet as sheet_mod, sheet_hashes
from shell.mcp import tool
from shell.mcp.tools.builds import sheet_path, snapshot
from shell.outputs import build_image, build_pdf as pdf_out, build_yaml as yaml_out, dim_link
from shell.sources import icons


def _load(slug):
    path = sheet_path(slug)
    try:
        return path, sheet_mod.load(path)
    except ValueError as e:   # SheetError included
        raise ToolError(str(e)) from e


def register(mcp: MCPServer, ctx: Context) -> None:
    def _pdf(slug, boxes=None):
        """Writes the sheet's PDF and regenerates its .md view; returns (path, sheet, warnings)."""
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
            tables, armor, set_perks = None, None, None   # shortcut: no set perk lines offline; cache them if players ask
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
        links = sheet_hashes.links({**hashes, **(s.get("hashes") or {})}, pdf_out.LIGHT_GG, language)
        for w in pdf_out.write(pdf, s, files, armor, set_perks, lexicon.current(), links, boxes):
            (missing if w.startswith("no icon:") else warnings).append(w)
        if missing:   # one line, not one per icon
            names = ", ".join(m.removeprefix("no icon: ") for m in missing[:3])
            warnings.append(f"{len(missing)} icons missing (placeholders): {names}{'...' if len(missing) > 3 else ''}")
        return pdf, s, warnings

    @tool(mcp)
    def build_pdf(slug: str) -> dict:
        """PDF of build sheet `slug` (profile/builds/<slug>.pdf), A4 landscape in the in-game layout, showing the build
as designed, never what the inventory reached (subclass, wanted weapons and armor, artifact, stat targets, set bonus
as the game's tooltip), with the manifest icons, cached in cache/icons/ (the first export downloads them; later ones work
offline), each item's icon linking to its light.gg page. The Markdown view is regenerated first. Returns pdf (path) and warnings (Bungie unreachable, missing icons,
no Unicode font: symbols simplified)."""
        pdf, _, warnings = _pdf(slug)
        return {"pdf": str(pdf), "warnings": warnings}

    @tool(mcp)
    def build_png(slug: str) -> dict:
        """Image of build sheet `slug` (profile/builds/<slug>.png): the build_pdf page, about 2100 px wide, to post
anywhere. Also refreshes the PDF. Returns png (path) and warnings, as build_pdf."""
        pdf, _, warnings = _pdf(slug)
        out = pdf.with_suffix(".png")
        out.write_bytes(build_image.png(pdf.read_bytes()))
        return {"png": str(out), "warnings": warnings}

    @tool(mcp)
    def build_html(slug: str) -> dict:
        """Web page of build sheet `slug` (profile/builds/<slug>.html): one self-contained file showing the build_pdf
page as an image, each item's icon linking to its light.gg page. Also refreshes the PDF. Returns html (path) and
warnings, as build_pdf."""
        boxes = []
        pdf, s, warnings = _pdf(slug, boxes)
        out = pdf.with_suffix(".html")
        out.write_text(build_image.html(build_image.png(pdf.read_bytes()), boxes, s["name"]), encoding="utf-8")
        return {"html": str(out), "warnings": warnings}

    @tool(mcp)
    def build_yaml(slug: str) -> dict:
        """YAML export of build sheet `slug` (profile/builds/<slug>.yaml), to share: the build as designed, with the
hashes of what it names (run check_build first to refresh them), without what the inventory reached. Returns yaml
(path) and warnings."""
        path, s = _load(slug)
        out = path.with_suffix(".yaml")
        out.write_text(yaml_out.render(s), encoding="utf-8")
        return {"yaml": str(out), "warnings": [] if s.get("hashes") else ["no hashes yet: call check_build, then export"]}

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
