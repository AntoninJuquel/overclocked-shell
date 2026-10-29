import asyncio
import json
import random

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.core import paths
from shell.engines.builds import catalog, sheet
from shell.mcp.server import build_server
from shell.mcp.tools import bravery as tool
from tests.engines.test_bravery import ARMOR, WEAPONS, make_idx


class FakeManifest:
    def table(self, name, keep=True):
        return {"9": {"displayProperties": {"name": "Ashes to Assets"}, "collectibleHash": 1,
                      "plug": {"plugCategoryIdentifier": "enhancements.v2_head", "energyCost": {"energyCost": 3}}}}


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "profile_dir", lambda: tmp_path / "profile")
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(catalog, "load_catalog", lambda manifest: {"subclass": make_idx(), "costs": {"Grenade Mod": 3}})
    monkeypatch.setattr(tool, "owned_elements", lambda ctx, cls: ["Arc"])
    monkeypatch.setattr(tool, "RNG", random.Random(7))
    inv = tmp_path / "profile" / "inventory"
    inv.mkdir(parents=True)
    armor = [dict(x, energy="0/10", plugs=["General Armor Mod: Grenade Mod", "General Armor Mod: Balanced Tuning",
                                          "Helmet Armor Mod: Hands-On"]) for x in ARMOR]
    (inv / "armor.json").write_text(json.dumps(armor), encoding="utf-8")
    (inv / "weapons.json").write_text(json.dumps(WEAPONS), encoding="utf-8")
    return tmp_path


def call(args):
    ctx = Context()
    ctx.__dict__.update(manifest=FakeManifest())
    result = asyncio.run(build_server(ctx).call_tool("roll_bravery", args))
    return json.loads(result.content[0].text)


def test_full_roll_writes_a_valid_sheet(root):
    r = call({"character": "warlock"})
    s = sheet.load(sheet.path_for("bravery"))
    assert r["slug"] == "bravery" and s["class"] == "Warlock" and s["activity"] == "Ultimate Bravery"
    assert s["subclass"]["element"] == "Arc" and len(s["resolved"]["weapons"]) == 3
    assert s["intent"]["exotic"]["name"] in {"Ahelm-x", "Alegs-x"} and r["md"].endswith("bravery.md")
    assert all(set(a["mods"]) <= {"Ashes to Assets"} for a in s["resolved"]["armor"])


def test_reroll_weapons_keeps_the_rest(root):
    call({"character": "warlock"})
    before = sheet.load(sheet.path_for("bravery"))
    tool.RNG.seed(99)
    call({"character": "warlock", "part": "weapons"})
    after = sheet.load(sheet.path_for("bravery"))
    assert after["subclass"] == before["subclass"] and after["resolved"]["armor"] == before["resolved"]["armor"]


def test_part_errors(root):
    with pytest.raises(ToolError, match="roll a build first"):
        call({"character": "warlock", "part": "mods"})
    with pytest.raises(ToolError, match="part is one of"):
        call({"character": "warlock", "part": "shaders"})
    with pytest.raises(ToolError, match="titan, hunter or warlock"):
        call({"character": "ghost"})
    call({"character": "warlock"})
    with pytest.raises(ToolError, match="last roll is for Warlock"):
        call({"character": "hunter", "part": "weapons"})


def test_no_exotic_armor_fails_before_the_live_call_and_writes_nothing(root, monkeypatch):
    def live(ctx, cls):
        raise AssertionError("owned_elements called")
    monkeypatch.setattr(tool, "owned_elements", live)
    with pytest.raises(ToolError, match="no exotic armor for Titan"):
        call({"character": "titan"})
    assert not sheet.path_for("bravery").exists()


def test_reroll_armor_updates_exotic_and_mods_together(root):
    call({"character": "warlock"})
    before = sheet.load(sheet.path_for("bravery"))
    for seed in range(20):
        tool.RNG.seed(seed)
        r = call({"character": "warlock", "part": "armor"})
        s = sheet.load(sheet.path_for("bravery"))
        exotic = next(x["name"] for x in s["resolved"]["armor"] if x["itemId"] in {"helm-x", "legs-x"})
        assert s["intent"]["exotic"]["name"] == exotic
        assert s["intent"]["armor_mods"] == {x["slot"]: x["mods"] for x in s["resolved"]["armor"] if x["mods"]}
        assert r["mods"] == s["intent"]["armor_mods"]
        assert s["subclass"] == before["subclass"] and s["resolved"]["weapons"] == before["resolved"]["weapons"]


def test_reroll_subclass_keeps_the_rest(root, monkeypatch):
    call({"character": "warlock"})
    before = sheet.load(sheet.path_for("bravery"))
    monkeypatch.setattr(tool, "owned_elements", lambda ctx, cls: ["Void"])
    r = call({"character": "warlock", "part": "subclass"})
    after = sheet.load(sheet.path_for("bravery"))
    assert r["subclass"]["element"] == "Void" and after["subclass"]["element"] == "Void"
    assert after["resolved"]["armor"] == before["resolved"]["armor"]
    assert after["resolved"]["weapons"] == before["resolved"]["weapons"]


def test_reroll_mods_keeps_the_armor(root):
    call({"character": "warlock"})
    before = sheet.load(sheet.path_for("bravery"))
    r = call({"character": "warlock", "part": "mods"})
    after = sheet.load(sheet.path_for("bravery"))
    ids = lambda s: [x["itemId"] for x in s["resolved"]["armor"]]  # noqa: E731
    assert ids(after) == ids(before) and after["intent"]["exotic"] == before["intent"]["exotic"]
    assert after["subclass"] == before["subclass"] and r["mods"] == after["intent"]["armor_mods"]


def test_roll_keeps_installed_stat_mods_and_tunings_and_is_scratch(root):
    call({"character": "warlock"})
    s = sheet.load(sheet.path_for("bravery"))
    assert s["scratch"] is True
    assert all(a["stat_mod"] == "Grenade Mod" and a["tuning"] == "Balanced Tuning" for a in s["resolved"]["armor"])
    assert all(len(a["mods"]) <= 2 for a in s["resolved"]["armor"])     # 10 energy - 3 for the stat mod: 7 = 2 x 3
