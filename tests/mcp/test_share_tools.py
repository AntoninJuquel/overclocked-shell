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


ICON_DEFS = {h: {**d, "hash": int(h), "displayProperties": {**d.get("displayProperties", {}), "icon": f"/common/{h}.png"}}
             for h, d in DEFS.items()}


SETS = {"7": {"displayProperties": {"name": "AION Renewal"},
              "setPerks": [{"requiredSetCount": 2, "sandboxPerkHash": 71}]}}
SET_PERKS = {"71": {"displayProperties": {"name": "Renewal Grasp", "icon": "/common/71.png"}}}


class FakeManifest:
    def table(self, name, keep=True):
        return {"DestinyInventoryItemDefinition": ICON_DEFS, "DestinySocketTypeDefinition": SOCKET_TYPES,
                "DestinyStatDefinition": {}, "DestinySandboxPerkDefinition": SET_PERKS,
                "DestinyEquipableItemSetDefinition": SETS}[name]


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


def test_build_pdf(root):
    with pytest.raises(ToolError, match="unknown build: nope"):
        call("build_pdf", {"slug": "nope"})
    result = call("build_pdf", {"slug": "good"})
    pdf = root / "profile" / "builds" / "good.pdf"
    assert result["pdf"] == str(pdf) and pdf.read_bytes().startswith(b"%PDF")
    assert (root / "profile" / "builds" / "good.md").exists()
    assert b"/Subtype /Image" in pdf.read_bytes()
    assert icons.indexed()["setperk:Renewal Grasp"] == "/common/71.png"
    assert b"https://www.light.gg/db/" in pdf.read_bytes() and b"/items/50" in pdf.read_bytes()


def test_build_pdf_needs_no_snapshot(root):
    result = call("build_pdf", {"slug": "good"})
    assert (root / "profile" / "builds" / "good.pdf").exists()
    assert not any("refresh_inventory" in w for w in result["warnings"])


def test_build_pdf_links_from_the_sheet_when_offline(root, monkeypatch):
    s = json.loads((root / "profile" / "builds" / "good.json").read_text(encoding="utf-8"))
    s["hashes"] = {"item:Getaway Artist": 424242}
    (root / "profile" / "builds" / "good.json").write_text(json.dumps(s), encoding="utf-8")
    monkeypatch.setattr(icons, "download", failing)
    call("build_pdf", {"slug": "good"}, DownManifest())
    assert b"/items/424242" in (root / "profile" / "builds" / "good.pdf").read_bytes()


def failing(url):
    raise OSError("no network")


def test_build_pdf_offline_uses_index(root, monkeypatch):
    call("build_pdf", {"slug": "good"})
    monkeypatch.setattr(icons, "download", failing)
    result = call("build_pdf", {"slug": "good"}, DownManifest())
    assert any(w.startswith("Bungie unreachable") for w in result["warnings"])
    assert b"/Subtype /Image" in (root / "profile" / "builds" / "good.pdf").read_bytes()


def test_build_pdf_offline_never_cached(root, monkeypatch):
    monkeypatch.setattr(icons, "download", failing)
    result = call("build_pdf", {"slug": "good"}, DownManifest())
    assert (root / "profile" / "builds" / "good.pdf").read_bytes().startswith(b"%PDF")
    warnings = result["warnings"]
    assert "Bungie unreachable: icons from the cache only" in warnings
    (line,) = [w for w in warnings if "icons missing" in w]
    count, names = line.split(" icons missing (placeholders): ")
    assert int(count) > 3 and names.endswith("...") and len(names[:-3].split(", ")) == 3
    assert not any(w.startswith("no icon:") for w in warnings)


def test_build_pdf_missing_key_reported_once(root):
    result = call("build_pdf", {"slug": "good"}, FakeManifest())
    assert not any(w.startswith(("icon not found:", "no icon:")) for w in result["warnings"])


def test_build_pdf_offline_ignores_deleted_cache_file(root, monkeypatch):
    call("build_pdf", {"slug": "good"})
    index = icons.indexed()
    gone = next(iter(index))
    (icons.folder() / index[gone].rsplit("/", 1)[-1]).unlink()
    calls = []
    monkeypatch.setattr(icons, "download", lambda url: calls.append(url) or failing(url))
    result = call("build_pdf", {"slug": "good"}, DownManifest())
    assert not calls and not any("download failed" in w for w in result["warnings"])


def test_build_png_and_html(root):
    result = call("build_png", {"slug": "good"})
    assert result["png"].endswith("good.png")
    assert (root / "profile" / "builds" / "good.png").read_bytes().startswith(b"\x89PNG")
    result = call("build_html", {"slug": "good"})
    page = (root / "profile" / "builds" / "good.html").read_text(encoding="utf-8")
    assert result["html"].endswith("good.html") and "data:image/png;base64," in page
    assert "https://www.light.gg/db/" in page and "/items/50" in page


def test_build_yaml(root):
    result = call("build_yaml", {"slug": "good"})
    path = root / "profile" / "builds" / "good.yaml"
    assert result["yaml"] == str(path) and path.read_text(encoding="utf-8").startswith("name:")
    assert "call check_build" in result["warnings"][0]
    with pytest.raises(ToolError, match="unknown build: nope"):
        call("build_yaml", {"slug": "nope"})


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
