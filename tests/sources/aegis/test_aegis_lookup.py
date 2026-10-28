import json
import os

from shell.sources.aegis import lookup
from tests.sources.aegis.conftest import write_aegis


def test_missing_data_warns_once(isolated_aegis_dir, capsys):
    assert lookup.rows("endgame", "perks") == []
    assert lookup.weapon_rows("Kindled Orchid") == []
    err = capsys.readouterr().err
    assert err.count("refresh_references(source='aegis')") == 1


def test_data_dir_defaults_to_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(lookup, "DATA", None)
    assert lookup.data_dir() == tmp_path / "cache" / "aegis"


def test_find_and_weapon_rows(isolated_aegis_dir):
    write_aegis(isolated_aegis_dir, "endgame", "weapons-hcs", [
        {"_name": "Zaouli's Bane", "Name": "Zaouli's Bane\nPantheon version", "#": "6", "Tier": "A"},
        {"_name": "Zaouli's Bane", "Name": "Zaouli's Bane", "#": "7", "Tier": "B"}], tab="HCs")
    write_aegis(isolated_aegis_dir, "endgame", "exotic-weapons", [{"_name": "Ace of Spades", "Tier": "B"}])
    rows = lookup.weapon_rows("Zaouli’s Bane")
    assert [r["#"] for r in rows] == ["6", "7"] and rows[0]["_tab"] == "HCs"
    assert lookup.weapon_rows("ace of spades")[0]["Tier"] == "B"
    assert lookup.find("endgame", "weapons-hcs", "nope") == []


def test_best_and_labels():
    rows = [{"Tier": "B", "#": "2"}, {"Tier": "A", "#": "9"}, {"Tier": "A", "#": "3"}, {"Tier": ""}]
    assert lookup.best(rows) == {"Tier": "A", "#": "3"}
    assert lookup.best([]) is None
    assert lookup.tier_label({"Tier": "S", "#": "1"}) == "S #1"
    assert lookup.tier_label({"Tier": "B"}) == "B"
    assert lookup.tier_label({"Tier (ANALYSIS)": "S"}, tier="Tier (ANALYSIS)") == "S"
    assert lookup.tier_key({"Tier": "?"}) == (7, 10 ** 9)
    # Aegis also rates E (between D and F)
    assert lookup.best([{"Tier": "F", "#": "1"}, {"Tier": "E", "#": "5"}]) == {"Tier": "E", "#": "5"}


def test_perk_names():
    row = {"Barrel": "Fluted Barrel", "Perk 1": "Repulsor Brace\nShoot to Loot", "Perk 2": "Kill Clip",
           "Origin Trait": "Forge's Kin", "MW": "Reload", "Notes": "x"}
    assert lookup.perk_names(row) == {"fluted barrel", "repulsor brace", "shoot to loot", "kill clip", "forge's kin"}


def test_load_tab_is_cached_until_file_changes(isolated_aegis_dir, monkeypatch):
    path = isolated_aegis_dir / "endgame" / "perks.json"
    write_aegis(isolated_aegis_dir, "endgame", "perks", [{"_name": "Kill Clip", "Tier": "A"}])
    calls = []
    real_loads = json.loads
    monkeypatch.setattr(lookup.json, "loads", lambda *a, **k: calls.append(1) or real_loads(*a, **k))

    first = lookup.rows("endgame", "perks")
    first[0]["Tier"] = "Z"  # changing the result must not damage the cache
    assert lookup.rows("endgame", "perks")[0]["Tier"] == "A"
    assert len(calls) == 1

    mtime = path.stat().st_mtime_ns
    write_aegis(isolated_aegis_dir, "endgame", "perks", [{"_name": "Kill Clip", "Tier": "S"}])
    os.utime(path, ns=(mtime + 10 ** 9, mtime + 10 ** 9))
    assert lookup.rows("endgame", "perks")[0]["Tier"] == "S"
    assert len(calls) == 2


def test_find_uses_a_per_file_name_index(isolated_aegis_dir, monkeypatch):
    write_aegis(isolated_aegis_dir, "endgame", "perks", [
        {"_name": "Kill Clip", "Tier": "A"}, {"_name": "Rampage", "Tier": "B"}, {"_name": "Outlaw", "Tier": "C"}],
        tab="Perks")
    assert lookup.find("endgame", "perks", "Kill Clip")[0]["Tier"] == "A"  # warm-up: builds the index
    seen = []
    real = lookup.norm
    monkeypatch.setattr(lookup, "norm", lambda n: seen.append(n) or real(n))
    found = lookup.find("endgame", "perks", "kill clip")
    assert found[0]["_tab"] == "Perks" and seen == ["kill clip"]  # only the query is normalized
    found[0]["Tier"] = "Z"  # a copy: the cache is not damaged
    assert lookup.find("endgame", "perks", "Kill Clip")[0]["Tier"] == "A"
