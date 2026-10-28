import copy

from shell.engines import raids
from shell.outputs import raid_map, raid_page
from tests.engines.test_raids import ENC

NAMES = raids.names(ENC, {"terminal": "Term A"})


def test_svg_draws_placed_spots_only_and_labels_names():
    svg = raid_map.svg(ENC, "upper", NAMES, set())
    assert svg.startswith("<svg") and "Term A" in svg and "Hall" in svg and "Upstairs" in svg
    assert "Panel 1" not in svg                        # panel-l1 has no position: never drawn
    assert "Schematic — positions from the guides" in svg


def test_svg_highlights():
    assert 'class="spot hl"' in raid_map.svg(ENC, "upper", NAMES, {"terminal"})
    assert 'class="spot hl"' not in raid_map.svg(ENC, "upper", NAMES, set())


def test_page_has_refresh_steps_role_table_unplaced_conflicts_sources():
    page = raid_page.render(ENC, NAMES, "scanner", "panels")
    assert '<meta http-equiv="refresh" content="3">' in page
    assert "<title>Crypt Security — Panels — Scanner</title>" in page
    assert "<li>Call the lit panels.</li>" in page and "Shoot them." in page      # own steps, then the role table
    assert "Not on the map" in page and "Panel 1 (left)" in page
    assert "Shacknews numbers 5 panels per side" in page
    assert "grindout (2026-07-20)" in page and "Upstairs" in page and "Basement" not in page.split("Not on")[0]


def test_page_role_without_steps():
    assert "No steps for Add clear in the guides." in raid_page.render(ENC, NAMES, "adds", "panels")


def test_page_escapes_text():
    enc = copy.deepcopy(ENC)
    enc["phases"][0]["steps"]["scanner"] = ["<b>x</b>"]
    page = raid_page.render(enc, NAMES, "scanner", "panels")
    assert "<b>x</b>" not in page and "&lt;b&gt;x&lt;/b&gt;" in page


def test_write(tmp_path):
    path = tmp_path / "raids" / "live.html"
    raid_page.write(path, "<html></html>")
    assert path.read_text(encoding="utf-8") == "<html></html>"
