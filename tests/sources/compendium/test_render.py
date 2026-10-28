from shell.sources.compendium.model import Entry, TabResult
from shell.sources.compendium.render import read_meta, render_index, render_tab


def test_render_tab_groups_sections_and_escapes_titles():
    entries = [
        Entry("Assassin's Cowl", "Hunter", {"perk": "Vanishing Execution"}, "On Finisher:\nInvisibility."),
        Entry("Abeyant Leap", "Titan", {}, "# not a heading"),
        Entry("Athrys's Embrace", "Hunter", {}, ""),
    ]
    md = render_tab("Exotic Armors", entries, "2026-10-07", hidden_rows=3)
    assert md == (
        "# Exotic Armors\n\n"
        'Source: Destiny Data Compendium, tab "Exotic Armors", fetched on 2026-10-07.\n'
        "Rows hidden by the author (missing from this version): 3.\n\n"
        "## Hunter\n\n"
        "### Assassin's Cowl\n"
        "- section: Hunter\n"
        "- perk: Vanishing Execution\n\n"
        "On Finisher:\nInvisibility.\n\n"
        "### Athrys's Embrace\n"
        "- section: Hunter\n\n"
        "## Titan\n\n"
        "### Abeyant Leap\n"
        "- section: Titan\n\n"
        "\\# not a heading\n"
    )


def test_read_meta_roundtrip():
    md = render_tab("Arc", [Entry("A", "S"), Entry("B", "S")], "2026-10-01", hidden_rows=2)
    assert read_meta(md) == ("2026-10-01", 2, 2)
    assert read_meta("nothing") == (None, 0, 0)


def test_render_index():
    results = [
        TabResult("Exotic Armors", "exotic-armors", 140, "2026-10-07"),
        TabResult("Game Mechanics", "game-mechanics", 120, "2026-10-07", hidden_rows=57),
        TabResult("Solar", "subclass-solar", 66, "2026-10-07", hidden_rows=1),
        TabResult("Arc", "subclass-arc", 80, "2026-10-01", ok=False, note='Arc: anchor not found: "Glossary"'),
        TabResult("Void", "subclass-void", 0, None, ok=False, note="not fetched yet"),
    ]
    md = render_index(results, "https://sheet", "2026-10-07")
    assert "Source: https://sheet" in md and "Last run: 2026-10-07" in md
    assert "Oldest data: 2026-10-01" in md  # Void (no data) ignored
    assert "| Exotic Armors | [exotic-armors.md](exotic-armors.md) | 140 | ok |" in md
    assert "| Game Mechanics | [game-mechanics.md](game-mechanics.md) | 120 | ok · 57 hidden rows |" in md
    assert "| Solar | [subclass-solar.md](subclass-solar.md) | 66 | ok · 1 hidden row |" in md
    assert ('| Arc | [subclass-arc.md](subclass-arc.md) | 80 | ⚠ Arc: anchor not found: "Glossary" '
            "— data from 2026-10-01 |") in md
    assert "| Void | subclass-void.md | 0 | ⚠ not fetched yet — no data |" in md


def test_escape_setext_hr_and_indented_headings():
    md = render_tab("T", [Entry("A", "S", {}, "-----\n  ### x\n=== \nnormal - text\n- item")], "2026-10-07")
    assert "\n\\-----\n" in md
    assert "\n  \\### x\n" in md
    assert "\n\\=== \n" in md
    assert "normal - text\n- item\n" in md


def test_attr_values_newlines_flattened():
    md = render_tab("T", [Entry("A", "S", {"k": "a\nb"})], "2026-10-07")
    assert "- k: a / b\n" in md


def test_read_meta_ignores_body_text():
    e = Entry("A", "S", {}, "fetched on 1999-01-01\nmissing from this version): 9")
    assert read_meta(render_tab("T", [e], "2026-10-07")) == ("2026-10-07", 1, 0)


def test_index_hint_mentions_sections():
    md = render_index([], "s", "2026-10-07")
    assert '-e "^## " -e "^### <name>"' in md and "several sections" in md
    assert "also repeat within one section" in md and "other attributes" in md


def test_index_without_any_data_has_no_oldest_date():
    md = render_index([TabResult("Void", "subclass-void", 0, None, ok=False, note="x")], "s", "2026-10-07")
    assert "Last run: 2026-10-07" in md and "Oldest data: none" in md
