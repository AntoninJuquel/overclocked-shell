"""Ultimate Bravery: a random, rule-abiding build from the player's own items, as DIM's Randomize does
(auto-loadouts.ts randomLoadout / randomSubclassConfiguration, loadout-drawer-reducer.ts randomizeLoadoutMods).

Pure: every function takes a `random.Random` so tests can seed it.
"""
import re

from shell.engines.builds import subclass as subclass_mod
from shell.engines.builds.rules import UTILITY_SOCKETS

WEAPON_SLOTS = ("Kinetic", "Energy", "Power")
ARMOR_SLOTS = ("Helmet", "Gauntlets", "Chest", "Legs", "Class Item")
MOD_SLOTS = {"enhancements.v2_head": "Helmet", "enhancements.v2_arms": "Gauntlets",
             "enhancements.v2_chest": "Chest", "enhancements.v2_legs": "Legs",
             "enhancements.v2_class_item": "Class Item"}


def _usable(item, cls):
    """Not stuck in the postmaster, not equipped on another character."""
    loc = item.get("location") or ""
    return "Postmaster" not in loc and not (item.get("equipped") and cls and loc != cls)


def roll_subclass(cls: str, owned_elements: list[str], idx: dict, rng) -> dict:
    element = rng.choice(sorted(owned_elements))
    known = idx[element]
    abilities = {k: rng.choice(sorted(v)) for k, v in known["abilities"][cls].items() if v}
    sub = {"element": element, "super": abilities.pop("super", None), "abilities": abilities}
    aspects = sorted(known["aspects"][cls])
    sub["aspects"] = rng.sample(aspects, min(subclass_mod.MAX_ASPECTS, len(aspects)))
    slots = subclass_mod.fragment_slots({"class": cls, "subclass": sub}, idx)
    fragments = sorted(known["fragments"])
    sub["fragments"] = rng.sample(fragments, min(slots, len(fragments)))
    if sub["super"] is None:
        del sub["super"]
    return sub


def _entry(slot, item):
    return {"slot": slot, "itemId": item["itemId"], "name": item["name"]}


def roll_weapons(items: list[dict], rng, cls: str | None = None) -> list[dict]:
    """One random weapon per slot, at most one exotic (slots are visited in random order)."""
    chosen, exotic = {}, False
    for slot in rng.sample(WEAPON_SLOTS, len(WEAPON_SLOTS)):
        pool = [w for w in items if w["slot"] == slot and _usable(w, cls)
                and not (exotic and w.get("rarity") == "Exotic")]
        if pool:
            pick = rng.choice(pool)
            exotic = exotic or pick.get("rarity") == "Exotic"
            chosen[slot] = _entry(slot, pick)
    return [chosen[s] for s in WEAPON_SLOTS if s in chosen]


def roll_armor(items: list[dict], cls: str, rng) -> list[dict]:
    """One random piece per slot for the class, exactly one exotic (the sheet needs it)."""
    mine = [x for x in items if x.get("classType") == cls and _usable(x, cls)]
    exotics = [x for x in mine if x.get("rarity") == "Exotic"]
    if not exotics:
        raise ValueError(f"no exotic armor for {cls}")
    # a slot with no legendary can only be filled by the exotic
    bare = [s for s in ARMOR_SLOTS if not any(x["slot"] == s and x.get("rarity") != "Exotic" for x in mine)]
    if bare:
        exotics = [x for x in exotics if x["slot"] == bare[0]] if len(bare) == 1 else []
        if not exotics:
            raise ValueError(f"no legendary {', '.join(bare)} for {cls}")
    exotic = rng.choice(exotics)
    chosen = {exotic["slot"]: _entry(exotic["slot"], exotic)}
    for slot in ARMOR_SLOTS:
        pool = [x for x in mine if x["slot"] == slot and x.get("rarity") != "Exotic"]
        if slot not in chosen and pool:
            chosen[slot] = _entry(slot, rng.choice(pool))
    return [chosen[s] for s in ARMOR_SLOTS if s in chosen]


def _capacity(item):
    m = re.fullmatch(r"\s*\d+\s*/\s*(\d+)\s*", str(item.get("energy") or ""))
    return int(m.group(1)) if m else 0


def roll_mods(armor_entries, armor_items, slot_mods: dict, rng, reserved: dict | None = None) -> dict[str, list[str]]:
    """Per armor slot, up to 3 random slot mods whose total cost fits the piece (repeats allowed, as in game).
    `reserved`: {itemId: energy kept for what stays installed (the stat mod)}.
    shortcut: mutually exclusive mods are not filtered; the equip preview shows a refused socket."""
    items = {x["itemId"]: x for x in armor_items}
    out = {}
    for e in armor_entries:
        budget = _capacity(items.get(e["itemId"], {})) - (reserved or {}).get(e["itemId"], 0)
        mods, pool = [], slot_mods.get(e["slot"], {})
        for _ in range(UTILITY_SOCKETS):
            fits = sorted(name for name, cost in pool.items() if cost <= budget) if budget > 0 else []
            if not fits:
                break
            pick = rng.choice(fits)
            mods.append(pick)
            budget -= pool[pick]
        out[e["slot"]] = mods
    return out


def slot_mods(defs: dict) -> dict[str, dict[str, int]]:
    """{armor slot: {mod name: energy cost}} from item definitions; only mods with a collectible (the others are
    artifact copies: discounted, or unlocked only by the artifact)."""
    out = {}
    for d in defs.values():
        plug = d.get("plug") or {}
        slot = MOD_SLOTS.get(plug.get("plugCategoryIdentifier"))
        name = (d.get("displayProperties") or {}).get("name")
        cost = (plug.get("energyCost") or {}).get("energyCost")
        if slot and name and cost is not None and d.get("collectibleHash") is not None:
            out.setdefault(slot, {})[name] = cost
    return out
