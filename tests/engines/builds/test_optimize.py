import dataclasses
import itertools
import json
import random

import pytest

from shell.engines.builds import optimize, sheet as sheet_mod
from shell.engines.builds.inventory import Piece
from shell.engines.builds.stats import SLOTS

COSTS = {**{f"{s} Mod": 3 for s in optimize.STATS}, **{f"Minor {s} Mod": 1 for s in optimize.STATS}}
Z = dict.fromkeys(optimize.STATS, 0)


def p(item_id, slot, *, exotic=False, set_=None, tuned=None, energy=0, mw_todo=False, location="Warlock", **st):
    return Piece(item_id=item_id, name=item_id, slot=slot, tier=5, exotic=exotic, stats={**Z, **st},
                 energy=energy, tuned=tuned, set=set_, masterwork_todo=mw_todo, location=location, locked=True)


def base_pieces():
    return {
        "Helmet": [p("h1", "Helmet", Health=30), p("h2", "Helmet", Health=20, set_="AION")],
        "Gauntlets": [p("g1", "Gauntlets", Health=30), p("g2", "Gauntlets", Health=20, set_="AION")],
        "Chest": [p("x", "Chest", exotic=True, Health=10)],
        "Legs": [p("l1", "Legs", Health=30)],
        "Class Item": [p("c1", "Class Item", Health=30)],
    }


INTENT = {"exotic": {"name": "x"}, "stats": {"minimums": {}, "priority": ["Health"]}, "sets": [], "armor_mods": {}}


def test_prune_dominated():
    pieces = [p("a", "Helmet", Health=30, Grenade=20), p("b", "Helmet", Health=25, Grenade=20),
              p("c", "Helmet", Health=20, Grenade=30)]
    kept = optimize.prune(pieces, ["Health", "Grenade"], set())
    assert [x.item_id for x in kept] == ["a", "c"]


def test_prune_keeps_required_set_and_tuning():
    pieces = [p("a", "Helmet", Health=30), p("b", "Helmet", Health=25, set_="AION"),
              p("c", "Helmet", Health=20, tuned="Health")]
    kept = optimize.prune(pieces, ["Health"], {"AION"})
    assert [x.item_id for x in kept] == ["a", "b", "c"]


def test_best_combination_by_priority():
    out = optimize.optimize(base_pieces(), INTENT, {}, COSTS, "Warlock", top=2)
    assert out["feasible"]
    best = out["results"][0]
    assert {a["itemId"] for a in best["armor"]} == {"h1", "g1", "x", "l1", "c1"}
    assert best["stats"]["Health"] == 130


def test_set_constraint_beats_raw_stats():
    intent = {**INTENT, "sets": [{"set": "AION", "pieces": 2}]}
    best = optimize.optimize(base_pieces(), intent, {}, COSTS, "Warlock")["results"][0]
    assert {"h2", "g2"} <= {a["itemId"] for a in best["armor"]}


def test_fragments_count_and_infeasible_report():
    intent = {**INTENT, "stats": {"minimums": {"Health": 150}, "priority": []}}
    out = optimize.optimize(base_pieces(), intent, {"Health": 10}, COSTS, "Warlock")
    assert not out["feasible"]
    assert len(out["results"]) <= 3
    assert out["results"][0]["deficit"] == {"Health": 10}   # 130 + 10 (fragment) = 140


def test_fewer_actions_breaks_ties():
    pieces = base_pieces()
    pieces["Legs"] = [p("l1", "Legs", Health=30, mw_todo=True, energy=11), p("l2", "Legs", Health=30, location="Vault", energy=11)]
    out = optimize.optimize(pieces, INTENT, {}, COSTS, "Warlock")
    legs = [a for a in out["results"][0]["armor"] if a["slot"] == "Legs"][0]
    assert legs["itemId"] == "l2"


def test_write_keeps_intent_and_weapons(tmp_path):
    s = {"name": "T", "class": "Warlock", "subclass": {"element": "Arc", "fragments": []},
         "intent": INTENT, "resolved": {"weapons": [{"slot": "Kinetic", "itemId": "9", "name": "W"}],
                                        "rationale": ["r"]}}
    path = tmp_path / "t.json"
    sheet_mod.save(path, s)
    out = optimize.optimize(base_pieces(), INTENT, {}, COSTS, "Warlock")
    optimize.write_result(path, out["results"][0], today="2026-10-07")
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["intent"] == INTENT
    assert saved["resolved"]["weapons"] == [{"slot": "Kinetic", "itemId": "9", "name": "W"}]
    assert saved["resolved"]["date"] == "2026-10-07"
    assert [a["slot"] for a in saved["resolved"]["armor"]] == ["Helmet", "Gauntlets", "Chest", "Legs", "Class Item"]
    assert "## Result (2026-10-07)" in (tmp_path / "t.md").read_text(encoding="utf-8")


def test_fill_mods_prefer_fillable_energy_and_are_written(tmp_path):
    costs = {**COSTS, "Void Siphon": 3, "Ashes to Assets": 1}
    pieces = base_pieces()
    pieces["Helmet"] = [p("h1", "Helmet", Health=30, energy=3), p("h2", "Helmet", Health=30, energy=11, location="Vault")]
    intent = {**INTENT, "stats": {"minimums": {}, "priority": []}, "armor_mods": {"Helmet": ["Void Siphon"]},
              "armor_mods_fill": {"Helmet": ["Void Siphon", "Ashes to Assets"]}}
    best = optimize.optimize(pieces, intent, {}, costs, "Warlock")["results"][0]
    helmet = best["armor"][0]
    # h2 (11): the intent's Siphon, then Siphon + Ashes as fillers; preferred despite the transfer
    assert helmet["itemId"] == "h2"
    assert helmet["mods"] == ["Void Siphon", "Void Siphon", "Ashes to Assets"] and helmet["energy_left"] == 4
    s = {"name": "T", "class": "Warlock", "subclass": {"element": "Arc", "fragments": []}, "intent": intent}
    path = tmp_path / "t.json"
    sheet_mod.save(path, s)
    optimize.write_result(path, best, today="2026-10-07")
    saved = json.loads(path.read_text(encoding="utf-8"))["resolved"]["armor"][0]
    assert saved["mods"] == ["Void Siphon", "Void Siphon", "Ashes to Assets"]


def test_no_exotic_slot_is_an_error():
    pieces = base_pieces()
    pieces["Chest"] = []
    with pytest.raises(ValueError, match="exotic"):
        optimize.optimize(pieces, INTENT, {}, COSTS, "Warlock")


def test_negative_totals_are_floored_and_writable(tmp_path):
    s = {"name": "T", "class": "Warlock", "subclass": {"element": "Arc", "fragments": []},
         "intent": INTENT, "resolved": {"weapons": [{"slot": "Kinetic", "itemId": "9", "name": "W"}],
                                        "rationale": ["r"]}}
    path = tmp_path / "t.json"
    sheet_mod.save(path, s)
    out = optimize.optimize(base_pieces(), INTENT, {"Weapons": -10}, COSTS, "Warlock")
    best = out["results"][0]
    assert best["stats"]["Weapons"] == 0
    assert all(v >= 0 for v in best["stats"].values())
    optimize.write_result(path, best, today="2026-10-07")
    assert json.loads(path.read_text(encoding="utf-8"))["resolved"]["stats"]["Weapons"] == 0


# ---- pruning details -------------------------------------------------------------------------------------

def test_prune_keeps_piece_already_on_character():
    pieces = [p("a", "Helmet", Health=30, location="Vault"), p("b", "Helmet", Health=30)]
    assert [x.item_id for x in optimize.prune(pieces, ["Health"], set(), "Warlock")] == ["b"]
    out = optimize.optimize({**base_pieces(), "Helmet": pieces}, INTENT, {}, COSTS, "Warlock")
    assert out["results"][0]["actions"]["transfers"] == 0


def test_prune_keeps_any_tuned_piece():
    pieces = [p("a", "Helmet", Health=30), p("b", "Helmet", Health=30, tuned="Melee")]
    kept = optimize.prune(pieces, ["Health"], set(), "Warlock")
    assert [x.item_id for x in kept] == ["b"]                      # the tuned piece is never beaten by a bare one
    assert [x.item_id for x in optimize.prune(pieces[::-1], ["Health"], set(), "Warlock")] == ["b"]
    two = [p("a", "Helmet", Health=30, tuned="Grenade"), p("b", "Helmet", Health=30, tuned="Melee")]
    assert len(optimize.prune(two, ["Health"], set(), "Warlock")) == 2


def test_prune_compares_useful_energy_only():
    pieces = [p("a", "Helmet", Health=30, energy=11), p("b", "Helmet", Health=30, energy=5)]
    assert [x.item_id for x in optimize.prune(pieces, ["Health"], set(), "Warlock", energy_cap=3)] == ["a"]
    low = [p("a", "Helmet", Health=30, energy=2), p("b", "Helmet", Health=30, energy=5)]
    assert [x.item_id for x in optimize.prune(low, ["Health"], set(), "Warlock", energy_cap=3)] == ["b"]


# ---- search behaviour ------------------------------------------------------------------------------------

def test_infeasible_top5_returns_three():
    intent = {**INTENT, "stats": {"minimums": {"Health": 200}, "priority": ["Grenade"]}}
    pieces = base_pieces()
    pieces["Helmet"] = [p(f"h{i}", "Helmet", Health=10 + i, Grenade=20 - i) for i in range(6)]
    out = optimize.optimize(pieces, intent, {}, COSTS, "Warlock", top=5)
    assert not out["feasible"] and len(out["results"]) == 3 and out["complete"]


def test_utility_mods_over_energy_gives_no_result():
    intent = {**INTENT, "armor_mods": {"Helmet": ["Health Mod"]}}
    out = optimize.optimize(base_pieces(), intent, {}, COSTS, "Warlock")
    assert out["results"] == [] and not out["feasible"]


def test_unreachable_set_requirement_gives_no_result():
    intent = {**INTENT, "sets": [{"set": "AION", "pieces": 3}]}
    assert optimize.optimize(base_pieces(), intent, {}, COSTS, "Warlock")["results"] == []


def test_two_required_sets():
    pieces = base_pieces()
    pieces["Legs"] = [p("l1", "Legs", Health=30), p("l2", "Legs", Health=10, set_="B")]
    pieces["Class Item"] = [p("c1", "Class Item", Health=30), p("c2", "Class Item", Health=10, set_="B")]
    intent = {**INTENT, "sets": [{"set": "AION", "pieces": 2}, {"set": "B", "pieces": 2}]}
    best = optimize.optimize(pieces, intent, {}, COSTS, "Warlock")["results"][0]
    assert {a["itemId"] for a in best["armor"]} >= {"h2", "g2", "l2", "c2"}


def test_input_order_does_not_matter():
    rng = random.Random(7)
    pieces = {s: [p(f"{s[0]}{i}", s, Health=rng.choice([10, 20, 30]), Grenade=rng.choice([0, 10, 20]),
                    location=rng.choice(["Warlock", "Vault"])) for i in range(4)] for s in SLOTS}
    pieces["Chest"] = [dataclasses.replace(x, exotic=True) for x in pieces["Chest"]]
    intent = {**INTENT, "stats": {"minimums": {"Grenade": 40}, "priority": ["Health"]}}
    ref = optimize.optimize(pieces, intent, {}, COSTS, "Warlock", top=4)
    for seed in range(5):
        shuffled = {s: random.Random(seed).sample(v, len(v)) for s, v in pieces.items()}
        assert optimize.optimize(shuffled, intent, {}, COSTS, "Warlock", top=4) == ref


def test_search_stops_at_the_evaluation_limit(monkeypatch):
    monkeypatch.setattr(optimize, "MAX_EVALS", 1)
    pieces = base_pieces()
    pieces["Legs"] = [p(f"l{i}", "Legs", Health=10 * i, Grenade=40 - 10 * i) for i in range(1, 4)]
    intent = {**INTENT, "stats": {"minimums": {}, "priority": ["Health", "Grenade"]}}
    out = optimize.optimize(pieces, intent, {}, COSTS, "Warlock")
    assert not out["complete"] and out["combinations"] == 1


def _random_pieces(rng, values=(0, 5, 10, 15, 20, 25, 30)):
    pieces = {}
    for slot in SLOTS:
        pieces[slot] = [
            p(f"{slot[0]}{slot[1]}{i}", slot, exotic=slot == "Chest", set_=None if slot == "Chest" else rng.choice([None, "A"]),
              tuned=rng.choice([None, *optimize.STATS]), energy=rng.choice([0, 1, 3, 11]),
              mw_todo=rng.random() < .3, location=rng.choice(["Warlock", "Vault"]),
              **{s: rng.choice(values) for s in optimize.STATS})
            for i in range(rng.randint(2, 3))]
    return pieces


def _brute(pieces, intent, frag, costs, cls):
    req = {e["set"]: e["pieces"] for e in intent["sets"]}
    best = None
    for combo in itertools.product(*(pieces[s] for s in SLOTS)):
        if any(sum(x.set == name for x in combo) < n for name, n in req.items()):
            continue
        ev = optimize._evaluate(combo, frag, intent, costs, cls)
        if ev and (best is None or ev[0] > best[0]):
            best = ev
    return best


def _filled(result, intent):
    util = intent.get("armor_mods", {})
    return sum(COSTS[m] for a in result["armor"] for m in a["mods"][len(util.get(a["slot"], [])):])


def _check_against_brute_force(seed, rounds, values, minimums, fragments, components=6):
    rng = random.Random(seed)
    for _ in range(rounds):
        pieces = _random_pieces(rng, values)
        stats = rng.sample(optimize.STATS, 4)
        intent = {"exotic": {"name": "x"},
                  "stats": {"minimums": {s: rng.choice(minimums) for s in stats[:rng.randint(0, 2)]},
                            "priority": stats[2:2 + rng.randint(0, 2)]},
                  "sets": [{"set": "A", "pieces": rng.randint(2, 3)}] if rng.random() < .4 else [],
                  "armor_mods": {"Helmet": ["Minor Health Mod"]} if rng.random() < .3 else {},
                  "armor_mods_fill": {"Helmet": ["Minor Class Mod", "Health Mod"],
                                      "Legs": ["Grenade Mod"] * 3} if rng.random() < .5 else {}}
        frag = {rng.choice(optimize.STATS): rng.choice(fragments)}
        out = optimize.optimize(pieces, intent, frag, COSTS, "Warlock", top=2)
        want = _brute(pieces, intent, frag, COSTS, "Warlock")
        if want is None:
            assert out["results"] == []
            continue
        got = out["results"][0]
        prio = intent["stats"]["priority"]
        assert (got["feasible"], -sum(got["deficit"].values()),
                tuple(min(max(0, got["stats"][s]), optimize.CAP) for s in prio),
                -got["waste"], _filled(got, intent), -got["actions"]["masterwork"],
                -got["actions"]["transfers"])[:components] == want[0][:components], intent


def test_search_matches_brute_force(seed=2024):
    _check_against_brute_force(seed, 200, (0, 5, 10, 15, 20, 25, 30), (20, 40, 60), (-10, 0, 10))


def test_search_is_exact_near_the_cap(monkeypatch):
    """Without pruning: the search alone is exact on every component of the key."""
    monkeypatch.setattr(optimize, "prune", lambda pieces, *a, **k: list(pieces))
    _check_against_brute_force(99, 200, (0, 5, 15, 25, 35, 45), (60, 120, 190), (-10, 0, 20, 40, 60))


def test_pruning_keeps_feasibility_near_the_cap():
    """With pruning: feasibility stays exact. The deficit and priority stats can differ by one point in rare
    cases (mods.assign reads irrelevant stats), and so can the tie-breaks."""
    _check_against_brute_force(99, 200, (0, 5, 15, 25, 35, 45), (60, 120, 190), (-10, 0, 20, 40, 60), components=1)


def test_check_sets_unknown_name_suggests_manifest_name():
    known = {"Smoke Jumper Set", "AION Renewal", "AION Adapter"}
    with pytest.raises(ValueError, match=r"^unknown set: Smoke Jumper \(suggestion: Smoke Jumper Set\)$"):
        optimize.check_sets({"sets": [{"set": "Smoke Jumper", "pieces": 2}]}, known)
    with pytest.raises(ValueError, match=r"^unknown set: Zzz$"):
        optimize.check_sets({"sets": [{"set": "Zzz", "pieces": 2}]}, known)


def test_check_sets_known_names_pass():
    optimize.check_sets({"sets": [{"set": "AION Renewal", "pieces": 2}]}, {"AION Renewal"})
    optimize.check_sets({"sets": []}, set())


def test_evaluate_given_combination():
    pieces = base_pieces()
    combo = [pieces["Class Item"][0], pieces["Helmet"][1], pieces["Gauntlets"][0], pieces["Chest"][0],
             pieces["Legs"][0]]   # any order
    res = optimize.evaluate(combo, {}, INTENT, COSTS, "Warlock")
    assert res.totals["Health"] == 120    # 20 + 30 + 10 + 30 + 30
    assert not res.deficit


def test_evaluate_none_when_utility_mods_do_not_fit():
    intent = {**INTENT, "armor_mods": {"Helmet": ["Health Mod"]}}   # costs 3, the helmet has 0 energy
    combo = [lst[0] for lst in base_pieces().values()]
    assert optimize.evaluate(combo, {}, intent, COSTS, "Warlock") is None


def test_masterwork_is_written_in_english():
    pieces = base_pieces()
    pieces["Legs"] = [p("l1", "Legs", Health=30, mw_todo=True)]
    armor = optimize.optimize(pieces, INTENT, {}, COSTS, "Warlock")["results"][0]["armor"]
    assert {a["slot"]: a["masterwork"] for a in armor}["Legs"] == "todo"
    assert {a["masterwork"] for a in armor if a["slot"] != "Legs"} == {"done"}


@pytest.mark.parametrize("specs,no_sets,message", [
    (["AION"], False, "sets"), (["AION:3"], False, "sets"), (["AION:2"], True, "no_sets"),
])
def test_invalid_set_override(specs, no_sets, message):
    with pytest.raises(ValueError, match=message):
        optimize.parse_set_override(specs, no_sets)


def test_set_override_parses():
    assert optimize.parse_set_override(["AION:2", " B :2"], False) == [{"set": "AION", "pieces": 2},
                                                                      {"set": "B", "pieces": 2}]
    assert optimize.parse_set_override(None, True) == []
    assert optimize.parse_set_override(None, False) is None


def test_versus_resolved():
    piece = {"slot": "Helmet", "itemId": "1", "name": "Hood", "stat_mod": "Grenade Mod", "tuning": None, "mods": []}
    result = {"armor": [piece], "stats": {"Grenade": 100, "Super": 50}}
    assert optimize.versus_resolved(result, {}) is None
    resolved = {"armor": [piece], "stats": {"Grenade": 100, "Super": 50}}
    assert optimize.versus_resolved(result, resolved) == {"same": True, "pieces": [], "mods": [], "stats": {}}
    other = {**piece, "itemId": "2", "name": "Mask"}
    out = optimize.versus_resolved(result, {"armor": [other], "stats": {"Grenade": 90, "Super": 50}})
    assert out["pieces"] == [{"slot": "Helmet", "from": "Mask", "to": "Hood"}] and out["stats"] == {"Grenade": 10}
    out = optimize.versus_resolved(result, {"armor": [{**piece, "stat_mod": None}], "stats": result["stats"]})
    assert not out["same"] and out["mods"][0]["slot"] == "Helmet" and out["pieces"] == []
