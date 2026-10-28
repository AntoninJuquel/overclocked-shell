"""DIM loadout link: https://app.destinyitemmanager.com/loadouts?loadout=<url-encoded Loadout JSON>.

DIM decodes it itself (src/app/loadout/loadout-share/loadout-import.ts, decodeUrlLoadout): no API key, no
short link. Opening it shows the loadout in DIM; nothing is applied until the player chooses to.
"""
import json
from urllib.parse import quote

BASE = "https://app.destinyitemmanager.com/loadouts"
MAX_LENGTH = 8000  # browsers and chat apps accept this much; beyond, the notes go first


def _url(loadout):
    return f"{BASE}?loadout={quote(json.dumps(loadout, ensure_ascii=False, separators=(',', ':')), safe='')}"


def url(loadout: dict) -> tuple[str, list[str]]:
    """(link, warnings)."""
    link, warnings = _url(loadout), []
    if len(link) > MAX_LENGTH and loadout.get("notes"):
        link = _url({k: v for k, v in loadout.items() if k != "notes"})
        warnings.append("link too long: notes left out")
    if len(link) > MAX_LENGTH:
        warnings.append(f"link is {len(link)} characters: it may be refused or cut by some apps")
    return link, warnings
