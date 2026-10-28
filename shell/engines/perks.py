"""Choose weapon perks among the options each column rolled (crafted or multi-option weapons)."""
from shell.engines.sockets import norm


def plan_perks(row: dict, character_id: str, select: list[str]) -> tuple[list[dict], list[str]]:
    used: set[int] = set()
    plans, notes = [], []
    for wanted in select:
        hits = [(c, o) for c in row["columns"] for o in c["options"] if norm(o["name"]) == norm(wanted)]
        if not hits:
            notes.append(f'"{wanted}" is not one of its rolled options')
            continue
        if len({c["socketIndex"] for c, _ in hits}) > 1:
            notes.append(f'"{wanted}" appears in more than one column')
            continue
        column, opt = sorted(hits, key=lambda hit: not hit[1]["enhanced"])[0]
        if column["socketIndex"] in used:
            notes.append(f'"{wanted}" shares the {column["label"]} column with another requested perk')
            continue
        used.add(column["socketIndex"])
        if opt["hash"] == column["selectedHash"]:
            notes.append(f'"{wanted}" is already selected')
        elif not opt["canInsert"]:
            notes.append(f'"{wanted}" can\'t be selected right now (Bungie)')
        else:
            plans.append({"itemId": row["itemId"], "characterId": character_id, "name": row["name"],
                          "column": column["label"], "socketIndex": column["socketIndex"],
                          "from": column["selected"], "to": opt["name"], "hashes": [opt["hash"]]})
    return plans, notes
