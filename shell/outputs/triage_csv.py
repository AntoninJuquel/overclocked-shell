"""Readable triage CSV (`;`, utf-8-sig so Excel opens it): one row per item with its decision and reason."""
import csv
from pathlib import Path

STATS = ["Weapons", "Health", "Class", "Grenade", "Super", "Melee"]
HEADERS = {
    "armor": ["Decision", "Class", "Slot", "Name", "Rarity", "Tier", "Set", "Set bonus", "Archetype", "Profile",
              "Total", "MW stats (W/H/C/G/S/M)", "MW total", "Locked", "Location", "Reason", "Id", "Hash"],
    "weapons": ["Decision", "Name", "Type", "Rarity", "Tier", "Crafted", "Wishlist grade", "Traits", "Locked",
                "Location", "Reason", "Id", "Hash"],
}


def _yes(flag):
    return "yes" if flag else ""


def _armor(i):
    return [i["decision"], i["classType"], i["slot"], i["name"], i["rarity"], i["gearTier"], i["set"] or "",
            " | ".join(i["setBonus"]), i["archetype"] or "", i["profile"], i["total"],
            "/".join(str(i["mw"][k]) for k in STATS), i["mwTotal"], _yes(i["locked"]), i["location"], i["reason"],
            i["itemId"], i["itemHash"]]


def _weapon(w):
    traits = ((w["frame"],) if w["rarity"] == "Exotic" else ()) + tuple(w["traits"])
    return [w["decision"], w["name"], w["type"], w["rarity"], w["gearTier"], _yes(w["crafted"]), w["grade"],
            " | ".join(traits), _yes(w["locked"]), w["location"], w["reason"], w["itemId"], w["itemHash"]]


def write(path: Path, kind: str, rows: list[dict]) -> None:
    if kind == "armor":
        rows, line = sorted(rows, key=lambda x: (x["decision"], x["classType"], x["slot"], x["set"] or "", x["name"])), _armor
    else:
        rows, line = sorted(rows, key=lambda x: (x["decision"], x["type"], x["name"])), _weapon
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(HEADERS[kind])
        w.writerows(line(r) for r in rows)
