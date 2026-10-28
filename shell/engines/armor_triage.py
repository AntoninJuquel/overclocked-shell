"""Armor vault triage (Armor 3.0): KEEP / JUNK with a reason for each piece.

Only stat quality counts: neither loadouts nor what is equipped protect a piece.
"""
import re
from collections import defaultdict

STATS = ["Weapons", "Health", "Class", "Grenade", "Super", "Melee"]
ARCHETYPES = {"Brawler", "Gunner", "Grenadier", "Specialist", "Paragon", "Bulwark",
              "Powerhouse", "Siegebreaker", "Reaver", "Demolitionist", "Skirmisher", "Colossus"}


def armor_sets(manifest) -> dict[int, dict]:
    """{itemHash: {"set": name, "bonus": ["2 pieces: …", "4 pieces: …"]}} for every set armor piece."""
    sets = manifest.table("DestinyEquipableItemSetDefinition", keep=False)
    perks = manifest.table("DestinySandboxPerkDefinition", keep=False)
    by_item = {}
    for s in sets.values():
        bonus = [f"{p['requiredSetCount']} pieces: {perks[str(p['sandboxPerkHash'])]['displayProperties']['name']}"
                 for p in sorted(s.get("setPerks", []), key=lambda p: p["requiredSetCount"])
                 if str(p["sandboxPerkHash"]) in perks]
        for h in s.get("setItems", []):
            by_item[h] = {"set": s["displayProperties"]["name"], "bonus": bonus}
    return by_item


def base_stats(item):
    """Removes equipped stat mods to get back the base distribution."""
    s = dict(item["stats"])
    tuned = None
    for p in item["plugs"]:
        m = re.match(r"General Armor Mod: (Minor )?(\w+) Mod$", p)
        if m and m.group(2) in STATS:
            s[m.group(2)] -= 5 if m.group(1) else 10
        m = re.match(r"General Armor Mod: \+(\w+) / -(\w+)$", p)
        if m:
            s[m.group(1)] -= 5
            s[m.group(2)] += 5
            tuned = m.group(1)
    return s, tuned


def project_mw(base):
    """Projected stats once masterworked (Armor 3.0): the 3 focus stats stay as they are, the other
    3 go to 5, whatever the current upgrade level."""
    s = dict(base)
    for k in sorted(STATS, key=lambda k: -base[k])[3:]:
        s[k] = 5
    return s


def dominates(a, b):
    """a >= b on every projected stat."""
    return all(a["mw"][k] >= b["mw"][k] for k in STATS)


def rank(item):
    """Bigger = better copy: projected stat quality only.
    The current lock only breaks ties between strictly identical copies."""
    return (item["gearTier"], item["mwTotal"], item["locked"])


def _fmt(it):
    return "/".join(f"{it['mw'][k]}" for k in STATS)


def _decide(it, keep, reason):
    it["decision"] = "KEEP" if keep else "JUNK"
    it["reason"] = reason


def _keep_best(grp, label):
    """Keeps the best copy (projected MW stats); another copy is kept only if no kept copy dominates
    it stat by stat, or if its known tuning differs."""
    grp.sort(key=rank, reverse=True)
    kept = []
    for it in grp:
        beaten = next((k for k in kept if dominates(k, it)), None)
        if beaten is None:
            kept.append(it)
            _decide(it, True, f"best copy {label} — MW {_fmt(it)} = {it['mwTotal']}")
        elif it["tuned"] and it["tuned"] not in {k["tuned"] for k in kept} and it["gearTier"] == beaten["gearTier"]:
            kept.append(it)
            _decide(it, True, f"same stats but different tuning +{it['tuned']}")
        else:
            _decide(it, False, f"beaten by {beaten['name']} T{beaten['gearTier']} — MW {_fmt(beaten)} = "
                               f"{beaten['mwTotal']} vs {_fmt(it)} = {it['mwTotal']}")


def triage_armor(rows: list[dict], sets: dict[int, dict]) -> list[dict]:
    items = [dict(r) for r in rows]
    for it in items:
        b, tuned = base_stats(it)
        it["base"] = b
        it["tuned"] = tuned
        it["mw"] = project_mw(b)
        it["mwTotal"] = sum(it["mw"].values())
        it["archetype"] = next((p for p in it["plugs"] if p in ARCHETYPES), None)
        top = sorted(STATS, key=lambda k: -b[k])[:3]
        it["profile"] = "/".join(top)  # primary / secondary / tertiary
        it["tertiary"] = top[2]
        it["spirits"] = tuple(sorted(p for p in it["plugs"] if p.startswith("Intrinsic: Spirit")))
        info = sets.get(it["itemHash"], {})
        it["set"] = info.get("set")
        it["setBonus"] = info.get("bonus", [])
        it["decision"], it["reason"] = None, ""

    # 1) Legacy (tier 0, before Armor 3.0): always junk, even with no replacement.
    for it in items:
        if it["gearTier"] == 0:
            _decide(it, False, "legacy (pre-Armor 3.0)")

    # 2) Armor 3.0, one best copy per stat distribution:
    #    Legendaries: (class, slot, set, archetype, tertiary), all tiers together,
    #                 so a T3 is junked only if a better piece of the SAME set dominates it.
    #    Exotics    : (name, spirit perks, archetype, tertiary).
    groups = defaultdict(list)
    for it in items:
        if it["gearTier"] >= 1:
            if it["rarity"] == "Exotic":
                key = ("X", it["name"], it["spirits"], it["archetype"], it["tertiary"])
            else:
                key = ("L", it["classType"], it["slot"], it["set"] or it["name"], it["archetype"], it["tertiary"])
            groups[key].append(it)
    for key, grp in groups.items():
        _keep_best(grp, f"{key[3] if key[0] == 'X' else key[4]} tertiary {key[-1]}")

    # 3) Postmaster: left alone.
    for it in items:
        if "Postmaster" in it["location"]:
            _decide(it, True, "postmaster (ignored)")
    return items


def lock_plan(rows: list[dict]) -> tuple[list[str], list[str]]:
    """(lock, unlock): KEEP not locked yet (postmaster excluded), JUNK still locked."""
    lock = [i["itemId"] for i in rows
            if i["decision"] == "KEEP" and not i["locked"] and "Postmaster" not in i["location"]]
    unlock = [i["itemId"] for i in rows if i["decision"] == "JUNK" and i["locked"]]
    return lock, unlock
