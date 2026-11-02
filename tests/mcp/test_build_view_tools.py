import asyncio
import copy
import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.core import paths
from shell.engines.builds import catalog
from shell.mcp.server import build_server
from tests.engines.builds.test_sheet import SHEET
from tests.engines.builds.test_subclass import plug
from tests.engines.builds.test_weapons import ITEMS
from tests.sources.aegis.conftest import write_aegis

ITEM_DEFS = {
    "1": plug("Electrostatic Mind", "warlock.arc.aspects", cap=2),
    "2": plug("Lightning Surge", "warlock.arc.aspects", cap=3),
    "3": plug("Spark of Shock", "shared.arc.fragments", cost=1),
    "4": plug("Spark of Magnitude", "shared.arc.fragments", cost=1),
    "5": plug("Stormtrance", "warlock.arc.supers"),
    "6": plug("Storm Grenade", "shared.arc.grenades"),
}
ARTIFACT_MD = "## Satchel (Revenant)\n\n### Supernova\n- section: Satchel (Revenant)\n- column: 3\n"


class _NoTables:
    def table(self, name, keep=True):
        return {}


@pytest.fixture
def root(tmp_path, monkeypatch):
    from shell.sources.aegis import lookup
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(paths, "profile_dir", lambda: tmp_path / "profile")
    monkeypatch.setattr(lookup, "DATA", None)
    monkeypatch.setattr(catalog, "load_catalog", lambda manifest: {"subclass": catalog.build_index(ITEM_DEFS)})
    return tmp_path


@pytest.fixture
def call(root):
    ctx = Context()
    ctx.__dict__.update(manifest=_NoTables(), defs={"plugs": {}})
    mcp = build_server(ctx)

    def run(name, args=None):
        result = asyncio.run(mcp.call_tool(name, args or {}))
        return (result.structured_content or {}).get("result", json.loads(result.content[0].text)
                                                      if result.content[0].text.startswith("{") else None)
    return run


def write_sheet(root, slug, s):
    folder = root / "profile" / "builds"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{slug}.json").write_text(json.dumps(s), encoding="utf-8")


def test_check_build(call, root):
    write_sheet(root, "good", SHEET)
    result = call("check_build", {"slug": "good"})
    assert result["ok"] and result["problems"] == [] and (root / "profile" / "builds" / "good.md").exists()

    bad = copy.deepcopy(SHEET)
    bad["subclass"]["fragments"] = ["Spark of Nowhere"]
    bad["intent"]["artifact"] = {"name": "Satchel", "perks": ["Supernova"]}
    write_sheet(root, "bad", bad)
    result = call("check_build", {"slug": "bad"})
    assert not result["ok"] and result["problems"] == [
        "subclass: unknown fragment for Arc: Spark of Nowhere",
        'artifact: artifact-perks.md missing: run refresh_references(source="compendium")']

    (root / "cache" / "compendium").mkdir(parents=True)
    (root / "cache" / "compendium" / "artifact-perks.md").write_text(ARTIFACT_MD, encoding="utf-8")
    bad["intent"]["artifact"]["perks"] = ["Nope"]
    write_sheet(root, "bad", bad)
    assert call("check_build", {"slug": "bad"})["problems"][1] == "artifact: Nope is not a perk of Satchel"

    (root / "profile" / "builds" / "broken.json").write_text("{", encoding="utf-8")
    result = call("check_build", {"slug": "broken"})
    assert not result["ok"] and result["problems"][0].startswith("sheet: invalid JSON") and result["md"] is None

    with pytest.raises(ToolError, match="Unknown build: nope. Existing: bad, broken, good"):
        call("check_build", {"slug": "nope"})


def test_check_build_fills_the_hash_table(root):
    class Manifest:
        def table(self, name, keep=True):
            return {"DestinyInventoryItemDefinition": {"9": {"displayProperties": {"name": "Rifle"}, "itemType": 3,
                                                             "hash": 9}}}.get(name, {})

    s = copy.deepcopy(SHEET)
    s["intent"]["weapons"][0]["items"] = ["Rifle"]
    s["intent"]["weapons"][0]["mods"] = ["Nope"]
    write_sheet(root, "named", s)
    ctx = Context()
    ctx.__dict__.update(manifest=Manifest(), defs={"plugs": {}}, lexicon=None)
    result = asyncio.run(build_server(ctx).call_tool("check_build", {"slug": "named"}))
    assert "weapon: Kinetic: Nope is not an option of Rifle" in result.content[0].text
    saved = json.loads((root / "profile" / "builds" / "named.json").read_text(encoding="utf-8"))
    assert saved["intent"]["weapons"][0]["items"] == ["Rifle"] and saved["hashes"]["item:Rifle"] == 9


def test_subclass_options(call, root):
    text = call("subclass_options", {"class_type": "warlock", "element": "arc"})
    assert text.startswith("Aspects Warlock Arc") and "- Lightning Surge: 3" in text
    with pytest.raises(ToolError, match="element"):
        call("subclass_options", {"class_type": "Warlock", "element": "Fire"})


def test_artifact_options(call, root):
    with pytest.raises(ToolError, match="artifact-perks.md missing"):
        call("artifact_options")
    (root / "cache" / "compendium").mkdir(parents=True)
    (root / "cache" / "compendium" / "artifact-perks.md").write_text(ARTIFACT_MD, encoding="utf-8")
    assert call("artifact_options") == ["Satchel:", "  column 3: Supernova"]


def test_rankings(call, root):
    with pytest.raises(ToolError, match="Aegis data missing"):
        call("rankings", {"view": "aspects"})
    write_aegis(root / "cache" / "aegis", "endgame", "aspects", [
        {"_name": "Controlled Demolition", "Subclass": "Void", "Class": "T", "#": "1", "Tier": "S"}])
    assert call("rankings", {"view": "aspects", "class_type": "Titan"}) == [
        "S #1 | Controlled Demolition | Subclass: Void | Class: T"]
    with pytest.raises(ToolError, match="unknown view"):
        call("rankings", {"view": "nope"})


def test_rankings_output_is_bounded(call, root):
    write_aegis(root / "cache" / "aegis", "endgame", "aspects", [
        {"_name": f"Aspect {i:03}", "Subclass": "Void", "Class": "T", "#": str(i), "Tier": "S"} for i in range(1, 251)])
    lines = call("rankings", {"view": "aspects"})
    assert len(lines) == 61 and lines[-1] == "… 190 more (narrow the filters or raise limit)"
    assert len(call("rankings", {"view": "aspects", "limit": 1000})) == 201  # capped at 200
    with pytest.raises(ToolError, match="at least 3 characters"):
        call("rankings", {"view": "name", "name": "a"})


def test_weapon_candidates_limit_capped(call, root):
    write_weapons(root)
    from shell.mcp.tools import build_views
    assert build_views.MAX_LIMIT == 200


def write_weapons(root):
    folder = root / "profile" / "inventory"
    folder.mkdir(parents=True)
    (folder / "weapons.json").write_text(json.dumps(ITEMS), encoding="utf-8")


def test_weapon_candidates(call, root):
    with pytest.raises(ToolError, match="refresh_inventory"):
        call("weapon_candidates")
    write_weapons(root)
    lines = call("weapon_candidates", {"slot": "Energy", "limit": 1})
    assert lines[0].startswith("snapshot: ") and lines[1].startswith("2 | Ahab Char") and lines[2].startswith("… 1 more")


def test_weapon_options(call, root, monkeypatch):
    from shell.sources import wishlists

    def offline(source, force=False):
        raise OSError("offline")

    monkeypatch.setattr(wishlists, "fetch", offline)
    write_weapons(root)
    text = call("weapon_options", {"item_id": "2"})
    assert text.startswith("snapshot: ") and "\nAhab Char | 2 |" in text and "wishlist unavailable" in text
    with pytest.raises(ToolError, match="not in the weapon snapshot: 404"):
        call("weapon_options", {"item_id": "404"})
