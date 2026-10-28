"""Raid guides chosen by the player, cached as Markdown with their in-article images (cache/guides/<raid>/).

Third-party content: kept locally for the Ghost to read when it writes an encounter file, never published.
"""
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from shell.core import paths
from shell.sources import report, web, write_if_changed
from shell.sources.guides import extract, sites

NAME = "guides"
GUIDES = {
    "deep-stone-crypt": {
        "grindout": "https://grindout.com/destiny-2/guides/deep-stone-crypt",
        "shacknews": "https://www.shacknews.com/article/121651/deep-stone-crypt-raid-guide-destiny-2",
        "overgear": "https://overgear.com/guides/destiny2/deep-stone-crypt-raid-guide/",
    },
}
ENCOUNTERS = {
    "deep-stone-crypt": ["desolation", "crypt-security", "atraks-1", "descent", "taniks-reborn",
                         "taniks-abomination"],
}

IMAGE_TYPES = (".jpg", ".jpeg", ".png", ".webp", ".gif")


def folder() -> Path:
    return paths.cache_dir() / "guides"


def guide_path(raid: str, guide: str) -> Path:
    return folder() / raid / f"{guide}.md"


def _images(raid, guide, images):
    """Downloads the images next to the guide; Markdown for each, best-effort."""
    target = folder() / raid / guide
    shutil.rmtree(target, ignore_errors=True)
    out = []
    for n, (url, alt) in enumerate(images):
        ext = Path(urlsplit(url).path).suffix.lower()
        ext = ext if ext in IMAGE_TYPES else ".jpg"
        try:
            data = web.get(url)
        except (OSError, ValueError):
            out.append(f"![{alt} (image unavailable)]()")
            continue
        target.mkdir(parents=True, exist_ok=True)
        (target / f"img-{n:02}{ext}").write_bytes(data)
        out.append(f"![{alt}]({guide}/img-{n:02}{ext})")
    return out


def _index(raid):
    rows = ["| guide | updated | images | url | fetched |", "|---|---|---|---|---|"]
    for guide, url in GUIDES[raid].items():
        path = guide_path(raid, guide)
        if not path.exists():
            continue
        head = path.read_text(encoding="utf-8").split("\n", 1)[0]
        updated = (re.search(r"updated: (\S+)", head) or [None, "unknown"])[1]
        images = len(list((folder() / raid / guide).glob("img-*"))) if (folder() / raid / guide).exists() else 0
        fetched = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).date().isoformat()
        rows.append(f"| {guide} | {updated} | {images} | {url} | {fetched} |")
    write_if_changed(folder() / raid / "index.md", f"# Guides — {raid}\n\n" + "\n".join(rows) + "\n")


def _refresh_guide(raid, guide, url, force, changed, stale, errors):
    path, rel = guide_path(raid, guide), f"{raid}/{guide}.md"
    if path.exists() and not force:
        return
    try:
        page = web.get(url).decode("utf-8", "replace")
    except OSError as e:
        stale.append(rel) if path.exists() else errors.append(f"{raid}/{guide}: {e}")
        return
    try:
        html, updated = sites.article(guide, page)
    except ValueError as e:   # the page changed shape: keep the cache, say so
        errors.append(f"{raid}/{guide}: {e}")
        return
    md, images = extract.to_markdown(html, url)
    for n, image in enumerate(_images(raid, guide, images)):
        md = md.replace(f"{{{{img:{n}}}}}", image, 1)
    text = f"<!-- source: {url} · updated: {updated or 'unknown'} -->\n# {raid} — {guide}\n\n{md}\n"
    if write_if_changed(path, text):
        changed.append(rel)


def refresh(force: bool = False, only: list[str] | None = None) -> dict:
    """`only`: raid slugs (default: every configured raid)."""
    changed, stale, errors = [], [], []
    for raid in only or list(GUIDES):
        if raid not in GUIDES:
            errors.append(f"unknown raid: {raid} (raids: {', '.join(GUIDES)})")
            continue
        for guide, url in GUIDES[raid].items():
            _refresh_guide(raid, guide, url, force, changed, stale, errors)
        _index(raid)
    return report(NAME, folder(), changed, stale, errors)
