import asyncio
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.core import paths
from shell.mcp.server import build_server
from tests.engines.builds.test_sheet import SHEET
from tests.engines.test_share import ARMOR, DEFS, SOCKET_TYPES, WEAPONS


class FakeManifest:
    def table(self, name, keep=True):
        return {"DestinyInventoryItemDefinition": DEFS, "DestinySocketTypeDefinition": SOCKET_TYPES}[name]


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(paths, "profile_dir", lambda: tmp_path / "profile")
    folder = tmp_path / "profile" / "builds"
    folder.mkdir(parents=True)
    (folder / "good.json").write_text(json.dumps(SHEET), encoding="utf-8")
    return tmp_path


def call(name, args):
    ctx = Context()
    ctx.__dict__.update(manifest=FakeManifest())
    result = asyncio.run(build_server(ctx).call_tool(name, args))
    return json.loads(result.content[0].text)


def test_build_pdf(root):
    with pytest.raises(ToolError, match="unknown build: nope"):
        call("build_pdf", {"slug": "nope"})
    result = call("build_pdf", {"slug": "good"})
    pdf = root / "profile" / "builds" / "good.pdf"
    assert result["pdf"] == str(pdf) and pdf.read_bytes().startswith(b"%PDF")
    assert (root / "profile" / "builds" / "good.md").exists()


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
