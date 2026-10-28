import pytest

from shell.sources.aegis.config import TabSpec
from shell.sources.aegis.table import ParseError, clean_header, parse_table

WEAPON_SPEC = TabSpec("HCs", "weapons-hcs", ("Name", "Tier"), ("Name",), 2, weapon_type="Hand Cannon", rank="#")

WEAPONS = [
    [("WEAPON", 1, 2), ("INFO", 1, 2), ("PERKS", 1, 3), ("ANALYSIS", 1, 3), ("KEY", 1, 2)],
    ["🖼️", "Name", "Season", "Energy", "Perk 1", "Perk 2", "", "Notes", "#", "Tier", "", ""],
    ["", "Kindled Orchid", "29", "Void", "Repulsor Brace\nShoot to Loot", "Destabilizing Rounds", "",
     "probably the best", "1", "S", "S", "game-warping"],
    ["", "Zaouli's Bane\nPantheon version", "29", "Solar", "Firefly", "Incandescent", "x", "double splash",
     "2", "A", "A", "great"],
    ["", "Zaouli's Bane", "29", "Solar", "Redirection", "Incandescent", "", "", "3", "B", "", ""],
]


def test_clean_header():
    assert clean_header(" crit\nShot ") == "crit Shot"


def test_weapon_table(sheet):
    t = parse_table(sheet(WEAPONS), WEAPON_SPEC)
    assert t.tab == "HCs"
    assert t.columns == ["Name", "Season", "Energy", "Perk 1", "Perk 2", "PERKS", "Notes", "#", "Tier"]
    assert t.groups["Perk 1"] == "PERKS" and t.groups["Tier"] == "ANALYSIS"
    assert [r["_name"] for r in t.rows] == ["Kindled Orchid", "Zaouli's Bane", "Zaouli's Bane"]
    first = t.rows[0]
    assert first["Perk 1"] == "Repulsor Brace\nShoot to Loot" and first["Tier"] == "S" and first["#"] == "1"
    assert "🖼️" not in first and "PERKS" not in first
    assert t.rows[1]["Name"] == "Zaouli's Bane\nPantheon version" and t.rows[1]["PERKS"] == "x"
    assert t.legend == {"S": "game-warping", "A": "great"}
    assert all(r["_section"] == "" for r in t.rows)


def test_duplicate_headers_get_band_suffix(sheet):
    rows = [
        [("INFO", 1, 3), ("ANALYSIS", 1, 2)],
        ["Artifact", "Mod", "Tier", "Description", "Tier"],
        ["Encrypted Data Disk", "Blinding Jolts", "II", "blind", "S"],
        ["Encrypted Data Disk", "Kinetic Synthesis", "I", "refill", "A"],
    ]
    spec = TabSpec("Artifact Mods", "artifact-mods", ("Artifact", "Mod"), ("Mod",), 2, tier="Tier (ANALYSIS)")
    t = parse_table(sheet(rows), spec)
    assert t.columns == ["Artifact", "Mod", "Tier (INFO)", "Description", "Tier (ANALYSIS)"]
    assert t.rows[0]["Tier (ANALYSIS)"] == "S" and t.rows[0]["Tier (INFO)"] == "II"


def test_header_merged_over_columns_names_each_column(sheet):
    # Pack Hunter: "Explosion" spans two columns (value, then ratio), under the INFORMATIONAL band
    rows = [
        [("TESTING", 1, 1), ("INFORMATIONAL", 1, 3), ("Notes", 2, 1)],
        ["Modifiers", "Base", ("Explosion", 1, 2)],
        ["None [1]", "74,469", "56,676", "N/A", "26% boost"],
        ["Bait and Switch [5]", "96,809", "73,679", "1.300", "not on impact"],
    ]
    spec = TabSpec("Pack Hunter", "pack-hunter", ("Modifiers",), ("Modifiers",), 2, tier=None)
    t = parse_table(sheet(rows), spec)
    assert t.columns == ["Modifiers", "Base", "Explosion", "Explosion 2", "Notes"]
    assert t.groups["Explosion 2"] == "INFORMATIONAL"
    assert t.rows[1]["Explosion 2"] == "1.300" and t.rows[1]["Notes"] == "not on impact"


def test_no_band_composite_key_and_vertical_merge(sheet):
    rows = [
        ["#", "Activity", "Boss", "effective\nHealth"],
        ["1", ("Last Wish", 2, 1), "Kalli", "149,720"],
        ["2", "Shuro Chi", "126,756"],
    ]
    spec = TabSpec("Bosses", "bosses", ("Activity", "Boss"), ("Activity", "Boss"), 2, tier=None)
    t = parse_table(sheet(rows), spec)
    assert t.columns == ["#", "Activity", "Boss", "effective Health"]
    assert [r["_name"] for r in t.rows] == ["Last Wish — Kalli", "Last Wish — Shuro Chi"]
    assert t.rows[1]["Activity"] == "Last Wish"          # vertical merge repeated


def test_sections_and_repeated_headers(sheet):
    rows = [
        ["Name", "Tier"],
        [("Pantheon", 1, 2)],
        ["Advanced Reflexes", "A"],
        ["Name", "Tier"],
        ["Gun and Run", "B"],
    ]
    spec = TabSpec("X", "x", ("Name", "Tier"), ("Name",), 2)
    t = parse_table(sheet(rows), spec)
    assert [(r["_name"], r["_section"]) for r in t.rows] == [("Advanced Reflexes", "Pantheon"),
                                                            ("Gun and Run", "Pantheon")]


def test_hidden_rows_are_counted(sheet):
    t = parse_table(sheet([["Name", "Tier"], ["A", "S"], ["B", "A"]], hidden=(2,)), TabSpec("X", "x", ("Name",), ("Name",), 1))
    assert t.hidden_rows == 1


def test_errors_name_the_tab(sheet):
    with pytest.raises(ParseError, match="HCs: headers not found"):
        parse_table(sheet([["Nom", "Rang"], ["A", "S"]]), WEAPON_SPEC)
    with pytest.raises(ParseError, match="1 row found, at least 2 expected"):
        parse_table(sheet([["Name", "Tier"], ["A", "S"]]), WEAPON_SPEC)
    spec = TabSpec("X", "x", ("Tier",), ("Name",), 1)
    with pytest.raises(ParseError, match="key column not found: Name"):
        parse_table(sheet([["Nom", "Tier"], ["A", "S"]]), spec)


def test_legend_cells_do_not_affect_sections(sheet):
    rows = [
        [("INFO", 1, 2), ("KEY", 1, 2)],
        ["Name", "Tier", "", ""],
        [("Pantheon", 1, 2), "S", "game-warping"],
        ["Advanced Reflexes", "A", "", ""],
    ]
    t = parse_table(sheet(rows), TabSpec("X", "x", ("Name", "Tier"), ("Name",), 1))
    assert [(r["_name"], r["_section"]) for r in t.rows] == [("Advanced Reflexes", "Pantheon")]
    assert t.legend == {"S": "game-warping"}


def test_unmerged_title_row_is_not_a_band(sheet):
    rows = [
        [("Hand Cannons - updated S29", 1, 1), "", "", ""],
        ["Name", "Notes", "", "Tier"],
        ["A", "n", "", "S"],
        ["B", "m", "", "A"],
    ]
    t = parse_table(sheet(rows), TabSpec("X", "x", ("Name", "Tier"), ("Name",), 2))
    assert t.columns == ["Name", "Notes", "Tier"]
    assert set(t.groups.values()) == {""}


def test_ignored_icon_header_merged_over_columns_stays_ignored(sheet):
    rows = [
        [("INFO", 1, 4)],
        [("🖼️", 1, 2), "Name", "Tier"],
        ["", "icon-a", "A", "S"],
        ["", "icon-b", "B", "B"],
    ]
    t = parse_table(sheet(rows), TabSpec("X", "x", ("Name", "Tier"), ("Name",), 2))
    assert t.columns == ["Name", "Tier"]
    assert [r["Name"] for r in t.rows] == ["A", "B"]
