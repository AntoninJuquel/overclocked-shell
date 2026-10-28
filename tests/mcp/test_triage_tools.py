import asyncio
import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

import shell.mcp.tools.triage as triage
from shell.context import Context
from shell.core.bungie import BungieApiError
from shell.mcp.server import build_server
from tests.engines.fakes import FakeActions
from tests.engines.test_armor_triage import piece


@pytest.fixture
def run(tmp_path, monkeypatch):
    from shell.core import paths
    monkeypatch.setattr(paths, "profile_dir", lambda: tmp_path)
    rows = [piece("keep", hash_=1), piece("junk-locked", w=25, locked=True), piece("legacy", tier=0, locked=True),
            piece("pm", hash_=2, archetype="Brawler", location="Titan (Postmaster)")]
    monkeypatch.setattr(triage, "read_rows", lambda ctx, kind: rows)
    monkeypatch.setattr(triage, "armor_sets", lambda manifest: {})
    ctx = Context()
    ctx.__dict__.update(manifest=None)
    mcp = build_server(ctx)
    return lambda name, args=None: json.loads(asyncio.run(mcp.call_tool(name, args or {})).content[0].text)


def test_triage_armor_saves_plan_and_summarises(run, tmp_path):
    result = run("triage_armor")
    assert (result["keep"], result["junk"], result["to_lock"], result["to_unlock"]) == (2, 2, 1, 2)
    assert [r["itemId"] for r in result["review"]] == ["junk-locked"] and result["review_total"] == 1
    saved = json.loads((tmp_path / "triage" / "armor.json").read_text(encoding="utf-8"))
    assert saved["lock"] == ["keep"] and saved["unlock"] == ["junk-locked", "legacy"]
    assert (tmp_path / "triage" / "armor.csv").exists()


def location(where, locked):
    return {"itemId": "x", "itemHash": 1, "where": where, "characterId": None, "locked": locked, "name": "Helm"}


def test_apply_plan_skips_postmaster_and_reports_failures():
    plan = {"lock": ["a", "pm", "gone", "hand"], "unlock": ["b"]}
    locations = {"a": location("vault", False), "pm": location("postmaster", False), "b": location("vault", True),
                 "hand": location("vault", True)}
    actions = FakeActions(errors=[1623])
    result = triage.apply_plan(actions, locations, {"w": 2}, plan)
    assert (result["locked"], result["unlocked"], result["already"]) == (0, 1, 1)
    assert result["skipped"] == [{"itemId": "pm", "name": "Helm", "result": "postmaster (skipped)"}]
    assert [(f["itemId"], f["result"].split(":")[0]) for f in result["failed"]] == [("a", "failed"),
                                                                                    ("gone", "not found")]
    counted = result["locked"] + result["unlocked"] + result["already"] + len(result["skipped"]) + len(result["failed"])
    assert counted == len(plan["lock"]) + len(plan["unlock"])


def test_bad_wishlist_download_is_a_tool_error(run, monkeypatch):
    from shell.sources.sheets import fetch
    monkeypatch.setattr(fetch, "_get", lambda url: b"<html>404</html>")
    with pytest.raises(ToolError, match="wishlist: unexpected response"):
        asyncio.run(build_server(Context()).call_tool("triage_weapons", {"wishlist": "https://example.com/w.txt"}))


def test_stale_wishlist_is_flagged(run, monkeypatch, tmp_path):
    from shell.core import paths
    from shell.sources import wishlists
    from shell.sources.sheets import fetch
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(fetch, "_get", lambda url: b"dimwishlist:item=1")
    wishlists.fetch("https://example.com/w.txt")
    monkeypatch.setattr(fetch, "_get", lambda url: b"<html>")
    monkeypatch.setattr(triage, "decide_weapons", lambda rows, *wl: [])
    ctx = Context()
    ctx.__dict__.update(defs={"plugs": {}})
    result = json.loads(asyncio.run(build_server(ctx).call_tool(
        "triage_weapons", {"wishlist": "https://example.com/w.txt", "refresh_wishlist": True})).content[0].text)
    assert result["wishlist_stale"] is True


def test_apply_without_saved_plan_errors(run):
    with pytest.raises(ToolError, match="Run triage_weapons first"):
        asyncio.run(build_server(Context()).call_tool("apply_triage", {"kind": "weapons"}))


def test_export_dim_tags_warns(run, tmp_path):
    with pytest.raises(ToolError):
        asyncio.run(build_server(Context()).call_tool("export_dim_tags", {}))
    run("triage_armor")
    result = run("export_dim_tags")
    assert (result["rows"], result["keep"], result["junk"]) == (4, 2, 2)
    assert "replaces the tag and note" in result["warning"]
    assert (tmp_path / "triage" / "dim_tags.csv").read_text(encoding="utf-8").startswith("Id,Hash,Tag,Notes")
