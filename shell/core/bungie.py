"""Bungie.net Platform API client: API key, optional OAuth bearer, Response unwrapping, retries."""
import time
from typing import Any, Callable

import httpx

from shell.core.settings import Settings

BASE = "https://www.bungie.net"
API = BASE + "/Platform"
RETRYABLE_CODES = {5, 35, 36}  # SystemDisabled, ThrottleLimit, PerEndpointRequestThrottleExceeded
MAX_RETRIES = 3


class BungieApiError(Exception):
    def __init__(self, message: str, error_code: int | None = None, status: str | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.status = status


class BungieClient:
    def __init__(self, settings: Settings, oauth=None, http: httpx.Client | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        self.settings = settings
        self.oauth = oauth
        self.http = http or httpx.Client(timeout=60)
        self.sleep = sleep

    def get(self, path: str, params: dict | None = None, auth: bool = False, retries: int = MAX_RETRIES,
            **request) -> Any:
        """`request`: extra httpx options, e.g. `timeout`."""
        return self._call("GET", path, auth, retries, params=params, **request)

    def post(self, path: str, body: dict) -> Any:
        return self._call("POST", path, True, MAX_RETRIES, json=body)

    def download(self, url: str) -> Any:
        """GET a raw JSON document (manifest tables), with the same retries and errors as API calls."""
        return self._send("GET", url, {}, False, MAX_RETRIES)

    def _call(self, method: str, path: str, auth: bool, retries: int, **kwargs) -> Any:
        headers = {"X-API-Key": self.settings.api_key}
        if auth:
            headers["Authorization"] = f"Bearer {self.oauth.access_token()}"
        return self._send(method, API + path, headers, True, retries, **kwargs)

    def _send(self, method: str, url: str, headers: dict, envelope: bool, retries: int, **kwargs) -> Any:
        for attempt in range(retries + 1):
            wait = 2 ** attempt
            try:
                res = self.http.request(method, url, headers=headers, **kwargs)
            except httpx.TransportError as e:
                error = BungieApiError(f"Network error calling Bungie: {e}")
            else:
                try:
                    data = res.json()
                except ValueError:
                    data = None
                if envelope and isinstance(data, dict) and "ErrorCode" in data:
                    if data["ErrorCode"] == 1:
                        return data.get("Response")
                    error = BungieApiError(f"Bungie error {data.get('ErrorStatus')}: {data.get('Message', '')}",
                                           data["ErrorCode"], data.get("ErrorStatus"))
                    if error.error_code not in RETRYABLE_CODES:
                        raise error
                    wait = max(data.get("ThrottleSeconds") or 0, wait)
                elif not envelope and res.status_code == 200 and data is not None:
                    return data
                else:
                    error = BungieApiError(f"Bungie HTTP {res.status_code}: unexpected response")
                    if res.status_code < 500 and res.status_code != 429:
                        raise error
            if attempt == retries:
                raise error
            self.sleep(wait)
