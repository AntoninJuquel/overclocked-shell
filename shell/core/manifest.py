"""Manifest definition tables, downloaded once per manifest version into cache/manifest/<version>/ (English) or
cache/manifest-<lang>/<version>/ (another language)."""
import json
import os
import shutil
import threading
from pathlib import Path

from shell.core import paths
from shell.core.bungie import BASE, BungieApiError, BungieClient

INDEX = "/Destiny2/Manifest/"
INDEX_TIMEOUT = 10   # seconds: with a local copy, Bungie being down must not hold a tool back
IDLE_SECONDS = 600   # the item table costs 2 s to parse and 600 MB to hold: kept between calls, freed when idle


class Manifest:
    def __init__(self, client: BungieClient, cache_dir: Path | None = None, lang: str = "en"):
        self.client = client
        self.lang = lang
        self.root = (cache_dir or paths.cache_dir()) / ("manifest" if lang == "en" else f"manifest-{lang}")
        self._index: dict | None = None
        self._tables: dict[str, dict] = {}
        self._idle: dict[str, dict] = {}
        self._idle_timer: threading.Timer | None = None
        self._lock = threading.Lock()   # parallel tool calls share one parse of a table

    def version(self) -> str:
        return self._load_index()["version"]

    def table(self, name: str, keep: bool = True) -> dict[str, dict]:
        """A table, shared between callers: read only. `keep=False` for huge tables: freed after IDLE_SECONDS unused."""
        with self._lock:
            if name in self._tables:
                return self._tables[name]
            table = self._idle.get(name)
            if table is None:
                file = self.root / self.version() / f"{name}.json"
                table = json.loads(file.read_text(encoding="utf-8")) if file.exists() else self._download(name, file)
            if keep:
                self._idle.pop(name, None)
                self._tables[name] = table
            else:
                self._idle[name] = table
                self._free_idle_later()
            return table

    def _free_idle_later(self) -> None:
        if self._idle_timer:
            self._idle_timer.cancel()
        self._idle_timer = threading.Timer(IDLE_SECONDS, self._free_idle)
        self._idle_timer.daemon = True
        self._idle_timer.start()

    def _free_idle(self) -> None:
        with self._lock:
            self._idle.clear()

    def _local_version(self) -> str | None:
        """The version on disk (a download removes the others), or None."""
        found = [d for d in self.root.iterdir() if d.is_dir()] if self.root.exists() else []
        return max(found, key=lambda d: d.stat().st_mtime).name if found else None

    def _load_index(self) -> dict:
        if self._index is None:
            local = self._local_version()
            if local is None:
                self._index = self.client.get(INDEX)
            else:
                try:
                    self._index = self.client.get(INDEX, retries=0, timeout=INDEX_TIMEOUT)
                except BungieApiError:
                    self._index = {"version": local}   # maintenance, no network: what is cached still answers
        return self._index

    def _download(self, name: str, file: Path) -> dict:
        if "jsonWorldComponentContentPaths" not in self._load_index():   # was offline: this table needs Bungie anyway
            self._index = self.client.get(INDEX)
            file = self.root / self.version() / file.name
        langs = self._load_index()["jsonWorldComponentContentPaths"]
        if self.lang not in langs:
            raise ValueError(f"unknown manifest language {self.lang!r}: one of {', '.join(sorted(langs))}")
        table = self.client.download(BASE + langs[self.lang][name])
        file.parent.mkdir(parents=True, exist_ok=True)
        tmp = file.with_suffix(".tmp")
        tmp.write_text(json.dumps(table), encoding="utf-8")
        os.replace(tmp, file)
        for old in self.root.iterdir():
            if old.is_dir() and old != file.parent:
                shutil.rmtree(old, ignore_errors=True)
        return table
