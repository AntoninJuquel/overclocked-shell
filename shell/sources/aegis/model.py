"""Shared types: a parsed tab and one tab's result for the index."""
from dataclasses import dataclass, field


@dataclass
class Table:
    tab: str                 # tab name (the config's)
    columns: list            # names of the kept columns, in Sheet order
    groups: dict             # column -> band above it ("PERKS", "ANALYSIS"...), "" otherwise
    rows: list               # one entry per row: {"_name", "_section", column: text}
    legend: dict = field(default_factory=dict)  # KEY block: symbol or tier -> meaning
    hidden_rows: int = 0     # rows hidden by the author, missing from the public view


@dataclass
class TabResult:
    sheet: str               # Sheet title ("Endgame Analysis")
    sheet_key: str           # "endgame", "boss"
    tab: str
    slug: str
    rows: int                # rows written (or kept)
    fetched: str | None      # fetch date of the data on disk, None if none
    updated: str | None = None  # date updated by Aegis (Status tab), if known
    ok: bool = True
    hidden_rows: int = 0
    note: str = ""
