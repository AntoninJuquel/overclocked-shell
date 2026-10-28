"""Aegis's Shopping List → farm needs: the items the player does not own yet, by priority."""
import re

from shell.engines.builds.sheet import slug as slug_of
from shell.engines.builds.stats import ARCHETYPES
from shell.sources.aegis.names import first_line, norm, strip_set

BUILD = "aegis"   # "build" of the Shopping List needs (farm_plan(build="aegis"))
LABEL = "Aegis Shopping List"
PRIORITY_SCORE = {"high": 0.10, "medium": 0.06, "low": 0.03, "niche": 0.01}
_CLASS_ROLE = re.compile(r"^(hunter|titan|warlock)\b", re.IGNORECASE)
_PIECES = re.compile(r"\((\d) pcs?\.?\)", re.IGNORECASE)
_EMPTY = {"n/a", "situational"}
ARMOR_SLOTS = ("Helmet", "Gauntlets", "Chest", "Legs", "Class Item")


def lines(text):
    """Options of a cell, one per line, without "N/A" or "situational"."""
    return [x.strip() for x in (text or "").split("\n") if x.strip() and x.strip().lower() not in _EMPTY]


def owns_named(name, items):
    return any(norm(it["name"]) == norm(name) for it in items)


def kind_of(name, weapon_names, set_names, weapons=()):
    """"weapon" (Aegis weapon tabs, or a weapon of the player's inventory for a name missing from the tabs),
    "set" (Set Bonuses) or "exotic" (exotic armor, the default)."""
    key = norm(name)
    if key in weapon_names:
        return "weapon"
    if strip_set(key) in set_names:
        return "set"
    return "weapon" if owns_named(name, weapons or ()) else "exotic"


def owns_weapon(row, weapons):
    """A copy of the name; for a legendary whose perks Aegis gives, a copy that can roll at least one Column 1
    perk in its 1st "Trait" column and one Column 2 perk in its 2nd (without two "Trait" columns: any column).
    A crafted weapon counts as owned: the inventory lists only its current perks, and it is reshaped at the Relic."""
    wanted = [{norm(p) for p in lines(row.get(c))} for c in ("Column 1", "Column 2")]
    for w in weapons:
        if norm(w["name"]) != norm(row["_name"]):
            continue
        if w.get("rarity") == "Exotic" or w.get("crafted"):
            return True
        cols = [{norm(o["name"]) for o in c.get("options", [])} for c in w.get("columns", [])]
        traits = [{norm(o["name"]) for o in c.get("options", [])} for c in w.get("columns", [])
                  if c.get("label") == "Trait"]
        pools = traits[:2] if len(traits) >= 2 else [set().union(*cols)] * 2
        if all(not want or want & pool for want, pool in zip(wanted, pools)):
            return True
    return False


def archetypes(text):
    """"Specialist/Gunner + class" → {"Specialist", "Gunner"} (known Armor 3.0 archetypes only)."""
    return {a.strip() for a in (text or "").split("+")[0].split("/") if a.strip() in ARCHETYPES}


def set_progress(row, armor, sets_by_hash):
    """(owned, progress) of a set: one class has enough slots covered by Armor 3.0 pieces of the set with a wanted
    archetype ("(2 pcs.)" in the role → 2, else 4); the progress describes the best class."""
    ordered = [a.strip() for a in (row.get("Column 1") or "").split("+")[0].split("/") if a.strip() in ARCHETYPES]
    want = set(ordered)
    m = _PIECES.search(row.get("Role") or "")
    need, key, slots = int(m.group(1)) if m else 4, strip_set(norm(row["_name"])), {}
    for it in armor:
        info = sets_by_hash.get(it["itemHash"])
        if not info or strip_set(norm(info["set"])) != key or (it.get("gearTier") or 0) < 1:
            continue
        arch = next((p for p in it.get("plugs", []) if p in ARCHETYPES), None)
        if want and arch not in want:
            continue
        slots.setdefault(it["classType"], set()).add(it["slot"])
    if not slots:
        return False, "no pieces"
    cls = max(sorted(slots), key=lambda c: len(slots[c]))
    missing = [s for s in ARMOR_SLOTS if s not in slots[cls]]
    label = "/".join(ordered) if ordered else "of the set"
    text = f"{len(slots[cls])}/{need} pieces {label} on {cls}"
    return len(slots[cls]) >= need, text + (f", missing: {', '.join(missing)}" if missing else "")


def _effects(row, kind, owned_alts, progress=""):
    out = [f"Aegis role: {row.get('Role') or '—'} (priority {row['Priority'].strip().lower()})"]
    perks = [" or ".join(lines(row.get(c))) for c in ("Column 1", "Column 2") if lines(row.get(c))]
    if kind == "weapon" and perks:
        out.append("perks: " + " + ".join(perks))
    if kind != "weapon" and archetypes(row.get("Column 1")):
        out.append("archetype: " + (row.get("Column 1") or "").replace("\n", " / "))
    if progress:
        out.append("progress: " + progress)
    if owned_alts:
        out.append("owned alternatives: " + ", ".join(owned_alts))
    return out


def shopping_needs(rows, armor, weapons, sets_by_hash, weapon_names, set_names):
    """(needs, warnings, complete) of the Shopping List; `complete` is false when weapons were skipped.
    `armor` / `weapons`: inventory snapshots; `weapons` None (no snapshot): weapons are skipped and counted in a
    warning. `weapon_names` / `set_names`: normalized names of Aegis's weapon tabs and Set Bonuses tab."""
    classes = {it["classType"] for it in armor if it.get("characterId")}
    by_id, skipped = {}, 0
    for row in rows:
        prio = (row.get("Priority") or "").strip().lower()
        if prio not in PRIORITY_SCORE:
            continue
        m = _CLASS_ROLE.match((row.get("Role") or "").strip())
        if m and m.group(1).capitalize() not in classes:
            continue
        name = first_line(row["_name"])
        kind = kind_of(name, weapon_names, set_names, weapons)
        if kind == "weapon" and weapons is None:
            skipped += 1
            continue
        progress = ""
        if kind == "set":
            owned, progress = set_progress(row, armor, sets_by_hash)
        elif kind == "weapon":
            owned = owns_weapon(row, weapons)
        else:
            owned = owns_named(name, armor)
        if owned:
            continue
        alts = [a for a in lines(row.get("Alternatives")) if owns_named(a, armor) or owns_named(a, weapons or [])]
        nid, effects, score = f"aegis/{slug_of(name)}", _effects(row, kind, alts, progress), PRIORITY_SCORE[prio]
        if nid in by_id:
            gain = by_id[nid]["builds"][0]["gain"]
            gain["effects"] += [e for e in effects if e not in gain["effects"]]
            gain["score"] = max(gain["score"], score)
            continue
        by_id[nid] = {"id": nid, "kind": "aegis", "label": f"Aegis: {name}",
                      "target": {"name": name, "type": kind, "source": row.get("Source") or ""},
                      "builds": [{"build": BUILD, "gain": {"stats": {}, "effects": effects, "score": score}}]}
    warnings = [f"no weapon snapshot: the {LABEL} skips {skipped} weapon(s) (call refresh_inventory)"] if skipped else []
    return list(by_id.values()), warnings, not skipped
