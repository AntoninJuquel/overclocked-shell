from shell.engines.equipping import equip

from .fakes import FakeActions
from .test_moving import BUCKET, CLASS_OF, locations


def status(*pairs):
    return {"equipResults": [{"itemInstanceId": i, "equipStatus": s} for i, s in pairs]}


def run(ids, dry_run=False, errors=None, responses=None):
    actions = FakeActions(errors, responses)
    return equip(actions, locations(), CLASS_OF, "w", ids, dry_run, BUCKET.get), actions


def test_moves_then_single_equip_call():
    result, actions = run(["v1", "w2", "h1"], responses={"EquipItems": [status(("v1", 1), ("w2", 1), ("h1", 1))]})
    assert [m["result"] for m in result["moves"]] == [
        "moved vault -> warlock", "already on warlock", "moved other character -> vault -> warlock"]
    assert actions.posts[-1] == ("EquipItems", {"itemIds": ["v1", "w2", "h1"], "characterId": "w"})
    assert [p[0] for p in actions.posts].count("EquipItems") == 1
    assert result["equipped"] == 3 and {e["result"] for e in result["equip"]} == {"equipped"}


def test_exotic_clash_retried_once():
    result, actions = run(["w2", "e1"], responses={"EquipItems": [status(("w2", 1641), ("e1", 1)), status(("w2", 1))]})
    assert actions.posts[-1] == ("EquipItems", {"itemIds": ["w2"], "characterId": "w"})
    assert result["equipped"] == 2


def test_clash_twice_reported():
    result, _ = run(["w2"], responses={"EquipItems": [status(("w2", 1641)), status(("w2", 1641))]})
    assert result["equip"][0]["result"] == "not equipped: unique-equip exotic clash" and result["equipped"] == 0


def test_skips_postmaster_and_equipped_elsewhere():
    locs = locations()
    locs["e2"] = {**locs["e1"], "itemId": "e2", "characterId": "h", "name": "item-e2"}
    actions = FakeActions(responses={"EquipItems": [status(("e1", 1))]})
    result = equip(actions, locs, CLASS_OF, "w", ["p1", "e2", "nope", "e1"], False, BUCKET.get)
    assert [m["result"] for m in result["moves"]] == [
        "in the postmaster: pull it first", "equipped on another character: unequip it there first", "not found",
        "already on warlock (equipped)"]
    assert actions.posts == [("EquipItems", {"itemIds": ["e1"], "characterId": "w"})]


def test_dry_run_reports_routes_and_posts_nothing():
    result, actions = run(["v1", "h1"], dry_run=True)
    assert [m["result"] for m in result["moves"]] == [
        "would move vault -> warlock", "would move other character -> vault -> warlock"]
    assert [e["result"] for e in result["equip"]] == ["would equip", "would equip"] and actions.posts == []


def test_failed_move_not_equipped():
    result, actions = run(["v1"], errors=[1623])
    assert result["moves"][0]["result"] == "move failed: item not found (Bungie error 1623)"
    assert result["equip"] == [] and result["equipped"] == 0
