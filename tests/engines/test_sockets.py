import copy

from shell.engines.sockets import apply, candidates, norm, plan_item

from .fakes import FakeActions
from .fixtures import DEFS

D = copy.deepcopy(DEFS)
D["plugs"].update({
    "30": {"n": "Empty Mod Socket", "t": "Armor Mod", "p": "enhancements.v2_general"},
    "31": {"n": "Weapons Mod", "t": "General Armor Mod", "p": "enhancements.v2_general"},
    "32": {"n": "Grenade Mod", "t": "General Armor Mod", "p": "enhancements.v2_general"},
    "33": {"n": "Firepower", "t": "Helmet Armor Mod", "p": "enhancements.v2_head"},
    "34": {"n": "Harmonic Siphon", "t": "Helmet Armor Mod", "p": "enhancements.v2_head"},
})
MODS = [30, 31, 32, 33, 34]


def plan(current, requests, force=False, reusable=None):
    return plan_item("i", "w", "Helm", current, [MODS] * len(current), reusable or {}, requests, D, force)


def test_norm():
    assert norm("Ember of Torches!") == "emberoftorches"


def test_candidates_order_and_dedupe():
    item_def = {"sockets": {"socketEntries": [
        {"reusablePlugSetHash": 7, "reusablePlugItems": [{"plugItemHash": 4}], "singleInitialItemHash": 1},
        {"randomizedPlugSetHash": 8, "singleInitialItemHash": 0}]}}
    live_sets = {"7": [{"plugItemHash": 2, "canInsert": True}, {"plugItemHash": 9, "canInsert": False}]}
    set_defs = {7: {"reusablePlugItems": [{"plugItemHash": 3}, {"plugItemHash": 2}]}, 8: {}}
    assert candidates(item_def, {"0": [{"plugItemHash": 5}]}, live_sets, set_defs.get) == [[5, 2, 3, 4, 1], []]


def test_already_installed_is_kept():
    plans, notes = plan([31, 30], ["Weapons Mod"])
    assert plans == [] and notes == ["Weapons Mod already in socket 0"]


def test_prefers_empty_then_unrequested_socket():
    plans, _ = plan([33, 30], ["Grenade Mod"])
    assert [(p["socketIndex"], p["from"], p["to"]) for p in plans] == [(1, "Empty Mod Socket", "Grenade Mod")]
    plans, _ = plan([33, 31], ["Grenade Mod", "Weapons Mod"])
    assert [(p["socketIndex"], p["to"]) for p in plans] == [(0, "Grenade Mod")]


def test_indexed_empty_on_taken_socket_skipped():
    plans, notes = plan([31, 34], ["Weapons Mod", {"name": "Empty Mod Socket", "socketIndex": 0},
                                   {"name": "Empty Mod Socket", "socketIndex": 1}])
    assert [(p["socketIndex"], p["to"]) for p in plans] == [(1, "Empty Mod Socket")]
    assert 'no free socket left for "Empty Mod Socket"' in notes


def test_empty_removals_first_and_live_hashes_first():
    plans, _ = plan([33, 34], ["Grenade Mod", {"name": "Empty Mod Socket", "socketIndex": 1}],
                    reusable={"0": [{"plugItemHash": 32, "canInsert": True}]})
    assert [p["to"] for p in plans] == ["Empty Mod Socket", "Grenade Mod"]
    assert plans[1]["hashes"] == [32]


def test_unknown_and_wrong_socket_noted():
    _, notes = plan([30], ["Nope", {"name": "Grenade Mod", "socketIndex": 5}])
    assert notes == ['no socket takes "Nope" (check spelling or unlocks)', 'socket 5 can\'t take "Grenade Mod"']


def change(hashes, index=0):
    return {"itemId": "i", "characterId": "w", "socketIndex": index, "from": "a", "to": "b", "hashes": hashes}


def test_apply_tries_next_hash_on_1680_only():
    actions = FakeActions(errors=[1680, None, 1679])
    results = apply(actions, [change([1, 2]), change([3, 4], 1)])
    assert [b["plug"]["plugItemHash"] for _, b in actions.posts] == [1, 2, 3]
    assert results[0] == "done" and results[1].startswith("failed: plug already in this or another socket")
    assert actions.posts[0][1] == {"plug": {"socketIndex": 0, "socketArrayType": 0, "plugItemHash": 1},
                                   "itemId": "i", "characterId": "w"}
    assert actions.sleeps == [0.6, 0.6, 0.6]


def test_apply_stops_on_not_in_orbit():
    actions = FakeActions(errors=[1634])
    results = apply(actions, [change([1]), change([2], 1)])
    assert results[0].startswith("failed: character not in orbit") and results[1] == "not attempted: go to orbit"
    assert len(actions.posts) == 1


def test_same_plugs_in_another_order_is_nothing_to_do():
    defs = {"plugs": {str(h): {"n": n, "t": "", "p": ""} for h, n in {1: "A", 2: "B", 3: "C", 9: "Junk"}.items()},
            "weapons": {}, "gear": {}, "misc": {}}
    cands = [[1, 2, 3, 9]] * 3
    aimed = [{"name": "A", "socketIndex": 0}, {"name": "B", "socketIndex": 1}, {"name": "C", "socketIndex": 2}]
    plans, notes = plan_item("i", "c", "n", [3, 1, 2], cands, {}, aimed, defs, False)
    assert plans == [] and not [n for n in notes if "no free socket" in n]
    # outside the sockets asked for, a plug is not "already there": it must move (the sockets may be disabled)
    plans, notes = plan_item("i", "c", "n", [9, 9, 1], cands, {}, aimed[:2], defs, False)
    assert ("A", 0) in [(p["to"], p["socketIndex"]) for p in plans]
