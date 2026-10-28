"""Armor mod assignment: stat and tuning mods, then utility mods filling the energy left.
Energy costs come from the build catalog (`catalog.load_costs`)."""
from dataclasses import dataclass, field
from functools import lru_cache
from itertools import combinations

from shell.engines.builds.inventory import lowest3
from shell.engines.builds.rules import UTILITY_SOCKETS
from shell.engines.builds.stats import CAP, STATS


@dataclass
class Choice:
    stat_mod: str | None = None   # "Grenade Mod" / "Minor Grenade Mod"
    tuning: str | None = None     # "+Grenade / -Weapons" / "Balanced Tuning"


@dataclass
class Result:
    totals: dict
    choices: list
    deficit: dict = field(default_factory=dict)   # {stat: missing points}
    waste: int = 0                                 # points above 200
    fills: list = field(default_factory=list)      # filler mods per piece
    energy_left: list = field(default_factory=list)  # unused energy per piece, fillers included


def _cost(costs, name):
    if name not in costs:
        raise ValueError(f"unknown mod (energy cost not found in the manifest): {name}")
    return costs[name]


@lru_cache(maxsize=None)
def _best_fill(left, free, cand_costs):
    """Indexes of the chosen candidates: at most `free`, total cost <= `left`; the most energy used,
    then the best-ranked candidates (lowest indexes)."""
    best, best_key = (), (0, ())
    for k in range(1, min(free, len(cand_costs)) + 1):
        for combo in combinations(range(len(cand_costs)), k):
            used = sum(cand_costs[i] for i in combo)
            key = (used, tuple(-i for i in combo))
            if used <= left and key > best_key:
                best, best_key = combo, key
    return best


def fill(left, free, candidates, costs):
    """Filler mods of one piece: among `candidates` (priority order, duplicates allowed: a mod listed twice
    can be socketed twice), at most `free` that fit in `left` energy. Filling the energy comes before
    priority."""
    if free <= 0 or left <= 0 or not candidates:
        return []
    return [candidates[i] for i in _best_fill(left, free, tuple(_cost(costs, m) for m in candidates))]


def assign(pieces, totals, minimums, priority, costs, utility, fillers=None):
    """Picks one stat mod and one tuning per piece. `totals` = pieces' stats + fragments.
    Returns None when the utility mods exceed a piece's energy.
    `fillers`: {slot: filler mods in priority order}, socketed last in the energy left and the free utility
    sockets (see `fill`).

    Greedy and deterministic, in order:
    1. tuning `+T / -D` towards the deficits (donor D: a stat neither minimum nor priority, above the cap
       first then the lowest; otherwise a non-priority minimum that stays >= its minimum after -5);
    2. early `Balanced Tuning` for a piece with tuning, no tuning set, none of whose 3 lowest stats is at the
       cap and one of which, k, satisfies 0 < deficit(k) % 5 <= m (m = remaining eligible pieces with k
       among their 3 lowest): it then saves a stat mod;
    3. stat mods towards the deficits: largest deficit first, Major (if deficit > 5) or Minor on the free
       piece with the least sufficient energy;
    4. priorities: tuning `+P / -D` (if P < 200 - 1), then Major (if the gap to the cap > 5) or Minor on the
       free piece with the least sufficient energy, while P < 200;
    5. final `Balanced Tuning` if one of the 3 lowest stats has a deficit or is a priority under the cap;
    6. filling the energy left (stat mods first: a deficit or a priority comes before)."""
    fillers = fillers or {}
    left = []
    for p in pieces:
        used = sum(_cost(costs, m) for m in utility.get(p.slot, []))
        if used > p.energy:
            return None
        left.append(p.energy - used)
    t = dict(totals)
    choices = [Choice() for _ in pieces]
    relevant = set(minimums) | set(priority)
    n = range(len(pieces))
    stat_costs = {}
    low3 = [lowest3(p.stats) for p in pieces]

    def mod_costs(s):
        if s not in stat_costs:
            stat_costs[s] = (_cost(costs, f"{s} Mod"), _cost(costs, f"Minor {s} Mod"))
        return stat_costs[s]

    def need(s):
        return max(0, minimums.get(s, 0) - t[s])

    def donor(target):
        free = [s for s in STATS if s != target and s not in relevant and t[s] >= 5]
        if not free:
            free = [s for s in minimums if s != target and s not in priority and t[s] - 5 >= minimums[s]]
        return min(free, key=lambda s: (t[s] <= CAP, t[s], STATS.index(s))) if free else None

    def tune(i, s):
        d = donor(s)
        if d is not None:
            t[s] += 5
            t[d] -= 5
            choices[i].tuning = f"+{s} / -{d}"

    def balance(i):
        for k in low3[i]:
            t[k] += 1
        choices[i].tuning = "Balanced Tuning"

    def put(i, s, major):
        name = f"{s} Mod" if major else f"Minor {s} Mod"
        left[i] -= _cost(costs, name)
        t[s] += 10 if major else 5
        choices[i].stat_mod = name

    for i in n:
        if pieces[i].tuned and need(pieces[i].tuned) > 0:
            tune(i, pieces[i].tuned)

    def saves_a_mod(i):
        low = low3[i]
        if any(t[k] >= CAP for k in low):
            return False
        for k in low:
            m = sum(1 for j in range(i, len(pieces))
                    if pieces[j].tuned and choices[j].tuning is None and k in low3[j])
            if 0 < need(k) % 5 <= m:
                return True
        return False

    for i in n:
        if pieces[i].tuned and choices[i].tuning is None and saves_a_mod(i):
            balance(i)

    while True:
        s = max(STATS, key=lambda k: (need(k), -STATS.index(k)))
        if need(s) == 0:
            break
        major_c, minor_c = mod_costs(s)
        free = [i for i in n if choices[i].stat_mod is None and left[i] >= minor_c]
        if not free:
            break
        majors = [i for i in free if left[i] >= major_c]
        if need(s) > 5 and majors:
            put(min(majors, key=lambda i: (left[i], i)), s, True)
        else:
            put(min(free, key=lambda i: (left[i], i)), s, False)

    for s in priority:
        for i in n:
            if pieces[i].tuned == s and choices[i].tuning is None and CAP - t[s] > 1:
                tune(i, s)
        major_c, minor_c = mod_costs(s)
        while t[s] < CAP:
            free = [i for i in n if choices[i].stat_mod is None and left[i] >= minor_c]
            if not free:
                break
            majors = [i for i in free if left[i] >= major_c]
            if CAP - t[s] > 5 and majors:
                put(min(majors, key=lambda i: (left[i], i)), s, True)
            else:
                put(min(free, key=lambda i: (left[i], i)), s, False)

    for i in n:
        if pieces[i].tuned and choices[i].tuning is None:
            if any(need(k) > 0 or (k in priority and t[k] < CAP) for k in low3[i]):
                balance(i)

    fills = []
    for i in n:
        slot = pieces[i].slot
        chosen = fill(left[i], UTILITY_SOCKETS - len(utility.get(slot, [])), fillers.get(slot, []), costs)
        left[i] -= sum(_cost(costs, m) for m in chosen)
        fills.append(chosen)

    deficit = {s: need(s) for s in minimums if need(s) > 0}
    return Result(t, choices, deficit, sum(max(0, t[s] - CAP) for s in STATS), fills, left)
