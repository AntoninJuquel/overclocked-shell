"""Equip items on a character, moving them there first."""
from typing import Callable

from shell.core.bungie import BungieApiError
from shell.engines.actions import ERROR_NAMES, describe
from shell.engines.inventory import CLASS_NAME
from shell.engines.locking import clean_ids
from shell.engines.moving import failure, move

EQUIP = "/Destiny2/Actions/Items/EquipItems/"
EXOTIC_CLASH = 1641


def _equip_call(actions, ids: list[str], character_id: str) -> dict[str, int]:
    response = actions.post(EQUIP, {"itemIds": ids, "characterId": character_id}) or {}
    return {str(r["itemInstanceId"]): r["equipStatus"] for r in response.get("equipResults", [])}


def equip(actions, locations: dict, class_of: dict, character_id: str, item_ids: list[str], dry_run: bool,
          bucket_of: Callable[[int], int]) -> dict:
    who = CLASS_NAME[class_of[character_id]].lower()
    ids = clean_ids(item_ids)
    moves, to_equip = [], []
    for item_id in ids:
        loc = locations.get(item_id)
        entry = {"itemId": item_id, "name": loc["name"] if loc else None}
        moves.append(entry)
        if not loc:
            entry["result"] = "not found"
        elif loc["where"] == "postmaster":
            entry["result"] = "in the postmaster: pull it first"
        elif loc["characterId"] == character_id:
            entry["result"] = f"already on {who}" + (" (equipped)" if loc["where"] == "equipped" else "")
            to_equip.append(item_id)
        elif loc["where"] == "equipped":
            entry["result"] = "equipped on another character: unequip it there first"
        else:
            route = f"vault -> {who}" if loc["where"] == "vault" else f"other character -> vault -> {who}"
            if dry_run:
                entry["result"] = f"would move {route}"
                to_equip.append(item_id)
                continue
            notes, started = [], loc["where"]
            try:
                move(actions, locations, item_id, character_id, set(ids), bucket_of, notes)
                entry["result"] = f"moved {route}"
                to_equip.append(item_id)
            except BungieApiError as e:
                entry["result"] = "move " + failure(e, started, loc)
            if notes:
                entry["notes"] = notes

    names = {i: locations[i]["name"] for i in to_equip}
    if dry_run or not to_equip:
        return {"dry_run": dry_run, "equipped": 0, "moves": moves,
                "equip": [{"itemId": i, "name": names[i], "result": "would equip"} for i in to_equip]}
    try:
        statuses = _equip_call(actions, to_equip, character_id)
        clashes = [i for i in to_equip if statuses.get(i) == EXOTIC_CLASH]
        if clashes:  # the clashing exotic is often being replaced by another item of this same call
            statuses.update(_equip_call(actions, clashes, character_id))
    except BungieApiError as e:
        return {"dry_run": False, "equipped": 0, "moves": moves,
                "equip": [{"itemId": i, "name": names[i], "result": f"not equipped: {describe(e)}"}
                          for i in to_equip]}
    results = []
    for i in to_equip:
        code = statuses.get(i)
        result = "equipped" if code == 1 else f"not equipped: {ERROR_NAMES.get(code, f'error {code}')}"
        results.append({"itemId": i, "name": names[i], "result": result})
    return {"dry_run": False, "equipped": sum(r["result"] == "equipped" for r in results), "moves": moves,
            "equip": results}
