"""Each parser on the real cached HTML (cache/compendium/raw/). Skipped when the cache is missing:
fill it with the compendium source's refresh.

These are canaries: they may fail after a forced refresh if the author changes the Sheet (values
changed, entries renamed or moved). Then update the parser and these checks."""
import pytest

from shell.core import paths
from shell.sources.compendium.parsers import TABS, run
from shell.sources.sheets.fetch import parse_tab_list
from shell.sources.sheets.grid import parse_grid

RAW = paths.ROOT / "cache" / "compendium" / "raw"  # the real cache, not the monkeypatched cache_dir()


def find(entries, name):
    e = next((e for e in entries if e.name == name), None)
    assert e is not None, f"{name} missing"
    return e


CHECKS = {}  # tab name -> function(entries) with assertions on known entries


def _exotic_armors(entries):
    cowl = find(entries, "Assassin's Cowl")
    assert cowl.section == "Hunter" and cowl.attrs["perk"] == "Vanishing Execution"
    classes = [e for e in entries if e.section in ("Hunter", "Titan", "Warlock")]
    assert {e.section for e in classes} == {"Hunter", "Titan", "Warlock"}
    assert all("perk" in e.attrs for e in classes)
    assert not any(e.name.startswith("Sect of") for e in classes)
    assert len({sum(e.section == s for e in classes) for s in ("Hunter", "Titan", "Warlock")}) == 1
    assert find(entries, "Sect of Force").section == "Aeon Sects"


CHECKS["Exotic Armors"] = _exotic_armors


def _exotic_class(entries):
    assassin = find(entries, "Spirit of the Assassin")
    assert assassin.section == "Class-agnostic Perks" and assassin.attrs["role"].startswith("left")
    assert find(entries, "Spirit of the Star-Eater").attrs["role"].startswith("right")
    assert find(entries, "Spirit of the Coyote").section == "Hunter-exclusive Perks"
    count = lambda s: sum(e.section == s for e in entries)
    assert count("Class-agnostic Perks") >= 6
    assert all(count(f"{c}-exclusive Perks") >= 10 for c in ("Hunter", "Titan", "Warlock"))
    assert any(e.name == "Notes" and "Prismatic" in e.text for e in entries)


CHECKS["Exotic Class"] = _exotic_class


def _armor_mods(entries):
    firepower = find(entries, "Firepower")
    assert firepower.section == "Arms" and firepower.attrs["energy"] == "3"
    assert {"Helmet", "Arms", "Chest", "Legs", "Class Item", "Raid Specific"} <= {e.section for e in entries}
    relay = find(entries, "Relay Defender")
    assert relay.attrs["activity"] == "Garden of Salvation" and relay.attrs["variant"]


CHECKS["Armor Mods"] = _armor_mods


def _weapon_perks(entries):
    assert find(entries, "Accelerated Heatsink").section == "Weapon Traits"
    assert any("↑" in e.text for e in entries)
    hr = find(entries, "Harmonic Resonance")
    assert hr.section == "Origin Traits"
    assert hr.attrs["source"] == "Root of Nightmares · Raid / +Epochal Integration"
    assert "Shiny Renegade Drops" in find(entries, "Accelerated Assault").attrs["source"]
    sections = [e.section for e in entries]
    assert set(sections) >= {"Weapon Traits", "Weapon Mods", "Intrinsic Traits", "Heavy Crossbow Information",
                             "Glaive Information", "Sword Guard Information", "Origin Traits"}
    note_sections = [e.section for e in entries if e.name == "Notes"]
    assert len(note_sections) == len(set(note_sections))


CHECKS["Weapon Perks"] = _weapon_perks


def _armor_perks(entries):
    aion = find(entries, "AION Renewal")
    assert aion.attrs["2 pieces"] == "Force Converter" and aion.attrs["4 pieces"] == "Reactive Booster"
    assert "Kepler" in aion.attrs["source"]
    assert find(entries, "Crystocrene").attrs["crucible"] == "4 pieces disabled"
    sets = [e for e in entries if e.name != "Notes"]
    for e in sets:
        assert "2 pieces" in e.attrs and "4 pieces" in e.attrs, f"{e.name}: incomplete 2/4 pieces bonus"
    assert len({e.name for e in sets}) == len(sets)


CHECKS["Armor Perks"] = _armor_perks


def _artifact_perks(entries):
    assert find(entries, "Press The Advantage").section.startswith("Encrypted Data Disk")
    first = find(entries, "Press The Advantage")
    assert first.attrs["order"] == "1" and "column" in first.attrs
    perks = [e for e in entries if e.name != "Notes"]
    assert all(e.text for e in perks), "perk without description"
    assert len({e.section for e in perks}) >= 7
    assert any("elements" in e.attrs for e in perks if e.attrs["order"] == "2")
    for section in {e.section for e in perks}:
        assert len([e for e in perks if e.section == section]) % 3 == 0, f"{section}: incomplete perks"


CHECKS["Artifact Perks"] = _artifact_perks


SUBCLASS_VARIANTS = ("Touch of Thunder", "Touch of Flame", "Touch of Winter", "Chaos Accelerant", "Mindspun Invocation")


def _grenades_complete(entries):
    """Every grenade without "info" must be a known variant, a prismatic grenade or Handheld Supernova:
    a new variant name (not recognized, so taken for a grenade) fails here."""
    for e in entries:
        if e.section.split(" — ")[-1] != "Grenade Abilities" or e.name == "Notes" or "info" in e.attrs:
            continue
        variant = any(e.name.endswith(f"({v})") or f"({v}, " in e.name for v in SUBCLASS_VARIANTS)
        assert variant or e.text.startswith("Prismatic Grenade") or e.name.startswith("Handheld Supernova"), \
            f"grenade without info: {e.name}"


def _prismatic(entries):
    awakening = find(entries, "Awakening")
    assert awakening.section == "Fragments" and awakening.attrs["stats"] == "+10 Health"
    assert {"Hunter — Aspects", "Titan — Aspects", "Warlock — Aspects"} <= {e.section for e in entries}
    _grenades_complete(entries)


def _arc(entries):
    assert find(entries, "Flashbang Grenade (Touch of Thunder)").section == "Grenade Abilities"
    assert "Base Cooldown" in find(entries, "Arcbolt Grenade").attrs["info"]
    _grenades_complete(entries)


def _class_abilities(entries):
    assert find(entries, "Acrobat's Dodge").section == "Hunter — Abilities"
    assert find(entries, "Phoenix Dive").section == "Warlock — Abilities"


def _subclass(entries):
    sections = {e.section.split(" — ")[-1] for e in entries}
    assert {"Fragments", "Aspects", "Super Abilities"} <= sections
    _grenades_complete(entries)


CHECKS["Prismatic"] = _prismatic


def _exotic_weapons(entries):
    ace = find(entries, "Ace of Spades")
    assert ace.section == "Kinetic Slot Weapons" and "Memento Mori" in ace.attrs["perks"]
    assert len({e.section for e in entries if e.name != "Notes"}) >= 3
    notes = find(entries, "Notes")
    assert notes.section == "Exotic Weapons" and "NON-ENHANCED" in notes.text
    find(entries, "Ergo Sum (Arc Element)")
    assert find(entries, "D.A.R.C.I.").attrs["perks"] == "Personal Assistant · Target Acquired"
    names = [e.name for e in entries if e.name != "Notes"]
    assert len(names) == len(set(names))


def _game_mechanics(entries):
    assert find(entries, "Chill Touch").section == "Activity Modifiers"
    assert any(e.text.startswith("|") or "\n|" in e.text for e in entries)  # at least one table
    assert find(entries, "Character Attributes").section == "Armor & Character Stats"
    health = find(entries, "Health")
    assert health.attrs.get("group") == "Armor Stats" and "| Health Stat | 0 |" in health.text
    assert "Armor Charges are a resource" in find(entries, "What are Armor Charges?").text
    assert find(entries, "Caltrops").section == "Combatant Information"
    sections = list(dict.fromkeys(e.section for e in entries))
    assert sections == [
        "Ability Tiers and Energy Gains", "Activity Modifiers", "Armor Charge", "Armor & Character Stats",
        "Champions of the Darkness", "Combatant Information", "Heat Weapons (Blasters)", "Super Ability Energy",
    ]
    assert find(entries, "Mobility In-Depth").section == "Armor & Character Stats"
    super_energy = find(entries, "Super Energy from Kills, Orbs of Power, and Other Sources.")
    assert "\n| Tier 1 Combatant | 0.60% | Reaper x1 \\| Firepower x1 \\| Heavy Handed x1 | 0.80% |\n" in super_energy.text


CHECKS["Exotic Weapons"] = _exotic_weapons
CHECKS["Game Mechanics"] = _game_mechanics
CHECKS["Arc"] = _arc
CHECKS["Class Abilities"] = _class_abilities
for _tab in ("Solar", "Void", "Stasis", "Strand"):
    CHECKS[_tab] = _subclass


def _gids():
    if not (RAW / "_tabs.html").exists():
        return {}
    return dict(parse_tab_list((RAW / "_tabs.html").read_text(encoding="utf-8")))


@pytest.mark.parametrize("tab", sorted(TABS))
def test_live(tab):
    if not (RAW / "_tabs.html").exists():
        pytest.skip("cache missing: run the compendium source's refresh")
    gid = _gids().get(tab)
    if gid is None:
        pytest.fail(f"tab {tab!r} missing from the tab list")
    raw = RAW / f"{gid}.html"
    if not raw.exists():
        pytest.skip("cache missing: run the compendium source's refresh")
    slug, module = TABS[tab]
    entries = run(tab, module, parse_grid(raw.read_text(encoding="utf-8")))
    CHECKS.get(tab, lambda e: None)(entries)
