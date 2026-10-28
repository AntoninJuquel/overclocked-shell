import pytest

from shell.engines import recommend
from tests.sources.aegis.conftest import write_aegis


@pytest.fixture
def aegis(tmp_path, monkeypatch):
    from shell.sources.aegis import lookup
    monkeypatch.setattr(lookup, "DATA", tmp_path / "aegis")
    monkeypatch.setattr(lookup, "_warned", False)
    return tmp_path / "aegis"


def w(item_id, name, type_="Auto Rifle", slot="Kinetic", element="Strand", rarity="Legendary", frame="Support Frame",
      ammo="Primary", location="Vault", equipped=False, locked=True):
    return {"itemId": item_id, "name": name, "type": type_, "slot": slot, "element": element, "rarity": rarity,
            "frame": frame, "ammo": ammo, "location": location, "equipped": equipped, "locked": locked, "columns": []}


AR = "weapons-autos"
ITEMS = [
    w("1", "Adamantite"),
    w("2", "Adamantite", location="Warlock", equipped=True),          # same name: the equipped copy wins the tie
    w("3", "Rufus's Fury", location="Hunter"),
    w("4", "DECATUR 02", slot="Energy", element="Void", location="Warlock", equipped=True),
    w("5", "Choir of One", slot="Power", element="Void", rarity="Exotic", ammo="Heavy", location="Warlock",
      equipped=True),
    w("6", "Sweet Business", rarity="Exotic"),
    w("7", "Unrated Gun"),
]


def write_ratings(aegis):
    write_aegis(aegis, "endgame", AR, [
        {"_name": "Rufus's Fury", "Tier": "S", "#": "1", "Energy": "Strand"},
        {"_name": "Adamantite", "Tier": "A", "#": "2", "Energy": "Strand"},
        {"_name": "DECATUR 02", "Tier": "B", "#": "1", "Energy": "Void"},
        {"_name": "Unowned Best", "Tier": "S", "#": "2", "Energy": "Strand"},
        {"_name": "Unowned Arc", "Tier": "S", "#": "3", "Energy": "Arc"},
        {"_name": "Too Low", "Tier": "B", "#": "9", "Energy": "Strand"}])
    write_aegis(aegis, "endgame", "exotic-weapons", [
        {"_name": "Sweet Business", "Tier": "B", "#": "1", "Type": "Auto Rifle"}])


def test_general_ranking_one_line_per_name_and_notes(aegis):
    write_ratings(aegis)
    r = recommend.recommend(ITEMS, {"1": "A #3"}, "warlock", slot="Kinetic")
    names = [line.split(" | ")[2] for line in r["picks"]]
    assert names == ["Rufus's Fury", "Adamantite", "Sweet Business", "Unrated Gun"]
    rufus, adamantite, sweet = r["picks"][:3]
    assert rufus.startswith("1 | 3 | ") and "Aegis S #1" in rufus and rufus.endswith("on Hunter · swap: replaces Adamantite")
    assert " | 1 | Adamantite" in adamantite and "grade A #3" in adamantite        # graded copy beats equipped copy
    assert sweet.endswith("in vault · swap: replaces Adamantite · second exotic: unequip Choir of One")
    assert r["equipped"] == ["Kinetic | Adamantite | Auto Rifle | Strand", "Energy | DECATUR 02 | Auto Rifle | Void",
                             "Power | Choir of One | Auto Rifle | Void | exotic"]


def test_equipped_copy_wins_tie(aegis):
    write_ratings(aegis)
    line = next(x for x in recommend.recommend(ITEMS, {}, "warlock")["picks"] if x.split(" | ")[2] == "Adamantite")
    assert " | 2 | Adamantite" in line and line.endswith("equipped")


def test_filters_and_top(aegis):
    write_ratings(aegis)
    r = recommend.recommend(ITEMS, {}, "warlock", element="void", top=1)
    assert [x.split(" | ")[2] for x in r["picks"]] == ["DECATUR 02"]
    assert recommend.recommend(ITEMS, {}, "warlock", type_="sword")["picks"] == []


def test_not_owned_needs_type_and_beats_best_owned(aegis):
    write_ratings(aegis)
    assert recommend.recommend(ITEMS, {}, "warlock")["not_owned"] == []
    r = recommend.recommend(ITEMS, {}, "warlock", type_="auto", element="Strand")
    assert r["not_owned"] == []                                       # Rufus's Fury S #1 is owned and best
    r = recommend.recommend(ITEMS[:2], {}, "warlock", type_="auto", element="Strand")
    assert r["not_owned"] == ["S #1 | Rufus's Fury | weapons-autos", "S #2 | Unowned Best | weapons-autos"]


def test_bad_arguments(aegis):
    with pytest.raises(ValueError, match="character"):
        recommend.recommend(ITEMS, {}, "ghost")
    with pytest.raises(ValueError, match="role"):
        recommend.recommend(ITEMS, {}, "warlock", role="vibes")
    with pytest.raises(ValueError, match="top"):
        recommend.recommend(ITEMS, {}, "warlock", top=0)


ROCKETS = [
    w("10", "Hezen Vengeance", type_="Rocket Launcher", slot="Power", element="Strand", frame="Aggressive Frame",
      ammo="Heavy"),
    w("11", "Bad Omens", type_="Rocket Launcher", slot="Power", element="Void", frame="Precision Frame", ammo="Heavy"),
    w("12", "Gjallarhorn", type_="Rocket Launcher", slot="Power", element="Solar", rarity="Exotic", frame="Wolfpack",
      ammo="Heavy"),
    w("13", "Slug", type_="Shotgun", slot="Energy", frame="Rapid Fire Slug", ammo="Special"),
    w("14", "Pellets", type_="Shotgun", slot="Energy", frame="Rapid-Fire Frame", ammo="Special"),
    w("15", "Corrective Measure", type_="Machine Gun", slot="Power", frame="Aggressive Frame", ammo="Heavy",
      location="Warlock", equipped=True),
]


def write_dps(aegis):
    write_aegis(aegis, "boss", "sustained", [
        {"_name": "Aggressive rocket launcher", "Name": "Aggressive rocket launcher\nCluster Bomb + Elemental Honing",
         "Family": "rocket", "DPS": "13,514"},
        {"_name": "Gjallarhorn", "Name": "Gjallarhorn\nWolfpack Rounds", "Family": "rocket", "DPS": "15,000"},
        {"_name": "Rapid-fire slug shotgun", "Name": "Rapid-fire slug shotgun", "Family": "shotgun", "DPS": "9,000"},
        {"_name": "Rapid-fire shotgun", "Name": "Rapid-fire shotgun", "Family": "shotgun", "DPS": "8,000"},
        {"_name": "Aggressive sword", "Name": "Aggressive sword", "Family": "sword", "DPS": "20,000"}])


def test_dps_matches_archetype_and_exotic_by_name(aegis):
    write_dps(aegis)
    r = recommend.recommend(ROCKETS, {}, "warlock", role="dps")
    assert [x.split(" | ")[2] for x in r["picks"]] == ["Gjallarhorn", "Hezen Vengeance", "Slug", "Pellets"]
    hezen = r["picks"][1]
    assert "DPS 13,514 (Aggressive rocket launcher: Cluster Bomb + Elemental Honing)" in hezen
    assert hezen.endswith("in vault · swap: replaces Corrective Measure")
    assert r["not_owned"] == [] and r["warnings"] == ["no Aegis DPS row for: Bad Omens, Corrective Measure"]


def test_dps_without_any_match_warns(aegis):
    write_dps(aegis)
    r = recommend.recommend(ROCKETS, {}, "warlock", role="dps", type_="machine gun")
    assert r["picks"] == [] and r["warnings"] == ["no Aegis DPS row for: Corrective Measure"]


def test_missing_aegis_data(aegis):
    with pytest.raises(FileNotFoundError, match="refresh_references"):
        recommend.recommend(ITEMS, {}, "warlock")
    with pytest.raises(FileNotFoundError, match="refresh_references"):
        recommend.recommend(ITEMS, {}, "warlock", role="dps")


def test_variants_share_one_line(aegis):
    write_ratings(aegis)
    items = [w("20", "Adamantite (Timelost)", location="Warlock", equipped=True), w("21", "Adamantite")]
    assert [x.split(" | ")[2] for x in recommend.recommend(items, {}, "warlock")["picks"]] == ["Adamantite (Timelost)"]


def test_long_dps_warning_is_capped(aegis):
    write_dps(aegis)
    items = [w(str(i), f"Gun {i:02}") for i in range(12)]
    assert recommend.recommend(items, {}, "warlock", role="dps")["warnings"] == [
        "no Aegis DPS row for: " + ", ".join(f"Gun {i:02}" for i in range(10)) + " … and 2 more"]
