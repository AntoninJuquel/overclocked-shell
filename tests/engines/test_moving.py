import pytest

from shell.core.bungie import BungieApiError
from shell.engines.moving import pull_postmaster, transfer

from .fakes import FakeActions

BUCKET = {1: 10, 2: 10, 3: 20}


def loc(item_id, h, where, cid=None, quantity=1):
    return {"itemId": item_id, "itemHash": h, "bucketHash": BUCKET[h], "where": where, "characterId": cid,
            "quantity": quantity, "locked": False, "name": f"item-{item_id}"}


def locations():
    return {l["itemId"]: l for l in [
        loc("v1", 1, "vault"), loc("v2", 2, "vault"), loc("h1", 1, "inventory", "h"),
        loc("w1", 2, "inventory", "w"), loc("w2", 3, "inventory", "w"), loc("e1", 1, "equipped", "w"),
        loc("p1", 3, "postmaster", "w"), loc("pm:w:3:7", 3, "postmaster", "w", quantity=4)]}


CLASS_OF = {"w": 2, "h": 1}


def run(ids, to, dry_run=False, errors=None):
    actions = FakeActions(errors)
    result = transfer(actions, locations(), CLASS_OF, ids, to, dry_run, BUCKET.get)
    return result, actions


def test_vault_to_character_one_leg():
    result, actions = run(["v1"], "warlock")
    assert result["moved"] == 1 and result["items"][0]["result"] == "moved to warlock"
    assert actions.posts == [("TransferItem", {"itemReferenceHash": 1, "stackSize": 1, "transferToVault": False,
                                               "itemId": "v1", "characterId": "w"})]


def test_character_to_character_via_vault():
    _, actions = run(["h1"], "warlock")
    assert [(b["transferToVault"], b["characterId"]) for _, b in actions.posts] == [(True, "h"), (False, "w")]


def test_full_bucket_makes_room_once():
    result, actions = run(["v1", "v2"], "warlock", errors=[1642])
    # v1 hit a full bucket: w1 (same bucket, not requested) goes to the vault, then v1 is retried
    assert [(b["itemId"], b["transferToVault"]) for _, b in actions.posts] == [
        ("v1", False), ("w1", True), ("v1", False), ("v2", False)]
    assert result["items"][0]["notes"] == ["made room: sent item-w1 to the vault"]
    assert result["moved"] == 2


def test_full_bucket_without_victim_fails():
    # the only same-bucket item on the warlock (w1) is itself requested, so nothing can make room
    result, actions = run(["v1", "w1"], "warlock", errors=[1642])
    assert result["items"][0]["result"].startswith("failed: no room in destination")
    assert len(actions.posts) == 1 and result["items"][1]["result"] == "already there"


def test_full_vault_reported_as_failure():
    result, _ = run(["w1"], "vault", errors=[1642])
    assert result["items"][0]["result"].startswith("failed: no room in destination") and result["moved"] == 0


def test_equipped_postmaster_already_there_and_missing():
    result, actions = run(["e1", "p1", "w1", "nope"], "warlock")
    assert [i["result"] for i in result["items"]] == [
        "equipped: unequip it first", "in the postmaster: pull it first", "already there", "not found"]
    assert actions.posts == []


def test_dry_run_posts_nothing():
    result, actions = run(["v1"], "vault", dry_run=True)
    assert result["items"][0]["result"] == "already there"
    result, actions = run(["h1"], "vault", dry_run=True)
    assert result["items"][0]["result"] == "would move to vault" and actions.posts == []


def test_unknown_class_raises():
    with pytest.raises(BungieApiError, match="No titan on this account."):
        run(["v1"], "titan")


def test_pull_lists_without_ids():
    result = pull_postmaster(FakeActions(), locations(), "w", None, False, False)
    assert result == {"postmaster": [{"itemId": "p1", "name": "item-p1", "quantity": 1},
                                     {"itemId": "pm:w:3:7", "name": "item-pm:w:3:7", "quantity": 4}]}


def test_pull_uninstanced_uses_zero_id_and_quantity():
    actions = FakeActions()
    result = pull_postmaster(actions, locations(), "w", None, True, False)
    assert result["pulled"] == 2
    assert actions.posts[1] == ("PullFromPostmaster", {"itemReferenceHash": 3, "stackSize": 4, "itemId": "0",
                                                       "characterId": "w"})


def test_pull_dry_run():
    actions = FakeActions()
    result = pull_postmaster(actions, locations(), "w", ["p1"], False, True)
    assert result["items"] == [{"itemId": "p1", "name": "item-p1", "result": "would pull"}] and actions.posts == []


def test_partial_move_says_where_the_item_is():
    # leg 1 (hunter -> vault) works, leg 2 (vault -> warlock) fails: the item is now in the vault
    result, _ = run(["h1"], "warlock", errors=[None, 1623])
    assert result["items"][0]["result"] == "failed: item not found (Bungie error 1623); it is now in the vault"


def test_room_made_then_retry_failed_still_reported():
    result, _ = run(["v1"], "warlock", errors=[1642, None, 1642])
    entry = result["items"][0]
    assert entry["result"].startswith("failed: no room in destination")
    assert entry["notes"] == ["made room: sent item-w1 to the vault"]


def test_victim_chosen_by_real_bucket_and_never_bucket_zero():
    locs = locations()
    locs["w1"]["bucketHash"] = 99  # w1's real bucket differs from what the index says
    actions = FakeActions([1642])
    result = transfer(actions, locs, CLASS_OF, ["v1"], "warlock", False, lambda h: 99 if h == 1 else 0)
    assert [b["itemId"] for _, b in actions.posts] == ["v1", "w1", "v1"] and result["moved"] == 1
    actions = FakeActions([1642])
    result = transfer(actions, locations(), CLASS_OF, ["v1"], "warlock", False, lambda h: 0)
    assert len(actions.posts) == 1 and result["moved"] == 0


def test_pull_reports_ids_not_in_postmaster():
    result = pull_postmaster(FakeActions(), locations(), "w", ["p1", "pm:w:3:9", "v1"], False, True)
    assert [(i["itemId"], i["result"]) for i in result["items"]] == [
        ("p1", "would pull"), ("pm:w:3:9", "not found"), ("v1", "not found")]
