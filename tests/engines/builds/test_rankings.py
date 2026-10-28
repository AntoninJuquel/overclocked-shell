import pytest

from shell.engines.builds import rankings
from tests.sources.aegis.conftest import write_aegis


@pytest.fixture
def data(aegis_dir):
    d = aegis_dir
    write_aegis(d, "endgame", "weapons-rockets", [
        {"_name": "Hezen Vengeance", "Energy": "Solar", "Perk 1": "Cluster Bomb", "Notes": "best\nrocket", "#": "1", "Tier": "S"},
        {"_name": "Bellowing Giant", "Energy": "Kinetic", "#": "4", "Tier": "B"}], tab="Rockets")
    write_aegis(d, "endgame", "weapons-hcs", [{"_name": "Kindled Orchid", "Energy": "Void", "#": "1", "Tier": "S"}], tab="HCs")
    write_aegis(d, "endgame", "aspects", [
        {"_name": "Controlled Demolition", "Subclass": "Void", "Class": "T", "#": "1", "Tier": "S"},
        {"_name": "Weavewalk", "Subclass": "Strand", "Class": "W", "#": "2", "Tier": "S"}])
    write_aegis(d, "boss", "sustained", [
        {"_name": "High-impact bow", "Name": "High-impact bow\nHeavy Bolts", "Type": "power", "DPS": "17,960"},
        {"_name": "Adaptive rocket launcher", "Name": "Adaptive rocket launcher", "Type": "power", "DPS": "16,231"},
        {"_name": "Truth", "Name": "Truth", "Type": "power", "DPS": "20,100"}])
    write_aegis(d, "boss", "bosses", [{"_name": "Last Wish — Kalli", "Activity": "Last Wish", "Boss": "Kalli",
                                       "effective Health": "149,720"}])
    return d


def test_weapons_filters_and_order(data):
    lines = rankings.rank("weapons", type="rocket")
    assert lines[0].startswith("S #1 | Hezen Vengeance | Rockets | Energy: Solar | Perk 1: Cluster Bomb |")
    assert lines[0].endswith("| Notes: best / rocket")
    assert lines[1].startswith("B #4 | Bellowing Giant") and len(lines) == 2
    assert rankings.rank("weapons", element="void")[0].startswith("S #1 | Kindled Orchid")
    assert len(rankings.rank("weapons", tier="a")) == 2       # B excluded


def test_aspects_by_class_and_element(data):
    assert rankings.rank("aspects", class_type="titan")[0].startswith("S #1 | Controlled Demolition")
    assert "Weavewalk" in rankings.rank("aspects", element="Strand")[0]
    assert rankings.rank("aspects", class_type="Hunter") == ["no matching entry"]


def test_dps_and_bosses(data):
    assert rankings.rank("dps-sustained", top=2) == ["20,100 | Truth | Type: power",
                                                     "17,960 | High-impact bow / Heavy Bolts | Type: power"]
    assert rankings.rank("bosses", activity="last")[0].startswith("Last Wish — Kalli | effective Health: 149,720")


def test_name_search(data):
    lines = rankings.rank("name", name="kindled")
    assert lines[0].startswith("endgame/weapons-hcs | S #1 | Kindled Orchid") and "    Energy: Void" in lines


def test_missing_data(aegis_dir):
    with pytest.raises(FileNotFoundError, match="refresh_references"):
        rankings.rank("perks")
    with pytest.raises(FileNotFoundError, match="refresh_references"):
        rankings.rank("name", name="x")


@pytest.mark.parametrize("kwargs,needle", [
    ({"view": "nope"}, "unknown view"),
    ({"view": "dps-swap", "top": 0}, "top"),
    ({"view": "weapons", "tier": "Z"}, "tier"),
    ({"view": "aspects", "class_type": "Paladin"}, "class_type"),
    ({"view": "name"}, "name"),
])
def test_bad_arguments(data, kwargs, needle):
    with pytest.raises(ValueError, match=needle):
        rankings.rank(**kwargs)


def test_swap_shows_swap_dps_only_when_different(data):
    write_aegis(data, "boss", "swap", [
        {"_name": "A", "Name": "A", "Type": "burst", "swap DPS": "40,000", "true DPS": "30,000"},
        {"_name": "B", "Name": "B", "Type": "super", "swap DPS": "20,000", "true DPS": "20,000"}])
    assert rankings.rank("dps-swap") == ["30,000 | A | Type: burst | swap DPS: 40,000", "20,000 | B | Type: super"]


def test_exotic_columns(data):
    write_aegis(data, "endgame", "exotic-weapons", [
        {"_name": "Gjallarhorn", "Ammo": "12", "Type": "Rocket Launcher", "Tags": "damage", "Usage": "wolfpack", "#": "1", "Tier": "S"}])
    assert rankings.rank("exotic-weapons") == ["S #1 | Gjallarhorn | Type: Rocket Launcher | Tags: damage | Usage: wolfpack"]


def test_type_filter_lists_other_tab_rows_last_with_a_note(data):
    write_aegis(data, "endgame", "weapons-other", [
        {"_name": "Refurbished A499", "Energy": "Kinetic", "#": "1", "Tier": "S"}], tab="Other")
    lines = rankings.rank("weapons", type="rocket")
    assert [line.split(" | ")[1] for line in lines] == ["Hezen Vengeance", "Bellowing Giant", "Refurbished A499"]
    assert lines[2].endswith("type not given by Aegis (Other tab)")
    assert "type not given" not in lines[0]
    assert not any("type not given" in line for line in rankings.rank("weapons"))     # no --type: no note
    solar = rankings.rank("weapons", type="rocket", element="solar")                  # other filters kept
    assert len(solar) == 1 and "Hezen Vengeance" in solar[0]
