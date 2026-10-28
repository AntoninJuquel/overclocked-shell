"""Armor optimizer: picks the exotic + 4 legendaries and their mods for a build sheet. No in-game action."""
import difflib
import heapq
from datetime import date

from shell.engines.builds import inventory, mods, sheet as sheet_mod
from shell.engines.builds.rules import UTILITY_SOCKETS
from shell.engines.builds.stats import CAP, SLOTS, STATS

MAX_EVALS = 200_000   # safety net: most combinations evaluated (calls to mods.assign)


def relevant_stats(intent):
    st = intent.get("stats", {})
    rel = list(dict.fromkeys(list(st.get("minimums", {})) + st.get("priority", [])))
    return rel or list(STATS)


def _dominates(q, p, rel, req_sets, cls, cap):
    """q makes p useless. Stats are compared raw: waste above 200 is not taken into account (known limit);
    it only affects tie-breaks (waste, masterworks, transfers). Likewise, mods.assign's greedy pass reads
    irrelevant stats (tuning donor, Balanced Tuning), which can shift the deficit or a priority stat by one
    point in rare cases; feasibility stays exact in the tests. The tuning stat is compared whatever `rel`."""
    return (all(q.stats[s] >= p.stats[s] for s in rel)
            and min(q.energy, cap) >= min(p.energy, cap)
            and q.masterwork_todo <= p.masterwork_todo
            and (p.tuned is None or q.tuned == p.tuned)
            and (p.set not in req_sets or q.set == p.set)
            and (q.location == cls or p.location != cls))


def prune(pieces, rel, req_sets, cls=None, energy_cap=None):
    """Drops dominated pieces; among equivalent pieces, keeps the first (locked, then id).

    `energy_cap`: energy above which a piece gains nothing (cost of the utility mods, one major stat mod
    and the filler mods); None = raw energy."""
    cap = float("inf") if energy_cap is None else energy_cap
    order = sorted(pieces, key=lambda x: (not x.locked, x.item_id))
    kept = []
    for i, p in enumerate(order):
        beaten = any(_dominates(q, p, rel, req_sets, cls, cap)
                     and (not _dominates(p, q, rel, req_sets, cls, cap) or j < i)
                     for j, q in enumerate(order) if q is not p)
        if not beaten:
            kept.append(p)
    return kept


def _util_cost(costs, intent, slot):
    return sum(mods._cost(costs, m) for m in intent.get("armor_mods", {}).get(slot, []))


def _fill_potential(costs, intent, slot):
    """Most energy the slot's filler mods can take."""
    free = UTILITY_SOCKETS - len(intent.get("armor_mods", {}).get(slot, []))
    fill_costs = sorted((mods._cost(costs, m) for m in intent.get("armor_mods_fill", {}).get(slot, [])),
                        reverse=True)
    return sum(fill_costs[:max(0, free)])


def _major_cost(costs):
    return max((costs[f"{s} Mod"] for s in STATS if f"{s} Mod" in costs), default=0)


def _evaluate(combo, frag, intent, costs, cls):
    st = intent.get("stats", {})
    mins, prio = st.get("minimums", {}), st.get("priority", [])
    totals = {s: sum(p.stats[s] for p in combo) + frag.get(s, 0) for s in STATS}
    res = mods.assign(combo, totals, mins, prio, costs, intent.get("armor_mods", {}),
                      intent.get("armor_mods_fill", {}))
    if res is None:
        return None
    mw = sum(p.masterwork_todo for p in combo)
    moves = sum(p.location != cls for p in combo)
    # Key ends with the itemId tuple, for a deterministic ranking whatever the input order.
    # energy taken by filler mods: after the stats, before masterworks and transfers
    filled = sum(mods._cost(costs, m) for f in res.fills for m in f)
    key = (not res.deficit, -sum(res.deficit.values()), tuple(min(res.totals[s], CAP) for s in prio),
           -res.waste, filled, -mw, -moves, tuple(p.item_id for p in combo))
    return key, combo, res


def evaluate(combo, frag, intent, costs, cls):
    """mods.Result of a given combination (one piece per slot), or None if the utility mods exceed a
    piece's energy. The intent's sets are not checked."""
    ev = _evaluate(tuple(sorted(combo, key=lambda x: SLOTS.index(x.slot))), frag, intent, costs, cls)
    return ev[2] if ev else None


def _describe(combo, res, cls, intent):
    order = {s: i for i, s in enumerate(SLOTS)}
    util = intent.get("armor_mods", {})
    pairs = sorted(zip(combo, res.choices, res.fills, res.energy_left), key=lambda pc: order.get(pc[0].slot, 99))
    return {
        "feasible": not res.deficit,
        # the game floors stats at 0: a negative fragment never produces a negative stat
        "stats": {s: max(0, v) for s, v in res.totals.items()},
        "deficit": res.deficit,
        "waste": res.waste,
        "armor": [{"slot": p.slot, "itemId": p.item_id, "name": p.name, "set": p.set,
                   "masterwork": "todo" if p.masterwork_todo else "done",
                   "stat_mod": c.stat_mod, "tuning": c.tuning, "mods": util.get(p.slot, []) + f,
                   "energy_left": left, "location": p.location} for p, c, f, left in pairs],
        "actions": {"masterwork": sum(p.masterwork_todo for p in combo),
                    "transfers": sum(p.location != cls for p in combo)},
    }


def _bonus(p, s):
    """Upper bound of what a piece's mods can add to stat s: a major mod (+10), tuning (+5 if it is its
    stat) or Balanced Tuning (+1)."""
    return 10 + 5 * (p.tuned == s) + (p.tuned is not None)


def _search(slots, rel, intent, frag, costs, cls, n):
    """Depth-first branch and bound. slots[0] = exotics, then the 4 legendary slots.
    Returns (heap of (key, ev) of size <= n, evaluations, complete)."""
    st = intent.get("stats", {})
    mins, prio = st.get("minimums", {}), st.get("priority", [])
    req = {e["set"]: e["pieces"] for e in intent.get("sets", [])}
    depth = len(slots)
    # suffix[d][s]: best possible contribution (stats + mods) of slots d.. to stat s
    suffix = [dict.fromkeys(rel, 0) for _ in range(depth + 1)]
    for d in range(depth - 1, -1, -1):
        for s in rel:
            suffix[d][s] = suffix[d + 1][s] + max(p.stats[s] + _bonus(p, s) for p in slots[d])
    heap = []
    state = {"evals": 0, "complete": True}

    def promising(d, part):
        if len(heap) < n:
            return True
        ub = {s: part[s] + suffix[d][s] + frag.get(s, 0) for s in rel}
        dlb = sum(max(0, m - ub[s]) for s, m in mins.items())
        return (dlb == 0, -dlb, tuple(min(ub[s], CAP) for s in prio)) >= heap[0][0][:3]

    def rec(d, chosen, part, have):
        if d == depth:
            state["evals"] += 1
            # canonical slot order: mods.assign is greedy, its result depends on the order
            ev = _evaluate(tuple(sorted(chosen, key=lambda x: SLOTS.index(x.slot))), frag, intent, costs, cls)
            if ev:
                item = (ev[0], ev)
                if len(heap) < n:
                    heapq.heappush(heap, item)
                elif item[0] > heap[0][0]:
                    heapq.heapreplace(heap, item)
            return
        for p in slots[d]:
            if not state["complete"]:
                return
            if state["evals"] >= MAX_EVALS:
                state["complete"] = False   # reported by the caller (optimize_build's warnings)
                return
            new_have = have
            if d > 0:   # exotics have no set: only the 4 legendaries count
                new_have = {**have, p.set: have.get(p.set, 0) + 1}
            if sum(max(0, k - new_have.get(name, 0)) for name, k in req.items()) > depth - 1 - d:
                continue
            new_part = {s: part[s] + p.stats[s] + _bonus(p, s) for s in rel}
            if not promising(d + 1, new_part):
                continue
            chosen.append(p)
            rec(d + 1, chosen, new_part, new_have)
            chosen.pop()

    rec(0, [], dict.fromkeys(rel, 0), {})
    return heap, state["evals"], state["complete"]


def optimize(pieces, intent, frag, costs, cls, top=5):
    """{"feasible": bool, "complete": bool, "combinations": n, "results": [...]}.
    `combinations` = combinations evaluated (calls to mods.assign)."""
    ex_slot = inventory.exotic_slot(pieces)
    if ex_slot is None:
        raise ValueError(f"exotic not found: {intent['exotic']['name']}")
    rel = relevant_stats(intent)
    req = {e["set"] for e in intent.get("sets", [])}
    major = _major_cost(costs)

    def usable(slot, exotic):
        util = _util_cost(costs, intent, slot)
        return [p for p in pieces.get(slot, []) if p.exotic == exotic and p.energy >= util]

    pools = [(ex_slot, usable(ex_slot, True))] + [(s, usable(s, False)) for s in SLOTS if s != ex_slot]
    if any(not lst for _, lst in pools):
        return {"feasible": False, "complete": True, "combinations": 0, "results": []}

    def candidates(slot, lst):
        cap = _util_cost(costs, intent, slot) + major + _fill_potential(costs, intent, slot)
        kept = prune(lst, rel, req, cls, cap)
        return sorted(kept, key=lambda x: -sum(x.stats[s] for s in rel))   # good stats first: early threshold

    slots = [candidates(s, lst) for s, lst in pools]
    heap, count, complete = _search(slots, rel, intent, frag, costs, cls, max(top, 3))
    best = [ev for _, ev in sorted(heap, key=lambda h: h[0], reverse=True)]
    feasible = bool(best) and best[0][0][0]
    chosen = [ev for ev in best if ev[0][0]][:top] if feasible else best[:3]
    results = [{"rank": rank, **_describe(combo, res, cls, intent)}
               for rank, (_, combo, res) in enumerate(chosen, 1)]
    return {"feasible": feasible, "complete": complete, "combinations": count, "results": results}


def check_sets(intent, known):
    """Refuses a required set missing from the manifest (`known`: set names), with up to 3 suggestions."""
    by_lower = {k.lower(): k for k in known}
    for e in intent.get("sets", []):
        name = e["set"]
        if name in known:
            continue
        hints = [by_lower[k] for k in (name.lower(), f"{name} set".lower()) if k in by_lower]
        hints += difflib.get_close_matches(name, sorted(known), n=3, cutoff=0.6)
        hints = list(dict.fromkeys(hints))[:3]
        raise ValueError(f"unknown set: {name}" + (f" (suggestion: {', '.join(hints)})" if hints else ""))


def parse_set_override(specs, no_sets):
    """`sets` ["Name:2", ...] or `no_sets` → sets applied instead of the intent's; None without either."""
    if no_sets and specs:
        raise ValueError("sets and no_sets exclude each other")
    if no_sets:
        return []
    if not specs:
        return None
    sets = []
    for spec in specs:
        name, sep, pieces = spec.rpartition(":")
        if not sep or not name.strip() or not pieces.strip().isdigit():
            raise ValueError(f"sets expects \"Name:2\" or \"Name:4\": {spec!r}")
        sets.append({"set": name.strip(), "pieces": int(pieces)})
    sheet_mod.validate_sets(sets, "sets")   # SheetError is a ValueError
    return sets


def write_result(path, result, today=None, sets=None):
    """Writes one combination into `resolved` (armor + stats + date) without touching the intent or weapons.

    `sets`: sets actually applied when they differ from the intent (concession); None = the intent's.
    """
    s = sheet_mod.load(path)
    res = s.setdefault("resolved", {})
    res["date"] = today or date.today().isoformat()
    if sets is None:
        res.pop("sets", None)
    else:
        res["sets"] = sets
    res["armor"] = [{k: a[k] for k in ("slot", "itemId", "name", "masterwork", "stat_mod", "tuning", "mods")}
                    for a in result["armor"]]
    res["stats"] = result["stats"]
    sheet_mod.save(path, s)
