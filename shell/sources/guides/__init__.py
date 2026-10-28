"""Raid guides chosen by the player, cached as Markdown with their in-article images (cache/guides/<raid>/).

Third-party content: kept locally for the Ghost to read when it writes an encounter file, never published.
"""
import http.client
import json
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

MAX_IMAGE = 10 * 1024 * 1024
UNAVAILABLE = "(image unavailable)"
DOWNLOAD_ERRORS = (OSError, ValueError, http.client.HTTPException)


def folder() -> Path:
    return paths.cache_dir() / "guides"


def guide_path(raid: str, guide: str) -> Path:
    return folder() / raid / f"{guide}.md"


def _today():
    return datetime.now(timezone.utc).date().isoformat()


def _image_type(data):
    """Extension from the file's first bytes (hosts serve WebP as .jpg, or an HTML error page); None if not an image."""
    if not data or len(data) > MAX_IMAGE:
        return None
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    magics = ((bytes.fromhex("ffd8ff"), ".jpg"), (bytes.fromhex("89504e47"), ".png"), (b"GIF8", ".gif"))
    return next((ext for magic, ext in magics if data.startswith(magic)), None)


def _images(raid, guide, images):
    """Downloads the images into a side folder, once each (best-effort): (Markdown per image, folder, failures)."""
    tmp = folder() / raid / f".{guide}.new"
    shutil.rmtree(tmp, ignore_errors=True)
    out, failed = [], 0
    for n, (url, alt) in enumerate(images):
        try:
            data = web.get(url, tries=1)
        except DOWNLOAD_ERRORS:
            data = None
        ext = _image_type(data)
        if ext is None:
            failed += 1
            out.append(f"![{alt} {UNAVAILABLE}]()")
            continue
        tmp.mkdir(parents=True, exist_ok=True)
        (tmp / f"img-{n:02}{ext}").write_bytes(data)
        out.append(f"![{alt}]({guide}/img-{n:02}{ext})")
    return out, tmp, failed


def _fetched_path(raid):
    return folder() / raid / "fetched.json"


def _mark_fetched(raid, guide):
    path = _fetched_path(raid)
    dates = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    dates[guide] = _today()
    write_if_changed(path, json.dumps(dates, indent=1))


def _index(raid):
    rows = ["| guide | updated | images | url | fetched |", "|---|---|---|---|---|"]
    for guide, url in GUIDES[raid].items():
        path = guide_path(raid, guide)
        if not path.exists():
            continue
        head = path.read_text(encoding="utf-8").split("\n", 1)[0]
        updated = (re.search(r"updated: (\S+)", head) or [None, "unknown"])[1]
        images = len(list((folder() / raid / guide).glob("img-*"))) if (folder() / raid / guide).exists() else 0
        dates = json.loads(_fetched_path(raid).read_text(encoding="utf-8")) if _fetched_path(raid).exists() else {}
        fetched = dates.get(guide) or datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).date().isoformat()
        rows.append(f"| {guide} | {updated} | {images} | {url} | {fetched} |")
    write_if_changed(folder() / raid / "index.md", f"# Guides — {raid}\n\n" + "\n".join(rows) + "\n")


def _refresh_guide(raid, guide, url, force, changed, stale, errors):
    path, rel = guide_path(raid, guide), f"{raid}/{guide}.md"
    if path.exists() and not force:
        return
    try:
        page = web.get(url).decode("utf-8", "replace")
    except DOWNLOAD_ERRORS as e:
        if path.exists():
            stale.append(rel)
        else:
            errors.append(f"{raid}/{guide}: {e}")
        return
    try:
        html, updated = sites.article(guide, page)
    except ValueError as e:   # the page changed shape: keep the cache, say so
        errors.append(f"{raid}/{guide}: {e}")
        return
    md, images = extract.to_markdown(html, url)
    shown, tmp, failed = _images(raid, guide, images)
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old is not None and failed > old.count(UNAVAILABLE):
        # more images missing than last time (a host down?): keep the previous text and images together
        shutil.rmtree(tmp, ignore_errors=True)
        stale.append(rel)
        return
    target = folder() / raid / guide
    shutil.rmtree(target, ignore_errors=True)
    if tmp.exists():
        tmp.rename(target)
    for n, image in enumerate(shown):
        md = md.replace(f"{{{{img:{n}}}}}", image, 1)
    _mark_fetched(raid, guide)
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
