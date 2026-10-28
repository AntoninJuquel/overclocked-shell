import httpx
import pytest

from shell.core.bungie import BungieApiError, BungieClient
from shell.core.settings import Settings

SETTINGS = Settings("k", "1", "s", "https://localhost:7777/callback")
OK = {"ErrorCode": 1, "ErrorStatus": "Success", "Response": {"x": 1}}


class FakeOAuth:
    def access_token(self):
        return "a"


def client(responses, sleeps=None):
    seen = []

    def handler(request):
        seen.append(request)
        r = responses.pop(0)
        return r if isinstance(r, httpx.Response) else httpx.Response(200, json=r)

    c = BungieClient(SETTINGS, FakeOAuth(), http=httpx.Client(transport=httpx.MockTransport(handler)),
                     sleep=(sleeps.append if sleeps is not None else lambda s: None))
    return c, seen


def test_get_unwraps_and_sends_api_key():
    c, seen = client([OK])
    assert c.get("/Destiny2/Manifest/") == {"x": 1}
    assert str(seen[0].url) == "https://www.bungie.net/Platform/Destiny2/Manifest/"
    assert seen[0].headers["X-API-Key"] == "k"
    assert "Authorization" not in seen[0].headers


def test_auth_get_sends_bearer():
    c, seen = client([OK])
    c.get("/User/GetMembershipsForCurrentUser/", auth=True)
    assert seen[0].headers["Authorization"] == "Bearer a"


def test_post_is_authenticated_json():
    c, seen = client([OK])
    c.post("/Destiny2/Actions/Items/SetLockState/", {"state": True})
    assert seen[0].method == "POST" and seen[0].headers["Authorization"] == "Bearer a"
    assert seen[0].content == b'{"state":true}' or b'"state": true' in seen[0].content


def test_error_code_raises_without_retry():
    c, seen = client([{"ErrorCode": 1601, "ErrorStatus": "DestinyAccountNotFound", "Message": "nope"}])
    with pytest.raises(BungieApiError) as e:
        c.get("/x/")
    assert e.value.error_code == 1601 and e.value.status == "DestinyAccountNotFound"
    assert len(seen) == 1


def test_throttle_retried_then_ok():
    sleeps = []
    c, seen = client([{"ErrorCode": 36, "ErrorStatus": "Throttle", "ThrottleSeconds": 5}, OK], sleeps)
    assert c.get("/x/") == {"x": 1}
    assert sleeps == [5]


def test_maintenance_gives_up_after_3_retries():
    down = {"ErrorCode": 5, "ErrorStatus": "SystemDisabled", "Message": "maintenance"}
    c, seen = client([down] * 4)
    with pytest.raises(BungieApiError) as e:
        c.get("/x/")
    assert e.value.error_code == 5 and len(seen) == 4


def test_http_503_retried():
    c, seen = client([httpx.Response(503, text="busy"), OK])
    assert c.get("/x/") == {"x": 1} and len(seen) == 2
