import asyncio
import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from shell.context import Context
from shell.core import paths
from shell.mcp.server import build_server
from tests.sources.test_distortions import ORDER


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path / "cache")
    return tmp_path


def call(args):
    result = asyncio.run(build_server(Context()).call_tool("distortions", args))
    return json.loads(result.content[0].text)


def write(root, fetched):
    folder = root / "cache" / "distortions"
    folder.mkdir(parents=True)
    (folder / "rotation.json").write_text(json.dumps(
        {"order": ORDER, "anchor_hour": 494803, "anchor_index": 5, "source": "u", "fetched": fetched}),
        encoding="utf-8")


def test_distortions_tool(root):
    with pytest.raises(ToolError, match='refresh_references\\(source="distortions"\\)'):
        call({})
    write(root, "2020-01-01T00:00:00+00:00")
    r = call({"hours": 3})
    assert len(r["schedule"]) == 3 and r["schedule"][0].startswith("now until ")
    assert r["now"] == r["schedule"][0] and r["offset"].startswith("UTC")
    assert r["warnings"][0].startswith("rotation fetched on 2020-01-01")
    r = call({"destination": "Throne World"})
    assert len(r["next"]) == 3 and r["destination"] == "Savathun's Throne World"
    with pytest.raises(ToolError, match="not a Distortion destination"):
        call({"destination": "Mars"})
    with pytest.raises(ToolError, match="destinations: Cosmodrome"):
        call({"destination": ""})
    with pytest.raises(ToolError, match="hours"):
        call({"hours": 0})
