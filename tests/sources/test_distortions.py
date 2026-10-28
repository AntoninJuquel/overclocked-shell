import json

import pytest

from shell.sources import distortions, sources

PAGE = """<script>
	// Community-observed hourly rotation, anchored to a verified live reading
	var ROTATION = [
		'Cosmodrome',
		'EDZ',
		'Dreaming City',
		"Savathun's Throne World",
		'Moon',
		'Europa',
		'Nessus'
	];
	var ANCHOR_HOUR = 494803; // Unix epoch hours; ROTATION[5] active this hour
	var ANCHOR_INDEX = 5;
</script>"""
ORDER = ["Cosmodrome", "EDZ", "Dreaming City", "Savathun's Throne World", "Moon", "Europa", "Nessus"]


@pytest.fixture
def page(monkeypatch):
    """page(text or exception): what the next download returns or raises."""
    state = {}

    def get(url):
        assert url == distortions.URL
        if isinstance(state["v"], Exception):
            raise state["v"]
        return state["v"].encode("utf-8")

    monkeypatch.setattr(distortions.web, "get", get)
    return lambda v: state.__setitem__("v", v)


def test_registered():
    assert "distortions" in sources()


def test_parse_and_cache(page):
    page(PAGE)
    r = distortions.refresh()
    assert r["ok"] and r["changed"] == ["rotation.json"] and r["stale"] == []
    rot = distortions.load()
    assert rot["order"] == ORDER and rot["anchor_hour"] == 494803 and rot["anchor_index"] == 5
    assert rot["source"] == distortions.URL and rot["fetched"]
    page(RuntimeError("must not download"))
    assert distortions.refresh()["changed"] == []          # cached: no download without force


def test_reanchored_page_is_not_a_change(page):
    page(PAGE)
    distortions.refresh()
    page(PAGE.replace("494803", "494810"))                  # 7 hours later, same index: same schedule
    assert distortions.refresh(force=True)["changed"] == []
    page(PAGE.replace("'Moon',\n\t\t'Europa'", "'Europa',\n\t\t'Moon'"))
    assert distortions.refresh(force=True)["changed"] == ["rotation.json"]


@pytest.mark.parametrize("bad", [PAGE.replace("ANCHOR_HOUR", "START"), PAGE.replace("\t\t'Nessus'\n", ""),
                                 PAGE.replace("ANCHOR_INDEX = 5", "ANCHOR_INDEX = 9")])
def test_invalid_page_keeps_the_cache(page, bad):
    page(PAGE)
    distortions.refresh()
    before = distortions.path().read_text(encoding="utf-8")
    page(bad)
    r = distortions.refresh(force=True)
    assert not r["ok"] and "tracker page" in r["errors"][0]
    assert distortions.path().read_text(encoding="utf-8") == before


def test_download_error(page):
    page(OSError("offline"))
    r = distortions.refresh(force=True)
    assert not r["ok"] and r["errors"] == ["offline"] and distortions.load() is None
    page(PAGE)
    distortions.refresh()
    page(OSError("offline"))
    r = distortions.refresh(force=True)
    assert r["ok"] and r["stale"] == ["rotation.json"]
    assert json.loads(distortions.path().read_text(encoding="utf-8"))["order"] == ORDER
