import types

import pytest

from shell.sources.compendium.model import Entry, ParseError
from shell.sources.compendium.parsers import TABS, armor_mods, armor_perks, artifact_perks, exotic_armors, exotic_class, is_ignored, run, weapon_perks
from shell.sources.compendium.parsers import class_abilities, exotic_weapons, game_mechanics, subclass
from shell.sources.compendium.parsers._common import Notes, banner, find_row, first_line, is_section_title, other_lines


def fake(anchors=("Title",), minimum=1, result=None, error=None):
    def parse(grid):
        if error:
            raise error
        return result if result is not None else [Entry("A", "S")]
    return types.SimpleNamespace(ANCHORS=anchors, MIN_ENTRIES=minimum, parse=parse)


def test_run_ok(sheet):
    assert run("T", fake(), sheet([["Title"]])) == [Entry("A", "S")]


def test_run_accepts_anchor_on_first_line(sheet):
    assert run("T", fake(), sheet([["Title\nsous-titre"]]))


def test_run_missing_anchor(sheet):
    with pytest.raises(ParseError, match='T: anchor not found: "Title"'):
        run("T", fake(), sheet([["Other"]]))


def test_run_too_few_entries(sheet):
    with pytest.raises(ParseError, match="0 entries found, at least 1 expected"):
        run("T", fake(result=[]), sheet([["Title"]]))


@pytest.mark.parametrize("error", [StopIteration(), ValueError("x"), IndexError("x"), KeyError("x"),
                                   AttributeError("x"), TypeError("x")])
def test_run_wraps_structure_errors(sheet, error):
    with pytest.raises(ParseError, match="unexpected structure"):
        run("T", fake(error=error), sheet([["Title"]]))


def test_run_accepts_generators(sheet):
    module = fake()
    module.parse = lambda grid: (e for e in [Entry("A", "S")])
    assert run("T", module, sheet([["Title"]])) == [Entry("A", "S")]


def test_is_ignored():
    assert is_ignored("Landing") and is_ignored("OLD Armor Mods") and not is_ignored("Arc")


def test_common_helpers(sheet):
    g = sheet([[("Banner", 1, 4)], ["a", "b", ("narrow", 1, 2)], ["Perk", "Description"]])
    assert banner(g, 0) == "Banner"
    assert banner(g, 1) is None
    assert find_row(g, ["Perk", "Description"]) == 2
    with pytest.raises(ValueError):
        find_row(g, ["Absent"])
    assert first_line("Nom\n\nsuite\nfin") == "Nom"
    assert other_lines("Nom\n\nsuite\nfin") == ["suite", "fin"]


def test_banner_rejects_row_with_vertical_merge_in_other_column(sheet):
    g = sheet([[("Set", 2, 1), "2p", "", ""], [("4p", 1, 3)]])
    assert banner(g, 1) is None


def test_banner_rejects_narrow_row(sheet):
    g = sheet([["a", "b", "c", "d"], [("narrow", 1, 1)]])
    assert banner(g, 1) is None


def test_banner_accepts_exactly_half_width(sheet):
    g = sheet([["a", "b", "c", "d"], [("Half", 1, 2)]])
    assert banner(g, 1) == "Half"


def test_registry_is_consistent():
    slugs = [slug for slug, _ in TABS.values()]
    assert len(slugs) == len(set(slugs))
    for tab, (slug, module) in TABS.items():
        assert module.ANCHORS, tab
        assert module.MIN_ENTRIES >= 1, tab
        assert callable(module.parse), tab


EXOTIC_ARMORS = [
    [("Exotic Armor", 1, 9)],
    [("Hunters", 1, 3), ("Titans", 1, 3), ("Warlocks", 1, 3)],
    ["Armor", "Icon", "Notes", "Armor", "Icon", "Notes", "Armor", "Icon", "Notes"],
    ["Assassin's Cowl", "", ("On Powered Melee Kill or Finisher:\nGrants Void Invisibility.", 3, 1),
     "Abeyant Leap", "", ("Enhances Drengr's Lash.", 3, 1),
     "Apotheosis Veil", "", ("On Super Cast: restores abilities.", 3, 1)],
    ["", "", "", "", "", ""],
    ["Vanishing Execution", "", "Puppeteer's Control", "", "Insatiable", ""],
    [("Aeon Sects", 1, 9)],
    ["Sect of Force\n\nFoebreaker Chant", "", "Grants Force.",
     "Sect of Insight\n\nArmsbearer Chant", "", "Grants Insight.",
     "Sect of Vigor\n\nLightgiver Chant", "", "Grants Vigor."],
]


def test_exotic_armors(sheet):
    entries = exotic_armors.parse(sheet(EXOTIC_ARMORS))
    assert [(e.name, e.section, e.attrs) for e in entries] == [
        ("Assassin's Cowl", "Hunter", {"perk": "Vanishing Execution"}),
        ("Abeyant Leap", "Titan", {"perk": "Puppeteer's Control"}),
        ("Apotheosis Veil", "Warlock", {"perk": "Insatiable"}),
        ("Sect of Force", "Aeon Sects", {"perk": "Foebreaker Chant"}),
        ("Sect of Insight", "Aeon Sects", {"perk": "Armsbearer Chant"}),
        ("Sect of Vigor", "Aeon Sects", {"perk": "Lightgiver Chant"}),
    ]
    assert entries[0].text == "On Powered Melee Kill or Finisher:\nGrants Void Invisibility."


EXOTIC_CLASS = [
    [("Exotic Class Perks", 1, 6)],
    [("The Left Column determines the Armor Archetype…", 1, 6)],
    [("Class-agnostic Perks", 1, 6)],
    ["Spirit of the Assassin", "", "On Powered Melee Kill:\nGrants Void Invisibility.",
     "Spirit of the Star-Eater", "", "Picking up an Orb of Power while Super is full…"],
    [("Hunter-exclusive Perks", 1, 6)],
    ["Spirit of Caliban", "", "Powered Melee Kills trigger an explosion.", "Spirit of the Coyote", "", "Grants an extra Class Ability charge."],
    [("Exotic Class Items will only ever roll…", 1, 6)],
]


def test_exotic_class(sheet):
    entries = exotic_class.parse(sheet(EXOTIC_CLASS))
    notes = [(e.section, e.text) for e in entries if e.name == "Notes"]
    assert notes == [
        ("Exotic Class Perks", "The Left Column determines the Armor Archetype…"),
        ("Hunter-exclusive Perks", "Exotic Class Items will only ever roll…"),
    ]
    entries = [e for e in entries if e.name != "Notes"]
    assert [(e.name, e.section, e.attrs["role"]) for e in entries] == [
        ("Spirit of the Assassin", "Class-agnostic Perks", "left (archetype)"),
        ("Spirit of the Star-Eater", "Class-agnostic Perks", "right (tertiary stats)"),
        ("Spirit of Caliban", "Hunter-exclusive Perks", "left (archetype)"),
        ("Spirit of the Coyote", "Hunter-exclusive Perks", "right (tertiary stats)"),
    ]
    assert entries[0].text == "On Powered Melee Kill:\nGrants Void Invisibility."


def test_exotic_class_incomplete_pair(sheet):
    rows = [[("Class-agnostic Perks", 1, 6)], ["Spirit of the Assassin", "", "", "", "", ""]]
    with pytest.raises(ValueError):
        exotic_class.parse(sheet(rows))


ARMOR_MODS = [
    ["w", ("Helmet", 1, 2), "Effect", ("Arms", 1, 2), "Effect", "LEGACY", ("Raid-Specific", 1, 2), "Effect"],
    ["", ("Ammo Finder\n[3 Energy]", 1, 2), "Special Ammo Finders: 1.25x progress.",
     ("Firepower\n[3 Energy]", 1, 2), "On Grenade Kill:\nSpawns an Orb of Power.", "-",
     ("Salvation's Edge", 1, 2), ""],
    ["", ("Siphon\n[1–2–3 Energy]", 1, 2), "Weapon kills create Orbs.",
     ("Nightmare Banisher\n[1 | 2 | 3 Energy]", 1, 2), "Grants 66% [133%] increased damage.", "",
     ("Arm's Reach", 1, 2), "Upon killing an enemy within range…"],
]


def test_armor_mods(sheet):
    entries = armor_mods.parse(sheet(ARMOR_MODS))
    assert [(e.name, e.section, e.attrs) for e in entries] == [
        ("Ammo Finder", "Helmet", {"energy": "3"}),
        ("Siphon", "Helmet", {"energy": "1–2–3"}),
        ("Firepower", "Arms", {"energy": "3"}),
        ("Nightmare Banisher", "Arms", {"energy": "1 | 2 | 3"}),
        ("Arm's Reach", "Raid Specific", {"activity": "Salvation's Edge"}),
    ]
    assert entries[2].text == "On Grenade Kill:\nSpawns an Orb of Power."


ARMOR_MODS_REAL_CASES = [
    ["w", ("Helmet", 1, 2), "Effect", ("Raid-Specific", 1, 2), "Effect"],
    ["", ("Melee\nKickstart\n[3 Energy]", 1, 2), "On Melee Ability Charge Usage…",
     ("Garden of Salvation", 1, 2), ""],
    ["", ("Fastball\n[1 Energy]", 1, 2), "Grenades travel faster.",
     ("Relay Defender\n\nEnhanced Relay Defender", 1, 2), "While near a Vex Relay: 5% [10%]…"],
]


def test_armor_mods_slot_mod_without_effect(sheet):
    rows = [
        ["w", ("Helmet", 1, 2), "Effect"],
        ["", ("Ammo Finder\n[3 Energy]", 1, 2), ""],
    ]
    with pytest.raises(ValueError, match="mod without effect"):
        armor_mods.parse(sheet(rows))


def test_armor_mods_heading_whitespace(sheet):
    rows = [
        ["w", ("Helmet", 1, 2), "Effect", ("Raid-Specific", 1, 2), "Effect"],
        ["", ("Ammo Finder\n[3 Energy]", 1, 2), "Text.", ("Last\nWish", 1, 2), ""],
        ["", "", "", "", ("Taken Barrier", 1, 2), "Upon damage."],
    ]
    entries = armor_mods.parse(sheet(rows))
    assert [(e.name, e.attrs) for e in entries if e.section == "Raid Specific"] == [
        ("Taken Barrier", {"activity": "Last Wish"})
    ]


def test_armor_mods_real_cases(sheet):
    entries = armor_mods.parse(sheet(ARMOR_MODS_REAL_CASES))
    assert [(e.name, e.section, e.attrs) for e in entries] == [
        ("Melee Kickstart", "Helmet", {"energy": "3"}),
        ("Fastball", "Helmet", {"energy": "1"}),
        ("Relay Defender", "Raid Specific",
         {"variant": "Enhanced Relay Defender", "activity": "Garden of Salvation"}),
    ]



WEAPON_PERKS = [
    [("Gear Perks, Traits, and Mods", 1, 6)],
    [("Perk", 1, 2), ("Description", 1, 4)],
    ["", ("Enhanced Traits are shown in ↑Yellow, with their improved values.", 1, 4)],
    [("Weapon Traits", 1, 6)],
    [("Accelerated Heatsink", 1, 2), ("Passively grants +25 Cooling Efficiency.", 1, 4)],
    [("Air Trigger\n(Origin)", 1, 2), ("Passively grants +20 ↑+30 Ammo Generation.", 1, 4)],
    [("Weapon Mods", 1, 6)],
    [("Backup Mag", 1, 2), ("+30% Magazine Size.", 1, 4)],
]


def test_weapon_perks(sheet):
    entries = weapon_perks.parse(sheet(WEAPON_PERKS))
    assert [(e.name, e.section, e.attrs) for e in entries] == [
        ("Notes", "Weapon Traits", {}),
        ("Accelerated Heatsink", "Weapon Traits", {}),
        ("Air Trigger", "Weapon Traits", {"detail": "(Origin)"}),
        ("Backup Mag", "Weapon Mods", {}),
    ]
    assert entries[2].text == "Passively grants +20 ↑+30 Ammo Generation."


def test_weapon_perks_footnote_row_and_mods_note(sheet):
    rows = [
        [("Perk", 1, 2), ("Description", 1, 4)],
        [("Weapon Traits", 1, 6)],
        [("Zen Moment", 1, 2), ("On Hit: Grants Flinch Resist.", 1, 4)],
        [("For in-depth Damage Stacking info, check out Court's Modifier Database", 1, 2),
         ("Reload Perk Notes:\n\nGenerate = Grants Ammo.", 1, 4)],
        [("Weapon Mods", 1, 6)],
        [("Enhanced Weapon Mods are equippable only on Tier 4 and Tier 5 Weapons.", 1, 6)],
        [("Abundant Ammo", 1, 2), ("+10 ↑+12 Ammo Generation.", 1, 4)],
    ]
    entries = weapon_perks.parse(sheet(rows))
    assert [(e.name, e.section) for e in entries] == [
        ("Zen Moment", "Weapon Traits"),
        ("Notes", "Weapon Traits"),
        ("Notes", "Weapon Mods"),
        ("Abundant Ammo", "Weapon Mods"),
    ]
    assert entries[1].text.startswith("For in-depth Damage Stacking info")
    assert "Reload Perk Notes" in entries[1].text


def test_weapon_perks_origin_source_and_multiline_names(sheet):
    rows = [
        [("Perk", 1, 2), ("Description", 1, 4)],
        [("Enhanced Traits are shown in \u2191Yellow.\n\nSmaller + signs are color-coded.", 1, 6)],
        [("Origin Traits", 1, 6)],
        [("Harmonic Resonance\n\nRoot of Nightmares\nRaid\n\n+Epochal Integration", 1, 2), ("Grants Resonance.", 1, 4)],
        [("Accelerated Assault\n\nShiny Renegade Drops\nVanguard Alerts", 1, 2), ("Upon damage.", 1, 4)],
        [("Weapon Mods", 1, 6)],
        [("Enhanced Weapon Mods are equippable only on Tier 4 and Tier 5 Weapons.", 1, 6)],
        [("Abundant Ammo", 1, 2), ("+10.", 1, 4)],
    ]
    entries = weapon_perks.parse(sheet(rows))
    assert [(e.name, e.section, e.attrs) for e in entries] == [
        ("Notes", "Weapon Traits", {}),
        ("Harmonic Resonance", "Origin Traits", {"source": "Root of Nightmares · Raid / +Epochal Integration"}),
        ("Accelerated Assault", "Origin Traits", {"source": "Shiny Renegade Drops · Vanguard Alerts"}),
        ("Notes", "Weapon Mods", {}),
        ("Abundant Ammo", "Weapon Mods", {}),
    ]
    assert entries[3].text == "Enhanced Weapon Mods are equippable only on Tier 4 and Tier 5 Weapons."


def test_weapon_perks_notes_merge_per_section(sheet):
    rows = [
        [("Perk", 1, 2), ("Description", 1, 4)],
        [("Weapon Traits", 1, 6)],
        [("Note one is long enough to be a note and not a title, really, yes.", 1, 6)],
        [("Zen Moment", 1, 2), ("On Hit.", 1, 4)],
        [("For in-depth Damage Stacking info, check out Court's Modifier Database", 1, 2), ("Second.", 1, 4)],
    ]
    entries = weapon_perks.parse(sheet(rows))
    notes = [e for e in entries if e.name == "Notes"]
    assert len(notes) == 1 and notes[0].text.startswith("Note one") and "Second." in notes[0].text


ARMOR_PERKS = [
    [("Armor Set Bonuses", 1, 6)],
    [("Armor Set", 1, 2), ("Description", 1, 4)],
    [("AION Renewal\n\nKepler\nDestination", 2, 2), ("2 Piece | Force Converter\n\nUpon scoring a kill…", 1, 4)],
    [("4 Piece | Reactive Booster\n\nSprinting grants…", 1, 4)],
    [("Bushido\n\nXûr\nVendor", 2, 2), ("2 Piece | Iaido\n\nUpon scoring a Precision Hit…", 1, 4)],
    [("4 Piece | Unfaltering Focus\n\nOn Sword Kill…", 1, 4)],
]


def test_armor_perks(sheet):
    entries = armor_perks.parse(sheet(ARMOR_PERKS))
    assert [(e.name, e.attrs) for e in entries] == [
        ("AION Renewal", {"source": "Kepler · Destination", "2 pieces": "Force Converter", "4 pieces": "Reactive Booster"}),
        ("Bushido", {"source": "Xûr · Vendor", "2 pieces": "Iaido", "4 pieces": "Unfaltering Focus"}),
    ]
    assert entries[0].section == "Armor Set Bonuses"
    assert entries[0].text == ("2 pieces — Force Converter:\nUpon scoring a kill…\n\n"
                               "4 pieces — Reactive Booster:\nSprinting grants…")


def test_armor_perks_notes_and_disabled_marker(sheet):
    rows = [
        [("Armor Set Bonuses", 1, 6)],
        [("Armor Set", 1, 2), ("Description", 1, 4)],
        [("Note: values are approximate and may change between patches, see the author.", 1, 6)],
        [("Circuit\n\nSparrow Racing League", 2, 2), ("2 Piece | Revving Up\n\nWhile fast.", 1, 4)],
        [("4 Piece | Dielectric Drift\n>>DISABLED IN CRUCIBLE<<\n\nSliding.", 1, 4)],
        [("Second note that is long enough to not be mistaken for a section title at all.", 1, 6)],
    ]
    entries = armor_perks.parse(sheet(rows))
    assert [(e.name, e.section) for e in entries] == [("Notes", "Armor Set Bonuses"), ("Circuit", "Armor Set Bonuses")]
    assert entries[0].text.startswith("Note: values") and "Second note" in entries[0].text
    assert entries[1].attrs == {"source": "Sparrow Racing League", "2 pieces": "Revving Up",
                                "4 pieces": "Dielectric Drift", "crucible": "4 pieces disabled"}
    assert ">>DISABLED IN CRUCIBLE<<" in entries[1].text


def test_is_section_title():
    assert is_section_title("Origin Traits")
    assert is_section_title("x" * 60)
    assert not is_section_title("x" * 61)
    assert not is_section_title("Deux\nlignes")


def test_notes_helper_one_entry_per_section():
    entries = []
    notes = Notes(entries)
    notes.add("A", "un")
    notes.add("B", "deux")
    notes.add("A", "trois")
    assert [(e.name, e.section, e.text) for e in entries] == [
        ("Notes", "A", "un\n\ntrois"),
        ("Notes", "B", "deux"),
    ]


def test_armor_perks_stray_row_goes_to_notes(sheet):
    rows = [
        [("Armor Set Bonuses", 1, 6)],
        [("Armor Set", 1, 2), ("Description", 1, 4)],
        [("", 1, 2), ("stray text", 1, 2)],
        [("Circuit\n\nSparrow Racing League", 2, 2), ("2 Piece | Revving Up\n\nWhile fast.", 1, 4)],
        [("4 Piece | Dielectric Drift\n\nSliding.", 1, 4)],
    ]
    entries = armor_perks.parse(sheet(rows))
    assert [(e.name, e.text) for e in entries[:1]] == [("Notes", "stray text")]
    assert entries[1].name == "Circuit"


def test_armor_perks_flags_crucible_disabled(sheet):
    rows = [
        [("Armor Set Bonuses", 1, 6)],
        [("Armor Set", 1, 2), ("Description", 1, 4)],
        [("Crystocrene\n\nEuropa\nDestination", 2, 2), ("2 Piece | Resupply\n\nOrb.", 1, 4)],
        [("4 Piece | From the Storm\n>>DISABLED IN CRUCIBLE<<\n\nAfter a while.", 1, 4)],
        [("Both Off\n\nSomewhere", 2, 2), ("2 Piece | One\n>>DISABLED IN CRUCIBLE<<\n\nA.", 1, 4)],
        [("4 Piece | Two\n>>DISABLED IN CRUCIBLE<<\n\nB.", 1, 4)],
    ]
    a, b = armor_perks.parse(sheet(rows))
    assert a.attrs["crucible"] == "4 pieces disabled" and a.attrs["4 pieces"] == "From the Storm"
    assert ">>DISABLED IN CRUCIBLE<<" in a.text
    assert b.attrs["crucible"] == "2 pieces disabled · 4 pieces disabled"


ARTIFACT_PERKS = [
    [("Artifact Perks", 1, 9)],
    ["", ("⯁", 1, 2), "", ("⯁ ⯁", 1, 2), "", ("⯁ ⯁ ⯁", 1, 2)],
    [("Artifacts from past seasons are equippable, with each focused on specific elements.", 1, 9)],
    ["", "", "", "", ("Perks are disabled in Competitive.", 1, 4)],
    ["", "", "", ("Encrypted Data Disk (Renegades)", 2, 3)],
    [""],
    ["", "", "Press The Advantage", "", "", "Dielectric", "", "", "Elemental Orbs: Arc"],
    ["", ("Upon breaking a Combatant's Shield…", 1, 2), "", ("On Arc-Debuffed Enemy Kill…", 1, 2), "", ("Upon scoring 6 [2?] Arc Weapon Kills…", 1, 2)],
    ["", "", "Riposte"],
    ["", ("After guarding with a Sword…", 1, 2)],
    ["", "", "", ("Implement of Curiosity (Reclamation)", 1, 3)],
    ["", "", "", ("Kinetic | Solar ⯁ Bow | Sword", 1, 3)],
    ["", "", "Reload at Range", "", "", "Orphan"],
    ["", ("Upon scoring a Precision Hit…", 1, 2), "", "", "", "", ("Desc without name…", 1, 2)],
]


def test_artifact_perks(sheet):
    entries = artifact_perks.parse(sheet(ARTIFACT_PERKS))
    real = [e for e in entries if e.name != "Notes"]
    assert [(e.name, e.section) for e in real] == [
        ("Press The Advantage", "Encrypted Data Disk (Renegades)"),
        ("Dielectric", "Encrypted Data Disk (Renegades)"),
        ("Elemental Orbs: Arc", "Encrypted Data Disk (Renegades)"),
        ("Riposte", "Encrypted Data Disk (Renegades)"),
        ("Reload at Range", "Implement of Curiosity (Reclamation)"),
        ("Orphan", "Implement of Curiosity (Reclamation)"),
    ]
    assert [e.attrs["column"] for e in real[:3]] == ["1", "2", "3"]
    assert real[3].text == "After guarding with a Sword…"
    assert real[3].attrs == {"order": "1", "column": "1"}
    # subtitle: elements and weapon types of the artifact, applied to its perks
    reload_ = real[4]
    assert reload_.attrs == {"elements": "Kinetic | Solar", "weapons": "Bow | Sword", "order": "2", "column": "1"}
    assert reload_.text == "Upon scoring a Precision Hit…"
    assert real[5].name == "Orphan" and real[5].text == "" and real[5].attrs["column"] == "2"  # name without description kept
    # author's notes and description without name kept, diamond header ignored
    assert [(e.section, e.text) for e in entries if e.name == "Notes"] == [
        ("Artifact Perks", "Artifacts from past seasons are equippable, with each focused on specific elements.\n\nPerks are disabled in Competitive."),
        ("Implement of Curiosity (Reclamation)", "Desc without name…"),
    ]


E = ""  # empty cell


def row(name="", text="", extra="", head=""):
    """Subclass row: head (col. 0), name (col. 1), description (col. 3-12), info (col. 13)."""
    return [head, name, E, (text, 1, 10), extra]


SUBCLASS = [
    [("Go back to the top!", 1, 3), ("Arc Subclasses", 1, 10), ("Support the Data Compendium", 1, 2)],
    [E, ("Hunter", 1, 5), ("Titan", 1, 5), ("Warlock", 1, 4)],
    [E, ("Glossary", 1, 13), E],
    row("Amplified", "Intrinsic Arc Subclass Buff."),
    [E, "Fragments", "Icon", ("Information", 1, 10), "Stat Changes"],
    row("Spark of Brilliance", "Precision Kills against blinded enemies…", "+10 Super"),
    row("Spark of Haste", "After 1.25 seconds of sprinting…", "-"),
    [E, ("Grenade Abilities", 1, 13), E],
    row("Flashbang Grenade", "Medium Trajectory\n\nExplodes on impact.", "Base Cooldown: 131.7 s\nChunk: 5%"),
    row("Touch of Thunder", "Explodes an additional time."),
    [("Hunter", 1, 1), ("-", 1, 5), ("Hunters", 1, 3), ("-", 1, 6)],
    [E, ("Super Abilities", 1, 13), E],
    row("Arc Staff", "General Super Information…", "Tier 2 Super\n\n556 seconds"),
    [E, "Aspect", E, ("Information", 1, 10), "Fragment Slots"],
    row("Flow State", "Scoring a Jolted Enemy…"),
    row("Touch of Thunder", "Must not be renamed: not a grenade."),
]


def test_subclass(sheet):
    entries = subclass.parse(sheet(SUBCLASS))
    assert [(e.name, e.section, e.attrs) for e in entries] == [
        ("Amplified", "Glossary", {}),
        ("Spark of Brilliance", "Fragments", {"stats": "+10 Super"}),
        ("Spark of Haste", "Fragments", {}),
        ("Flashbang Grenade", "Grenade Abilities", {"info": "Base Cooldown: 131.7 s · Chunk: 5%"}),
        ("Flashbang Grenade (Touch of Thunder)", "Grenade Abilities", {}),
        ("Arc Staff", "Hunter — Super Abilities", {"info": "Tier 2 Super · 556 seconds"}),
        ("Flow State", "Hunter — Aspects", {}),
        ("Touch of Thunder", "Hunter — Aspects", {}),
    ]


PRISMATIC = [
    [("Hunter", 1, 1), ("-", 1, 5), ("Hunters", 1, 3), ("-", 1, 6)],
    row("Hailfire Spike", "Prismatic Grenade\n\nAttaches to targets."),
    [E, ("Shared Abilities\n\nClass Abilities shared with other subclasses", 3, 2), E, "Arcbolt Grenade", E, "Swarm Grenade"],
    [E, E, "Combination Blow", E, "Knife Trick"],
    [],
]


def test_subclass_prismatic(sheet):
    entries = subclass.parse(sheet(PRISMATIC))
    assert [(e.name, e.section) for e in entries] == [
        ("Hailfire Spike", "Hunter — Grenade Abilities"),
        ("Shared Abilities", "Hunter — Abilities"),
    ]
    assert entries[1].text == "- Arcbolt Grenade\n- Swarm Grenade\n- Combination Blow\n- Knife Trick"


CLASS_ABILITIES = [
    [("Hunter", 1, 1), ("-", 1, 5), ("Hunters", 1, 3), ("-", 1, 6)],
    [E, E, E, ("Hunters intrinsically possess…", 1, 10), E],
    row("Acrobat's Dodge", "Performs an acrobatic leap…", "Base Cooldown: 56 [148.4]s"),
    [("Titans", 1, 1), ("-", 1, 5), ("Titans", 1, 3), ("-", 1, 6)],
    row("Thruster", "Performs an evasive fist…", "Base Cooldown: 52.1 seconds"),
]


def test_class_abilities(sheet):
    entries = class_abilities.parse(sheet(CLASS_ABILITIES))
    assert [(e.name, e.section) for e in entries if e.name != "Notes"] == [
        ("Acrobat's Dodge", "Hunter — Abilities"),
        ("Thruster", "Titan — Abilities"),
    ]
    # class introduction text (intrinsic traits) kept as a note
    assert [(e.section, e.text) for e in entries if e.name == "Notes"] == [
        ("Hunter — Abilities", "Hunters intrinsically possess…"),
    ]
    assert class_abilities.ANCHORS == ("Hunter", "Titans", "Warlocks")


SUBCLASS_REAL_CASES = [
    [E, ("Hunter", 1, 3), E, E, ("Titan", 1, 3), E, E, ("Warlock", 1, 3)],  # navigation bar
    [E, ("Glossary", 1, 13), E],
    [E, E, E, ("Movement Abilities can be freely picked.", 1, 11)],  # name as an image: author's note
    [E, "Fragments", "Icon", ("Information", 1, 10), "Stat Changes"],
    row("Focus", "After sprinting…", "-10 Weapons (Hunter)\n-10 Health (Titan)"),
    row("Solar Effect\nDamage Scaling", "Scorch damage scales…"),
    [E, ("Grenade Abilities", 1, 13), E],
    [E, ("Numbers in [Smaller Parenthesis] are with Spark of Magnitude equipped!", 1, 13), E],
    row("Firebolt Grenade", "Scans up to 4 enemies.", "Base Cooldown: 83.8 seconds"),
    row("Touch of Flame", "Scans up to 5 enemies."),
    row("Axion Bolt", "Scans up to 2 enemies.", "Base Cooldown: 219.5 seconds"),
    row("Chaos Accelerant\n(Charged)", "Scans up to 4 enemies."),
    row("Handheld Supernova\n\nChaos Accelerant", "While Magnetic Grenade is equipped…"),
    row("Coldsnap Grenade", "Seekers.", "Base Cooldown: 151.5 seconds"),
    row("Touch of Winter", "Seekers duplicate."),
    row("Grapple", "Grapple point.", "Base Cooldown: 91 seconds"),
    row("Mindspun Invocation", "Grapple Melee creates Threadlings."),
    # Void Titan block: "-" in column 0, the class only in column 6
    ["-", "-", "-", "-", "-", "-", ("Titans", 1, 3), "-", "-", "-", "-", "-", "-"],
    [E, ("Super Abilities", 1, 13), E],
    row("Chaos Reach", "General Super Information…", "Tier 4 Super\n\nBase Cooldown:\n455 seconds"),
    row("Nova Bomb: Cataclysm", "General Super Information…"),
    [("Warlocks", 1, 1), ("-", 1, 5), ("Warlocks", 1, 3), ("-", 1, 6)],
    [E, E, E, ("Warlocks intrinsically possess…", 1, 10), E],
    [E, "Aspects", E, ("Information", 1, 10), "Fragment Slots"],
    row("Touch of Flame", "Enhances certain Grenade types."),
]


def test_subclass_real_cases(sheet):
    entries = subclass.parse(sheet(SUBCLASS_REAL_CASES))
    assert [(e.name, e.section) for e in entries] == [
        ("Notes", "Glossary"),
        ("Focus", "Fragments"),
        ("Solar Effect (Damage Scaling)", "Fragments"),
        ("Notes", "Grenade Abilities"),
        ("Firebolt Grenade", "Grenade Abilities"),
        ("Firebolt Grenade (Touch of Flame)", "Grenade Abilities"),
        ("Axion Bolt", "Grenade Abilities"),
        ("Axion Bolt (Chaos Accelerant, Charged)", "Grenade Abilities"),
        ("Handheld Supernova (Chaos Accelerant)", "Grenade Abilities"),
        ("Coldsnap Grenade", "Grenade Abilities"),
        ("Coldsnap Grenade (Touch of Winter)", "Grenade Abilities"),
        ("Grapple", "Grenade Abilities"),
        ("Grapple (Mindspun Invocation)", "Grenade Abilities"),
        ("Chaos Reach", "Titan — Super Abilities"),
        ("Nova Bomb (Cataclysm)", "Titan — Super Abilities"),
        ("Notes", "Warlock — Abilities"),
        ("Touch of Flame", "Warlock — Aspects"),
    ]
    by = {(e.name, e.section): e for e in entries}
    assert by["Notes", "Glossary"].text == "Movement Abilities can be freely picked."
    assert by["Notes", "Grenade Abilities"].text == "Numbers in [Smaller Parenthesis] are with Spark of Magnitude equipped!"
    assert by["Notes", "Warlock — Abilities"].text == "Warlocks intrinsically possess…"
    assert by["Focus", "Fragments"].attrs == {"stats": "-10 Weapons (Hunter) · -10 Health (Titan)"}
    assert by["Chaos Reach", "Titan — Super Abilities"].attrs == {"info": "Tier 4 Super · Base Cooldown: 455 seconds"}


def test_subclass_prismatic_shared_note(sheet):
    entries = subclass.parse(sheet(PRISMATIC))
    assert entries[1].attrs == {"note": "Class Abilities shared with other subclasses"}


PRISMATIC_REAL = [
    [("Titan", 1, 1), ("-", 1, 5), ("Titans", 1, 3), ("-", 1, 6)],
    row("Electrified Snare", "Prismatic Grenade\n\nExplosive charged with Light and Darkness."),
    # real case: the "Shared Abilities" cell is alone on its row, the abilities on the next 2 rows
    [E, ("Shared Abilities\n\nClass Abilities and Movement Abilities are all shared.", 3, 2), E],
    [E, "Pulse Grenade", E, "Thermite Grenade"],
    [E, "Thunderclap", E, "Hammer Strike"],
    [E, "Aspects", E, ("Information", 1, 10), "Fragment Slots"],
    row("Knockout", "On Melee Kill…"),
    [E, ("Super Abilities", 1, 13), E],
    row("Golden Gun:\nDeadshot", "General Super Information…", "Tier 3 Super"),
]


def test_subclass_prismatic_real_layout(sheet):
    entries = subclass.parse(sheet(PRISMATIC_REAL))
    assert [(e.name, e.section) for e in entries] == [
        ("Electrified Snare", "Titan — Grenade Abilities"),
        ("Shared Abilities", "Titan — Abilities"),
        ("Knockout", "Titan — Aspects"),
        ("Golden Gun (Deadshot)", "Titan — Super Abilities"),
    ]
    assert entries[1].text == "- Pulse Grenade\n- Thermite Grenade\n- Thunderclap\n- Hammer Strike"
    assert entries[1].attrs == {"note": "Class Abilities and Movement Abilities are all shared."}


def test_subclass_class_column_needs_column_0(sheet):
    # navigation-bar-like row: columns 0 and 1 empty, "Titan" in column 6 -> not a class block
    entries = subclass.parse(sheet([
        [("Hunter", 1, 1), ("-", 1, 5), ("Hunters", 1, 3), ("-", 1, 6)],
        [E, E, E, E, E, E, ("Titan", 1, 3)],
        [E, ("Super Abilities", 1, 13), E],
        row("Golden Gun", "General Super Information…", "Tier 3 Super"),
    ]))
    assert [(e.name, e.section) for e in entries] == [("Golden Gun", "Hunter — Super Abilities")]


EXOTIC_WEAPONS = [
    ["", ("[PVP-Specific]", 1, 2), ("Exotic Weapon Documentation", 1, 3), ("PVE-Specific", 1, 3)],
    [("Kinetic Weapons", 1, 4), "Energy Weapons", ("Power Weapons", 1, 4)],
    [("Weapons don't inherit frame bonuses unless stated.", 1, 9)],
    [E, E, ("Catalysts are displayed with ↑Yellow.\nBase values apply.", 1, 6)],
    [("Kinetic Slot Weapons", 1, 9)],
    [("Ace of Spades\n\nMemento Mori\nFirefly\n↑Funeral Pyre", 1, 3), ("Kinetic Adaptive Hand Cannon\n\nRadar remains active.", 1, 6)],
    [("Energy Slot Weapons", 1, 9)],
    [("Euphony\n\nUnwound\nSpindle", 1, 3), ("Special Ammo Strand Linear Fusion Rifle.", 1, 6)],
]


def test_exotic_weapons(sheet):
    entries = exotic_weapons.parse(sheet(EXOTIC_WEAPONS))
    notes = [e for e in entries if e.name == "Notes"]
    assert [(e.section, e.text) for e in notes] == [(
        "Exotic Weapons",
        "Weapons don't inherit frame bonuses unless stated.\n\nCatalysts are displayed with ↑Yellow.\nBase values apply.",
    )]
    entries = [e for e in entries if e.name != "Notes"]
    assert [(e.name, e.section, e.attrs) for e in entries] == [
        ("Ace of Spades", "Kinetic Slot Weapons", {"perks": "Memento Mori · Firefly", "catalyst": "Funeral Pyre"}),
        ("Euphony", "Energy Slot Weapons", {"perks": "Unwound · Spindle"}),
    ]
    assert entries[0].text == "Kinetic Adaptive Hand Cannon\n\nRadar remains active."


EXOTIC_WEAPONS_REAL = [
    [("Power Weapons", 1, 9)],
    [("Kinetic Slot Weapons", 1, 9)],
    [("Praxic Blade\nTechnically-Not-A-Lightsaber\n\nRanged Weapon\nCormorant Combo", 1, 1), E, E, ("Special Ammo Sword", 1, 6)],
    [("Praxic Blade 2:\nAttack of the Cores\n\nPower Cores", 1, 1), E, E, ("Cores grant effects.", 1, 6)],
    [("Ergo Sum\n\nTranscendent Duelist\n↑Transcendent Steel", 1, 1), E, E, ("Special Ammo Sword", 1, 6)],
    [("Ergo Sum\n\nArc Element", 1, 1), E, E, ("Continuation of the Ergo Sum Exotic.", 1, 6)],
    [("D.A.R.C.I.\nDARCI\nPersonal Assistant\nTarget Acquired\n↑Networked Targeting", 1, 1), E, E, ("Arc Sniper Rifle", 1, 6)],
    [("Heirloom\n\nBolt Thrower\n↑Incandescent\n\nBoltcaster <3", 1, 1), E, E, ("Solar Crossbow", 1, 6)],
    [E, E, ("A note in the middle of a section.", 1, 6)],
    [("Fafnir\n\nQuantum Nova\n\n", 1, 1), E, E, ("Void LFR", 1, 4), ("Only in PvE.", 1, 2)],
]


def test_exotic_weapons_real_layout(sheet):
    entries = exotic_weapons.parse(sheet(EXOTIC_WEAPONS_REAL))
    assert [(e.name, e.attrs) for e in entries] == [
        ("Praxic Blade", {"subtitle": "Technically-Not-A-Lightsaber", "perks": "Ranged Weapon · Cormorant Combo"}),
        ("Praxic Blade 2", {"subtitle": "Attack of the Cores", "perks": "Power Cores"}),
        ("Ergo Sum", {"perks": "Transcendent Duelist", "catalyst": "Transcendent Steel"}),
        ("Ergo Sum (Arc Element)", {}),
        ("D.A.R.C.I.", {"subtitle": "DARCI", "perks": "Personal Assistant · Target Acquired", "catalyst": "Networked Targeting"}),
        ("Heirloom", {"perks": "Bolt Thrower", "catalyst": "Incandescent", "note": "Boltcaster <3"}),
        ("Notes", {}),
        ("Fafnir", {"perks": "Quantum Nova"}),
    ]
    assert entries[6].section == "Kinetic Slot Weapons" and entries[6].text == "A note in the middle of a section."
    assert entries[7].text == "Void LFR\n\nPvE-specific:\nOnly in PvE."


def test_exotic_weapons_alias_heuristic_is_strict(sheet):
    entries = exotic_weapons.parse(sheet([
        [("Kinetic Slot Weapons", 1, 9)],
        [("Cull's Shadow\nSoulburn\nSoulforge\nBlades of Unmaking", 1, 1), E, E, ("Kinetic Fusion Rifle", 1, 6)],
        [("One Thousand Voices\n1KV\nAhamkara's Eye\nUnforeseen Repercussions\n↑Fall From Grace", 1, 1), E, E, ("Solar Fusion Rifle", 1, 6)],
        [("Odd\nA\nB\nC\n↑X\n↑Y", 1, 1), E, E, ("Odd weapon", 1, 6)],
    ]))
    assert [(e.name, e.attrs) for e in entries] == [
        ("Cull's Shadow", {"perks": "Soulburn · Soulforge · Blades of Unmaking"}),
        ("One Thousand Voices", {"subtitle": "1KV", "perks": "Ahamkara's Eye · Unforeseen Repercussions", "catalyst": "Fall From Grace"}),
        ("Odd", {"perks": "A · B · C", "catalyst": "X · Y"}),
    ]


def test_exotic_weapons_row_with_only_column_0_is_a_weapon(sheet):
    entries = exotic_weapons.parse(sheet([
        [("Kinetic Slot Weapons", 1, 9)],
        [("Lonely Gun\n\nPerk", 1, 1)],
        [E, E, ("Stray note.", 1, 6)],
    ]))
    assert [(e.name, e.section, e.attrs, e.text) for e in entries] == [
        ("Lonely Gun", "Kinetic Slot Weapons", {"perks": "Perk"}, ""),
        ("Notes", "Kinetic Slot Weapons", {}, "Stray note."),
    ]


GAME_MECHANICS = [
    [("Go back to the top!", 1, 3), ("Game Mechanics", 1, 6)],
    ["", ("Table of Contents", 1, 6)],
    ["", "", "", "", ("Ability Tiers and Energy Gains", 1, 4)],
    ["", "", "", "", ("Activity Modifiers", 1, 4)],
    ["", "", "", "", ("Armor & Character Stats", 1, 4)],
    [],
    ["", "Ability Tiers", ("Ability Energy Generation", 1, 6)],
    ["", "", ("Ability Chunk Energy Gains are generally defined by the base cooldowns of all Abilities, in seconds.", 1, 6)],
    ["", "", ("Activity Modifiers", 1, 6)],
    ["", "", ("Chill Touch", 1, 3), ("Combatant Melee Attacks inflict Slow.", 1, 3)],
    ["", "", ("Grounded\n▲▲▲▲", 1, 3), ("While airborne: 100% increased damage taken.", 1, 3)],
    ["", "", ("Mobility Speeds", 1, 6)],
    ["", "Mobility Tier", "3", "4", "5"],
    ["", "Walk Speed [m/s]", "5.60", "5.80", "6.00"],
]


def test_game_mechanics(sheet):
    entries = game_mechanics.parse(sheet(GAME_MECHANICS))
    assert [(e.name, e.section) for e in entries] == [
        ("Ability Tiers", "Ability Tiers and Energy Gains"),
        ("Chill Touch", "Activity Modifiers"),
        ("Grounded", "Activity Modifiers"),
        ("Mobility Speeds", "Activity Modifiers"),
    ]
    assert entries[0].text.startswith("Ability Energy Generation\n\nAbility Chunk Energy Gains")
    assert entries[2].attrs == {"detail": "▲▲▲▲"}
    assert entries[3].text == ("| Mobility Tier | 3 | 4 | 5 |\n|---|---|---|---|\n"
                               "| Walk Speed [m/s] | 5.60 | 5.80 | 6.00 |")


GAME_MECHANICS_REAL = [
    [("Game Mechanics", 1, 12)],
    ["", ("Table of Contents", 1, 11)],
    ["", "", "", ("Activity Modifiers", 1, 4)],
    ["", "", "", ("Armor Charge", 1, 4)],
    ["", "", "", ("Armor & Character Stats", 1, 4)],
    ["", "", "", ("Heat Weapons (Blasters)\nBalanced Heat | Dynamic Heat", 1, 4)],
    [],
    ["", "", ("Activity Modifiers", 1, 10)],
    ["", "", ("Minor Negative | Modifiers that alter Combatant behavior.\n▲▲", 1, 10)],
    ["", "", ("Chill Touch", 1, 2), "", ("Combatant Melee Attacks inflict Slow.", 1, 7)],
    [],
    ["", "Armor Charges", ("Armor Charge", 1, 10)],
    ["", "", ("What are Armor Charges?", 1, 10)],
    ["", "", ("Armor Charges are a resource used by Armor Charge Mods, activating Passive Effects.", 1, 10)],
    [],
    ["", "Character Attributes", ("Character Attributes", 1, 10)],
    ["", "", ("Guardians, by default, have Tier 3 Mobility and T10 Resilience.", 1, 10)],
    [],
    ["", "Mobility In-Depth", "", "", "", ("Movement Speed", 1, 3), ("", 1, 4)],
    ["", "Mobility Tier", "3", "4", "5", ("", 1, 7)],
    ["", "Walk Speed\n[m/s]", "5.60", "5.80", "6.00", ("", 1, 7)],
    ["", "Sprint Speed", ("Base Movement Speed of 8 meters per second.", 1, 10)],
    ["", "", ("Titans and Warlocks have a baseline of 30 Mobility, Hunters have 100 Mobility.", 1, 5),
     ("Movement Speed Increases only affect GROUNDED Movement Speed, not airborne.", 1, 5)],
    [],
    ["", "Character Attributes", ("Armor Stats", 1, 10)],
    [],
    ["", "", "Melee", "", ("Grants Melee Ability Regeneration per point.", 1, 8)],
    ["", "Melee Stat", "0", "50", "100", ("", 1, 7)],
    ["", "Melee Damage", "0%", "", "30%", ("", 1, 7)],
    [],
    ["", "", ("Heat Weapons", 1, 10)],
    ["", "", ("Balanced Weapons Info", 1, 5), ("Dynamic Weapons Info", 1, 5)],
    ["", "", ("Low Heat Generation | Low Cooling Efficiency", 1, 5), ("High Heat Generation | High Cooling Efficiency", 1, 5)],
    ["", "", ("Rank Classification", 1, 2), ("Super Energy", 1, 3), ("Orb of Power", 1, 3), ("Super Energy", 1, 2)],
    ["", "", ("Tier 1 Combatant", 1, 2), ("0.60%", 1, 3), ("Reaper x1", 1, 3), ("0.80%", 1, 2)],
    ["", "", ("", 1, 2), ("", 1, 3), ("Siphon x2", 1, 3), ("3.75%", 1, 2)],
]


def test_game_mechanics_real_layout(sheet):
    entries = game_mechanics.parse(sheet(GAME_MECHANICS_REAL))
    assert [(e.section, e.name, e.attrs) for e in entries] == [
        ("Activity Modifiers", "Minor Negative", {"detail": "▲▲"}),
        ("Activity Modifiers", "Chill Touch", {"group": "Minor Negative"}),
        # A paragraph starting with "Armor Charge" is not a chapter.
        ("Armor Charge", "What are Armor Charges?", {}),
        # Header missing from the table of contents, attached by a shared word.
        ("Armor & Character Stats", "Character Attributes", {}),
        ("Armor & Character Stats", "Mobility In-Depth", {}),
        ("Armor & Character Stats", "Melee", {"group": "Armor Stats"}),
        ("Heat Weapons (Blasters)", "Heat Weapons", {}),
    ]
    by_name = {e.name: e for e in entries}
    assert by_name["Minor Negative"].text == "Modifiers that alter Combatant behavior."
    assert by_name["What are Armor Charges?"].text.startswith("Armor Charges are a resource")
    assert by_name["Character Attributes"].text.startswith("Guardians, by default")
    assert by_name["Mobility In-Depth"].text == (
        "Movement Speed\n\n"
        "| Mobility Tier | 3 | 4 | 5 |\n|---|---|---|---|\n"
        "| Walk Speed<br>[m/s] | 5.60 | 5.80 | 6.00 |\n"
        "| Sprint Speed | Base Movement Speed of 8 meters per second. |  |  |\n\n"
        "Titans and Warlocks have a baseline of 30 Mobility, Hunters have 100 Mobility.\n\n"
        "Movement Speed Increases only affect GROUNDED Movement Speed, not airborne.")
    assert by_name["Melee"].text == (
        "Grants Melee Ability Regeneration per point.\n\n"
        "| Melee Stat | 0 | 50 | 100 |\n|---|---|---|---|\n"
        "| Melee Damage | 0% |  | 30% |")
    assert by_name["Heat Weapons"].text == (
        "| Balanced Weapons Info | Dynamic Weapons Info |\n|---|---|\n"
        "| Low Heat Generation \\| Low Cooling Efficiency | High Heat Generation \\| High Cooling Efficiency |\n\n"
        "| Rank Classification | Super Energy | Orb of Power | Super Energy |\n|---|---|---|---|\n"
        "| Tier 1 Combatant | 0.60% | Reaper x1 | 0.80% |\n"
        "|  |  | Siphon x2 | 3.75% |")


def test_game_mechanics_header_only_switches_to_next_chapter(sheet):
    entries = game_mechanics.parse(sheet([
        [("Game Mechanics", 1, 12)],
        ["", ("Table of Contents", 1, 11)],
        ["", "", "", ("Armor Charge", 1, 4)],
        ["", "", "", ("Armor & Character Stats", 1, 4)],
        ["", "", "", ("Champions of the Darkness", 1, 4)],
        ["", "", "", ("Recovery Mechanics", 1, 4)],
        [],
        ["", "Armor Charges", ("Armor Charge", 1, 10)],
        [],
        ["", "Character Attributes", ("Character Attributes", 1, 10)],
        ["", "", ("Guardians, by default, have Tier 3 Mobility and T10 Resilience.", 1, 10)],
        [],
        ["", "Health and Shields | HP Recovery Mechanics", ("Health and Shields | HP Recovery Mechanics", 1, 10)],
        ["", "", ("Guardians possess, by default, 70 Health Points and 130 Shield Points in total.", 1, 10)],
    ]))
    assert [(e.section, e.name) for e in entries] == [
        ("Armor & Character Stats", "Character Attributes"),
        ("Armor & Character Stats", "Health and Shields | HP Recovery Mechanics"),
    ]


def test_game_mechanics_term_row_is_not_a_chapter(sheet):
    entries = game_mechanics.parse(sheet([
        [("Game Mechanics", 1, 12)],
        ["", ("Table of Contents", 1, 11)],
        ["", "", "", ("Activity Modifiers", 1, 4)],
        ["", "", "", ("Armor Charge", 1, 4)],
        [],
        ["", "", ("Activity Modifiers", 1, 10)],
        ["", "", ("Armor Charges", 1, 2), "", ("Some definition.", 1, 7)],
        ["", "", ("Chill Touch", 1, 2), "", ("Combatant Melee Attacks inflict Slow.", 1, 7)],
    ]))
    assert [(e.section, e.name, e.text) for e in entries] == [
        ("Activity Modifiers", "Armor Charges", "Some definition."),
        ("Activity Modifiers", "Chill Touch", "Combatant Melee Attacks inflict Slow."),
    ]
