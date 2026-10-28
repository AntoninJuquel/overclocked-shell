"""Transfers (vault ↔ characters, character → character through the vault) and postmaster pulls."""
from typing import Callable

from shell.core.bungie import BungieApiError
from shell.engines.account import CLASS_TYPE
from shell.engines.actions import describe
from shell.engines.locking import clean_ids

TRANSFER = "/Destiny2/Actions/Items/TransferItem/"


def _leg(actions, loc: dict, character_id: str, to_vault: bool) -> None:
    actions.post(TRANSFER, {"itemReferenceHash": loc["itemHash"], "stackSize": 1, "transferToVault": to_vault,
                            "itemId": loc["itemId"], "characterId": character_id})
    loc["where"], loc["characterId"] = ("vault", None) if to_vault else ("inventory", character_id)


def move(actions, locations: dict, item_id: str, target: str | None, requested: set[str],
         bucket_of: Callable[[int], int]) -> list[str]:
    loc, notes = locations[item_id], []
    if loc["where"] == "inventory":
        _leg(actions, loc, loc["characterId"], True)
    if target is None:
        return notes
    try:
        _leg(actions, loc, target, False)
    except BungieApiError as e:
        if e.error_code != 1642:
            raise
        bucket = bucket_of(loc["itemHash"])
        victim = next((v for v in locations.values() if v["characterId"] == target and v["where"] == "inventory"
                       and v["itemId"] not in requested and bucket_of(v["itemHash"]) == bucket), None)
        if not victim:
            raise
        _leg(actions, victim, target, True)
        notes.append(f"made room: sent {victim['name']} to the vault")
        _leg(actions, loc, target, False)
    return notes


def target_character(class_of: dict, to: str) -> str | None:
    to = to.lower()
    if to == "vault":
        return None
    cid = next((c for c, t in class_of.items() if t == CLASS_TYPE.get(to)), None)
    if cid is None:
        raise BungieApiError(f"No {to} on this account.")
    return cid


def transfer(actions, locations: dict, class_of: dict, item_ids: list[str], to: str, dry_run: bool,
             bucket_of: Callable[[int], int]) -> dict:
    target, to = target_character(class_of, to), to.lower()
    ids = clean_ids(item_ids)
    items, moved = [], 0
    for item_id in ids:
        loc = locations.get(item_id)
        entry = {"itemId": item_id, "name": loc["name"] if loc else None}
        items.append(entry)
        if not loc:
            entry["result"] = "not found"
        elif loc["where"] == "equipped":
            entry["result"] = "equipped: unequip it first"
        elif loc["where"] == "postmaster":
            entry["result"] = "in the postmaster: pull it first"
        elif (target is None and loc["where"] == "vault") or (target and loc["characterId"] == target):
            entry["result"] = "already there"
        elif dry_run:
            entry["result"] = f"would move to {to}"
        else:
            try:
                notes = move(actions, locations, item_id, target, set(ids), bucket_of)
                entry["result"], moved = f"moved to {to}", moved + 1
                if notes:
                    entry["notes"] = notes
            except BungieApiError as e:
                entry["result"] = f"failed: {describe(e)}"
    return {"dry_run": dry_run, "moved": moved, "items": items}


def pull_postmaster(actions, locations: dict, character_id: str, item_ids: list[str] | None, pull_all: bool,
                    dry_run: bool) -> dict:
    waiting = [l for l in locations.values() if l["where"] == "postmaster" and l["characterId"] == character_id]
    if not item_ids and not pull_all:
        return {"postmaster": [{"itemId": l["itemId"], "name": l["name"], "quantity": l["quantity"]}
                               for l in waiting]}
    wanted = set(clean_ids(item_ids or []))
    items, pulled = [], 0
    for loc in waiting:
        if item_ids and loc["itemId"] not in wanted:
            continue
        entry = {"itemId": loc["itemId"], "name": loc["name"]}
        items.append(entry)
        if dry_run:
            entry["result"] = "would pull"
            continue
        try:
            actions.post("/Destiny2/Actions/Items/PullFromPostmaster/", {
                "itemReferenceHash": loc["itemHash"], "stackSize": loc["quantity"],
                "itemId": "0" if loc["itemId"].startswith("pm:") else loc["itemId"], "characterId": character_id})
            entry["result"], pulled = "pulled", pulled + 1
        except BungieApiError as e:
            entry["result"] = f"failed: {describe(e)}"
    return {"dry_run": dry_run, "pulled": pulled, "items": items}
