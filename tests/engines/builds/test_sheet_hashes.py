import copy

from shell.engines.builds import sheet_hashes
from tests.engines.test_build_icons import PERKS, SETS, STATS, fixture
from tests.engines.test_share import SHEET, SOCKET_TYPES


def run(s):
    s = copy.deepcopy(s)
    defs = {h: {**d, "hash": int(h)} for h, d in fixture().items()}
    stats = {h: {**d, "hash": int(h)} for h, d in STATS.items()}
    sets = {h: {**d, "hash": int(h)} for h, d in SETS.items()}
    return s, sheet_hashes.fill(s, defs, SOCKET_TYPES, stats, sets, PERKS, {})


def test_every_kind_of_name():
    s, problems = run({**SHEET, "intent": {**SHEET["intent"], "weapons": [
        {"slot": "Kinetic", "items": ["DECATUR 02"], "mods": ["Physic"]}], "armor_mods_fill": {"Helmet": ["Firepower"]}}})
    table = s["hashes"]
    assert table["item:Getaway Artist"] == 50 and table["plug:Storm Grenade"] == 12
    assert table["mod:Ashes to Assets"] == 20 and table["mod:Firepower"] == 24          # the base copy; the filler too
    assert table["artifact:Shieldcrush"] == 62 and table["stat:Grenade"] == 1735777505
    assert table["set:Great Hunt"] == 7 and table["setperk:Taken Barrier"] == 71
    assert problems == ["Kinetic: Physic is not an option of DECATUR 02"]
    assert table["item:DECATUR 02"] == 2001


def test_resolved_names_too():
    s, _ = run(SHEET)
    table = s["hashes"]
    assert table["item:Hood"] == 1001 and table["item:DECATUR 02"] == 2001 and table["perk:Physic"] == 60
    assert table["mod:Grenade Mod"] == 22 and table["mod:Balanced Tuning"] == 23


def test_rebuilt_each_time():
    s, _ = run({**SHEET, "hashes": {"item:Gone": 1}})
    assert "item:Gone" not in s["hashes"]


def test_links_only_for_what_has_a_page():
    assert sheet_hashes.links({"item:A": 1, "perk:B": 2, "stat:C": 3, "set:D": 4, "setperk:E": 5}, "u/{lang}/{hash}", "fr") == {
        "item:A": "u/fr/1", "perk:B": "u/fr/2"}
