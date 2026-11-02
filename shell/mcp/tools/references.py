"""Reference data: refresh the local copies of the sources in shell/sources/."""
import re
from datetime import date, datetime

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.core import paths
from shell.mcp import tool
from shell.sources import sources


def data_date(source: str) -> date | None:
    """Date of a source's oldest data: its index.md says it, else its latest written file; None without data."""
    folder = paths.cache_dir() / source
    index = folder / "index.md"
    found = re.search(r"^Oldest data: (\d{4}-\d{2}-\d{2})", index.read_text(encoding="utf-8"), re.M) if index.exists() else None
    if found:
        return date.fromisoformat(found.group(1))
    files = [f.stat().st_mtime for f in folder.iterdir() if f.is_file()] if folder.exists() else []
    return datetime.fromtimestamp(max(files)).date() if files else None


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def refresh_references(source: str | None = None, force: bool = False, tabs: list[str] | None = None,
                           max_age_days: int | None = None) -> dict:
        """Refresh reference data into cache/<source>/ (all sources when source is omitted). Sources:
- compendium: Destiny Data Compendium, exact game values (cache/compendium/<tab>.md, index.md)
- aegis: Aegis Endgame Analysis and Boss Damage sheets, tiers / ranks / DPS / Shopping List
  (cache/aegis/<sheet>/<tab>.md and .json); changes.md lists tier and rank changes and the builds concerned
- bungie-api: Bungie API endpoints and schemas (cache/bungie-api/*.md)
- wishlists: the default DIM weapon wishlist (cache/wishlists/)
- distortions: the hourly Distortion rotation, community-observed (cache/distortions/rotation.json); read it
  with the distortions tool
- guides: raid guides chosen by the player, as Markdown with their images (cache/guides/<raid>/<guide>.md,
  index.md); `tabs` = raid slugs (e.g. ["deep-stone-crypt"]). Read them with the raid-companion skill
Without force, cached downloads are reused and only rendering runs; force re-downloads. tabs limits the
Compendium / Aegis to those tab names. max_age_days: re-downloads only a source with data older than that or none,
the others report {"source", "fresh": true, "oldest"}. Read or grep the Markdown afterwards to answer questions."""
        found = sources()
        if source is not None and source not in found:
            raise ToolError(f"Unknown source {source!r}. Known: {', '.join(sorted(found))}.")
        reports = []
        for name in [source] if source else sorted(found):
            oldest = data_date(name) if max_age_days is not None else None
            if oldest and (date.today() - oldest).days <= max_age_days:
                reports.append({"source": name, "fresh": True, "oldest": oldest.isoformat()})
            else:
                reports.append(found[name].refresh(force=force or max_age_days is not None, only=tabs))
        return {"reports": reports}
