import json

from shell.engines.builds import catalog


def mod(name, cat, cost=None):
    plug = {"plugCategoryIdentifier": cat}
    if cost is not None:
        plug["energyCost"] = {"energyCost": cost}
    return {"displayProperties": {"name": name}, "plug": plug}


def test_costs_keep_highest_per_name():
    items = {"1": mod("Grenade Mod", "enhancements.v2_general", 1),
             "2": mod("Grenade Mod", "enhancements.v2_general", 3),
             "3": mod("Health Mod", "enhancements.universal"),
             "4": mod("Arc Siphon", "enhancements.v2_head", 3),
             "5": mod("Ignored", "shader", 9)}
    assert catalog.load_costs(items) == {"Grenade Mod": 3, "Arc Siphon": 3}


def aspect(name, slots):
    return {"displayProperties": {"name": name},
            "plug": {"plugCategoryIdentifier": "warlock.arc.aspects", "energyCapacity": {"capacityValue": slots}}}


ITEMS = {
    "10": aspect("Electrostatic Mind", 2),
    "11": mod("Spark of Shock", "shared.arc.fragments", 1),
    "12": mod("Empty Fragment Socket", "shared.arc.fragments", 0),
    "13": mod("Stormtrance", "warlock.arc.supers"),
    "14": mod("Storm Grenade", "shared.arc.grenades"),
    "20": {"displayProperties": {"name": "Stormcaller"}, "itemType": 16, "classType": 2,
           "sockets": {"socketEntries": [{"singleInitialItemHash": 13}, {"singleInitialItemHash": 12},
                                         {"singleInitialItemHash": 12}, {"singleInitialItemHash": 0}]}},
}


def test_subclass_index_aspects_fragments_sockets():
    idx = catalog.build_index(ITEMS)
    arc = idx["Arc"]
    assert arc["aspects"]["Warlock"] == {"Electrostatic Mind": 2} and arc["aspects"]["Hunter"] == {}
    assert arc["fragments"] == {"Spark of Shock"}
    assert arc["fragment_sockets"] == {"Warlock": [1, 2]}
    assert arc["abilities"]["Warlock"]["super"] == {"Stormtrance"}
    assert arc["abilities"]["Hunter"]["grenade"] == {"Storm Grenade"}


class FakeManifest:
    def __init__(self, version):
        self._version, self.calls = version, []

    def version(self):
        return self._version

    def table(self, name, keep=True):
        assert keep is False
        self.calls.append(name)
        return {"DestinyInventoryItemDefinition": {**ITEMS, "30": mod("Grenade Mod", "enhancements.v2_general", 3)},
                "DestinyEquipableItemSetDefinition": {"1": {"displayProperties": {"name": "AION Renewal"},
                                                            "setItems": [555],
                                                            "setPerks": [{"requiredSetCount": 2, "sandboxPerkHash": 7}]}},
                "DestinySandboxPerkDefinition": {"7": {"displayProperties": {"name": "Foo"}}}}[name]


def test_catalog_cached_per_version(tmp_path):
    m = FakeManifest("v1")
    first = catalog.load_catalog(m, tmp_path)
    assert m.calls.count("DestinyInventoryItemDefinition") == 1
    (tmp_path / "defs").mkdir(exist_ok=True)
    (tmp_path / "defs" / "s2-v1.json").write_text("{}", encoding="utf-8")   # the defs index is left alone
    m2 = FakeManifest("v1")
    assert catalog.load_catalog(m2, tmp_path) == first and m2.calls == []
    assert (tmp_path / "defs" / f"builds-s{catalog.SCHEMA}-v1.json").exists()
    m3 = FakeManifest("v/2")
    catalog.load_catalog(m3, tmp_path)
    assert m3.calls
    names = sorted(p.name for p in (tmp_path / "defs").iterdir())
    assert names == [f"builds-s{catalog.SCHEMA}-v_2.json", "s2-v1.json"]


def test_sets_keys_are_ints_after_reload(tmp_path):
    catalog.load_catalog(FakeManifest("v1"), tmp_path)
    cat = catalog.load_catalog(FakeManifest("v1"), tmp_path)
    assert cat["sets"] == {555: {"set": "AION Renewal", "bonus": ["2 pieces: Foo"]}}
    assert cat["costs"] == {"Grenade Mod": 3}
    assert cat["subclass"]["Arc"]["fragments"] == {"Spark of Shock"}
    assert cat["subclass"]["Arc"]["abilities"]["Warlock"]["super"] == {"Stormtrance"}
    assert cat["subclass"]["Arc"]["fragment_sockets"] == {"Warlock": [1, 2]}


def test_default_cache_dir_is_resolved_at_call_time(isolated_dirs):
    catalog.load_catalog(FakeManifest("v1"))
    assert json.loads((isolated_dirs / "cache" / "defs" / f"builds-s{catalog.SCHEMA}-v1.json")
                      .read_text(encoding="utf-8"))["costs"] == {"Grenade Mod": 3}
