import json

import pytest

from shell.sources import aegis
from shell.sources.aegis.config import SheetConfig, TabSpec
from tests.sources.conftest import sheet_html

CONF = {"s": SheetConfig("s", "Sheet S", "ID", (
    TabSpec("Status", "status", ("TAB", "UPDATED"), ("TAB",), 1, tier=None),
    TabSpec("Good", "good", ("Name", "Tier"), ("Name",), 1, rank="#"),
    TabSpec("Broken", "broken", ("Name", "Tier"), ("Name",), 1),
    TabSpec("Fireteam", "fireteam", ("Name",), ("Name",), 1, pattern=r"Fireteam( \(S\d+\))?", tier=None),
), ("Changelog",))}

GOOD = sheet_html([["Name", "#", "Tier"], ["Kindled Orchid", "1", "S"], ["Fresh", "2", "B"]])
PAGES = {
    "1": sheet_html([["TAB", "UPDATED"], ["Good", "2026-08-19"]]),
    "2": GOOD,
    "3": sheet_html([["Something else"]]),
    "4": sheet_html([["Name"], ["Rotation A"]]),
}


class FakeSource:
    def __init__(self, sheet_id, raw):
        self.tabs_stale = False

    def list_tabs(self, refresh=False):
        return [("Status", "1"), ("Good", "2"), ("Broken", "3"), ("Fireteam (S31)", "4"), ("Changelog", "5"), ("New", "6")]

    def tab_html(self, gid, refresh=False):
        return PAGES[gid], False

    def cache_date(self, gid):
        return "2026-10-09"


@pytest.fixture
def env(isolated_aegis_dir, tmp_path, monkeypatch):
    builds = tmp_path / "profile" / "builds"
    builds.mkdir(parents=True)
    monkeypatch.setattr(aegis, "SHEETS", CONF)
    monkeypatch.setattr(aegis, "SheetSource", FakeSource)
    monkeypatch.setitem(PAGES, "2", GOOD)
    return isolated_aegis_dir, builds


def test_writes_tabs_index_and_isolates_failures(env):
    out, _ = env
    (out / "s").mkdir(parents=True)
    (out / "s" / "broken.json").write_text(json.dumps({"fetched": "2026-09-01", "rows": [{"_name": "Old"}]}),
                                           encoding="utf-8")
    result = aegis.refresh()
    assert result["source"] == "aegis" and not result["ok"]
    assert result["errors"] == ["Sheet S: Broken: headers not found: Name, Tier"]
    good = json.loads((out / "s" / "good.json").read_text(encoding="utf-8"))
    assert good["updated"] == "2026-08-19" and [r["_name"] for r in good["rows"]] == ["Kindled Orchid", "Fresh"]
    assert "### Kindled Orchid" in (out / "s" / "good.md").read_text(encoding="utf-8")
    assert (out / "s" / "fireteam.md").exists()                      # name with a season recognized
    assert "Old" in (out / "s" / "broken.json").read_text(encoding="utf-8")   # previous file kept
    index = (out / "index.md").read_text(encoding="utf-8")
    assert "| Sheet S | Good | [s/good.md](s/good.md) | 2 | 2026-08-19 | 2026-10-09 | ok |" in index
    assert "⚠ Broken: headers not found: Name, Tier — data from 2026-09-01" in index
    assert result["unhandled"] == ["Sheet S: New"]                   # Changelog is ignored, not unhandled
    assert result["folder"] == str(out)


def test_second_run_reports_changes_for_builds(env):
    out, builds = env
    (builds / "hc.json").write_text(json.dumps({"resolved": {"weapons": [{"name": "Kindled Orchid"}]}}),
                                    encoding="utf-8")
    assert aegis.refresh()["changed"] == []
    PAGES["2"] = sheet_html([["Name", "#", "Tier"], ["Kindled Orchid", "1", "A"]])
    result = aegis.refresh(force=True)
    changes = (out / "changes.md").read_text(encoding="utf-8")
    assert "- hc: Good — Kindled Orchid: Tier S → A" in changes
    assert "- Fresh: removed (was Tier B)" in changes
    assert "hc: Good — Kindled Orchid: Tier S → A" in result["changed"]
    assert "Good — Fresh: removed (was Tier B)" in result["changed"]


def test_refresh_names_concerned_build(env):
    _, builds = env
    (builds / "x.json").write_text(json.dumps({"intent": {"exotic": {"name": "Kindled Orchid"}}}), encoding="utf-8")
    aegis.refresh()
    PAGES["2"] = sheet_html([["Name", "#", "Tier"], ["Kindled Orchid", "1", "A"], ["Fresh", "2", "B"]])
    changed = aegis.refresh()["changed"]
    assert changed == ["x: Good — Kindled Orchid: Tier S → A"]


def test_unreadable_status_keeps_previous_update_dates(env, monkeypatch):
    out, _ = env
    aegis.refresh()
    monkeypatch.setitem(PAGES, "1", sheet_html([["Something else"]]))
    assert not aegis.refresh()["ok"]
    good = json.loads((out / "s" / "good.json").read_text(encoding="utf-8"))
    assert good["updated"] == "2026-08-19"
    assert "| Sheet S | Good | [s/good.md](s/good.md) | 2 | 2026-08-19 |" in (out / "index.md").read_text(encoding="utf-8")


def test_status_tab_is_not_diffed(env, monkeypatch):
    out, _ = env
    aegis.refresh()
    monkeypatch.setitem(PAGES, "1", sheet_html([["TAB", "UPDATED"], ["Good", "2026-09-01"], ["Brand new", "2026-09-02"]]))
    assert aegis.refresh()["changed"] == []
    changes = (out / "changes.md").read_text(encoding="utf-8")
    assert "Status" not in changes and "Brand new" not in changes and "No changes." in changes


def test_only_keeps_other_tabs(env):
    out, _ = env
    assert aegis.refresh(only=["Good"])["ok"]
    assert (out / "s" / "good.json").exists() and not (out / "s" / "fireteam.json").exists()
    index = (out / "index.md").read_text(encoding="utf-8")
    assert "| Sheet S | Fireteam | s/fireteam.md | 0 | — | — | ⚠ not fetched yet — no data |" in index


def test_unknown_tab_is_rejected(env):
    result = aegis.refresh(only=["Unknown"])
    assert not result["ok"] and result["errors"][0].startswith("unknown tab: Unknown")
    assert not (env[0] / "index.md").exists()


def test_stale_tab_is_reported(env, monkeypatch):
    monkeypatch.setattr(FakeSource, "tab_html", lambda self, gid, refresh=False: (PAGES[gid], gid == "2"))
    assert aegis.refresh()["stale"] == ["Sheet S: Good"]


def test_tab_list_failure_is_an_error(env, monkeypatch):
    def fail(self, refresh=False):
        raise OSError("offline")
    monkeypatch.setattr(FakeSource, "list_tabs", fail)
    result = aegis.refresh()
    assert result["errors"] == ["tab list (Sheet S): offline"]
    assert "⚠ Good: network (offline) — no data" in (env[0] / "index.md").read_text(encoding="utf-8")
