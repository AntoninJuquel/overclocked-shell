"""Equip plan of a build sheet: the write calls to make, without running any."""
import re
from collections import Counter
from datetime import date

from shell.engines.builds import artifact as artifact_mod
from shell.engines.builds import subclass
from shell.engines.builds.inventory import LEGACY_MAX_ENERGY, has_tuning_data
from shell.engines.builds.rules import UTILITY_SOCKETS
from shell.engines.builds.stats import STATS

STALE_DAYS = 7
ABILITIES = ["grenade", "melee", "class", "jump"]
SUBCLASS_ITEMS = {
    "Hunter": {"Arc": "Arcstrider", "Solar": "Gunslinger", "Void": "Nightstalker", "Stasis": "Revenant",
               "Strand": "Threadrunner", "Prismatic": "Prismatic Hunter"},
    "Titan": {"Arc": "Striker", "Solar": "Sunbreaker", "Void": "Sentinel", "Stasis": "Behemoth",
              "Strand": "Berserker", "Prismatic": "Prismatic Titan"},
    "Warlock": {"Arc": "Stormcaller", "Solar": "Dawnblade", "Void": "Voidwalker", "Stasis": "Shadebinder",
                "Strand": "Broodweaver", "Prismatic": "Prismatic Warlock"},
}

STAT_MOD = re.compile(r"^(Major |Minor )?(" + "|".join(STATS) + r") Mod$")
TUNING = re.compile(r"^(\+\w+ / -\w+|Balanced Tuning)$")
SLOT_MOD_TYPES = {"Helmet Armor Mod", "Arms Armor Mod", "Chest Armor Mod", "Leg Armor Mod",
                  "Class Item Armor Mod"}
NO_TUNING_WARNING = ("snapshot without the tuning stat: installed tunings kept, real stats differ from the sheet; "
                     "refresh_inventory then re-optimize")


def _installed(item):
    """(stat mods, tunings, slot mods) installed according to the snapshot ('Type: Name')."""
    stat, tuning, util = [], [], []
    for p in item.get("plugs") or []:
        kind, _, name = p.partition(": ")
        if kind == "General Armor Mod":
            if STAT_MOD.match(name):
                stat.append(name)
            elif TUNING.match(name):
                tuning.append(name)
        elif kind in SLOT_MOD_TYPES:
            util.append(name)
    return stat, tuning, util


def _capacity(item):
    """A piece's energy: the snapshot's denominator, projected to 10 for a legacy piece still to masterwork."""
    if item.get("gearTier") == 0 and not item.get("masterworked"):
        return LEGACY_MAX_ENERGY
    try:
        return int(item["energy"].rpartition("/")[2])
    except (KeyError, ValueError, AttributeError):
        return LEGACY_MAX_ENERGY


def _kept_utility(a, util, item, costs, warnings):
    """Slot mods kept when the sheet has no opinion: removes, most expensive first, what does not fit in the
    piece's energy with the stat mod."""
    def cost(m):
        if m not in costs:
            warnings.append(f"{a['slot']}: unknown cost of mod {m} (counted 0)")
        return costs.get(m, 0)

    total = (cost(a["stat_mod"]) if a.get("stat_mod") else 0) + sum(cost(m) for m in util)
    cap = _capacity(item)
    kept = list(util)
    removed = []
    while kept and total > cap:
        worst = max(kept, key=lambda m: costs.get(m, 0))
        kept.remove(worst)
        removed.append(worst)
        total -= costs.get(worst, 0)
    if util:
        text = f"{a['slot']}: {a['name']}: slot mods kept: {', '.join(kept) or 'none'}"
        if removed:
            text += f"; removed (energy {cap} exceeded): {', '.join(removed)}"
        warnings.append(text)
    return kept, removed


def _socket_plugs(a, wanted, item, costs, warnings, tuning_data=True):
    """Plugs to insert on a piece to reach the wanted state, emptying only what is installed.
    `wanted`: wanted slot mods; None when the sheet has no opinion (installed ones that fit are kept).
    `tuning_data`: false when the snapshot lacks the tuning stat (installed tunings are then kept)."""
    stat, tuning, util = _installed(item)
    plugs = []
    if a.get("stat_mod"):
        plugs.append(a["stat_mod"])
    elif stat:
        plugs.append({"name": "Empty Mod Socket", "socketIndex": 0})
    if a.get("tuning"):
        plugs.append(a["tuning"])
    elif tuning and tuning_data:
        plugs.append("Empty Tuning Mod Socket")
    if wanted is None:
        wanted, removed = _kept_utility(a, util, item, costs, warnings)
        emit = bool(removed)
    else:
        removed = list((Counter(util) - Counter(wanted)).elements())
        emit = bool(wanted)
    if len(wanted) > UTILITY_SOCKETS:
        warnings.append(f"{a['slot']}: more than {UTILITY_SOCKETS} slot mods wanted")
    if emit:
        plugs += wanted          # set_sockets keeps an installed mod, then takes an empty socket, then replaces
    if removed:
        plugs += [{"name": "Empty Mod Socket", "socketIndex": k} for k in range(1, UTILITY_SOCKETS + 1)]
    return plugs


def _energy_warning(a, wanted, item, costs):
    """Energy the plan leaves free on a piece (only when the snapshot gives the energy)."""
    if not item.get("energy") or wanted is None:
        return None
    used = sum(costs.get(m, 0) for m in ([a["stat_mod"]] if a.get("stat_mod") else []) + list(wanted))
    cap = _capacity(item)
    if used >= cap:
        return None
    text = f"{a['slot']}: {a['name']}: {cap - used} free energy of {cap}: "
    if len(wanted) >= UTILITY_SOCKETS:
        return text + (f"all {UTILITY_SOCKETS} slots are taken: replace a cheap mod in intent.armor_mods with a "
                       f"costlier one, then re-optimize")
    return text + ("add mods to intent.armor_mods_fill (the same mod can be used more than once) "
                   "then re-optimize")


def _weapon_setup(w, item, problems, warnings):
    """(perks to select, mod to insert) of a resolved weapon, from the weapon snapshot."""
    label = f"{w['slot']}: {w['name']}"
    cols = item.get("columns") or []
    select = []
    if "perks" in w:
        where = {o["name"]: c for c in cols for o in c.get("options", [])}
        missing = [p for p in w["perks"] if p not in where]
        if missing:
            problems.append(f"{label}: perks not in the weapon's options: {', '.join(missing)}")
        select = [p for p in w["perks"] if p in where and where[p].get("selected") != p]
    else:
        multi = [c["label"] for c in cols if len(c.get("options", [])) > 1]
        if multi:
            warnings.append(f"{label}: perks to choose (columns with options: {', '.join(multi)}): "
                            f"set resolved.weapons[].perks")
    mod = w.get("mod")
    if "mod" not in w and not item.get("mod"):
        warnings.append(f"{label}: no weapon mod: set resolved.weapons[].mod")
    return select, (mod if mod and mod != item.get("mod") else None)


def build_plan(s, armor_items, weapon_items, frag, today, idx, costs, artifacts=None):
    """`artifacts`: {artifact: {perk: column}} from the compendium (artifact.load), needed when the sheet has one."""
    res = s.get("resolved") or {}
    cls, sub = s["class"], s["subclass"]
    armor, weapons = res.get("armor") or [], res.get("weapons") or []
    problems = [] if armor else ["no resolved armor: run optimize-build"]
    problems += [f"subclass: {p}" for p in subclass.check(s, idx)]
    warnings = []
    known = {i["itemId"]: i for i in armor_items}
    known.update({i["itemId"]: i for i in weapon_items})
    for e in armor + weapons:
        item = known.get(e["itemId"])
        label = f"{e['slot']}: {e['name']} ({e['itemId']})"
        if item is None:
            problems.append(f"{label} not in the inventory")
        elif "(Postmaster)" in item.get("location", ""):
            problems.append(f"{label} in the postmaster")
        elif item.get("equipped") and item.get("location") != cls:
            problems.append(f"{label} equipped on {item.get('location')}: unequip it first")
    if armor and res.get("date"):
        try:
            if (today - date.fromisoformat(res["date"])).days > STALE_DAYS:
                warnings.append(f"result from {res['date']} (over {STALE_DAYS} days old): offer optimize-build")
        except (ValueError, TypeError):
            warnings.append(f"unreadable result date: {res['date']}")
    if armor and not weapons:
        warnings.append("no resolved weapons")
    if len(weapons) < 3 and any((known.get(w["itemId"]) or {}).get("rarity") == "Exotic" for w in weapons):
        warnings.append("exotic weapon resolved with fewer than 3 weapons: an exotic equipped in another slot "
                        "can block the change")
    mods = s["intent"].get("armor_mods", {})
    tuning_data = has_tuning_data(armor_items)
    if armor and not tuning_data:
        warnings.append(NO_TUNING_WARNING)
    sockets = []
    for a in armor:
        # final mods of the piece (slot + filler) written by the optimizer, else the intent's
        wanted = a["mods"] if "mods" in a else mods.get(a["slot"])
        item = known.get(a["itemId"]) or {}
        plugs = _socket_plugs(a, wanted, item, costs, warnings, tuning_data)
        if plugs:
            sockets.append({"itemId": a["itemId"], "slot": a["slot"], "name": a["name"], "plugs": plugs})
        energy = _energy_warning(a, wanted, item, costs)
        if energy:
            warnings.append(energy)
    weapon_perks, weapon_sockets = [], []
    for w in weapons:
        if w["itemId"] not in known:
            continue
        select, mod = _weapon_setup(w, known[w["itemId"]], problems, warnings)
        if select:
            weapon_perks.append({"itemId": w["itemId"], "name": w["name"], "select": select})
        if mod:
            weapon_sockets.append({"itemId": w["itemId"], "name": w["name"], "plugs": [mod]})
    abilities = sub.get("abilities", {})
    sub_plugs = ([sub["super"]] if sub.get("super") else []) + [abilities[k] for k in ABILITIES if abilities.get(k)]
    fragments = sub.get("fragments", [])
    sub_plugs += sub.get("aspects", [])
    slots = subclass.fragment_slots(s, idx)
    wanted = fragments + ["Empty Fragment Socket"] * max(0, slots - len(fragments))
    if len(wanted) > len(fragments):
        warnings.append("fewer fragments than slots: the remaining slots are emptied")
    sockets_of = idx[sub["element"]].get("fragment_sockets", {}).get(cls, [])
    if len(sockets_of) >= len(wanted):
        # the first fragment sockets are the active ones: a fragment must not target a disabled socket
        sub_plugs += [{"name": n, "socketIndex": k} for n, k in zip(wanted, sockets_of)]
    else:
        sub_plugs += wanted
        warnings.append("unknown fragment sockets: a fragment may target a disabled socket; "
                        "check fragment slots in game")
    art = s["intent"].get("artifact")
    art_plan = None
    if art:
        art_problems = artifact_mod.check(art, artifacts or {})
        problems += [f"artifact: {p}" for p in art_problems]
        if not art_problems:
            art_plan = {"name": art["name"], "plugs": artifact_mod.assign(art.get("perks", []), artifacts[art["name"]])}
            if len(art.get("perks", [])) < len(art_plan["plugs"]):
                warnings.append("artifact: fewer perks than sockets, the remaining sockets are emptied")
    entries = armor + weapons
    todo = [a["name"] for a in armor if a.get("masterwork") == "todo"]
    if todo:
        warnings.append(f"expected stats after masterworking: {', '.join(todo)}, lower until then")
    stats = res.get("stats") or {}
    return {
        "ready": not problems,
        "problems": problems,
        "warnings": warnings,
        "character": cls.lower(),
        "equip": [e["itemId"] for e in entries],
        "subclass": {"element": sub["element"], "item": SUBCLASS_ITEMS[cls][sub["element"]], "plugs": sub_plugs},
        "armor_sockets": sockets,
        "weapon_perks": weapon_perks,
        "weapon_sockets": weapon_sockets,
        "artifact": art_plan,
        "lock": [e["itemId"] for e in entries if e["itemId"] in known and not known[e["itemId"]].get("locked")],
        "masterwork_todo": todo,
        "transfers": [{"name": e["name"], "from": known[e["itemId"]]["location"]} for e in entries
                      if e["itemId"] in known and known[e["itemId"]]["location"] != cls],
        "expected_armor_stats": {k: stats[k] - frag.get(k, 0) for k in STATS if k in stats},
    }
