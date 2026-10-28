"""Shared types: a compendium entry, a tab's result, the parsing error."""
from dataclasses import dataclass, field

from shell.sources.sheets.errors import ParseError  # noqa: F401 (re-export)


@dataclass
class Entry:
    name: str                                  # "Assassin's Cowl", "Firepower", "Awakening"
    section: str                               # ## grouping in the .md: "Hunter", "Fragments"…
    attrs: dict = field(default_factory=dict)  # short metadata: perk, energy, stats, source…
    text: str = ""                             # description, line breaks kept


@dataclass
class TabResult:
    tab: str               # tab name in the Sheet
    slug: str              # .md file name without extension
    entries: int           # number of entries written (or kept)
    date: str | None       # date of the data on disk (YYYY-MM-DD), None if none
    ok: bool = True
    hidden_rows: int = 0   # rows hidden by the author, missing from the public view
    note: str = ""         # detail shown in the index (error, cache…)
