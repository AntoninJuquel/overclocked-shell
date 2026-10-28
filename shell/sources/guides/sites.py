"""Where each guide site keeps its article and its last-modified date (checked on the live pages 2026-10-28)."""
import json
import re
from datetime import datetime

# shortcut: the article ends at the first end marker after its start; nested <article> would cut it short.
CONTAINERS = {
    "shacknews": (r'<article id="detail-view"', "</article>"),
    "overgear": (r'<div class="entry-content"', "</main>"),
}


def _ld_modified(html):
    m = re.search(r'"dateModified"\s*:\s*"(\d{4}-\d\d-\d\d)', html)
    return m.group(1) if m else None


def _grindout(html):
    m = re.search(r'<script[^>]*data-page="app"[^>]*>(.*?)</script>', html, re.S)
    try:
        guide = json.loads(m.group(1))["props"]["guide"]
        article = guide["description"]
    except (AttributeError, KeyError, TypeError, ValueError):
        raise ValueError("grindout: article not found (page data changed)") from None
    try:
        date = datetime.strptime(guide.get("updated_at") or "", "%d %b %Y").date().isoformat()
    except ValueError:
        date = None
    return article, date


def article(site: str, html: str) -> tuple[str, str | None]:
    """(article HTML, last-modified date YYYY-MM-DD or None). ValueError when the article cannot be found."""
    if site == "grindout":
        return _grindout(html)
    if site not in CONTAINERS:
        raise ValueError(f"{site}: unknown guide site")
    start_pattern, end = CONTAINERS[site]
    start = re.search(start_pattern, html)
    if start is None:
        raise ValueError(f"{site}: article not found (page layout changed)")
    stop = html.find(end, start.start())
    body = html[start.start(): stop + len(end) if end == "</article>" and stop >= 0 else stop if stop >= 0 else None]
    meta = re.search(r'property="article:modified_time"\s+content="(\d{4}-\d\d-\d\d)', html)
    return body, meta.group(1) if meta else _ld_modified(html)
