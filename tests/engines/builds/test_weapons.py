import json

from shell.engines.builds import weapons
from tests.sources.aegis.conftest import write_aegis


def opt(name, can_insert, enhanced=False):
    return {"name": name, "hash": 1, "enhanced": enhanced, "canInsert": can_insert}


def w(item_id, name, slot="Kinetic", element="Strand", type_="Auto Rifle", rarity="Legendary", frame="Support Frame"):
    return {"itemId": item_id, "name": name, "slot": slot, "element": element, "type": type_, "rarity": rarity,
            "frame": frame, "locked": True, "location": "Vault",
            "columns": [{"label": "Barrel", "selected": "Arrowhead Brake",
                         "options": [opt("Arrowhead Brake", True), opt("Corkscrew Rifling", True)]},
                        {"label": "Trait", "selected": "Reciprocity", "options": [
                            opt("Reciprocity", True), opt("Rampage", True), opt("Kill Clip", False)]},
                        {"label": "Trait", "selected": "Circle of Life", "options": [opt("Circle of Life", True)]},
                        {"label": "Origin Trait", "selected": "Willing Vessel",
                         "options": [opt("Willing Vessel", True)]},
                        {"label": "Intrinsic", "selected": "Precision Frame",
                         "options": [opt("Precision Frame", True)]}]}


ITEMS = [w("1", "Adamantite"), w("2", "Ahab Char", slot="Energy", element="Solar"),
         w("3", "Ergo Sum", slot="Energy", element="Arc", type_="Sword", rarity="Exotic", frame="Wolfpack Rounds")]
EMPTY = {"itemId": "4", "name": "Bare", "slot": "Power", "element": "Kinetic", "type": "Rocket Launcher",
         "rarity": "Exotic", "frame": "", "ammo": "Heavy", "locked": False, "location": "Vault", "columns": []}


def test_filters():
    assert [x["itemId"] for x in weapons.select(ITEMS, slot="Energy")] == ["2", "3"]
    assert [x["itemId"] for x in weapons.select(ITEMS, element="arc")] == ["3"]
    assert [x["itemId"] for x in weapons.select(ITEMS, type_="auto")] == ["1", "2"]
    assert [x["itemId"] for x in weapons.select(ITEMS, name="ERGO")] == ["3"]


def test_grades_join_and_order(isolated_dirs):
    folder = isolated_dirs / "profile" / "triage"
    folder.mkdir(parents=True)
    (folder / "weapons.json").write_text(json.dumps({"items": [
        {"itemId": "2", "name": "Ahab Char", "grade": "god roll PvE"}, {"itemId": "1", "name": "Adamantite", "grade": ""},
        {"itemId": "5", "name": "Old"}]}), encoding="utf-8")
    grades = weapons.load_grades()
    assert grades == {"2": "god roll PvE"}
    rows = weapons.select(ITEMS, grades=grades)
    assert rows[0]["itemId"] == "2"          # graded weapons first


def test_missing_grades_file():
    assert weapons.load_grades() == {}


def test_format_line():
    line = weapons.fmt(ITEMS[2], {})
    assert line.startswith("3 | Ergo Sum | Sword | Arc | Energy |")
    assert "Wolfpack Rounds" in line and "grade —" in line
    perks = weapons.fmt(ITEMS[0], {})
    assert "Reciprocity [Rampage], Circle of Life, Willing Vessel, Precision Frame" in perks
    assert "Arrowhead" not in perks and "Kill Clip" not in perks
    assert " | Support Frame | " in perks          # frame always shown, even for a legendary


def test_format_enhanced_flags_and_empty():
    it = w("9", "Enh")
    it["columns"][1]["options"][0]["enhanced"] = True
    it["equipped"] = True
    it["crafted"] = True
    line = weapons.fmt(it, {})
    assert "Reciprocity* [Rampage]" in line
    assert "equipped" in line and "crafted" in line
    assert "equipped" not in weapons.fmt(ITEMS[0], {}) and "crafted" not in weapons.fmt(ITEMS[0], {})
    bare = weapons.fmt(EMPTY, {})
    assert "Heavy" in bare and "unlocked" in bare
    assert weapons.fmt(ITEMS[2], {}).count("Wolfpack Rounds") == 1


def test_perk_filter():
    ids = lambda **kw: [x["itemId"] for x in weapons.select(ITEMS, **kw)]  # noqa: E731
    assert ids(perk="rampage") == ["1", "2", "3"]          # alternative of a column
    assert ids(perk="WOLFPACK") == ["3"]                    # frame
    assert ids(perk="corkscrew") == []                      # barrel option: column not shown
    assert ids(perk="nothing") == []


def test_grade_ordering():
    items = [w("1", "Zeta"), w("2", "Alpha"), w("3", "Mid"), w("4", "Nope"), w("5", "Beta"), w("6", "Gamma")]
    grades = {"1": "A #20", "2": "B #3", "3": "A #5", "5": "S", "6": "god roll"}
    got = [x["itemId"] for x in weapons.select(items, grades=grades)]
    assert got == ["5", "3", "1", "2", "6", "4"]
    rev = [w("1", "Zeta"), w("2", "Alpha")]
    assert [x["itemId"] for x in weapons.select(rev, grades={"1": "A", "2": "A"})] == ["2", "1"]


def test_candidates_overflow_and_empty():
    lines = weapons.candidates(ITEMS, {}, limit=2)
    assert len(lines) == 3 and lines[-1].startswith("… 1 more ")
    assert weapons.candidates(ITEMS, {}, limit=1)[-1].startswith("… 2 more ")
    assert weapons.candidates(ITEMS, {}, name="zzz") == ["no matching weapon"]
    assert weapons.candidates(ITEMS, {}, slot="energy", element="ARC")[0].startswith("3 | Ergo Sum")


def test_wishlist_perks_cites_and_full_roll():
    item = {**w("1", "Adamantite"), "itemHash": 10}
    rolls = {10: [frozenset({"rampage", "kill clip", "enhanced-only"}), frozenset({"reciprocity", "circle of life"})]}
    cited, full = weapons.wishlist_perks(item, rolls, {})
    assert {"rampage", "reciprocity"} <= cited and full
    # fallback by name (reissue with another hash), no full roll
    cited, full = weapons.wishlist_perks({**item, "itemHash": 99}, {11: [frozenset({"rampage", "x"})]},
                                         {"adamantite": [11]})
    assert cited == {"rampage", "x"} and not full


def test_wishlist_index_from_the_cached_list(isolated_dirs, monkeypatch):
    from shell.sources import wishlists
    path = isolated_dirs / "w.txt"
    path.write_text("//Adamantite\ndimwishlist:item=10&perks=7,8\n", encoding="utf-8")
    monkeypatch.setattr(wishlists, "fetch", lambda source, force=False: (path, False))
    rolls, by_name = weapons.load_wishlist_index({"7": "Rampage", "8": "Enhanced Kill Clip"})
    assert rolls[10] == [frozenset({"rampage", "kill clip"})] and by_name == {"adamantite": [10]}

    def offline(source, force=False):
        raise OSError("offline")

    monkeypatch.setattr(wishlists, "fetch", offline)
    assert weapons.load_wishlist_index({}) == (None, None)


def test_detail_lists_every_column_with_marks():
    item = {**w("1", "Adamantite"), "gearTier": 5, "mod": "", "masterwork": "Tier 4: Range"}
    lines = weapons.detail(item, {"1": "S #1"}, ({"rampage"}, False))
    assert lines[0] == ("Adamantite | 1 | Auto Rifle | Strand | Kinetic | tier 5 | grade S #1 | mod: — | "
                        "no full wishlist roll | Tier 4: Range")
    assert lines[1] == "  Barrel: Arrowhead Brake (selected) / Corkscrew Rifling"
    assert lines[2] == "  Trait: Reciprocity (selected) / Rampage ✓ / Kill Clip (not insertable)"
    assert weapons.detail(item, {})[-1].startswith("  (wishlist unavailable")


def test_aegis_tier_in_list_and_detail(aegis_dir):
    write_aegis(aegis_dir, "endgame", "weapons-autos", [
        {"_name": "Adamantite", "Name": "Adamantite", "Perk 1": "Reciprocity\nRampage", "Perk 2": "Circle of Life",
         "MW": "Range\nHandling", "Notes": "solid\nsupport", "#": "2", "Tier": "A"},
        {"_name": "Adamantite", "Name": "Adamantite\nold version", "Perk 1": "Kill Clip", "#": "9", "Tier": "C"}],
        tab="Autos")
    assert "| grade — | aegis A #2+ |" in weapons.fmt(ITEMS[0], {})
    assert "| aegis — |" in weapons.fmt(ITEMS[1], {})
    item = {**ITEMS[0], "gearTier": 5, "mod": "", "masterwork": ""}
    lines = weapons.detail(item, {}, (set(), False))
    assert lines[0].endswith("| Aegis A #2 (Autos)")
    assert lines[2] == "  Trait: Reciprocity A (selected) / Rampage A / Kill Clip A (not insertable)"
    assert lines[-2:] == ["  Aegis A #2 (Autos): MW Range / Handling · solid / support",
                          "  Aegis C #9 (Autos, old version): MW — · —"]


def test_aegis_absent_keeps_detail_unchanged(aegis_dir):
    item = {**ITEMS[0], "gearTier": 5, "mod": "", "masterwork": ""}
    lines = weapons.detail(item, {}, (set(), False))
    assert "Aegis" not in lines[0] and not any(" A " in line or line.endswith(" A") for line in lines)
