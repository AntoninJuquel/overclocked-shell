from shell.engines.locations import read_locations
from shell.engines.locking import set_lock

from .fakes import FakeActions
from .fixtures import DEFS, profile


def run(ids, locked, dry_run=False, errors=None):
    p = profile()
    p["characterInventories"]["data"]["w"]["items"].append({"itemHash": 101, "bucketHash": 215593132})
    actions = FakeActions(errors)
    locs, class_of = read_locations(p, DEFS)
    return set_lock(actions, locs, class_of, ids, locked, dry_run), actions


def test_locks_and_skips_already_locked():
    result, actions = run(['"g3"', "a1", "g2", "g2 "], True)
    assert result == {"dry_run": False, "changed": 2, "items": [
        {"itemId": "g3", "name": "Axe", "result": "locked"},
        {"itemId": "a1", "name": "Star-Eater Scales", "result": "already locked"},
        {"itemId": "g2", "name": "Bow", "result": "locked"}]}
    assert actions.posts == [("SetLockState", {"state": True, "itemId": "g3", "characterId": "w"}),
                             ("SetLockState", {"state": True, "itemId": "g2", "characterId": "w"})]


def test_vault_item_uses_first_character():
    _, actions = run(["g1"], False)
    assert actions.posts == [("SetLockState", {"state": False, "itemId": "g1", "characterId": "w"})]


def test_dry_run_posts_nothing():
    result, actions = run(["g3"], True, dry_run=True)
    assert result["items"][0]["result"] == "would lock" and result["changed"] == 0 and actions.posts == []


def test_not_found_and_pm_ids_skipped():
    result, actions = run(["nope", "pm:w:101:2"], True)
    assert [i["result"] for i in result["items"]] == ["not found", "not found"] and actions.posts == []


def test_failure_named_and_batch_continues():
    result, actions = run(["g3", "g2"], True, errors=[1623])
    assert result["items"][0]["result"] == "failed: item not found (Bungie error 1623)"
    assert result["items"][1]["result"] == "locked" and result["changed"] == 1
