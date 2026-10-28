import base64
import json
from urllib.parse import parse_qs

import httpx
import pytest
import time
from concurrent.futures import ThreadPoolExecutor

from shell.core import paths
from shell.core.bungie import BungieApiError

from shell.core.auth import NotSignedIn, OAuth
from shell.core.settings import Settings

SETTINGS = Settings("k", "1", "s", "https://localhost:7777/callback")
NOW = 1_000_000.0
TOKEN_RESPONSE = {
    "access_token": "a", "token_type": "Bearer", "expires_in": 3600,
    "refresh_token": "r", "refresh_expires_in": 7776000, "membership_id": "42",
}


def make(tmp_path, handler, tokens=None):
    token_file = tmp_path / "auth" / "tokens.json"
    if tokens:
        token_file.parent.mkdir(parents=True)
        token_file.write_text(json.dumps(tokens))
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return OAuth(SETTINGS, token_file=token_file, http=http, clock=lambda: NOW), token_file


def stored(access_in, refresh_in=1000.0):
    return {"access_token": "a", "refresh_token": "r", "access_expires_at": NOW + access_in,
            "refresh_expires_at": NOW + refresh_in, "membership_id": "42"}


def never(request):
    raise AssertionError("no HTTP call expected")


def test_authorize_url():
    oauth = OAuth(SETTINGS, token_file=None)
    assert oauth.authorize_url("xyz") == (
        "https://www.bungie.net/en/oauth/authorize?client_id=1&response_type=code&state=xyz")


def test_exchange_code_stores_tokens(tmp_path):
    def handler(request):
        assert str(request.url) == "https://www.bungie.net/platform/app/oauth/token/"
        assert request.headers["Authorization"] == "Basic " + base64.b64encode(b"1:s").decode()
        form = parse_qs(request.content.decode())
        assert form == {"grant_type": ["authorization_code"], "code": ["abc"]}
        return httpx.Response(200, json=TOKEN_RESPONSE)

    oauth, token_file = make(tmp_path, handler)
    tokens = oauth.exchange_code("abc")
    assert tokens.access_expires_at == NOW + 3600
    assert json.loads(token_file.read_text())["membership_id"] == "42"


def test_access_token_refreshes_near_expiry(tmp_path):
    calls = []

    def handler(request):
        calls.append(parse_qs(request.content.decode()))
        return httpx.Response(200, json={**TOKEN_RESPONSE, "access_token": "a2"})

    oauth, token_file = make(tmp_path, handler, stored(access_in=60))
    assert oauth.access_token() == "a2"
    assert calls == [{"grant_type": ["refresh_token"], "refresh_token": ["r"]}]
    assert json.loads(token_file.read_text())["access_token"] == "a2"


def test_access_token_cached_when_fresh(tmp_path):
    oauth, _ = make(tmp_path, never, stored(access_in=600))
    assert oauth.access_token() == "a"


def test_expired_refresh_raises_not_signed_in(tmp_path):
    oauth, _ = make(tmp_path, never, stored(access_in=-10, refresh_in=-1))
    with pytest.raises(NotSignedIn, match="shell auth login"):
        oauth.access_token()


def test_no_tokens_raises_not_signed_in(tmp_path):
    oauth, _ = make(tmp_path, never)
    with pytest.raises(NotSignedIn, match="shell auth login"):
        oauth.access_token()


def test_missing_refresh_token_mentions_confidential(tmp_path):
    body = {k: v for k, v in TOKEN_RESPONSE.items() if k != "refresh_token"}
    oauth, _ = make(tmp_path, lambda r: httpx.Response(200, json=body))
    with pytest.raises(RuntimeError, match="Confidential"):
        oauth.exchange_code("abc")


def test_status(tmp_path):
    oauth, token_file = make(tmp_path, never, stored(access_in=600))
    s = oauth.status()
    assert s["signed_in"] is True and s["membership_id"] == "42" and s["token_file"] == str(token_file)
    oauth2, _ = make(tmp_path / "x", never)
    assert oauth2.status()["signed_in"] is False


def test_refused_refresh_raises_not_signed_in(tmp_path):
    oauth, _ = make(tmp_path, lambda r: httpx.Response(400, json={"error": "invalid_grant"}), stored(access_in=-10))
    with pytest.raises(NotSignedIn, match="refused"):
        oauth.access_token()


def test_token_endpoint_down_raises_bungie_error(tmp_path):
    oauth, _ = make(tmp_path, lambda r: httpx.Response(503, text="down"), stored(access_in=-10))
    with pytest.raises(BungieApiError):
        oauth.access_token()


def test_network_error_on_refresh_raises_bungie_error(tmp_path):
    def handler(request):
        raise httpx.ConnectError("offline")
    oauth, _ = make(tmp_path, handler, stored(access_in=-10))
    with pytest.raises(BungieApiError):
        oauth.access_token()


def test_concurrent_calls_refresh_once(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        time.sleep(0.2)
        return httpx.Response(200, json={**TOKEN_RESPONSE, "access_token": "a2"})

    oauth, _ = make(tmp_path, handler, stored(access_in=60))
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: oauth.access_token(), range(2)))
    assert results == ["a2", "a2"] and len(calls) == 1


def test_sign_in_hint_names_install_root():
    assert f'uv run --directory "{paths.ROOT}" shell auth login' in str(NotSignedIn())
