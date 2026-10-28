import pytest

from shell.engines.builds import stats


def test_parse_simple_and_multi():
    assert stats.parse_stats("+10 Health", "Warlock") == {"Health": 10}
    assert stats.parse_stats("+10 Health · +10 Super", "Hunter") == {"Health": 10, "Super": 10}


def test_parse_class_specific_and_typo():
    text = "-10 Weapons (Hunter) · -10 Health (Titan) · -10 Class (Warlock)"
    assert stats.parse_stats(text, "Warlock") == {"Class": -10}
    assert stats.parse_stats(text, "Hunter") == {"Weapons": -10}
    assert stats.parse_stats("+10 Weapon · +10 Super", "Titan") == {"Weapons": 10, "Super": 10}


def test_parse_rejects_garbage():
    with pytest.raises(ValueError, match="unreadable"):
        stats.parse_stats("lots of Health", "Titan")


FRAGMENTS_MD = """# Arc

## Fragments

### Shock
- section: Fragments

Text.

### Magnitude
- section: Fragments
- stats: -10 Grenade

### Focus
- section: Fragments
- stats: -10 Weapons (Hunter) · -10 Health (Titan) · -10 Class (Warlock)

## Warlock — Aspects

### Magnitude
- section: Warlock — Aspects
- stats: +99 Super
"""


def test_fragment_stats(tmp_path):
    (tmp_path / "subclass-arc.md").write_text(FRAGMENTS_MD, encoding="utf-8")
    got = stats.fragment_stats(["Spark of Shock", "Spark of Magnitude", "Focus"], "Arc", "Warlock", tmp_path)
    assert got == {"Grenade": -10, "Class": -10}


def test_fragment_in_game_names_and_short_names(tmp_path):
    (tmp_path / "subclass-arc.md").write_text(FRAGMENTS_MD, encoding="utf-8")
    expected = {"Grenade": -10, "Class": -10}
    assert stats.fragment_stats(["spark of Magnitude", "Focus"], "Arc", "Warlock", tmp_path) == expected
    assert stats.fragment_stats(["Magnitude", "Focus"], "Arc", "Warlock", tmp_path) == expected
    assert stats.fragment_stats(["Shock"], "Arc", "Warlock", tmp_path) == {}


def test_duplicate_after_normalisation(tmp_path):
    (tmp_path / "subclass-arc.md").write_text(FRAGMENTS_MD, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        stats.fragment_stats(["Spark of Focus", "Focus"], "Arc", "Warlock", tmp_path)


def test_fragment_missing(tmp_path):
    (tmp_path / "subclass-arc.md").write_text(FRAGMENTS_MD, encoding="utf-8")
    with pytest.raises(ValueError, match="Spark of Nowhere"):
        stats.fragment_stats(["Spark of Nowhere"], "Arc", "Warlock", tmp_path)


def test_compendium_absent(tmp_path):
    with pytest.raises(ValueError, match="refresh_references"):
        stats.fragment_stats(["Focus"], "Arc", "Warlock", tmp_path)


def test_default_compendium_is_cache_compendium(isolated_dirs):
    folder = isolated_dirs / "cache" / "compendium"
    folder.mkdir(parents=True)
    (folder / "subclass-arc.md").write_text(FRAGMENTS_MD, encoding="utf-8")
    assert stats.fragment_stats(["Magnitude"], "Arc", "Warlock") == {"Grenade": -10}


def test_entries_ignore_body_lines(tmp_path):
    md = "### Focus\n- section: Fragments\n\n- stats: +50 Health\n\n## Other\n- stats: +1 Super\n"
    (tmp_path / "subclass-arc.md").write_text(md, encoding="utf-8")
    assert stats.fragment_stats(["Focus"], "Arc", "Warlock", tmp_path) == {}


def test_entries_split_on_first_colon(tmp_path):
    path = tmp_path / "x.md"
    path.write_text("### A\n- detail: Grants: more damage\n- key:no space\n", encoding="utf-8")
    assert stats.entries(path) == [("A", {"detail": "Grants: more damage"})]


def test_parse_unknown_class():
    with pytest.raises(ValueError, match="class"):
        stats.parse_stats("+10 Health", "Warlok")
    with pytest.raises(ValueError, match="class"):
        stats.parse_stats("+10 Health (Warlok)", "Warlock")


def test_parse_unknown_stat():
    with pytest.raises(ValueError, match="unreadable"):
        stats.parse_stats("+10 Healths", "Titan")


def test_unknown_element(tmp_path):
    with pytest.raises(ValueError, match="Kinetic"):
        stats.fragment_stats(["Focus"], "Kinetic", "Warlock", tmp_path)


def test_duplicate_fragment(tmp_path):
    (tmp_path / "subclass-arc.md").write_text(FRAGMENTS_MD, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        stats.fragment_stats(["Focus", "Focus"], "Arc", "Warlock", tmp_path)


def test_zero_totals_dropped_and_mixed_signs(tmp_path):
    md = (
        "### A\n- section: Fragments\n- stats: +10 Health · +20 Super\n\n"
        "### B\n- section: Fragments\n- stats: -10 Health · -10 Super\n"
    )
    (tmp_path / "subclass-arc.md").write_text(md, encoding="utf-8")
    assert stats.fragment_stats(["A", "B"], "Arc", "Warlock", tmp_path) == {"Super": 10}


def test_archetypes_are_distinct_stat_pairs():
    from shell.engines.builds.stats import ARCHETYPES, STATS
    assert len(ARCHETYPES) == 12
    pairs = list(ARCHETYPES.values())
    assert len(set(pairs)) == 12
    for primary, secondary in pairs:
        assert primary in STATS and secondary in STATS and primary != secondary
    assert ARCHETYPES["Demolitionist"] == ("Grenade", "Class")
