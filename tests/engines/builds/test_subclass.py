import pytest

from shell.engines.builds import subclass
from tests.sources.aegis.conftest import write_aegis


def plug(name, category, cap=None, cost=None):
    p = {"plugCategoryIdentifier": category}
    if cap is not None:
        p["energyCapacity"] = {"capacityValue": cap}
    if cost is not None:
        p["energyCost"] = {"energyCost": cost}
    return {"displayProperties": {"name": name}, "plug": p}


DEFS = {
    "1": plug("Empty Aspect Socket", "warlock.arc.aspects"),
    "2": plug("Arc Soul", "warlock.arc.aspects", cap=2),
    "3": plug("Lightning Surge", "warlock.arc.aspects", cap=3),
    "4": plug("Flow State", "hunter.arc.aspects", cap=2),
    "5": plug("Bleak Watcher", "warlock.stasis.totems", cap=2),
    "6": plug("Lightning Surge", "warlock.prism.aspects", cap=3),
    "7": plug("Empty Fragment Socket", "shared.arc.fragments"),
    "8": plug("Spark of Shock", "shared.arc.fragments", cost=1),
    "9": plug("Spark of Volts", "shared.arc.fragments", cost=1),
    "10": plug("Spark of Focus", "shared.arc.fragments", cost=1),
    "11": plug("Spark of Ions", "shared.arc.fragments", cost=1),
    "12": plug("Spark of Beacons", "shared.arc.fragments", cost=1),
    "13": plug("Spark of Haste", "shared.arc.fragments", cost=1),
    "14": plug("Whisper of Chains", "shared.stasis.trinkets", cost=1),
    "15": plug("Facet of Awakening", "shared.prism.fragments", cost=1),
    "16": plug("Grenade Mod", "enhancements.v2_general", cost=3),
    "20": {"displayProperties": {"name": "Stormcaller"}, "itemType": 16, "classType": 2,
           "sockets": {"socketEntries": [{"singleInitialItemHash": 21}, {"singleInitialItemHash": 1},
                                         {"singleInitialItemHash": 7}, {"singleInitialItemHash": 7},
                                         {"singleInitialItemHash": 0}, {"singleInitialItemHash": 7}]}},
    "21": plug("Stormtrance", "warlock.arc.supers"),
    "22": {"displayProperties": {"name": "Shadebinder"}, "itemType": 16, "classType": 2,
           "sockets": {"socketEntries": [{"singleInitialItemHash": 23}, {"singleInitialItemHash": 24},
                                         {"singleInitialItemHash": 24}]}},
    "23": plug("Winter's Wrath", "warlock.stasis.supers"),
    "24": plug("Empty Fragment Socket", "shared.fragments"),
}

DEFS2 = dict(DEFS)
DEFS2.update({
    "20": plug("Weaver's Call", "warlock.strand.aspects", cap=2),
    "21": plug("Weaver's Call", "warlock.prism.aspects", cap=3),
    "22": plug("Spark of Nothing", "shared.arc.fragments"),          # no energyCost: ignored
    "24": plug("Facet of Honor", "shared.prism.fragments", cost=1),
    "25": plug("Elemental Well", "warlock.arc.aspects", cap=2),
})

DEFS3 = dict(DEFS2)
DEFS3.update({
    "30": plug("Stormtrance", "warlock.arc.supers"),
    "31": plug("Chaos Reach", "warlock.arc.supers"),
    "32": plug("Storm Grenade", "shared.arc.grenades"),
    "33": plug("Chain Lightning", "warlock.arc.melee"),
    "34": plug("Healing Rift", "warlock.arc.class_abilities"),
    "35": plug("Burst Glide", "warlock.arc.movement"),
    "36": plug("Freezing Singularity", "warlock.prism.prism_grenade"),
    "37": plug("Hailfire Spike", "hunter.prism.prism_grenade"),
    "38": plug("Empty Super Socket", "warlock.arc.supers"),
})


@pytest.fixture
def compendium(isolated_dirs):
    """An (empty) subclass-arc.md, so list_text reaches fragment_stats (monkeypatched by the tests)."""
    folder = isolated_dirs / "cache" / "compendium"
    folder.mkdir(parents=True)
    (folder / "subclass-arc.md").write_text("", encoding="utf-8")
    return folder


def test_index():
    idx = subclass.build_index(DEFS)
    assert idx["Arc"]["aspects"]["Warlock"] == {"Arc Soul": 2, "Lightning Surge": 3}
    assert idx["Arc"]["aspects"]["Hunter"] == {"Flow State": 2}
    assert idx["Stasis"]["aspects"]["Warlock"] == {"Bleak Watcher": 2}
    assert idx["Prismatic"]["aspects"]["Warlock"] == {"Lightning Surge": 3}
    assert idx["Arc"]["fragments"] == {"Spark of Shock", "Spark of Volts", "Spark of Focus", "Spark of Ions",
                                       "Spark of Beacons", "Spark of Haste"}
    assert idx["Stasis"]["fragments"] == {"Whisper of Chains"}
    assert idx["Prismatic"]["fragments"] == {"Facet of Awakening"}
    assert idx["Solar"]["fragments"] == set()
    assert idx["Arc"]["fragment_sockets"] == {"Warlock": [2, 3, 5]}
    assert idx["Stasis"]["fragment_sockets"] == {"Warlock": [1, 2]}
    assert idx["Solar"]["fragment_sockets"] == {}


def test_index_slots_per_element_and_cost_filter():
    idx = subclass.build_index(DEFS2)
    assert idx["Strand"]["aspects"]["Warlock"]["Weaver's Call"] == 2
    assert idx["Prismatic"]["aspects"]["Warlock"]["Weaver's Call"] == 3
    assert "Spark of Nothing" not in idx["Arc"]["fragments"]


def test_index_abilities():
    idx = subclass.build_index(DEFS3)
    ab = idx["Arc"]["abilities"]
    assert ab["Warlock"]["super"] == {"Stormtrance", "Chaos Reach"}
    assert ab["Warlock"]["grenade"] == ab["Hunter"]["grenade"] == {"Storm Grenade"}   # shared grenades
    assert ab["Warlock"]["melee"] == {"Chain Lightning"} and ab["Hunter"]["melee"] == set()
    assert ab["Warlock"]["class"] == {"Healing Rift"} and ab["Warlock"]["jump"] == {"Burst Glide"}
    prism = idx["Prismatic"]["abilities"]
    assert prism["Warlock"]["grenade"] == {"Freezing Singularity"}
    assert prism["Hunter"]["grenade"] == {"Hailfire Spike"}


def sheet(aspects, fragments, cls="Warlock", element="Arc"):
    return {"class": cls, "subclass": {"element": element, "aspects": aspects, "fragments": fragments}}


def test_check_ok():
    idx = subclass.build_index(DEFS)
    s = sheet(["Arc Soul", "Lightning Surge"], ["Spark of Shock", "Spark of Volts", "Spark of Focus",
                                                "Spark of Ions", "Spark of Beacons"])
    assert subclass.check(s, idx) == []


@pytest.mark.parametrize("aspects,fragments,expected", [
    (["Arc Soul", "Flow State"], [], "unknown aspect for Warlock Arc: Flow State"),
    (["Arc Soul", "Lightning Surge", "Arc Soul"], [], "3 aspects (at most 2)"),
    (["Arc Soul", "Arc Soul"], [], "duplicate aspect: Arc Soul"),
    (["Arc Soul"], ["Spark of Shock", "Spark of Volts", "Spark of Ions"], "3 fragments for 2 slots"),
    (["Arc Soul"], ["Spark of Nowhere"], "unknown fragment for Arc: Spark of Nowhere"),
    (["Arc Soul"], ["Spark of Shock", "Spark of Shock"], "duplicate fragment: Spark of Shock"),
])
def test_check_problems(aspects, fragments, expected):
    idx = subclass.build_index(DEFS)
    assert expected in subclass.check(sheet(aspects, fragments), idx)


def test_list_text(monkeypatch, compendium):
    idx = subclass.build_index(DEFS)
    monkeypatch.setattr(subclass, "fragment_stats",
                        lambda names, element, cls: {"Grenade": -10} if names == ["Spark of Shock"] else {})
    text = subclass.list_text(idx, "Warlock", "Arc")
    assert "- Lightning Surge: 3" in text
    assert "- Spark of Shock: -10 Grenade" in text
    assert "- Spark of Volts: —" in text


def test_list_text_missing_in_compendium(monkeypatch, compendium):
    idx = subclass.build_index(DEFS)

    def boom(names, element, cls):
        raise subclass.FragmentNotFound("fragment not found")

    monkeypatch.setattr(subclass, "fragment_stats", boom)
    assert "- Spark of Shock: ? (not in the compendium)" in subclass.list_text(idx, "Warlock", "Arc")


def test_check_prismatic():
    idx = subclass.build_index(DEFS2)
    ok = sheet(["Weaver's Call"], ["Facet of Awakening", "Facet of Honor"], element="Prismatic")
    assert subclass.check(ok, idx) == []
    assert subclass.fragment_slots(ok, idx) == 3
    strand = sheet(["Weaver's Call"], ["Facet of Awakening"], element="Strand")
    assert "unknown fragment for Strand: Facet of Awakening" in subclass.check(strand, idx)
    bad = sheet(["Weaver's Call"], ["Spark of Shock"], element="Prismatic")
    assert "unknown fragment for Prismatic: Spark of Shock" in subclass.check(bad, idx)


def test_check_no_aspects():
    idx = subclass.build_index(DEFS)
    assert "no aspect" in subclass.check(sheet([], []), idx)


def test_three_aspects_overflow_against_best_two():
    idx = subclass.build_index(DEFS2)
    frags = ["Spark of Shock", "Spark of Volts", "Spark of Focus", "Spark of Ions", "Spark of Beacons",
             "Spark of Haste"]
    s = sheet(["Arc Soul", "Elemental Well", "Lightning Surge"], frags)
    assert subclass.fragment_slots(s, idx) == 5
    problems = subclass.check(s, idx)
    assert "3 aspects (at most 2)" in problems
    assert "6 fragments for 5 slots" in problems


def test_unknown_aspect_skips_slot_check():
    idx = subclass.build_index(DEFS)
    assert subclass.check(sheet(["Nope"], ["Spark of Shock"]), idx) == ["unknown aspect for Warlock Arc: Nope"]


def test_plural():
    idx = subclass.build_index(DEFS)
    assert "3 fragments for 2 slots" in subclass.check(
        sheet(["Arc Soul"], ["Spark of Shock", "Spark of Volts", "Spark of Ions"]), idx)
    assert "1 fragment for 0 slots" in subclass.check(sheet([], ["Spark of Shock"]), idx)


def test_name_suggestions():
    idx = subclass.build_index(DEFS)
    p = subclass.check(sheet(["arc soul"], ["Shock", "spark of volts", "Spark of Nowhere"]), idx)
    assert "unknown aspect for Warlock Arc: arc soul (expected name: Arc Soul)" in p
    assert "unknown fragment for Arc: Shock (expected name: Spark of Shock)" in p
    assert "unknown fragment for Arc: spark of volts (expected name: Spark of Volts)" in p
    assert "unknown fragment for Arc: Spark of Nowhere" in p


def test_list_text_compendium_file_missing():
    text = subclass.list_text(subclass.build_index(DEFS), "Warlock", "Arc")
    assert "refresh_references" in text and "subclass-arc.md" in text
    assert "- Spark of Shock" not in text


def test_list_text_other_error(monkeypatch, compendium):
    idx = subclass.build_index(DEFS)

    def boom(names, element, cls):
        raise ValueError("unknown class: 'X'")

    monkeypatch.setattr(subclass, "fragment_stats", boom)
    assert "- Spark of Shock: ? (unknown class: 'X')" in subclass.list_text(idx, "Warlock", "Arc")


def test_duplicate_on_normalised_key():
    idx = subclass.build_index(DEFS)
    p = subclass.check(sheet(["Arc Soul"], ["spark of shock", "Shock"]), idx)
    assert "duplicate fragment: Shock" in p


def ability_sheet(**kw):
    s = sheet(["Arc Soul"], [])
    s["subclass"].update(kw)
    return s


def test_check_abilities_ok():
    idx = subclass.build_index(DEFS3)
    s = ability_sheet(super="Stormtrance", abilities={"grenade": "Storm Grenade", "melee": "Chain Lightning",
                                                       "class": "Healing Rift", "jump": "Burst Glide"})
    assert subclass.check(s, idx) == []


def test_check_abilities_unknown_and_hint():
    idx = subclass.build_index(DEFS3)
    s = ability_sheet(super="stormtrance", abilities={"grenade": "Nowhere", "melee": "Chain Lightning"})
    p = subclass.check(s, idx)
    assert "unknown super for Warlock Arc: stormtrance (expected name: Stormtrance)" in p
    assert "unknown grenade for Warlock Arc: Nowhere" in p
    assert len(p) == 2


def test_list_text_abilities(monkeypatch, compendium):
    monkeypatch.setattr(subclass, "fragment_stats", lambda names, element, cls: {})
    text = subclass.list_text(subclass.build_index(DEFS3), "Warlock", "Arc")
    assert "Supers: Chaos Reach, Stormtrance" in text
    assert "Grenades: Storm Grenade" in text
    assert "Melee: Chain Lightning" in text


def test_list_text_shows_aegis_tiers(monkeypatch, compendium, aegis_dir):
    write_aegis(aegis_dir, "endgame", "aspects", [{"_name": "Lightning Surge", "#": "3", "Tier": "A"}])
    write_aegis(aegis_dir, "endgame", "fragments", [{"_name": "Spark of Shock", "#": "12", "Tier": "B"}])
    idx = subclass.build_index(DEFS)
    monkeypatch.setattr(subclass, "fragment_stats", lambda names, element, cls: {})
    text = subclass.list_text(idx, "Warlock", "Arc")
    assert "- Lightning Surge: 3 · Aegis A #3" in text
    assert "- Spark of Shock: — · Aegis B #12" in text
    assert "- Spark of Volts: —\n" in text + "\n"
