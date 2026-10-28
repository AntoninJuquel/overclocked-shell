"""Lock and unlock items (triage keeps good gear locked; nothing is ever dismantled)."""
import re

from shell.core.bungie import BungieApiError
from shell.engines.actions import describe


def clean_ids(item_ids: list[str]) -> list[str]:
    return list(dict.fromkeys(re.sub(r"[\"'\s]", "", i) for i in item_ids))


def set_lock(actions, locations: dict, class_of: dict, item_ids: list[str], locked: bool, dry_run: bool) -> dict:
    verb = "locked" if locked else "unlocked"
    first_character = next(iter(class_of))
    items, changed = [], 0
    for item_id in clean_ids(item_ids):
        loc = locations.get(item_id)
        if not loc or item_id.startswith("pm:"):  # uninstanced postmaster stacks can't be locked
            items.append({"itemId": item_id, "name": loc["name"] if loc else None, "result": "not found"})
            continue
        entry = {"itemId": item_id, "name": loc["name"]}
        if loc["locked"] == locked:
            entry["result"] = f"already {verb}"
        elif dry_run:
            entry["result"] = f"would {verb[:-2]}"
        else:
            try:
                actions.post("/Destiny2/Actions/Items/SetLockState/", {
                    "state": locked, "itemId": item_id, "characterId": loc["characterId"] or first_character})
                entry["result"], changed = verb, changed + 1
            except BungieApiError as e:
                entry["result"] = f"failed: {describe(e)}"
        items.append(entry)
    return {"dry_run": dry_run, "changed": changed, "items": items}
