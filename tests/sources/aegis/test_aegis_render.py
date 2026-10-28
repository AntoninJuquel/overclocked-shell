import json

from shell.sources.aegis import render
from shell.sources.aegis.model import Table, TabResult

TABLE = Table("HCs", ["Name", "Perk 1", "Tier"], {"Name": "WEAPON", "Perk 1": "PERKS", "Tier": "ANALYSIS"},
              [{"_name": "Kindled Orchid", "_section": "", "Name": "Kindled Orchid",
                "Perk 1": "Repulsor Brace\nShoot to Loot", "Tier": "S"},
               {"_name": "Old One", "_section": "Legacy", "Name": "Old One", "Tier": "C"}],
              {"S": "game-warping"}, hidden_rows=2)


def test_to_json_and_load_meta(tmp_path):
    doc = render.to_json(TABLE, "endgame", "2026-08-19", "2026-10-09")
    assert doc["sheet"] == "endgame" and doc["tab"] == "HCs" and doc["updated"] == "2026-08-19"
    assert doc["rows"][0]["Perk 1"] == "Repulsor Brace\nShoot to Loot" and doc["legend"] == {"S": "game-warping"}
    path = tmp_path / "hcs.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert render.load_meta(path) == ("2026-10-09", "2026-08-19", 2, 2)
    assert render.load_meta(tmp_path / "absent.json") == (None, None, 0, 0)


def test_render_tab():
    md = render.render_tab(TABLE, "Endgame Analysis", "2026-08-19", "2026-10-09")
    assert md.startswith('# HCs\n\nSource: Aegis — Endgame Analysis, tab "HCs", updated by Aegis on '
                         "2026-08-19, fetched on 2026-10-09.\nRows hidden by the author (missing from this "
                         "version): 2.\n")
    assert "## Legend\n\n- S: game-warping\n" in md
    assert "## HCs\n\n### Kindled Orchid\n- Name: Kindled Orchid\n- Perk 1: Repulsor Brace / Shoot to Loot\n- Tier: S\n" in md
    assert "## Legacy\n\n### Old One\n- Name: Old One\n- Tier: C\n" in md
    assert md.endswith("\n") and not md.endswith("\n\n")


def test_render_tab_without_update_date():
    md = render.render_tab(TABLE, "Boss Damage", None, "2026-10-09")
    assert 'tab "HCs", fetched on 2026-10-09.' in md


def test_render_index():
    results = [TabResult("Endgame Analysis", "endgame", "HCs", "weapons-hcs", 40, "2026-10-09", "2026-08-19"),
               TabResult("Boss Damage", "boss", "Swap", "swap", 0, None, ok=False, note="Swap: tab missing from the Sheet")]
    md = render.render_index(results, "2026-10-09")
    assert "Last run: 2026-10-09" in md and "Oldest data: 2026-10-09" in md
    assert "| Endgame Analysis | HCs | [endgame/weapons-hcs.md](endgame/weapons-hcs.md) | 40 | 2026-08-19 | 2026-10-09 | ok |" in md
    assert "| Boss Damage | Swap | boss/swap.md | 0 | — | — | ⚠ Swap: tab missing from the Sheet — no data |" in md
    assert "https://docs.google.com/spreadsheets/d/1JM-0SlxVDAi-C6rGVlLxa-J1WGewEeL8Qvq4htWZHhY" in md
