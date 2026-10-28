"""Armor inventory snapshot → candidate pieces for a build."""
import re
from dataclasses import dataclass

from shell.engines.builds.stats import STATS

_STAT_MOD = re.compile(r"General Armor Mod: (Minor )?(\w+) Mod$")
_TUNING = re.compile(r"General Armor Mod: \+(\w+) / -(\w+)$")
LEGACY_MAX_ENERGY = 10  # a masterworked legacy piece shows "x/10"


@dataclass
class Piece:
    item_id: str
    name: str
    slot: str
    tier: int
    exotic: bool
    stats: dict            # starting stats: mods removed, masterwork projected
    energy: int            # energy capacity (projected to 10 for a legacy piece not masterworked)
    tuned: str | None      # stat raised by the piece's tuning mods
    set: str | None
    masterwork_todo: bool
    location: str
    locked: bool


def lowest3(stats):
    """The 3 lowest stats (non-focus), stable order."""
    return sorted(STATS, key=lambda k: (stats[k], STATS.index(k)))[:3]


def base_stats(item):
    """Stats without the stat mods and tuning applied.

    Artifice "X Forged" mods (+3) are deliberately NOT removed: the optimizer never touches the artifice
    socket, so the +3 stays in play and must stay counted.
    """
    s = {k: item["stats"].get(k, 0) for k in STATS}
    balanced = False
    for p in item["plugs"]:
        m = _STAT_MOD.match(p)
        if m and m.group(2) in STATS:
            s[m.group(2)] -= 5 if m.group(1) else 10
        m = _TUNING.match(p)
        if m:
            s[m.group(1)] -= 5
            s[m.group(2)] += 5
        if p == "General Armor Mod: Balanced Tuning":
            balanced = True
    if balanced:
        for k in lowest3(s):
            s[k] -= 1
    return s


def project_mw(stats):
    """Armor 3.0 masterwork: the 3 non-focus stats go to 5.

    Set to 5 (not +5) because a partly upgraded piece shows 1 to 3; the rule is assumed to hold for
    tiers 1 to 4 too.
    """
    s = dict(stats)
    for k in lowest3(s):
        s[k] = 5
    return s


def has_tuning_data(items):
    """Does the snapshot carry the tuning stat?"""
    return bool(items) and all("tunedStat" in it for it in items)


def load_pieces(items, cls, exotic, sets_by_hash, require_exotic=True):
    """{slot: [Piece]}: the class's legendaries of tier >= 1 + copies of the requested exotic."""
    wanted = {f"Intrinsic: {p}" for p in exotic.get("perks", [])}
    out = {}
    for it in items:
        if it["classType"] != cls or "(Postmaster)" in it["location"]:
            continue
        tier = it.get("gearTier") or 0
        is_exotic = it["rarity"] == "Exotic"
        if is_exotic and (it["name"] != exotic["name"] or not wanted <= set(it["plugs"])):
            continue
        if not is_exotic and tier < 1:
            continue
        stats = base_stats(it)
        todo = not it["masterworked"]
        if todo and tier >= 1:
            stats = project_mw(stats)
        # Legacy piece (tier 0) not masterworked: masterwork to do and energy projected to 10, but stats
        # unchanged (cautious: the legacy masterwork bonus is not projected).
        energy = int(it["energy"].rpartition("/")[2] or 0) if it.get("energy") else 0
        if todo and tier == 0:
            energy = LEGACY_MAX_ENERGY
        out.setdefault(it["slot"], []).append(Piece(
            item_id=it["itemId"], name=it["name"], slot=it["slot"], tier=tier, exotic=is_exotic,
            stats=stats, energy=energy, tuned=it.get("tunedStat"),
            set=(sets_by_hash.get(it["itemHash"]) or {}).get("set"),
            masterwork_todo=todo, location=it["location"], locked=it["locked"]))
    if require_exotic and exotic_slot(out) is None:
        raise ValueError(f"exotic not found in the inventory for {cls}: {exotic['name']}"
                         + (f" ({', '.join(exotic['perks'])})" if exotic.get("perks") else ""))
    return out


def exotic_slot(pieces):
    for slot, lst in pieces.items():
        if any(p.exotic for p in lst):
            return slot
    return None
