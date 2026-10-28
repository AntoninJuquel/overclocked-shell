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
