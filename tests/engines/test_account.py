import httpx
import pytest

from shell.core.bungie import BungieApiError, BungieClient
from shell.core.settings import Settings
from shell.engines.account import character_id, get_profile, primary_membership

SETTINGS = Settings("k", "1", "s", "https://localhost:7777/callback")


class FakeOAuth:
    def access_token(self):
        return "a"


def client(response, seen=None):
    def handler(request):
        if seen is not None:
            seen.append(request)
        return httpx.Response(200, json={"ErrorCode": 1, "Response": response})
    return BungieClient(SETTINGS, FakeOAuth(), http=httpx.Client(transport=httpx.MockTransport(handler)),
                        sleep=lambda s: None)


ACCOUNTS = [{"membershipType": 1, "membershipId": "1"}, {"membershipType": 3, "membershipId": "2"}]


def test_primary_membership_prefers_primary():
    assert primary_membership(client({"primaryMembershipId": "2", "destinyMemberships": ACCOUNTS}))["membershipId"] == "2"


def test_primary_membership_falls_back_to_first():
    assert primary_membership(client({"destinyMemberships": ACCOUNTS}))["membershipId"] == "1"


def test_no_destiny_account_raises():
    with pytest.raises(BungieApiError, match="No Destiny account"):
        primary_membership(client({"destinyMemberships": []}))


def test_get_profile_components():
    seen = []
    get_profile(client({}, seen), ACCOUNTS[1], [200, 205])
    assert seen[0].url.path == "/Platform/Destiny2/3/Profile/2/"
    assert seen[0].url.params["components"] == "200,205"
    assert seen[0].headers["Authorization"] == "Bearer a"


PROFILE = {"characters": {"data": {"h": {"classType": 1}, "w": {"classType": 2}}}}


def test_character_id_by_class():
    assert character_id(PROFILE, "Warlock") == "w"


def test_missing_class_raises():
    with pytest.raises(BungieApiError, match="^No titan on this account.$"):
        character_id(PROFILE, "titan")
