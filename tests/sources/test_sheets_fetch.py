import http.client
import os
import time
import urllib.error

import pytest

from shell.sources.sheets import fetch

TABS_JS = ('items.push({name: "Arc", pageUrl: "https:\\/\\/docs.google.com\\/x?gid\\x3d618967225", gid: "618967225"});'
           'items.push({name: "Armor \\x26 Stuff", pageUrl: "https:\\/\\/x", gid: "12"});')


def test_parse_tab_list():
    assert fetch.parse_tab_list(TABS_JS) == [("Arc", "618967225"), ("Armor & Stuff", "12")]


def test_cached_downloads_then_reuses(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(fetch, "_get", lambda url: calls.append(url) or "content".encode())
    path = tmp_path / "x.html"
    assert fetch.cached("http://u", path, refresh=False) == ("content", False)
    assert fetch.cached("http://u", path, refresh=False) == ("content", False)
    assert calls == ["http://u"]


def test_cached_falls_back_to_cache_on_network_error(tmp_path, monkeypatch):
    path = tmp_path / "x.html"
    path.write_text("old", encoding="utf-8")

    def boom(url):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(fetch, "_get", boom)
    assert fetch.cached("http://u", path, refresh=True) == ("old", True)


def test_cached_raises_without_cache(tmp_path, monkeypatch):
    def boom(url):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(fetch, "_get", boom)
    with pytest.raises(OSError):
        fetch.cached("http://u", tmp_path / "absent.html", refresh=False)


def test_cached_refresh_overwrites(tmp_path, monkeypatch):
    path = tmp_path / "x.html"
    path.write_text("old", encoding="utf-8")
    monkeypatch.setattr(fetch, "_get", lambda url: "new".encode())
    assert fetch.cached("http://u", path, refresh=True) == ("new", False)
    assert path.read_text(encoding="utf-8") == "new"


def test_cached_invalid_response_keeps_cache(tmp_path, monkeypatch):
    path = tmp_path / "x.html"
    path.write_text("old", encoding="utf-8")
    monkeypatch.setattr(fetch, "_get", lambda url: b"sign-in page")
    assert fetch.cached("http://u", path, refresh=True, validate=lambda t: "waffle" in t) == ("old", True)
    assert path.read_text(encoding="utf-8") == "old"


def test_cached_invalid_response_without_cache(tmp_path, monkeypatch):
    path = tmp_path / "x.html"
    monkeypatch.setattr(fetch, "_get", lambda url: b"sign-in page")
    with pytest.raises(OSError):
        fetch.cached("http://u", path, refresh=False, validate=lambda t: "waffle" in t)
    assert list(tmp_path.iterdir()) == []


def test_cached_wraps_http_exception(tmp_path, monkeypatch):
    def boom(url):
        raise http.client.IncompleteRead(b"")

    monkeypatch.setattr(fetch, "_get", boom)
    with pytest.raises(OSError):
        fetch.cached("http://u", tmp_path / "absent.html", refresh=False)


def test_file_date(tmp_path):
    f = tmp_path / "7.html"
    assert fetch.file_date(f) is None
    f.write_text("x", encoding="utf-8")
    ts = time.mktime((2026, 9, 1, 12, 0, 0, 0, 0, -1))
    os.utime(f, (ts, ts))
    assert fetch.file_date(f) == "2026-09-01"


def test_sheet_source_urls_and_cache(tmp_path, monkeypatch):
    urls = []
    pages = {"https://docs.google.com/spreadsheets/d/ID/htmlview": TABS_JS,
             "https://docs.google.com/spreadsheets/d/ID/htmlview/sheet?headers=false&gid=12": '<table class="waffle">'}
    monkeypatch.setattr(fetch, "_get", lambda url: urls.append(url) or pages[url].encode())
    src = fetch.SheetSource("ID", tmp_path / "raw")
    assert src.list_tabs() == [("Arc", "618967225"), ("Armor & Stuff", "12")]
    assert src.tabs_stale is False
    assert src.tab_html("12") == ('<table class="waffle">', False)
    assert (tmp_path / "raw" / "_tabs.html").exists() and (tmp_path / "raw" / "12.html").exists()
    assert src.cache_date("12") is not None and src.cache_date("99") is None
    assert len(urls) == 2


def test_sheet_source_without_tabs_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "_get", lambda url: b"<html></html>")
    with pytest.raises(OSError):
        fetch.SheetSource("ID", tmp_path).list_tabs()


def test_sheet_source_reports_stale_tab_list(tmp_path, monkeypatch):
    (tmp_path / "_tabs.html").write_text(TABS_JS, encoding="utf-8")

    def boom(url):
        raise OSError("network down")

    monkeypatch.setattr(fetch, "_get", boom)
    src = fetch.SheetSource("ID", tmp_path)
    assert src.list_tabs(refresh=True)[0][0] == "Arc"
    assert src.tabs_stale is True
