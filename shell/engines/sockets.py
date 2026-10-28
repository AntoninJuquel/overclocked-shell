"""Socket changes (armor and weapon mods, subclass aspects / fragments, artifact perks) with InsertSocketPlugFree."""
import re
from typing import Callable

from shell.core.bungie import BungieApiError
from shell.engines.actions import describe
from shell.engines.loadout import item_name

INSERT = "/Destiny2/Actions/Items/InsertSocketPlugFree/"
SOCKET_GAP = 0.6  # Bungie allows 2 socket actions per second per user
TRY_NEXT_HASH = {1676, 1680}
NOT_IN_ORBIT = 1634
EMPTY = re.compile(r"^empty", re.I)
EMPTY_OR_DEFAULT = re.compile(r"^(empty|default)", re.I)


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def candidates(item_def: dict, reusable: dict, plug_sets: dict, plug_set_def: Callable[[int], dict]) -> list[list[int]]:
    """Every plug each socket can take: live options, unlocked plug-set items, then the definition's own lists."""
    out = []
    for i, entry in enumerate(item_def.get("sockets", {}).get("socketEntries", [])):
        hashes = [o["plugItemHash"] for o in reusable.get(str(i), [])]
        for key in ("reusablePlugSetHash", "randomizedPlugSetHash"):
            plug_set = entry.get(key)
            if plug_set:
                hashes += [o["plugItemHash"] for o in plug_sets.get(str(plug_set), []) if o.get("canInsert") is not False]
                hashes += [p["plugItemHash"] for p in (plug_set_def(plug_set) or {}).get("reusablePlugItems", [])]
        hashes += [p["plugItemHash"] for p in entry.get("reusablePlugItems", [])]
        hashes.append(entry.get("singleInitialItemHash"))
        out.append([h for h in dict.fromkeys(hashes) if h])
    return out


def plan_item(item_id: str, character_id: str, name: str, current: list[int], cands: list[list[int]],
              reusable: dict, requests: list, defs: dict, force: bool) -> tuple[list[dict], list[str]]:
    requested = [(r, None) if isinstance(r, str) else (r["name"], r.get("socketIndex")) for r in requests]
    wanted = {norm(n) for n, _ in requested}
    current_name = lambda i: item_name(defs, current[i]) if current[i] else ""  # noqa: E731
    taken: set[int] = set()
    plans, notes = [], []
    for plug, index in requested:
        key = norm(plug)
        matching = {i: [h for h in hs if norm(item_name(defs, h)) == key] for i, hs in enumerate(cands)}
        matching = {i: hs for i, hs in matching.items() if hs}
        if index is not None:
            if index not in matching:
                notes.append(f'socket {index} can\'t take "{plug}"')
                continue
            matching = {index: matching[index]}
        if not matching:
            notes.append(f'no socket takes "{plug}" (check spelling or unlocks)')
            continue
        holder = None if force else next((i for i in matching if i not in taken and current[i] in matching[i]), None)
        if holder is not None:
            taken.add(holder)
            notes.append(f"{plug} already in socket {holder}")
            continue
        free = [i for i in matching if i not in taken]
        pick = next((i for i in free if not current[i] or EMPTY_OR_DEFAULT.match(current_name(i))), None)
        if pick is None:
            pick = next((i for i in free if norm(current_name(i)) not in wanted), None)
        if pick is None and EMPTY.match(plug) and free:
            pick = free[0]
        if pick is None:
            notes.append(f'no free socket left for "{plug}"')
            continue
        taken.add(pick)
        live = [o["plugItemHash"] for o in reusable.get(str(pick), []) if o.get("canInsert") is not False]
        hashes = list(dict.fromkeys([h for h in live if h in matching[pick]] + matching[pick]))
        plans.append({"itemId": item_id, "characterId": character_id, "name": name, "socketIndex": pick,
                      "from": current_name(pick) or "(empty)", "to": item_name(defs, hashes[0]), "hashes": hashes})
    plans.sort(key=lambda p: not EMPTY.match(p["to"]))  # free sockets before filling them
    return plans, notes


def apply(actions, plans: list[dict]) -> list[str]:
    results = []
    for plan in plans:
        if results and results[-1].startswith(("not attempted", "failed: character not in orbit")):
            results.append("not attempted: go to orbit")
            continue
        error = None
        for h in plan["hashes"]:
            try:
                actions.post(INSERT, {"plug": {"socketIndex": plan["socketIndex"], "socketArrayType": 0,
                                               "plugItemHash": h},
                                      "itemId": plan["itemId"], "characterId": plan["characterId"]}, gap=SOCKET_GAP)
                error = None
                break
            except BungieApiError as e:
                error = e
                actions.sleep(SOCKET_GAP)
                if e.error_code not in TRY_NEXT_HASH:
                    break
        results.append("done" if error is None else f"failed: {describe(error)}")
    return results
