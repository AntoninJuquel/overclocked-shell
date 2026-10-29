import asyncio
import copy
import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.core import paths
from shell.mcp.server import build_server
from tests.engines.test_raids import ENC

RAID = "deep-stone-crypt"


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(paths, "profile_dir", lambda: tmp_path / "profile")
    guides = tmp_path / "cache" / "guides" / RAID
    guides.mkdir(parents=True)
    for g in ("grindout", "shacknews", "overgear", "index"):
        (guides / f"{g}.md").write_text("x", encoding="utf-8")
    return tmp_path


def write(root, enc):
    folder = root / "profile" / "raids" / RAID
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "crypt-security.json").write_text(json.dumps(enc), encoding="utf-8")


def call(name, args):
    result = asyncio.run(build_server(Context()).call_tool(name, args))
    return json.loads(result.content[0].text)


def test_raid_check(root):
    with pytest.raises(ToolError, match="raid-companion"):
        call("raid_check", {"raid": RAID, "encounter": "crypt-security"})
    write(root, ENC)
    assert call("raid_check", {"raid": RAID, "encounter": "crypt-security"})["ok"]
    bad = copy.deepcopy(ENC)
    bad["spots"][1]["pos"] = [5, 5]
    write(root, bad)
    r = call("raid_check", {"raid": RAID, "encounter": "crypt-security"})
    assert not r["ok"] and r["problems"] == ["spot panel-l1: position without pos_source"]
    bad["spots"][0] = {"name": "no id"}
    write(root, bad)
    assert call("raid_check", {"raid": RAID, "encounter": "crypt-security"})["problems"][0].startswith("malformed")


def test_raid_show(root):
    write(root, ENC)
    r = call("raid_show", {"raid": RAID, "encounter": "crypt-security", "role": "Scanner"})
    page = root / "profile" / "raids" / "live.html"
    assert r["page"] == str(page) and "Call the lit panels." in page.read_text(encoding="utf-8")
    assert r["phase"] == "Panels" and r["steps"] == ["Call the lit panels."] and r["not_on_map"] == ["Panel 1 (left)"]
    assert r["phases"] == ["Panels"] and r["roles"] == ["Scanner", "Operator", "Add clear"] and r["conflicts"]
    with pytest.raises(ToolError, match="Scanner, Operator, Add clear"):
        call("raid_show", {"raid": RAID, "encounter": "crypt-security", "role": "Suppressor"})
    with pytest.raises(ToolError, match="phases: Panels"):
        call("raid_show", {"raid": RAID, "encounter": "crypt-security", "role": "scanner", "phase": "dps"})


def test_raid_show_refuses_invalid_file(root):
    bad = copy.deepcopy(ENC)
    bad["roles"][2]["count"] = 9
    write(root, bad)
    with pytest.raises(ToolError, match="counts sum to 11"):
        call("raid_show", {"raid": RAID, "encounter": "crypt-security", "role": "scanner"})


def test_raid_rename(root):
    write(root, ENC)
    r = call("raid_rename", {"raid": RAID, "spot_id": "panel-l1", "name": "left 1"})
    assert r["renames"] == {"panel-l1": "left 1"}
    shown = call("raid_show", {"raid": RAID, "encounter": "crypt-security", "role": "scanner"})
    assert shown["not_on_map"] == ["left 1"]
    with pytest.raises(ToolError, match="unknown spot"):
        call("raid_rename", {"raid": RAID, "spot_id": "nope", "name": "x"})
    assert call("raid_rename", {"raid": RAID, "spot_id": "panel-l1"})["renames"] == {}


def test_malformed_callouts_are_tool_errors(root):
    write(root, ENC)
    (root / "profile" / "raids" / RAID / "callouts.json").write_text("{oops", encoding="utf-8")
    with pytest.raises(ToolError, match="callouts.json: invalid JSON"):
        call("raid_show", {"raid": RAID, "encounter": "crypt-security", "role": "scanner"})
    with pytest.raises(ToolError, match="callouts.json: invalid JSON"):
        call("raid_rename", {"raid": RAID, "spot_id": "panel-l1", "name": "left 1"})


def test_raid_show_flags_a_guide_updated_since_the_file(root):
    write(root, ENC)
    (root / "cache" / "guides" / RAID / "index.md").write_text(
        "| guide | updated | images | url | fetched |\n|---|---|---|---|---|\n"
        "| grindout | 2026-08-02 | 49 | u | 2026-10-28 |\n", encoding="utf-8")
    r = call("raid_show", {"raid": RAID, "encounter": "crypt-security", "role": "scanner"})
    assert r["warnings"] == ["rebuild crypt-security: grindout updated 2026-08-02 (file built from 2026-07-20)"]
