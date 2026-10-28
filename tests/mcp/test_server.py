import asyncio
import json

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.core.auth import NotSignedIn
from shell.core.bungie import BungieClient
from shell.core.settings import Settings
from shell.mcp.server import build_server

SETTINGS = Settings("k", "1", "s", "https://localhost:7777/callback")


class FakeOAuth:
    def __init__(self, error=None):
        self.error = error

    def access_token(self):
        if self.error:
            raise self.error
        return "a"


class FakeManifest:
    def table(self, name):
        assert name == "DestinyClassDefinition"
        return {"2271682572": {"displayProperties": {"name": "Warlock"}}}


def ok(response):
    return httpx.Response(200, json={"ErrorCode": 1, "Response": response})


def handler(request):
    if request.url.path == "/Platform/User/GetMembershipsForCurrentUser/":
        return ok({"primaryMembershipId": "4611", "destinyMemberships": [
            {"membershipType": 1, "membershipId": "999", "bungieGlobalDisplayName": "Other"},
            {"membershipType": 3, "membershipId": "4611", "bungieGlobalDisplayName": "Antonin",
             "bungieGlobalDisplayNameCode": 1234}]})
    assert request.url.path == "/Platform/Destiny2/3/Profile/4611/"
    assert request.url.params["components"] == "200"
    return ok({"characters": {"data": {"c1": {"characterId": "c1", "classHash": 2271682572, "light": 2010}}}})


def context(oauth=None):
    ctx = Context()
    oauth = oauth or FakeOAuth()
    ctx.__dict__.update(settings=SETTINGS, oauth=oauth, manifest=FakeManifest(), client=BungieClient(
        SETTINGS, oauth, http=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None))
    return ctx


def call(ctx, name):
    return asyncio.run(build_server(ctx).call_tool(name, {}))


def test_discovers_tools():
    names = {t.name for t in asyncio.run(build_server(Context()).list_tools())}
    assert {"auth_status", "get_profile_summary"} <= names


def test_not_signed_in_is_one_line():
    with pytest.raises(ToolError) as e:
        call(context(FakeOAuth(NotSignedIn())), "get_profile_summary")
    assert "shell auth login" in str(e.value) and "Traceback" not in str(e.value)


def test_profile_summary_shape():
    result = call(context(), "get_profile_summary")
    assert json.loads(result.content[0].text) == {
        "display_name": "Antonin#1234", "membership_type": 3, "membership_id": "4611",
        "characters": [{"character_id": "c1", "class": "Warlock", "light": 2010}]}
