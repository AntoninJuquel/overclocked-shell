"""Every Aegis tab on the real cached HTML (cache/aegis/raw/). Skipped when the cache is absent: fill it
with refresh_references(source='aegis').

Canaries: they can fail after a forced refresh if Aegis changes a Sheet (renamed entries, changed tiers).
Then update the tab's config or these checks."""
import pytest

from shell.core import paths
from shell.sources.aegis.config import SHEETS
from shell.sources.aegis.table import parse_table
from shell.sources.sheets.fetch import SheetSource
from shell.sources.sheets.grid import parse_grid

RAW = paths.ROOT / "cache" / "aegis" / "raw"


def _tables(sheet_key):
    sheet = SHEETS[sheet_key]
    if not (RAW / sheet_key / "_tabs.html").exists():
        pytest.skip("Aegis cache absent: refresh_references(source='aegis')")
    src = SheetSource(sheet.id, RAW / sheet_key)
    tabs = src.list_tabs()
    out = {}
    for spec in sheet.tabs:
        gid = next(g for n, g in tabs if spec.matches(n))
        out[spec.slug] = parse_table(parse_grid(src.tab_html(gid)[0]), spec)
    return out


def _row(table, name):
    row = next((r for r in table.rows if r["_name"] == name), None)
    assert row is not None, f"{name} missing from {table.tab}"
    return row


def test_endgame_tabs():
    t = _tables("endgame")
    hc = _row(t["weapons-hcs"], "Kindled Orchid")
    assert hc["Tier"] and hc["Tier"][0] in "SABCDEF" and hc["#"].isdigit() and hc["Perk 1"] and hc["Origin Trait"]
    assert "Tier (ANALYSIS)" in t["artifact-mods"].columns
    assert _row(t["aspects"], "Controlled Demolition")["Subclass"] == "Void"
    assert t["set-bonuses"].rows[0]["Pcs"] in ("2", "4")
    assert {r["Priority"] for r in t["shopping-list"].rows} <= {"high", "medium", "low", "niche"}
    assert any(r["_name"].startswith("H — ") for r in t["subclasses"].rows)
    assert _row(t["status"], "HCs")["UPDATED"][:2] == "20"
    assert t["weapons-hcs"].legend or t["perks"].legend


def test_boss_tabs():
    t = _tables("boss")
    assert all(r.get("DPS") for r in t["sustained"].rows[:10])
    assert "true DPS" in t["swap"].columns
    assert any(r["_name"].startswith("Last Wish — ") for r in t["bosses"].rows)
    assert any(r["_name"].startswith("Auto rifle — ") for r in t["weapons"].rows)
    assert "Explosion 2" in t["pack-hunter"].columns  # header merged over two columns
