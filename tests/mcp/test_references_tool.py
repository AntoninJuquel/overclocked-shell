import asyncio
import json
import types

import pytest
from mcp.server.mcpserver.exceptions import ToolError

import shell.mcp.tools.references as references
from shell.context import Context
from shell.mcp.server import build_server


@pytest.fixture
def call(monkeypatch):
    calls = []

    def refresh(force=False, only=None):
        calls.append((force, only))
        return {"source": "fake", "ok": True, "changed": [], "stale": [], "errors": [], "folder": "x"}

    fake = types.SimpleNamespace(NAME="fake", refresh=refresh)
    other = types.SimpleNamespace(NAME="other", refresh=lambda force=False, only=None: {"source": "other"})
    monkeypatch.setattr(references, "sources", lambda: {"fake": fake, "other": other})
    mcp = build_server(Context())
    return lambda args: json.loads(asyncio.run(mcp.call_tool("refresh_references", args)).content[0].text), calls


def test_refresh_references_runs_named_source(call):
    run, calls = call
    result = run({"source": "fake", "force": True, "tabs": ["Exotic Armors"]})
    assert [r["source"] for r in result["reports"]] == ["fake"]
    assert calls == [(True, ["Exotic Armors"])]


def test_refresh_references_runs_all_by_default(call):
    run, _ = call
    assert [r["source"] for r in run({})["reports"]] == ["fake", "other"]


def test_unknown_source_lists_known(call):
    with pytest.raises(ToolError, match="fake, other"):
        call[0]({"source": "nope"})


def test_max_age_days_skips_fresh_data_and_forces_old_data(call, tmp_path, monkeypatch):
    from datetime import date, timedelta

    from shell.core import paths
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path)
    run, calls = call
    (tmp_path / "fake").mkdir()
    index = tmp_path / "fake" / "index.md"

    def oldest(days):
        index.write_text(f"Last run: x\nOldest data: {date.today() - timedelta(days=days)}\n", encoding="utf-8")

    oldest(7)
    assert run({"source": "fake", "max_age_days": 7})["reports"][0]["fresh"] is True and calls == []
    oldest(8)
    assert run({"source": "fake", "max_age_days": 7})["reports"][0]["source"] == "fake" and calls == [(True, None)]
    index.unlink()
    (tmp_path / "fake" / "rotation.json").write_text("{}", encoding="utf-8")   # no index: the file's date
    assert run({"source": "fake", "max_age_days": 7})["reports"][0]["fresh"] is True
    (tmp_path / "fake" / "rotation.json").unlink()
    calls.clear()
    run({"source": "fake", "max_age_days": 7})   # nothing yet
    assert calls == [(True, None)]
