import json

import pytest

from shell.engines.defs import build_defs, load_defs

ITEMS = {
    "1": {"itemType": 3, "displayProperties": {"name": "Gun"}, "itemTypeDisplayName": "Auto Rifle",
          "inventory": {"tierTypeName": "Legendary", "bucketTypeHash": 1498876634},
          "equippingBlock": {"ammoType": 1},
          "sockets": {"socketCategories": [{"socketCategoryHash": 4241085061, "socketIndexes": [1, 2]}]}},
    "2": {"itemType": 2, "displayProperties": {"name": "Helm"}, "itemTypeDisplayName": "Helmet",
          "classType": 2, "inventory": {"bucketTypeHash": 3448274439, "tierTypeName": "Exotic"}},
    "3": {"itemType": 19, "displayProperties": {"name": "Mod"}, "itemTypeDisplayName": "General Armor Mod",
          "plug": {"plugCategoryIdentifier": "enhancements.v2_general"}},
    "4": {"itemType": 0, "displayProperties": {"name": ""}, "plug": {}},
    "5": {"itemType": 1, "displayProperties": {"name": "Glimmer"}, "inventory": {}},
    "6": {"itemType": 0, "displayProperties": {"name": "Seasonal Artifact"}, "itemTypeDisplayName": "Artifact",
          "inventory": {"bucketTypeHash": 1506418338}},
}
STATS = {"10": {"displayProperties": {"name": "Health"}}, "11": {"displayProperties": {"name": ""}}}
CATS = {"20": {"displayProperties": {"name": "WEAPON PERKS"}}}


def test_classification_order():
    d = build_defs(ITEMS, STATS, CATS)
    assert d["weapons"]["1"] == {"n": "Gun", "t": "Auto Rifle", "r": "Legendary", "a": 1, "b": 1498876634,
                                 "sc": [[4241085061, [1, 2]]]}
    assert d["gear"]["2"] == ["Helm", "Helmet", 2, 3448274439, "Exotic"]
    assert d["gear"]["6"] == ["Seasonal Artifact", "Artifact", 3, 1506418338, ""]
    assert d["plugs"]["3"] == {"n": "Mod", "t": "General Armor Mod", "p": "enhancements.v2_general"}
    assert d["misc"] == {"5": "Glimmer"}
    assert "4" not in d["plugs"]
    assert d["stats"] == {"10": "Health"} and d["socketCategories"] == {"20": "WEAPON PERKS"}


class FakeManifest:
    def __init__(self, version, fail=False):
        self._version, self.fail, self.calls = version, fail, []

    def version(self):
        return self._version

    def table(self, name, keep=True):
        assert keep is False
        if self.fail:
            raise AssertionError("table should come from the defs cache")
        self.calls.append(name)
        return {"DestinyInventoryItemDefinition": ITEMS, "DestinyStatDefinition": STATS,
                "DestinySocketCategoryDefinition": CATS}[name]


def test_load_defs_cached_per_version(tmp_path):
    d = load_defs(FakeManifest("v1"), tmp_path)
    assert json.loads((tmp_path / "defs" / "v1.json").read_text())["gear"]["2"][0] == "Helm"
    assert load_defs(FakeManifest("v1", fail=True), tmp_path) == d


def test_load_defs_new_version_removes_old(tmp_path):
    load_defs(FakeManifest("v1"), tmp_path)
    load_defs(FakeManifest("v2"), tmp_path)
    assert [p.name for p in (tmp_path / "defs").iterdir()] == ["v2.json"]
