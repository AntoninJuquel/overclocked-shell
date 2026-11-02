import pytest

from shell.sources.compendium import lookup

MODS = """# Armor Mods

Source: Destiny Data Compendium, tab "Armor Mods", fetched on 2026-10-28.

## Helmet

### Ammo Finder
- energy: 3

Multiplier.

### Notes
Helmet remarks.

## Legs

### Ammo Finder
- energy: 1

### Spirit of the Inmost Light
Perk.
"""


@pytest.fixture
def cached(tmp_path, monkeypatch):
    from shell.core import paths
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path)
    (tmp_path / "compendium").mkdir()
    (tmp_path / "compendium" / "armor-mods.md").write_text(MODS, encoding="utf-8")
    (tmp_path / "compendium" / "index.md").write_text("### Ammo Finder\n", encoding="utf-8")


def test_every_copy_of_a_name_with_its_section(cached):
    found = lookup.find("ammo finder")["matches"]
    assert [(e["file"], e["section"], e["fetched"]) for e in found] == [
        ("armor-mods", "Helmet", "2026-10-28"), ("armor-mods", "Legs", "2026-10-28")]
    assert found[0]["text"] == "- energy: 3\n\nMultiplier."


def test_small_words_and_spelling_do_not_matter(cached):
    assert lookup.find("Spirit of Inmost Light")["matches"][0]["name"] == "Spirit of the Inmost Light"
    assert lookup.find("inmost")["matches"][0]["name"] == "Spirit of the Inmost Light"
    assert lookup.find("Amo Finder")["suggestions"] == ["Ammo Finder"]


def test_entry_named_after_part_of_the_name_is_flagged(cached):
    assert lookup.find("Ammo Finder")["partial"] is False
    out = lookup.find("Heavy Ammo Finder Plus")
    assert out["partial"] is True and {e["name"] for e in out["matches"]} == {"Ammo Finder"}
    out = lookup.find("Nothing Like It")
    assert out["partial"] is False and out["matches"] == []


def test_file_limit_and_more(cached):
    assert lookup.find("Notes", file="armor-mods")["matches"][0]["text"] == "Helmet remarks."
    assert lookup.find("Ammo Finder", file="other")["matches"] == []
    out = lookup.find("Ammo Finder", limit=1)
    assert len(out["matches"]) == 1 and out["more"] == 1
