import httpx
import pytest

from shell.core.bungie import BungieApiError, BungieClient
from shell.core.manifest import Manifest
from shell.core.settings import Settings

SETTINGS = Settings("k", "1", "s", "https://localhost:7777/callback")
TABLE_PATH = "/common/destiny2_content/json/en/DestinyClassDefinition-v1.json"


FR_PATH = TABLE_PATH.replace("/en/", "/fr/")


def server(version, table_calls, fail_table=False, table_responses=None):
    def handler(request):
        if request.url.path == "/Platform/Destiny2/Manifest/":
            return httpx.Response(200, json={"ErrorCode": 1, "Response": {
                "version": version,
                "jsonWorldComponentContentPaths": {"en": {"DestinyClassDefinition": TABLE_PATH},
                                                   "fr": {"DestinyClassDefinition": FR_PATH}}}})
        if request.url.path == FR_PATH:
            return httpx.Response(200, json={"1": {"displayProperties": {"name": "Arcaniste"}}})
        assert request.url.path == TABLE_PATH
        table_calls.append(version)
        if fail_table:
            raise httpx.ReadError("cut")
        if table_responses:
            return table_responses.pop(0)
        return httpx.Response(200, json={"1": {"displayProperties": {"name": "Warlock"}}})
    return BungieClient(SETTINGS, None, http=httpx.Client(transport=httpx.MockTransport(handler)),
                        sleep=lambda s: None)


def test_table_downloads_once_per_version(tmp_path):
    calls = []
    assert Manifest(server("v1", calls), tmp_path).table("DestinyClassDefinition")["1"]["displayProperties"]
    m2 = Manifest(server("v1", calls), tmp_path)
    m2.table("DestinyClassDefinition")
    assert calls == ["v1"]
    assert (tmp_path / "manifest" / "v1" / "DestinyClassDefinition.json").exists()


def test_new_version_removes_old_folder(tmp_path):
    calls = []
    Manifest(server("v1", calls), tmp_path).table("DestinyClassDefinition")
    Manifest(server("v2", calls), tmp_path).table("DestinyClassDefinition")
    assert not (tmp_path / "manifest" / "v1").exists()
    assert (tmp_path / "manifest" / "v2" / "DestinyClassDefinition.json").exists()


def test_no_partial_file_on_failure(tmp_path):
    with pytest.raises(BungieApiError):
        Manifest(server("v1", [], fail_table=True), tmp_path).table("DestinyClassDefinition")
    assert not list((tmp_path / "manifest").rglob("*.json"))


def test_table_fetch_retried(tmp_path):
    good = httpx.Response(200, json={"1": {}})
    m = Manifest(server("v1", [], table_responses=[httpx.Response(503, text="busy"), good]), tmp_path)
    assert m.table("DestinyClassDefinition") == {"1": {}}


def test_invalid_table_not_cached(tmp_path):
    bad = [httpx.Response(200, text="<html>error</html>")]
    with pytest.raises(BungieApiError):
        Manifest(server("v1", [], table_responses=bad), tmp_path).table("DestinyClassDefinition")
    assert not list((tmp_path / "manifest").rglob("*.json"))


def test_table_keep_false_is_shared_then_freed_when_idle(tmp_path):
    m = Manifest(server("v1", []), tmp_path)
    first = m.table("DestinyClassDefinition", keep=False)
    assert m._tables == {}
    assert m.table("DestinyClassDefinition", keep=False) is first
    m._free_idle()
    assert m.table("DestinyClassDefinition", keep=False) is not first
    kept = m.table("DestinyClassDefinition")
    assert m.table("DestinyClassDefinition") is kept
    m._free_idle()
    assert m.table("DestinyClassDefinition", keep=False) is kept


def offline_client():
    def handler(request):
        raise httpx.ConnectError("down")
    waits = []
    return BungieClient(SETTINGS, None, http=httpx.Client(transport=httpx.MockTransport(handler)),
                        sleep=waits.append), waits


def test_offline_serves_the_local_version_without_waiting(tmp_path):
    Manifest(server("v1", []), tmp_path).table("DestinyClassDefinition")
    client, waits = offline_client()
    m = Manifest(client, tmp_path)
    assert m.version() == "v1"
    assert m.table("DestinyClassDefinition")["1"]
    assert waits == []


def test_offline_without_local_copy_fails(tmp_path):
    with pytest.raises(BungieApiError):
        Manifest(offline_client()[0], tmp_path).version()


def test_new_table_after_an_offline_start_uses_bungie_s_version(tmp_path):
    Manifest(server("v1", []), tmp_path).table("DestinyClassDefinition")
    m = Manifest(offline_client()[0], tmp_path)
    assert m.version() == "v1"
    (tmp_path / "manifest" / "v1" / "DestinyClassDefinition.json").unlink()
    with pytest.raises(BungieApiError):   # still offline: the table cannot be had
        m.table("DestinyClassDefinition")
    m.client = server("v2", [])   # back online, and Bungie moved on
    assert m.table("DestinyClassDefinition")["1"]
    assert m.version() == "v2"
    assert (tmp_path / "manifest" / "v2" / "DestinyClassDefinition.json").exists()


def test_language_has_its_own_folder(tmp_path):
    Manifest(server("v1", []), tmp_path).table("DestinyClassDefinition")
    fr = Manifest(server("v2", []), tmp_path, lang="fr").table("DestinyClassDefinition")
    assert fr["1"]["displayProperties"]["name"] == "Arcaniste"
    assert (tmp_path / "manifest" / "v1" / "DestinyClassDefinition.json").exists()   # other language kept
    assert (tmp_path / "manifest-fr" / "v2" / "DestinyClassDefinition.json").exists()


def test_unknown_language_is_named(tmp_path):
    with pytest.raises(ValueError, match="unknown manifest language 'xx'"):
        Manifest(server("v1", []), tmp_path, lang="xx").table("DestinyClassDefinition")
