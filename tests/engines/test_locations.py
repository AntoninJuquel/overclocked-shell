from shell.engines.locations import read_locations

from .fixtures import DEFS, profile


def test_vault_inventory_postmaster_equipped():
    locs, class_of = read_locations(profile(), DEFS)
    assert class_of == {"w": 2}
    assert locs["a1"] == {"itemId": "a1", "itemHash": 200, "bucketHash": 138197802, "where": "vault",
                          "characterId": None, "quantity": 1, "locked": True, "name": "Star-Eater Scales"}
    assert (locs["a2"]["where"], locs["a2"]["characterId"]) == ("postmaster", "w")
    assert (locs["a3"]["where"], locs["a3"]["locked"]) == ("equipped", True)
    assert locs["x1"]["name"] == "#999"


def test_uninstanced_postmaster_stack_gets_pm_id():
    p = profile()
    p["characterInventories"]["data"]["w"]["items"].append({"itemHash": 101, "bucketHash": 215593132, "quantity": 3})
    locs, _ = read_locations(p, DEFS)
    assert locs["pm:w:101:2"] == {"itemId": "pm:w:101:2", "itemHash": 101, "bucketHash": 215593132,
                                  "where": "postmaster", "characterId": "w", "quantity": 3, "locked": False,
                                  "name": "Bow"}


def test_uninstanced_other_items_dropped():
    locs, _ = read_locations(profile(), DEFS)
    assert sorted(locs) == ["a1", "a2", "a3", "g1", "g2", "g3", "gh", "x1"]
