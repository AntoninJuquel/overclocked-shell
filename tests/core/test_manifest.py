import httpx
import pytest

from shell.core.bungie import BungieClient
from shell.core.manifest import Manifest
from shell.core.settings import Settings

SETTINGS = Settings("k", "1", "s", "https://localhost:7777/callback")
TABLE_PATH = "/common/destiny2_content/json/en/DestinyClassDefinition-v1.json"


def server(version, table_calls, fail_table=False):
    def handler(request):
        if request.url.path == "/Platform/Destiny2/Manifest/":
            return httpx.Response(200, json={"ErrorCode": 1, "Response": {
                "version": version,
                "jsonWorldComponentContentPaths": {"en": {"DestinyClassDefinition": TABLE_PATH}}}})
        assert request.url.path == TABLE_PATH
        table_calls.append(version)
        if fail_table:
            raise httpx.ReadError("cut")
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
    with pytest.raises(Exception):
        Manifest(server("v1", [], fail_table=True), tmp_path).table("DestinyClassDefinition")
    assert not list((tmp_path / "manifest").rglob("*.json"))
