import asyncio
import base64
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.core import paths
from shell.core.bungie import BungieApiError
from shell.sources import icons
from shell.mcp.server import build_server
from tests.engines.builds.test_sheet import SHEET
from tests.engines.test_share import ARMOR, DEFS, SOCKET_TYPES, WEAPONS


PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5E"
                       "rkJggg==")


ICON_DEFS = {h: {**d, "displayProperties": {**d.get("displayProperties", {}), "icon": f"/common/{h}.png"}}
             for h, d in DEFS.items()}


class FakeManifest:
    def table(self, name, keep=True):
        return {"DestinyInventoryItemDefinition": ICON_DEFS, "DestinySocketTypeDefinition": SOCKET_TYPES,
                "DestinyStatDefinition": {}}[name]


class DownManifest:
    def table(self, name, keep=True):
        raise BungieApiError("down")


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(paths, "profile_dir", lambda: tmp_path / "profile")
    folder = tmp_path / "profile" / "builds"
    folder.mkdir(parents=True)
    (folder / "good.json").write_text(json.dumps(SHEET), encoding="utf-8")
    return tmp_path


def call(name, args, manifest=None):
    ctx = Context()
    ctx.__dict__.update(manifest=manifest or FakeManifest())
    result = asyncio.run(build_server(ctx).call_tool(name, args))
    return json.loads(result.content[0].text)


@pytest.fixture(autouse=True)
def png(monkeypatch):
    monkeypatch.setattr(icons, "download", lambda url: PNG)


def snapshots(root):
    folder = root / "profile" / "inventory"
    folder.mkdir(parents=True)
    (folder / "armor.json").write_text(json.dumps(ARMOR), encoding="utf-8")
    (folder / "weapons.json").write_text(json.dumps(WEAPONS), encoding="utf-8")


def test_build_pdf(root):
    snapshots(root)
    with pytest.raises(ToolError, match="unknown build: nope"):
        call("build_pdf", {"slug": "nope"})
    result = call("build_pdf", {"slug": "good"})
    pdf = root / "profile" / "builds" / "good.pdf"
    assert result["pdf"] == str(pdf) and pdf.read_bytes().startswith(b"%PDF")
    assert (root / "profile" / "builds" / "good.md").exists()
    assert b"/Subtype /Image" in pdf.read_bytes()


def test_build_pdf_without_snapshot_warns(root):
    result = call("build_pdf", {"slug": "good"})
    assert any("refresh_inventory" in w for w in result["warnings"])


def failing(url):
    raise OSError("no network")


def test_build_pdf_offline_uses_index(root, monkeypatch):
    snapshots(root)
    call("build_pdf", {"slug": "good"})
    monkeypatch.setattr(icons, "download", failing)
    result = call("build_pdf", {"slug": "good"}, DownManifest())
    assert any(w.startswith("Bungie unreachable") for w in result["warnings"])
    assert b"/Subtype /Image" in (root / "profile" / "builds" / "good.pdf").read_bytes()


def test_build_pdf_offline_never_cached(root, monkeypatch):
    snapshots(root)
    monkeypatch.setattr(icons, "download", failing)
    result = call("build_pdf", {"slug": "good"}, DownManifest())
    assert (root / "profile" / "builds" / "good.pdf").read_bytes().startswith(b"%PDF")
    warnings = result["warnings"]
    assert "Bungie unreachable: icons from the cache only" in warnings
    (line,) = [w for w in warnings if "icons missing" in w]
    count, names = line.split(" icons missing (placeholders): ")
    assert int(count) > 3 and names.endswith("...") and len(names[:-3].split(", ")) == 3
    assert not any(w.startswith("no icon:") for w in warnings)


def test_build_pdf_corrupt_snapshot(root):
    snapshots(root)
    (root / "profile" / "inventory" / "armor.json").write_text("{", encoding="utf-8")
    result = call("build_pdf", {"slug": "good"})
    assert (root / "profile" / "builds" / "good.pdf").read_bytes().startswith(b"%PDF")
    assert any("armor snapshot" in w and "refresh_inventory" in w for w in result["warnings"])


def test_build_dim_link(root):
    with pytest.raises(ToolError, match="refresh_inventory"):
        call("build_dim_link", {"slug": "good"})
    folder = root / "profile" / "inventory"
    folder.mkdir(parents=True)
    (folder / "armor.json").write_text(json.dumps(ARMOR), encoding="utf-8")
    (folder / "weapons.json").write_text(json.dumps(WEAPONS), encoding="utf-8")
    result = call("build_dim_link", {"slug": "good"})
    loadout = json.loads(parse_qs(urlsplit(result["url"]).query)["loadout"][0])
    assert loadout["name"] == SHEET["name"] and result["length"] == len(result["url"])
    assert result["snapshot"] and isinstance(result["warnings"], list)
    assert result["items"] == len(loadout["equipped"]) and result["mods"] == len(loadout["parameters"]["mods"])
