import pytest

from shell.core import paths
from shell.engines.builds import artifact
from tests.sources.aegis.conftest import write_aegis

REAL_COMPENDIUM = paths.cache_dir() / "compendium"  # resolved at import, before the isolation fixture

MD = """# Artifact Perks

## Artifact Perks

### Notes
- section: Artifact Perks

Text.

## Satchel (Revenant)

### Wind Chill
- section: Satchel (Revenant)
- order: 4
- column: 1

### Total Carnage
- section: Satchel (Revenant)
- order: 4
- column: 1

### Power from Pain
- section: Satchel (Revenant)
- order: 4
- column: 1

### Weakened Clear
- section: Satchel (Revenant)
- order: 4
- column: 2

### Void Renewal
- section: Satchel (Revenant)
- order: 4
- column: 2

### Curative Orbs
- section: Satchel (Revenant)
- order: 4
- column: 2

### Old God's Rite
- section: Satchel (Revenant)
- order: 4
- column: 3

### Supernova
- section: Satchel (Revenant)
- order: 4
- column: 3

### Served Cold
- section: Satchel (Revenant)
- order: 4
- column: 3

## Data Disk (Renegades)

### Power from Pain
- section: Data Disk (Renegades)
- order: 1
- column: 1
"""


@pytest.fixture
def perks(tmp_path):
    (tmp_path / "artifact-perks.md").write_text(MD, encoding="utf-8")
    return artifact.load(tmp_path)


def test_load_strips_season(perks):
    assert set(perks) == {"Satchel", "Data Disk"}
    assert perks["Satchel"]["Weakened Clear"] == 2
    assert perks["Data Disk"] == {"Power from Pain": 1}


def test_load_defaults_to_the_cache_and_names_the_fix(isolated_dirs):
    with pytest.raises(ValueError, match=r"artifact-perks.md missing: run refresh_references"):
        artifact.load()
    folder = isolated_dirs / "cache" / "compendium"
    folder.mkdir(parents=True)
    (folder / "artifact-perks.md").write_text(MD, encoding="utf-8")
    assert "Satchel" in artifact.load()


def test_check_ok_and_assign(perks):
    chosen = ["Old God's Rite", "Weakened Clear", "Total Carnage", "Supernova", "Void Renewal", "Wind Chill",
              "Curative Orbs"]
    assert artifact.check({"name": "Satchel", "perks": chosen}, perks) == []
    assert artifact.assign(chosen, perks["Satchel"]) == [
        {"name": "Total Carnage", "socketIndex": 0}, {"name": "Wind Chill", "socketIndex": 1},
        {"name": "Weakened Clear", "socketIndex": 2}, {"name": "Void Renewal", "socketIndex": 3},
        {"name": "Curative Orbs", "socketIndex": 4}, {"name": "Old God's Rite", "socketIndex": 5},
        {"name": "Supernova", "socketIndex": 6}]


def test_assign_fills_free_sockets_with_empty(perks):
    assert artifact.assign(["Weakened Clear"], perks["Satchel"]) == [
        {"name": "Empty Artifact Mod", "socketIndex": 0}, {"name": "Empty Artifact Mod", "socketIndex": 1},
        {"name": "Weakened Clear", "socketIndex": 2}, {"name": "Empty Artifact Mod", "socketIndex": 3},
        {"name": "Empty Artifact Mod", "socketIndex": 4}, {"name": "Empty Artifact Mod", "socketIndex": 5},
        {"name": "Empty Artifact Mod", "socketIndex": 6}]


def test_assign_without_room_raises(perks):
    with pytest.raises(ValueError, match="no room left for Served Cold"):
        artifact.assign(["Old God's Rite", "Supernova", "Served Cold"], perks["Satchel"])


def test_low_column_perk_overflows_to_higher_sockets(perks):
    plugs = artifact.assign(["Wind Chill", "Total Carnage", "Power from Pain"], perks["Satchel"])
    assert [p["name"] for p in plugs[:3]] == ["Wind Chill", "Total Carnage", "Power from Pain"]


@pytest.mark.parametrize("intent,needle", [
    ({"name": "Nope", "perks": []}, "unknown artifact"),
    ({"name": "satchel", "perks": []}, "Satchel"),
    ({"name": "Satchel", "perks": ["Power from Pain", "Power from Pain"]}, "listed twice"),
    ({"name": "Satchel", "perks": ["Brain Freeze"]}, "is not a perk of Satchel"),
    ({"name": "Satchel", "perks": ["Old God's Rite", "Supernova", "Served Cold"]}, "column 3"),
])
def test_check_problems(perks, intent, needle):
    problems = artifact.check(intent, perks)
    assert problems and any(needle in p for p in problems)


def test_too_many_column_two_or_more(perks):
    chosen = ["Weakened Clear", "Void Renewal", "Curative Orbs", "Old God's Rite", "Supernova", "Served Cold"]
    assert any("column 3" in p for p in artifact.check({"name": "Satchel", "perks": chosen}, perks))


@pytest.mark.skipif(not (REAL_COMPENDIUM / "artifact-perks.md").exists(), reason="compendium missing")
def test_real_compendium_columns_fit_sockets():
    """Canary: every artifact of the compendium has its perks in columns the sockets accept."""
    known = artifact.load(REAL_COMPENDIUM)
    assert known
    top = max(artifact.ARTIFACT_SOCKET_COLUMNS)
    assert all(1 <= c <= top for perks in known.values() for c in perks.values())


def test_list_lines_with_aegis_tiers(perks, aegis_dir):
    write_aegis(aegis_dir, "endgame", "artifact-mods", [
        {"_name": "Supernova", "Tier (INFO)": "III", "Tier (ANALYSIS)": "S"},
        {"_name": "Power from Pain", "Tier (ANALYSIS)": "B"}, {"_name": "Power from Pain", "Tier (ANALYSIS)": "A"}])
    lines = artifact.list_lines(perks)
    assert lines[0] == "Satchel:"
    assert "  column 3: Old God's Rite, Supernova (S), Served Cold" in lines
    assert "  column 1: Wind Chill, Total Carnage, Power from Pain (A)" in lines


def test_list_lines_without_aegis(perks):
    assert "  column 3: Old God's Rite, Supernova, Served Cold" in artifact.list_lines(perks)


def test_list_lines_prefers_the_row_of_the_artifact(perks, aegis_dir):
    write_aegis(aegis_dir, "endgame", "artifact-mods", [
        {"_name": "Supernova", "Artifact": "Hunter's Journal", "Tier (ANALYSIS)": "S"},
        {"_name": "Supernova", "Artifact": "Satchel", "Tier (ANALYSIS)": "C"},
        {"_name": "Power from Pain", "Artifact": "Hunter's Journal", "Tier (ANALYSIS)": "A"}])
    lines = artifact.list_lines(perks)
    assert "  column 3: Old God's Rite, Supernova (C), Served Cold" in lines   # this artifact's row
    assert "  column 1: Wind Chill, Total Carnage, Power from Pain (A)" in lines  # fallback: best row
