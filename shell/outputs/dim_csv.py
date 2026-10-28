"""DIM tags and notes CSV (DIM: Settings > Spreadsheets > Import).

DIM's format (src/app/inventory/spreadsheets.ts, importTagsNotesFromCsv): header with Id, Hash, Tag, Notes.
`Tag` is keep / junk / favorite / infuse / archive (any other value clears the tag); `Notes` REPLACES the
existing note (empty = erased), truncated to 1024 characters.
"""
import csv
from pathlib import Path

TAGS = {"KEEP": "keep", "JUNK": "junk"}
NOTE_PREFIX = "shell: "
MAX_NOTE = 1024


def note_for(row: dict) -> str:
    """Short note: the triage reason, plus the set and the wishlist grade when they exist."""
    parts = [row["reason"]]
    if row.get("set"):
        parts.append(f"set {row['set']}")
    grade = row.get("grade")
    if grade and grade not in row["reason"]:  # god rolls already carry the grade in their reason
        parts.append(f"wishlist {grade}")
    return (NOTE_PREFIX + " · ".join(parts))[:MAX_NOTE]


def rows(triaged: list[dict], notes: bool = True) -> list[dict]:
    return [{"Id": str(r["itemId"]), "Hash": str(r["itemHash"]), "Tag": TAGS[r["decision"]],
             "Notes": note_for(r) if notes else ""} for r in triaged]


def write(path: Path, dim_rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["Id", "Hash", "Tag", "Notes"])
        w.writeheader()
        w.writerows(dim_rows)
