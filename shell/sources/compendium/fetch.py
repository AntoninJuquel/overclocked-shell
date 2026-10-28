"""The compendium's public Google Sheet, with its HTML cached in cache/compendium/raw/."""
from pathlib import Path

from shell.core import paths
from shell.sources.sheets.fetch import SheetSource

SHEET = "1WaxvbLx7UoSZaBqdFr1u32F2uWVLo-CJunJB4nlGUE4"


def folder() -> Path:
    """Rendered .md files; raw HTML in raw/ (one file per gid)."""
    return paths.cache_dir() / "compendium"


def sheet() -> SheetSource:
    return SheetSource(SHEET, folder() / "raw")
