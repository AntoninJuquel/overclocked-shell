import asyncio
import json
from datetime import datetime, timezone

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.core import paths
from shell.engines.builds import catalog
from shell.engines.todo import week
from shell.mcp.server import build_server
from tests.engines.todo.test_week import RAW, SETS, TABLES


class FakeManifest:
    def __init__(self):
        self.read = []

    def table(self, name, keep=True):
        self.read.append((name, keep))
        key = {table: key for key, table in week.TABLES.items()}[name]
        return TABLES[key]


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(paths, "profile_dir", lambda: tmp_path / "profile")
    monkeypatch.setattr(catalog, "load_catalog", lambda manifest: {"sets": SETS})
    return tmp_path


@pytest.fixture
def manifest():
    return FakeManifest()


@pytest.fixture
def call(root, manifest):
    ctx = Context()
    ctx.__dict__.update(manifest=manifest)
    mcp = build_server(ctx)

    def run(name, args=None):
        result = asyncio.run(mcp.call_tool(name, args or {}))
        return json.loads(result.content[0].text)
    return run


def write_raw(root, date, raw):
    folder = root / "profile" / "context"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{date}.json").write_text(json.dumps(raw), encoding="utf-8")


def test_week_context_without_raw_context_asks_for_refresh(call):
    with pytest.raises(ToolError, match=r"Call refresh_context\(character\) first\."):
        call("week_context")


def test_week_context_reads_newest_raw_context(call, root, manifest):
    write_raw(root, "2026-10-01", {**RAW, "character": "hunter"})
    write_raw(root, "2026-10-07", RAW)
    result = call("week_context")
    today = datetime.now(timezone.utc).date().isoformat()
    saved = root / "profile" / "todo" / "week" / f"{today}.json"
    assert result["saved_to"] == str(saved)
    assert json.loads(saved.read_text(encoding="utf-8"))["character"] == "warlock"
    assert result["summary"][0] == "Week until 2026-10-13 (reset 17:00 UTC)"
    assert result["warnings"] == ["context from 2026-10-07: week ended 2026-10-13, call refresh_context"]
    assert manifest.read and all(keep is False for _, keep in manifest.read)


def test_week_context_bad_overrides_is_one_line_error(call, root):
    write_raw(root, "2026-10-07", RAW)
    (root / "profile" / "todo").mkdir(parents=True)
    (root / "profile" / "todo" / "overrides.json").write_text(json.dumps({"notes": "x"}), encoding="utf-8")
    with pytest.raises(ToolError, match="overrides.json"):
        call("week_context")
