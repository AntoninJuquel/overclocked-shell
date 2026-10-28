import asyncio
import json
from datetime import datetime, timezone

import pytest
from mcp.server.mcpserver.exceptions import ToolError

import shell.mcp.tools.farm as farm_tool
from shell.engines.todo import plan
from shell.context import Context
from shell.mcp.server import build_server
from tests.engines.todo.test_plan import CTX, NEEDS, STATE


class FakeManifest:
    def table(self, name, keep=True):
        return {}


def _today():
    return datetime.now(timezone.utc).date().isoformat()


@pytest.fixture
def todo(tmp_path, monkeypatch):
    from shell.core import paths
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(paths, "profile_dir", lambda: tmp_path / "profile")
    monkeypatch.setattr(farm_tool, "load_catalog", lambda manifest: {"sets": {}})
    todo_dir = tmp_path / "profile" / "todo"
    (todo_dir / "week").mkdir(parents=True)
    (todo_dir / "needs.json").write_text(json.dumps(NEEDS), encoding="utf-8")
    (todo_dir / "state.json").write_text(json.dumps(STATE), encoding="utf-8")
    return todo_dir


@pytest.fixture
def call(todo):
    ctx = Context()
    ctx.__dict__.update(manifest=FakeManifest())
    mcp = build_server(ctx)
    return lambda name, **args: json.loads(asyncio.run(mcp.call_tool(name, args)).content[0].text)


def _week(todo, end):
    """A processed week whose reset ends at `end`."""
    (todo / "week" / "2026-10-07.json").write_text(
        json.dumps({**CTX, "reset": {"start": "2026-10-06T17:00:00Z", "end": end}}), encoding="utf-8")


def test_farm_plan_writes_plan_and_returns_sections(call, todo):
    _week(todo, "2999-01-01T17:00:00Z")
    out = call("farm_plan", top=1)
    md = todo / f"{_today()}.md"
    assert out["saved_to"] == str(md) and md.exists() and (todo / f"{_today()}.json").exists()
    assert out["hidden"] == {"done": 0, "ignored": 1}
    assert out["warnings"] == [plan.NO_ROTATION]   # no Distortion rotation cached here
    when = out["sections"]["When you can"]
    assert when["count"] == 2 and len(when["entries"]) == 1   # top=1 per section
    assert when["entries"][0] == {"id": "masterwork/8", "label": "Masterwork: Other", "priority": 0.02,
                                  "builds": ["c"], "where": ["masterwork in game"]}
    later = out["sections"]["Later"]["entries"][0]
    assert later["id"] == "catalyst/collective-obligation" and later["where"] == []
    assert out["week"]["focus"] == ["Contest of Elders"]


def test_stale_week_gives_no_boosted_section(call, todo):
    _week(todo, "2026-10-13T17:00:00Z")   # ended before today
    out = call("farm_plan")
    assert "This week" not in out["sections"]
    assert out["week"] is None
    assert any("out of date" in w for w in out["warnings"])


def test_farm_plan_build_filter_and_unknown_build(call, todo):
    out = call("farm_plan", build="c")
    assert out["saved_to"] == str(todo / f"{_today()}-c.md")
    assert [e["id"] for s in out["sections"].values() for e in s["entries"]] == ["masterwork/8"]
    with pytest.raises(ToolError, match=r"unknown build 'x'.*b, c"):
        call("farm_plan", build="x")


def test_farm_plan_without_needs(call, todo):
    (todo / "needs.json").unlink()
    with pytest.raises(ToolError, match=r"Call farm_needs first\."):
        call("farm_plan")


def test_farm_plan_reports_malformed_needs(call, todo):
    (todo / "needs.json").write_text(json.dumps({"needs": [{"id": "x"}]}), encoding="utf-8")
    with pytest.raises(ToolError, match="malformed"):
        call("farm_plan")
    (todo / "needs.json").write_text(json.dumps({"needs": [{"id": "x", "builds": 3}]}), encoding="utf-8")
    with pytest.raises(ToolError, match="malformed"):
        call("farm_plan")


def _state(todo):
    return json.loads((todo / "state.json").read_text(encoding="utf-8"))


def test_set_status_with_note_then_keep_then_clear(call, todo):
    out = call("set_need_status", need_id="masterwork/9", status="ignored", note="no time")
    assert out == {"id": "masterwork/9", "status": "ignored", "since": _today(), "note": "no time"}
    assert _state(todo)["masterwork/9"] == {"status": "ignored", "since": _today(), "note": "no time"}
    assert call("set_need_status", need_id="masterwork/9", status="todo")["note"] == "no time"
    assert "note" not in call("set_need_status", need_id="masterwork/9", status="done", note="")
    assert _state(todo)["masterwork/9"] == {"status": "done", "since": _today()}


def test_set_status_on_state_only_id(call, todo):
    assert call("set_need_status", need_id="masterwork/7", status="todo")["status"] == "todo"


def test_set_status_unknown_id_changes_nothing(call, todo):
    before = (todo / "state.json").read_text(encoding="utf-8")
    with pytest.raises(ToolError, match=r"unknown need id 'masterwork/99'.*nothing changed"):
        call("set_need_status", need_id="masterwork/99", status="done")
    assert (todo / "state.json").read_text(encoding="utf-8") == before


def test_set_status_invalid_status(call, todo):
    before = (todo / "state.json").read_text(encoding="utf-8")
    with pytest.raises(ToolError, match="unknown status 'finished'"):
        call("set_need_status", need_id="masterwork/9", status="finished")
    assert (todo / "state.json").read_text(encoding="utf-8") == before
