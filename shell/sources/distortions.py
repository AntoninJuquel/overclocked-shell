"""The hourly Distortion rotation (the Distorted destination drops one gear tier higher), in cache/distortions/.

Bungie does not publish it. Community trackers compute it from a fixed order of 7 destinations, one per hour,
and an anchor hour verified in game; this source reads those three constants from wewantdestiny3's tracker page
(nothing else of the page is kept) into rotation.json: order, anchor_hour (Unix epoch hours), anchor_index
(index of `order` active during anchor_hour), source, fetched.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from shell.core import paths
from shell.sources import report, web, write_if_changed

NAME = "distortions"
URL = "https://wewantdestiny3.com/distortion-tracker/"
SIZE = 7


def folder() -> Path:
    return paths.cache_dir() / "distortions"


def path() -> Path:
    return folder() / "rotation.json"


def load() -> dict | None:
    """The cached rotation, or None."""
    return json.loads(path().read_text(encoding="utf-8")) if path().exists() else None


def parse(html: str) -> dict:
    """{order, anchor_hour, anchor_index}; ValueError when the page no longer holds a valid rotation."""
    order = re.search(r"var\s+ROTATION\s*=\s*\[(.*?)\]", html, re.S)
    hour = re.search(r"var\s+ANCHOR_HOUR\s*=\s*(\d+)", html)
    index = re.search(r"var\s+ANCHOR_INDEX\s*=\s*(\d+)", html)
    if not (order and hour and index):
        raise ValueError("Distortion rotation not found on the tracker page")
    names = re.findall(r"""'([^']+)'|"([^"]+)\"""", order.group(1))
    names = [a or b for a, b in names]
    if len(names) != SIZE or len(set(names)) != SIZE or not 0 <= int(index.group(1)) < SIZE:
        raise ValueError(f"unexpected Distortion rotation on the tracker page: {names}, index {index.group(1)}")
    return {"order": names, "anchor_hour": int(hour.group(1)), "anchor_index": int(index.group(1))}


def _schedule_key(rot):
    """Two anchors giving the same schedule compare equal (the page may re-anchor)."""
    return rot["order"], (rot["anchor_index"] - rot["anchor_hour"]) % SIZE


def refresh(force: bool = False, only: list[str] | None = None) -> dict:
    old = load()
    if old is not None and not force:
        return report(NAME, folder())
    try:
        html = web.get(URL).decode("utf-8", "replace")
    except OSError as e:
        if old is not None:
            return report(NAME, folder(), stale=[path().name])
        return report(NAME, folder(), errors=[str(e)])
    try:
        rot = parse(html)
    except ValueError as e:   # the page changed shape: keep the cache, say so
        return report(NAME, folder(), stale=[path().name] if old is not None else [], errors=[str(e)])
    changed = old is None or _schedule_key(old) != _schedule_key(rot)
    rot.update(source=URL, fetched=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    write_if_changed(path(), json.dumps(rot, indent=1, ensure_ascii=False))
    return report(NAME, folder(), changed=[path().name] if changed else [])
