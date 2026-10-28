from shell.core.bungie import BungieApiError
from shell.engines.actions import Actions, describe


def test_describe_known_and_unknown_codes():
    assert describe(BungieApiError("boom", 1642)) == "no room in destination (boom)"
    assert describe(BungieApiError("weird", 9999)) == "weird"


class FakeClient:
    def __init__(self, fail=False):
        self.posts, self.fail = [], fail

    def post(self, path, body):
        self.posts.append((path, body))
        if self.fail:
            raise BungieApiError("nope", 1623)
        return {"ok": 1}


def test_post_adds_membership_type_and_sleeps_after_success_only():
    sleeps, client = [], FakeClient()
    actions = Actions(client, {"membershipType": 3, "membershipId": "1"}, sleep=sleeps.append)
    assert actions.post("/Destiny2/Actions/Items/SetLockState/", {"state": True}) == {"ok": 1}
    assert client.posts == [("/Destiny2/Actions/Items/SetLockState/", {"state": True, "membershipType": 3})]
    assert sleeps == [0.25]
    failing = Actions(FakeClient(fail=True), {"membershipType": 3}, sleep=sleeps.append)
    try:
        failing.post("/x/", {}, gap=0.6)
    except BungieApiError:
        pass
    assert sleeps == [0.25]
