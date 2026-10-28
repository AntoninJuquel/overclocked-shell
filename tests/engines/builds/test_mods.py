from shell.engines.builds import mods
from shell.engines.builds.inventory import Piece

COSTS = {**{f"{s} Mod": 3 for s in mods.STATS}, **{f"Minor {s} Mod": 1 for s in mods.STATS},
         "Arc Siphon": 3, "Harmonic Siphon": 5}
ZERO = dict.fromkeys(mods.STATS, 0)


def piece(slot, energy=11, tuned=None, stats=None):
    return Piece(item_id=slot, name=slot, slot=slot, tier=5, exotic=False,
                 stats=stats or {**ZERO, "Health": 30, "Grenade": 25, "Super": 20, "Weapons": 5, "Class": 5, "Melee": 5},
                 energy=energy, tuned=tuned, set=None, masterwork_todo=False, location="Vault", locked=True)


SLOTS = ["Helmet", "Gauntlets", "Chest", "Legs", "Class Item"]


def totals(**kw):
    return {**ZERO, **kw}


def test_threshold_reached_only_with_tuning():
    pieces = [piece(s, energy=0, tuned="Grenade") for s in SLOTS]
    res = mods.assign(pieces, totals(Grenade=125, Weapons=25), {"Grenade": 150}, [], COSTS, {})
    assert res.deficit == {}
    assert res.totals["Grenade"] == 150 and res.totals["Weapons"] == 0
    assert all(c.tuning == "+Grenade / -Weapons" for c in res.choices[:5])


def test_minor_when_energy_short_for_major():
    pieces = [piece("Helmet", energy=2)] + [piece(s, energy=0) for s in SLOTS[1:]]
    res = mods.assign(pieces, totals(Health=62), {"Health": 70}, [], COSTS, {})
    assert res.choices[0].stat_mod == "Minor Health Mod"
    assert res.deficit == {"Health": 3}


def test_major_on_smallest_sufficient_energy():
    pieces = [piece("Helmet", energy=11), piece("Gauntlets", energy=3)] + [piece(s, energy=0) for s in SLOTS[2:]]
    res = mods.assign(pieces, totals(Health=60), {"Health": 70}, [], COSTS, {})
    assert res.choices[1].stat_mod == "Health Mod" and res.choices[0].stat_mod is None
    assert res.deficit == {}


def test_utility_mods_reserve_energy_and_can_invalidate():
    pieces = [piece("Helmet", energy=4)] + [piece(s, energy=0) for s in SLOTS[1:]]
    res = mods.assign(pieces, totals(Health=60), {"Health": 70}, [], COSTS, {"Helmet": ["Arc Siphon"]})
    assert res.choices[0].stat_mod == "Minor Health Mod"
    assert mods.assign(pieces, totals(), {}, [], COSTS, {"Helmet": ["Harmonic Siphon"]}) is None


def test_priorities_and_cap():
    pieces = [piece(s, energy=11) for s in SLOTS]
    res = mods.assign(pieces, totals(Class=185, Super=50), {}, ["Class", "Super"], COSTS, {})
    # Class: one Major (195) then one Minor (200), the rest goes to Super (3 Majors)
    assert res.totals["Class"] == 200 and res.totals["Super"] == 80 and res.waste == 0


def test_balanced_tuning_when_low_stats_matter():
    low = {**ZERO, "Health": 30, "Grenade": 25, "Super": 20}
    pieces = [piece("Helmet", energy=0, tuned="Super", stats=low)] + [piece(s, energy=0) for s in SLOTS[1:]]
    res = mods.assign(pieces, totals(), {}, ["Melee"], COSTS, {})
    assert res.choices[0].tuning == "Balanced Tuning" and res.totals["Melee"] == 1


def test_unknown_utility_mod():
    import pytest
    with pytest.raises(ValueError, match="Mystery Mod"):
        mods.assign([piece(s) for s in SLOTS], totals(), {}, [], COSTS, {"Helmet": ["Mystery Mod"]})


def test_priority_minor_goes_to_least_energy_piece():
    pieces = [piece(s, energy=e) for s, e in zip(SLOTS, [3, 1, 0, 0, 0])]
    res = mods.assign(pieces, totals(Class=195, Super=50), {}, ["Class", "Super"], COSTS, {})
    assert res.totals["Class"] == 200 and res.totals["Super"] == 60


def test_priority_major_overshoot_allowed_when_gap_above_five():
    pieces = [piece(s, energy=3) for s in SLOTS]
    res = mods.assign(pieces, totals(Class=191, Super=50), {}, ["Class", "Super"], COSTS, {})
    assert res.totals["Class"] == 201 and res.totals["Super"] == 90


def test_balanced_tuning_before_deficit_mods_frees_energy():
    low = {**ZERO, "Weapons": 30, "Class": 25, "Grenade": 20}
    pieces = [piece("Helmet", energy=3, tuned="Grenade", stats=low)] + [piece(s, energy=0) for s in SLOTS[1:]]
    res = mods.assign(pieces, totals(Health=69, Super=100), {"Health": 70}, ["Super"], COSTS, {})
    assert res.choices[0].tuning == "Balanced Tuning" and res.choices[0].stat_mod == "Super Mod"
    assert res.totals["Health"] == 70 and res.totals["Super"] == 111 and res.deficit == {}


def test_no_balanced_tuning_when_priority_already_capped():
    pieces = [piece(s, energy=0, tuned="Super") for s in SLOTS]
    res = mods.assign(pieces, totals(Melee=200), {}, ["Melee"], COSTS, {})
    assert all(c.tuning is None for c in res.choices) and res.waste == 0 and res.totals["Melee"] == 200


def test_priority_tuning_allowed_with_small_overshoot():
    pieces = [piece("Helmet", energy=0, tuned="Class")] + [piece(s, energy=0) for s in SLOTS[1:]]
    res = mods.assign(pieces, totals(Class=197, Grenade=20), {}, ["Class"], COSTS, {})
    assert res.choices[0].tuning == "+Class / -Grenade" and res.totals["Class"] == 202


def test_missing_minor_cost_raises():
    costs = {k: v for k, v in COSTS.items() if k != "Minor Health Mod"}
    import pytest
    with pytest.raises(ValueError, match="Minor Health Mod"):
        mods.assign([piece(s, energy=11) for s in SLOTS], totals(Health=60), {"Health": 70}, [], costs, {})


def test_donor_prefers_stat_above_cap():
    pieces = [piece("Helmet", energy=0, tuned="Grenade")] + [piece(s, energy=0) for s in SLOTS[1:]]
    res = mods.assign(pieces, totals(Grenade=145, Weapons=205, Melee=10), {"Grenade": 150}, [], COSTS, {})
    assert res.choices[0].tuning == "+Grenade / -Weapons" and res.waste == 0 and res.deficit == {}


def test_donor_falls_back_to_minimum_with_slack():
    pieces = [piece("Helmet", energy=0, tuned="Grenade")] + [piece(s, energy=0) for s in SLOTS[1:]]
    res = mods.assign(pieces, totals(Grenade=145, Health=120), {"Grenade": 150, "Health": 100}, [], COSTS, {})
    assert res.choices[0].tuning == "+Grenade / -Health" and res.deficit == {}


def test_no_donor_no_tuning():
    pieces = [piece("Helmet", energy=0, tuned="Grenade")] + [piece(s, energy=0) for s in SLOTS[1:]]
    res = mods.assign(pieces, totals(Grenade=145), {"Grenade": 150}, [], COSTS, {})
    assert res.choices[0].tuning is None and res.deficit == {"Grenade": 5}


def test_two_competing_minimums_both_filled():
    pieces = [piece(s, energy=3) for s in SLOTS]
    res = mods.assign(pieces, totals(Health=60, Grenade=60), {"Health": 70, "Grenade": 70}, [], COSTS, {})
    names = {c.stat_mod for c in res.choices}
    assert {"Health Mod", "Grenade Mod"} <= names and res.deficit == {}


def test_early_balanced_skipped_when_major_mod_covers_deficit():
    low = {**ZERO, "Weapons": 30, "Class": 25, "Grenade": 20}
    pieces = [piece("Helmet", energy=3, tuned="Super", stats=low)] + [piece(s, energy=0) for s in SLOTS[1:]]
    res = mods.assign(pieces, totals(Health=60, Super=100, Weapons=50), {"Health": 70}, ["Super"], COSTS, {})
    assert res.choices[0].stat_mod == "Health Mod" and res.choices[0].tuning == "+Super / -Weapons"
    assert res.totals["Health"] == 70 and res.totals["Super"] == 105


def test_early_balanced_skipped_when_low_stat_at_cap():
    stats = {**ZERO, "Weapons": 30, "Class": 25, "Super": 20}
    pieces = [piece("Helmet", energy=3, tuned="Weapons", stats=stats)] + [piece(s, energy=0) for s in SLOTS[1:]]
    res = mods.assign(pieces, totals(Health=60, Melee=200), {"Health": 70}, ["Melee"], COSTS, {})
    assert res.choices[0].tuning is None and res.waste == 0


FILL_COSTS = {**COSTS, "Void Siphon": 3, "Heavy Ammo Finder": 3, "Void Targeting": 2, "Ashes to Assets": 1}


def test_fill_uses_all_energy_before_priority():
    # 5 energy, 2 sockets: Siphon (3) + Targeting (2) fills it, Siphon + Ashes would leave 1
    assert mods.fill(5, 2, ["Void Siphon", "Ashes to Assets", "Void Targeting"], FILL_COSTS) == [
        "Void Siphon", "Void Targeting"]


def test_fill_priority_breaks_ties_and_allows_duplicates():
    assert mods.fill(6, 2, ["Void Siphon", "Heavy Ammo Finder", "Void Siphon"], FILL_COSTS) == [
        "Void Siphon", "Heavy Ammo Finder"]
    assert mods.fill(6, 2, ["Void Siphon", "Void Siphon"], FILL_COSTS) == ["Void Siphon", "Void Siphon"]


def test_fill_respects_sockets_and_energy():
    assert mods.fill(9, 1, ["Void Siphon", "Void Targeting"], FILL_COSTS) == ["Void Siphon"]
    assert mods.fill(1, 3, ["Void Siphon"], FILL_COSTS) == []
    assert mods.fill(5, 0, ["Void Siphon"], FILL_COSTS) == []


def test_assign_fills_left_energy_after_stat_mods():
    pieces = [piece("Helmet", energy=11)] + [piece(s, energy=0) for s in SLOTS[1:]]
    res = mods.assign(pieces, totals(Health=60), {"Health": 70}, [], FILL_COSTS, {"Helmet": ["Void Siphon"]},
                      fillers={"Helmet": ["Heavy Ammo Finder", "Void Targeting", "Ashes to Assets"]})
    assert res.choices[0].stat_mod == "Health Mod"
    # 11 - 3 (Siphon) - 3 (Health Mod) = 5: two free sockets → Finder (3) + Targeting (2)
    assert res.fills[0] == ["Heavy Ammo Finder", "Void Targeting"]
    assert res.energy_left[0] == 0
    assert res.fills[1] == [] and res.energy_left[1] == 0


def test_assign_without_fill_reports_left_energy():
    pieces = [piece("Helmet", energy=11)] + [piece(s, energy=0) for s in SLOTS[1:]]
    res = mods.assign(pieces, totals(Health=60), {"Health": 70}, [], FILL_COSTS, {"Helmet": ["Void Siphon"]})
    assert res.fills[0] == [] and res.energy_left[0] == 5


def test_fill_unknown_mod():
    import pytest
    with pytest.raises(ValueError, match="Mystery Mod"):
        mods.assign([piece(s) for s in SLOTS], totals(), {}, [], COSTS, {}, fillers={"Helmet": ["Mystery Mod"]})
