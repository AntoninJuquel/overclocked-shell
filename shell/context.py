"""Shared services for tools, built on first use so the server starts even without a complete .env."""
import threading
from dataclasses import dataclass, field
from functools import cached_property

from shell.core.auth import OAuth
from shell.core.bungie import BungieClient
from shell.core.manifest import Manifest
from shell.core.settings import Settings, load_settings
from shell.engines.defs import load_defs


@dataclass
class Context:
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    @cached_property
    def settings(self) -> Settings:
        return load_settings()

    @cached_property
    def oauth(self) -> OAuth:
        return OAuth(self.settings)

    @cached_property
    def client(self) -> BungieClient:
        return BungieClient(self.settings, self.oauth)

    @cached_property
    def manifest(self) -> Manifest:
        return Manifest(self.client)

    @cached_property
    def defs(self) -> dict:
        with self._lock:  # parallel tool calls must not build the index (and download tables) twice
            return self.__dict__.get("defs") or load_defs(self.manifest)
