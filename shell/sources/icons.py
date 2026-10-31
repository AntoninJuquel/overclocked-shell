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
    """The refs resolved so far ({} when the index is absent, unreadable or not a mapping)."""
    try:
        index = json.loads((folder() / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return index if isinstance(index, dict) else {}


def _valid(file: Path) -> bool:
    try:
        with file.open("rb") as f:
            return f.read(4).startswith(_SIGNATURES)
    except OSError:
        return False


def local(refs: dict[str, str], download=None) -> tuple[dict[str, Path], list[str]]:
    """{key: local file} for the refs, downloading what is missing; (files, warnings). Never raises."""
    download = download or globals()["download"]
    try:
        folder().mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return {}, [f"icon cache not writable: {e.strerror or e}"]
    lock, failures = threading.Lock(), [0]
    by_name = {PurePosixPath(ref).name: ref for ref in refs.values()}  # one download per file

    def fetch(item):
        name, ref = item
        file = folder() / name
        if _valid(file):
            return name, file, "ok"
        with lock:
            if failures[0] >= MAX_FAILURES:
                return name, None, "skipped"
        try:
            data = download(BASE + ref)
            if not data.startswith(_SIGNATURES):
                raise ValueError("not an image")
            tmp = file.with_name(file.name + ".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, file)
            return name, file, "ok"
        except Exception:
            with lock:
                failures[0] += 1
            return name, None, "failed"

    with ThreadPoolExecutor(8) as pool:
        results = {n: (f, s) for n, f, s in pool.map(fetch, by_name.items())}
    status = {k: results[PurePosixPath(r).name] for k, r in refs.items()}
    files = {k: f for k, (f, s) in status.items() if s == "ok"}
    warnings = [f"icon download failed: {k}" for k, (_, s) in status.items() if s == "failed"]
    if any(s == "skipped" for _, s in status.values()):
        warnings.append(f"icons: Bungie unreachable, {len(refs) - len(files)} icons missing")
    if files:
        try:
            tmp = folder() / "index.json.tmp"
            tmp.write_text(json.dumps(indexed() | {k: refs[k] for k in files}, indent=1), encoding="utf-8")
            os.replace(tmp, folder() / "index.json")
        except OSError as e:
            warnings.append(f"icon cache not writable: {e.strerror or e}")
    return files, warnings
