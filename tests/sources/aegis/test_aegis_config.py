from shell.sources.aegis import config
from shell.sources.aegis.names import first_line, norm, strip_set


def test_names():
    assert first_line("Zaouli's Bane\nPantheon version") == "Zaouli's Bane"
    assert first_line("") == "" and first_line(None) == ""
    assert norm("  Zaouli’s   Bane \nPantheon version") == "zaouli's bane"
    assert norm("Hezen Vengeance (Timelost)") == "hezen vengeance"
    assert norm("Vex Mythoclast (Adept)") == "vex mythoclast"
    assert strip_set("smoke jumper set") == "smoke jumper" and strip_set("promised") == "promised"


def test_specs_match_names_and_patterns():
    boss = config.SHEETS["boss"]
    assert boss.spec_for("Fireteam (S29)").slug == "fireteam"
    assert boss.spec_for("fireteam (s31)").slug == "fireteam"
    assert boss.spec_for("Abilties").slug == "abilities"
    assert boss.spec_for("Graphing (S29)") is None and boss.is_ignored("Graphing (S29)")
    endgame = config.SHEETS["endgame"]
    assert endgame.spec_for("HCs").weapon_type == "Hand Cannon"
    assert endgame.is_ignored("Exotic Armor (ignore)") and endgame.is_ignored("Changelog")
    assert not endgame.is_ignored("HCs")


def test_slugs_are_unique_and_status_first():
    for sheet in config.SHEETS.values():
        slugs = [t.slug for t in sheet.tabs]
        assert len(slugs) == len(set(slugs))
    assert config.SHEETS["endgame"].tabs[0].slug == "status"


def test_weapon_tabs():
    tabs = config.weapon_tabs()
    assert len(tabs) == 20 and all(t.slug.startswith("weapons-") for t in tabs)
    assert {t.weapon_type for t in tabs if t.weapon_type} >= {"Rocket Launcher", "Sword", "Combat Bow"}
