"""Manifest definition tables, downloaded once per manifest version into cache/manifest/<version>/."""
import json
import os
import shutil
from pathlib import Path

from shell.core import paths
from shell.core.bungie import BASE, BungieClient


class Manifest:
    def __init__(self, client: BungieClient, cache_dir: Path | None = None):
        self.client = client
        self.root = (cache_dir or paths.cache_dir()) / "manifest"
        self._index: dict | None = None
        self._tables: dict[str, dict] = {}

    def version(self) -> str:
        return self._load_index()["version"]

    def table(self, name: str, keep: bool = True) -> dict[str, dict]:
        """`keep=False` for huge tables read once (e.g. to build an index): not memoized."""
        if name in self._tables:
            return self._tables[name]
        file = self.root / self.version() / f"{name}.json"
        table = json.loads(file.read_text(encoding="utf-8")) if file.exists() else self._download(name, file)
        if keep:
            self._tables[name] = table
        return table

    def _load_index(self) -> dict:
        if self._index is None:
            self._index = self.client.get("/Destiny2/Manifest/")
        return self._index

    def _download(self, name: str, file: Path) -> dict:
        table = self.client.download(BASE + self._load_index()["jsonWorldComponentContentPaths"]["en"][name])
        file.parent.mkdir(parents=True, exist_ok=True)
        tmp = file.with_suffix(".tmp")
        tmp.write_text(json.dumps(table), encoding="utf-8")
        os.replace(tmp, file)
        for old in self.root.iterdir():
            if old.is_dir() and old != file.parent:
                shutil.rmtree(old, ignore_errors=True)
        return table
