"""Aegis's two Sheets: tabs kept, their key, their checks and the tabs ignored."""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TabSpec:
    name: str                  # tab name in the Sheet (or display name if `pattern`)
    slug: str                  # name of the .md / .json files
    anchors: tuple             # headers that identify the header row (all present)
    key: tuple                 # column(s) that name a row (first line of each cell)
    min_rows: int              # fewer rows = layout changed
    pattern: str | None = None  # regular expression for the name when it carries a season
    weapon_type: str | None = None  # weapon type from the destiny-zen export (weapon tabs)
    tier: str | None = "Tier"   # tier column compared from one version to the next (None: none)
    rank: str | None = None     # rank column compared from one version to the next

    def matches(self, tab_name):
        return re.fullmatch(self.pattern or re.escape(self.name), tab_name.strip(), re.IGNORECASE) is not None


@dataclass(frozen=True)
class SheetConfig:
    key: str        # "endgame", "boss": subfolder of cache/aegis/
    title: str
    id: str         # Google Sheets id
    tabs: tuple     # TabSpec, in processing order
    ignored: tuple  # regular expressions of tabs deliberately not processed

    def spec_for(self, tab_name):
        return next((t for t in self.tabs if t.matches(tab_name)), None)

    def is_ignored(self, tab_name):
        return any(re.fullmatch(p, tab_name.strip(), re.IGNORECASE) for p in self.ignored)


def _weapon(name, slug, weapon_type, min_rows):
    return TabSpec(name, f"weapons-{slug}", ("Name", "Tier"), ("Name",), min_rows, weapon_type=weapon_type, rank="#")


WEAPON_TABS = (
    _weapon("Autos", "autos", "Auto Rifle", 30),
    _weapon("Bows", "bows", "Combat Bow", 12),
    _weapon("HCs", "hcs", "Hand Cannon", 35),
    _weapon("Pulses", "pulses", "Pulse Rifle", 30),
    _weapon("Scouts", "scouts", "Scout Rifle", 25),
    _weapon("Sidearms", "sidearms", "Sidearm", 20),
    _weapon("SMGs", "smgs", "Submachine Gun", 25),
    _weapon("BGLs", "bgls", "Grenade Launcher", 15),
    _weapon("Fusions", "fusions", "Fusion Rifle", 20),
    _weapon("Glaives", "glaives", "Glaive", 6),
    _weapon("Shotguns", "shotguns", "Shotgun", 30),
    _weapon("Snipers", "snipers", "Sniper Rifle", 30),
    _weapon("Rocket Sidearms", "rocket-sidearms", "Sidearm", 4),
    _weapon("Traces", "traces", "Trace Rifle", 6),
    _weapon("HGLs", "hgls", "Grenade Launcher", 12),
    _weapon("LFRs", "lfrs", "Linear Fusion Rifle", 10),
    _weapon("LMGs", "lmgs", "Machine Gun", 18),
    _weapon("Rockets", "rockets", "Rocket Launcher", 18),
    _weapon("Swords", "swords", "Sword", 20),
    _weapon("Other", "other", None, 4),
)

ENDGAME = SheetConfig(
    "endgame", "Endgame Analysis", "1JM-0SlxVDAi-C6rGVlLxa-J1WGewEeL8Qvq4htWZHhY",
    (
        TabSpec("Status", "status", ("TAB", "UPDATED"), ("TAB",), 20, tier=None),
        *WEAPON_TABS,
        TabSpec("Exotic Weapons", "exotic-weapons", ("Name", "Tier"), ("Name",), 100),
        TabSpec("Perks", "perks", ("Name", "Tier"), ("Name",), 150, rank="#"),
        TabSpec("Origin Traits", "origin-traits", ("Name", "Tier"), ("Name",), 50, rank="#"),
        TabSpec("Set Bonuses", "set-bonuses", ("Set", "Bonus", "Tier"), ("Set",), 60, rank="#"),
        TabSpec("Artifact Mods", "artifact-mods", ("Artifact", "Mod"), ("Mod",), 80, tier="Tier (ANALYSIS)"),
        TabSpec("Fragments", "fragments", ("Name", "Subclass", "Tier"), ("Name",), 60, rank="#"),
        TabSpec("Aspects", "aspects", ("Name", "Subclass", "Tier"), ("Name",), 35, rank="#"),
        TabSpec("Subclasses", "subclasses", ("Class", "Super", "Tier"), ("Class", "Super"), 12),
        TabSpec("Shopping List", "shopping-list", ("Name", "Priority"), ("Name",), 40, tier="Priority"),
        TabSpec("Archetypes", "archetypes", ("Weapon", "Frame"), ("Weapon", "Frame"), 50),
        TabSpec("Encounters", "encounters", ("Activity", "Encounter", "Tier"), ("Activity", "Encounter"), 30),
    ),
    ("Changelog", "Experimental", r".*\(ignore\)"),
)

BOSS = SheetConfig(
    "boss", "Boss Damage", "1_5wtBjRYHHxuF4oJKDb_iOGZs-wTkzB6RYbnyNLbuz4",
    (
        # "Type" also exists under HEALTHBAR: both columns take the name of their band
        TabSpec("Weapons", "weapons", ("Type", "Subtype"), ("Type (INFORMATION)", "Subtype"), 250, tier=None),
        TabSpec("Abilities", "abilities", ("Type", "Subtype"), ("Type", "Subtype"), 150,
                pattern=r"Abilit?i?es|Abilties", tier=None),
        TabSpec("Sustained", "sustained", ("Name", "DPS"), ("Name",), 150, tier=None),
        TabSpec("Swap", "swap", ("Name", "true DPS"), ("Name",), 120, tier=None),
        TabSpec("Bosses", "bosses", ("Activity", "Boss"), ("Activity", "Boss"), 40, tier=None),
        TabSpec("Fireteam", "fireteam", ("Category", "Name", "Boss"), ("Name", "Specifications"), 40,
                pattern=r"Fireteam( \(S\d+\))?", tier=None),
        TabSpec("Pack Hunter", "pack-hunter", ("Modifiers", "Weapon"), ("Modifiers",), 4, tier=None),
        TabSpec("Bolt Charge", "bolt-charge", ("Source",), ("Source",), 12, tier=None),
    ),
    ("Home", "Changelog", r".*\(old\)", r"Graphing.*", "Historical", "Testing"),
)

SHEETS = {s.key: s for s in (ENDGAME, BOSS)}


def weapon_tabs():
    """Legendary weapon tabs of the Endgame Analysis (one per weapon type)."""
    return list(WEAPON_TABS)
