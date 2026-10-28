"""Bungie.net OAuth 2.0, confidential client (https://github.com/Bungie-net/api/wiki/OAuth-Documentation)."""
import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode

import httpx

from shell.core import paths
from shell.core.bungie import BungieApiError
from shell.core.settings import Settings

AUTHORIZE_URL = "https://www.bungie.net/en/oauth/authorize"
TOKEN_URL = "https://www.bungie.net/platform/app/oauth/token/"
REFRESH_MARGIN = 120  # seconds before expiry


class NotSignedIn(Exception):
    def __init__(self, reason: str = "Not signed in to Bungie."):
        super().__init__(f'{reason} Run `uv run --directory "{paths.ROOT}" shell auth login`.')


@dataclass
class Tokens:
    access_token: str
    refresh_token: str
    access_expires_at: float
    refresh_expires_at: float
    membership_id: str


class OAuth:
    def __init__(self, settings: Settings, token_file: Path | None = None, http: httpx.Client | None = None,
                 clock: Callable[[], float] = time.time):
        self.settings = settings
        self.token_file = token_file or paths.profile_dir() / "auth" / "tokens.json"
        self.http = http or httpx.Client(timeout=30)
        self.clock = clock
        self._lock = threading.Lock()  # parallel tool calls must not both spend the refresh token

    def authorize_url(self, state: str) -> str:
        params = {"client_id": self.settings.client_id, "response_type": "code", "state": state}
        return f"{AUTHORIZE_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> Tokens:
        return self._request({"grant_type": "authorization_code", "code": code})

    def access_token(self) -> str:
        with self._lock:
            return self._access_token()

    def _access_token(self) -> str:
        tokens = self._load()
        if tokens is None:
            raise NotSignedIn()
        if self.clock() < tokens.access_expires_at - REFRESH_MARGIN:
            return tokens.access_token
        if self.clock() >= tokens.refresh_expires_at:
            raise NotSignedIn("Bungie sign-in has expired.")
        return self._request({"grant_type": "refresh_token", "refresh_token": tokens.refresh_token}).access_token

    def status(self) -> dict:
        tokens = self._load()
        if tokens is None:
            return {"signed_in": False, "token_file": str(self.token_file)}
        iso = lambda t: datetime.fromtimestamp(t, timezone.utc).isoformat()  # noqa: E731
        return {
            "signed_in": self.clock() < tokens.refresh_expires_at,
            "membership_id": tokens.membership_id,
            "access_expires_at": iso(tokens.access_expires_at),
            "refresh_expires_at": iso(tokens.refresh_expires_at),
            "token_file": str(self.token_file),
        }

    def _request(self, form: dict) -> Tokens:
        try:
            res = self.http.post(TOKEN_URL, data=form, auth=(self.settings.client_id, self.settings.client_secret))
        except httpx.TransportError as e:
            raise BungieApiError(f"Network error reaching Bungie sign-in: {e}") from e
        if res.status_code in (400, 401):
            raise NotSignedIn(f"Bungie refused the saved sign-in ({res.text[:200]}).")
        if res.status_code != 200:
            raise BungieApiError(f"Bungie sign-in unavailable: HTTP {res.status_code}")
        data = res.json()
        if not data.get("refresh_token") or not data.get("refresh_expires_in"):
            raise RuntimeError('Bungie returned no refresh token: set the app\'s OAuth Client Type to "Confidential".')
        now = self.clock()
        tokens = Tokens(data["access_token"], data["refresh_token"], now + data["expires_in"],
                        now + data["refresh_expires_in"], str(data["membership_id"]))
        self._save(tokens)
        return tokens

    def _load(self) -> Tokens | None:
        try:
            return Tokens(**json.loads(self.token_file.read_text()))
        except (OSError, ValueError, TypeError):
            return None

    def _save(self, tokens: Tokens) -> None:
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.token_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(tokens), indent=2))
        os.replace(tmp, self.token_file)
