import os
import time
import types
from datetime import date

import pytest

from shell.sources import compendium
from shell.sources import write_if_changed
from shell.sources.compendium import fetch
from shell.sources.compendium.model import Entry
from shell.sources.sheets import fetch as sheets_fetch
from shell.sources.sheets.fetch import SheetSource
from tests.sources.conftest import sheet_html

GOOD = types.SimpleNamespace(ANCHORS=("Title",), MIN_ENTRIES=1,
                             parse=lambda grid: [Entry(grid.text(1, 0), "S", {}, "text")])
TABS_JS = ('items.push({name: "Arc", pageUrl: "https:\\/\\/docs.google.com\\/x?gid\\x3d618967225", gid: "618967225"});'
           'items.push({name: "Armor \\x26 Stuff", pageUrl: "https:\\/\\/x", gid: "12"});')


def _list_tabs(tabs, stale=False):
    def list_tabs(self, refresh=False):
        self.tabs_stale = stale
        return tabs
    return list_tabs


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr(SheetSource, "list_tabs",
                        _list_tabs([("Exotic Armors", "1"), ("Broken", "2"), ("New", "3"), ("OLD X", "4")]))
    pages = {"1": sheet_html([["Title"], ["Entry A"]]), "2": sheet_html([["Something else"]])}
    monkeypatch.setattr(SheetSource, "tab_html", lambda self, gid, refresh=False: (pages[gid], False))
    monkeypatch.setattr(compendium, "TABS", {"Exotic Armors": ("exotic-armors", GOOD), "Broken": ("broken", GOOD)})
    out = fetch.folder()
    out.mkdir(parents=True)
    return out


def test_success_and_failure_are_isolated(env):
    (env / "broken.md").write_text("# Broken\n\nSource: …, fetched on 2026-09-01.\n\n## S\n\n### Old\n", encoding="utf-8")
    report = compendium.refresh()
    assert not report["ok"]
    assert "### Entry A" in (env / "exotic-armors.md").read_text(encoding="utf-8")
    assert "### Old" in (env / "broken.md").read_text(encoding="utf-8")  # old file kept
    assert report["changed"] == ["exotic-armors.md"]
    index = (env / "index.md").read_text(encoding="utf-8")
    assert "| Exotic Armors | [exotic-armors.md](exotic-armors.md) | 1 | ok |" in index
    assert '⚠ Broken: anchor not found: "Title" — data from 2026-09-01' in index
    assert 'Broken: anchor not found: "Title"' in report["errors"]
    assert report["unhandled"] == ["New"]  # informational, not an error
    assert not any("OLD X" in e for e in report["errors"])


def test_only_processes_requested_tabs(env):
    report = compendium.refresh(only=["Exotic Armors"])
    assert report["errors"] == [] and report["changed"] == ["exotic-armors.md"]
    assert not (env / "broken.md").exists()
    index = (env / "index.md").read_text(encoding="utf-8")
    assert "| Broken | broken.md | 0 | ⚠ not fetched yet — no data |" in index


def test_unknown_only_tab_is_rejected(env):
    report = compendium.refresh(only=["Unknown"])
    assert not report["ok"] and report["errors"][0].startswith("unknown tab: Unknown")
    assert not (env / "index.md").exists()


def test_second_identical_run_changes_nothing(env):
    assert compendium.refresh(only=["Exotic Armors"])["changed"] == ["exotic-armors.md"]
    assert compendium.refresh(only=["Exotic Armors"])["changed"] == []


def test_unreadable_html_is_a_per_tab_failure(env, monkeypatch):
    def bad_parse_grid(html):
        if "Something else" in html:
            raise ValueError("overlapping merges")
        return real(html)

    real = compendium.parse_grid
    monkeypatch.setattr(compendium, "parse_grid", bad_parse_grid)
    report = compendium.refresh()
    assert not report["ok"]
    assert "### Entry A" in (env / "exotic-armors.md").read_text(encoding="utf-8")
    assert "Broken: unreadable HTML (overlapping merges)" in report["errors"]
    assert "unreadable HTML (overlapping merges)" in (env / "index.md").read_text(encoding="utf-8")


def test_unexpected_exception_is_isolated(env, monkeypatch, capsys):
    def boom(grid):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(compendium, "TABS", {
        "Exotic Armors": ("exotic-armors", GOOD),
        "Broken": ("broken", types.SimpleNamespace(ANCHORS=("Something else",), MIN_ENTRIES=1, parse=boom)),
    })
    report = compendium.refresh()
    assert "### Entry A" in (env / "exotic-armors.md").read_text(encoding="utf-8")
    assert "Broken: unexpected error (RuntimeError('kaboom'))" in report["errors"]
    assert "Broken: unexpected error (RuntimeError('kaboom'))" in (env / "index.md").read_text(encoding="utf-8")
    assert "Traceback" in capsys.readouterr().err


def test_tab_date_is_the_cache_date_not_today(env, monkeypatch):
    monkeypatch.setattr(SheetSource, "cache_date", lambda self, gid: "2026-01-02")
    compendium.refresh()
    assert "fetched on 2026-01-02" in (env / "exotic-armors.md").read_text(encoding="utf-8")


def test_index_shows_oldest_data_date_without_refresh(env, monkeypatch):
    monkeypatch.setattr(SheetSource, "cache_date", lambda self, gid: "2026-01-02")
    compendium.refresh()
    index = (env / "index.md").read_text(encoding="utf-8")
    assert "Oldest data: 2026-01-02" in index
    assert "Last run: " + date.today().isoformat() in index


def test_list_tabs_failure_is_reported_and_keeps_index(env, monkeypatch):
    (env / "index.md").write_text("old index", encoding="utf-8")

    def boom(self, refresh=False):
        raise OSError("no network")

    monkeypatch.setattr(SheetSource, "list_tabs", boom)
    report = compendium.refresh()
    assert report["errors"] == ["tab list failed: no network"]
    assert (env / "index.md").read_text(encoding="utf-8") == "old index"


def test_stale_tab_list_is_reported(env, monkeypatch):
    monkeypatch.setattr(SheetSource, "list_tabs", _list_tabs([("Exotic Armors", "1")], stale=True))
    assert compendium.refresh(only=["Exotic Armors"])["stale"] == ["tab list"]


def test_stale_html_is_flagged(env, monkeypatch):
    monkeypatch.setattr(SheetSource, "tab_html",
                        lambda self, gid, refresh=False: (sheet_html([["Title"], ["Entry A"]]), True))
    report = compendium.refresh(only=["Exotic Armors"])
    assert report["stale"] == ["Exotic Armors"]
    assert "cache (network failed)" in (env / "index.md").read_text(encoding="utf-8")


def test_network_error_is_a_tab_failure(env, monkeypatch):
    def boom(self, gid, refresh=False):
        raise OSError("timeout")

    monkeypatch.setattr(SheetSource, "tab_html", boom)
    report = compendium.refresh(only=["Exotic Armors"])
    assert report["errors"] == ["Exotic Armors: network (timeout)"]
    assert "Exotic Armors: network (timeout)" in (env / "index.md").read_text(encoding="utf-8")


def test_tab_missing_from_sheet(env, monkeypatch):
    monkeypatch.setattr(SheetSource, "list_tabs", _list_tabs([("Exotic Armors", "1")]))
    report = compendium.refresh()
    assert report["errors"] == ["Broken: tab missing from the Sheet"]
    assert "Broken: tab missing from the Sheet" in (env / "index.md").read_text(encoding="utf-8")


def test_writes_are_atomic_no_tmp_left(env):
    compendium.refresh()
    assert not list(env.glob("*.tmp"))
    assert (env / "exotic-armors.md").exists() and (env / "index.md").exists()


def test_write_keeps_old_file_on_failure(tmp_path, monkeypatch):
    target = tmp_path / "x.md"
    target.write_text("old", encoding="utf-8")

    def boom(src, dst):
        raise OSError("disk full")
    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        write_if_changed(target, "new")
    assert target.read_text(encoding="utf-8") == "old"


# From dim-agent's test_fetch: the compendium's SheetSource, over a stubbed network.

def test_list_tabs_without_tabs_is_an_error(monkeypatch):
    monkeypatch.setattr(sheets_fetch, "_get", lambda url: b"<html></html>")
    report = compendium.refresh()
    assert len(report["errors"]) == 1 and report["errors"][0].startswith("tab list failed:")


def test_cache_date_is_cache_file_mtime():
    src = fetch.sheet()
    assert src.cache_date("7") is None
    f = fetch.folder() / "raw" / "7.html"
    f.parent.mkdir(parents=True)
    f.write_text("x", encoding="utf-8")
    ts = time.mktime((2026, 9, 1, 12, 0, 0, 0, 0, -1))
    os.utime(f, (ts, ts))
    assert src.cache_date("7") == "2026-09-01"


def test_list_tabs_reports_stale_cache(monkeypatch):
    raw = fetch.folder() / "raw"
    raw.mkdir(parents=True)
    (raw / "_tabs.html").write_text(TABS_JS, encoding="utf-8")

    def boom(url):
        raise OSError("network down")

    monkeypatch.setattr(sheets_fetch, "_get", boom)
    src = fetch.sheet()
    assert src.list_tabs(refresh=True)[0][0] == "Arc"
    assert src.tabs_stale is True
    src.list_tabs()
    assert src.tabs_stale is False
