"""The inventory snapshot refresh_inventory saves (profile/inventory/<kind>.json), read by build tools."""
import json
from datetime import datetime, timezone

from shell.core import paths


def read_snapshot(kind: str) -> tuple[list[dict], str]:
    """(rows, ISO time the snapshot was taken) for kind "armor" or "weapons"."""
    file = paths.profile_dir() / "inventory" / f"{kind}.json"
    if not file.exists():
        raise FileNotFoundError(f"No {kind} snapshot. Call refresh_inventory first.")
    taken = datetime.fromtimestamp(file.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    return json.loads(file.read_text(encoding="utf-8")), taken
