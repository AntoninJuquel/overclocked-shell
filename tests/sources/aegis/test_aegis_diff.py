import json

from shell.sources.aegis import diff

OLD = [{"_name": "Kindled Orchid", "Tier": "A", "#": "4"}, {"_name": "Zaouli's Bane", "Tier": "A", "#": "6"},
       {"_name": "Zaouli's Bane", "Tier": "B", "#": "7"}, {"_name": "Gone", "Tier": "C", "#": "9"}]
NEW = [{"_name": "Kindled Orchid", "Tier": "S", "#": "1"}, {"_name": "Zaouli's Bane", "Tier": "A", "#": "6"},
       {"_name": "Zaouli's Bane", "Tier": "B", "#": "7"}, {"_name": "Fresh", "Tier": "B", "#": "8"}]


def test_changes():
    got = diff.changes(OLD, NEW, "Tier", "#")
    assert {"name": "Kindled Orchid", "kind": "tier", "col": "Tier", "old": "A", "new": "S"} in got
    assert {"name": "Kindled Orchid", "kind": "rank", "col": "#", "old": "4", "new": "1"} in got
    assert {"name": "Fresh", "kind": "added", "col": "Tier", "old": None, "new": "B"} in got
    assert {"name": "Gone", "kind": "removed", "col": "Tier", "old": "C", "new": None} in got
    assert len(got) == 4                               # both Zaouli's Bane matched in order


def test_changes_without_tier_column():
    assert diff.changes([{"_name": "A", "DPS": "1"}], [{"_name": "A", "DPS": "2"}, {"_name": "B"}], None, None) == [
        {"name": "B", "kind": "added", "col": None, "old": None, "new": None}]


def test_build_names_and_concerned(tmp_path):
    sheet = {"name": "T", "class": "Warlock",
             "subclass": {"element": "Arc", "aspects": ["Electrostatic Mind"], "fragments": ["Spark of Shock"]},
             "intent": {"exotic": {"name": "Getaway Artist"}, "sets": [{"set": "Smoke Jumper Set", "pieces": 2}],
                        "artifact": {"name": "X", "perks": ["Amped Up"]},
                        "weapons": [{"slot": "Power", "wanted": "Bait and Switch + Cluster Bomb"}]},
             "resolved": {"weapons": [{"slot": "Energy", "itemId": "1", "name": "Kindled Orchid"}]}}
    (tmp_path / "arc.json").write_text(json.dumps(sheet), encoding="utf-8")
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    names = diff.build_names(tmp_path)
    assert set(names) == {"arc"}
    assert diff.concerned("Kindled Orchid", names) == ["arc"]
    assert diff.concerned("Smoke Jumper", names) == ["arc"]
    assert diff.concerned("Cluster Bomb", names) == ["arc"]          # cited in `wanted`
    assert diff.concerned("Luster", names) == []                      # never inside a word
    assert diff.concerned("Spark of Shock", names) == ["arc"]
    assert diff.concerned("Ace of Spades", names) == []


def test_concerned_weapon_variant(tmp_path):
    sheet = {"resolved": {"weapons": [{"slot": "Kinetic", "name": "Hezen Vengeance (Timelost)"}]}}
    (tmp_path / "v.json").write_text(json.dumps(sheet), encoding="utf-8")
    assert diff.concerned("Hezen Vengeance", diff.build_names(tmp_path)) == ["v"]


def test_build_names_skips_malformed(tmp_path):
    (tmp_path / "list.json").write_text("[1, 2]", encoding="utf-8")
    (tmp_path / "nulls.json").write_text(json.dumps(
        {"subclass": {"aspects": None, "fragments": None}, "intent": {"sets": None, "weapons": None,
         "artifact": {"perks": None}, "exotic": None}, "resolved": {"weapons": None}}), encoding="utf-8")
    (tmp_path / "ok.json").write_text(json.dumps({"subclass": {"aspects": ["Knockout"]}}), encoding="utf-8")
    names = diff.build_names(tmp_path)
    assert set(names) == {"nulls", "ok"}
    assert diff.concerned("Knockout", names) == ["ok"]


def test_describe_rank():
    assert diff.describe({"kind": "rank", "col": "#", "old": "4", "new": "1"}) == "#4 → #1"
    assert diff.describe({"kind": "rank", "col": "#", "old": None, "new": "1"}) == "— → #1"


def test_render_changes():
    entries = [{"sheet": "Endgame Analysis", "tab": "HCs", "name": "Kindled Orchid", "kind": "tier", "col": "Tier",
                "old": "A", "new": "S", "builds": ["arc"]},
               {"sheet": "Endgame Analysis", "tab": "HCs", "name": "Fresh", "kind": "added", "col": "Tier",
                "old": None, "new": "B", "builds": []},
               {"sheet": "Boss Damage", "tab": "Swap", "name": "Old", "kind": "removed", "col": None,
                "old": None, "new": None, "builds": []}]
    md = diff.render_changes(entries, "2026-10-09")
    assert md.startswith("# Aegis changes on 2026-10-09\n")
    assert "## Builds concerned\n\n- arc: HCs — Kindled Orchid: Tier A → S\n" in md
    assert "### Endgame Analysis — HCs\n\n- Kindled Orchid: Tier A → S\n- Fresh: new (Tier B)\n" in md
    assert "### Boss Damage — Swap\n\n- Old: removed\n" in md
    assert "No changes." in diff.render_changes([], "2026-10-09")
    assert "None.\n" in diff.render_changes(entries[1:], "2026-10-09")


def test_build_names_skips_scratch_sheets(tmp_path):
    (tmp_path / "bravery.json").write_text(json.dumps({"scratch": True, "subclass": {"aspects": ["Knockout"]}}),
                                           encoding="utf-8")
    assert diff.build_names(tmp_path) == {}
