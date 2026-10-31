"""Manifest icons cached as files in cache/icons/, with an index.json of the refs ever resolved (offline use)."""
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

import httpx

from shell.core import paths

BASE = "https://www.bungie.net"
MAX_FAILURES = 3
_SIGNATURES = (b"\x89PNG", b"\xff\xd8")


def folder() -> Path:
    return paths.cache_dir() / "icons"


def download(url: str) -> bytes:
    r = httpx.get(url, timeout=10, follow_redirects=True)
    r.raise_for_status()
    return r.content


def indexed() -> dict[str, str]:
    """The refs resolved so far ({} when the index is absent or unreadable)."""
    try:
        return json.loads((folder() / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _valid(file: Path) -> bool:
    try:
        with file.open("rb") as f:
            return f.read(4).startswith(_SIGNATURES)
    except OSError:
        return False


def local(refs: dict[str, str], download=None) -> tuple[dict[str, Path], list[str]]:
    """{key: local file} for the refs, downloading what is missing; (files, warnings)."""
    download = download or globals()["download"]
    folder().mkdir(parents=True, exist_ok=True)
    lock, failures = threading.Lock(), [0]

    def fetch(item):
        key, ref = item
        file = folder() / PurePosixPath(ref).name
        if _valid(file):
            return key, file, "ok"
        with lock:
            if failures[0] >= MAX_FAILURES:
                return key, None, "skipped"
        try:
            data = download(BASE + ref)
            if not data.startswith(_SIGNATURES):
                raise ValueError("not an image")
            tmp = file.with_name(file.name + ".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, file)
            return key, file, "ok"
        except Exception:
            with lock:
                failures[0] += 1
            return key, None, "failed"

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(fetch, refs.items()))
    files = {k: f for k, f, s in results if s == "ok"}
    warnings = [f"icon download failed: {k}" for k, _, s in results if s == "failed"]
    skipped = sum(s == "skipped" for _, _, s in results)
    if skipped:
        warnings.append(f"icons: Bungie unreachable, {len(refs) - len(files)} icons missing")
    if files:
        index = indexed() | {k: refs[k] for k in files}
        tmp = folder() / "index.json.tmp"
        tmp.write_text(json.dumps(index, indent=1), encoding="utf-8")
        os.replace(tmp, folder() / "index.json")
    return files, warnings
