import pytest

from shell.engines.builds import inventory


def item(item_id, slot, stats, *, name=None, cls="Warlock", rarity="Legendary", tier=5, mw=False,
         energy="0/11", plugs=(), tuned="Super", location="Vault", locked=True, item_hash=1):
    return {"itemId": item_id, "itemHash": item_hash, "name": name or f"P{item_id}", "slot": slot,
            "classType": cls, "rarity": rarity, "location": location, "locked": locked,
            "masterworked": mw, "gearTier": tier, "energy": energy, "tunedStat": tuned,
            "stats": dict(zip(["Weapons", "Health", "Class", "Grenade", "Super", "Melee"], stats)),
            "plugs": list(plugs)}


def test_base_stats_removes_stat_mods_and_tuning():
    it = item("1", "Helmet", [10, 30, 0, 30, 25, 0],
              plugs=["General Armor Mod: Grenade Mod", "General Armor Mod: +Weapons / -Melee"])
    # Grenade Mod +10 → 20; +Weapons/-Melee → Weapons 5, Melee 5
    assert inventory.base_stats(it) == {"Weapons": 5, "Health": 30, "Class": 0, "Grenade": 20, "Super": 25, "Melee": 5}


def test_base_stats_removes_balanced_tuning():
    it = item("1", "Helmet", [20, 1, 1, 1, 30, 25], plugs=["General Armor Mod: Balanced Tuning"])
    assert inventory.base_stats(it) == {"Weapons": 20, "Health": 0, "Class": 0, "Grenade": 0, "Super": 30, "Melee": 25}


def test_masterwork_projection_and_flag():
    pieces = inventory.load_pieces([item("1", "Helmet", [0, 30, 0, 25, 20, 0])], "Warlock", {"name": "X"}, {},
                                   require_exotic=False)
    p = pieces["Helmet"][0]
    assert p.stats == {"Weapons": 5, "Health": 30, "Class": 5, "Grenade": 25, "Super": 20, "Melee": 5}
    assert p.masterwork_todo and p.energy == 11 and p.tuned == "Super"


def test_filters():
    items = [
        item("1", "Helmet", [0, 30, 0, 25, 20, 0]),
        item("2", "Helmet", [0, 30, 0, 25, 20, 0], tier=0),                 # legacy legendary: excluded
        item("3", "Helmet", [0, 30, 0, 25, 20, 0], cls="Hunter"),           # other class
        item("4", "Legs", [20, 23, 4, 15, 17, 4], name="Other Exotic", rarity="Exotic", tier=0),  # other exotic
        item("5", "Chest", [20, 23, 4, 15, 17, 4], name="Getaway Artist", rarity="Exotic", tier=0,
             mw=True, energy="9/10", tuned=None),                            # requested exotic, legacy accepted
        item("6", "Chest", [0, 30, 0, 25, 20, 0], location="Warlock (Postmaster)"),  # postmaster
    ]
    pieces = inventory.load_pieces(items, "Warlock", {"name": "Getaway Artist"}, {9: {"set": "AION"}})
    assert [p.item_id for p in pieces["Helmet"]] == ["1"]
    assert "Legs" not in pieces
    ex = pieces["Chest"]
    assert [p.item_id for p in ex] == ["5"] and ex[0].exotic and not ex[0].masterwork_todo
    assert ex[0].stats["Weapons"] == 20 and ex[0].energy == 10
    assert inventory.exotic_slot(pieces) == "Chest"


def test_exotic_perks_and_sets():
    items = [
        item("1", "Class Item", [1, 1, 1, 20, 30, 25], name="Solipsism", rarity="Exotic",
             plugs=["Intrinsic: Spirit of Inmost Light", "Intrinsic: Spirit of Verity"], tuned=None),
        item("2", "Class Item", [1, 1, 1, 20, 30, 25], name="Solipsism", rarity="Exotic",
             plugs=["Intrinsic: Spirit of the Swarm", "Intrinsic: Spirit of Verity"], tuned=None),
        item("3", "Helmet", [0, 30, 0, 25, 20, 0], item_hash=9),
    ]
    exotic = {"name": "Solipsism", "perks": ["Spirit of Inmost Light", "Spirit of Verity"]}
    pieces = inventory.load_pieces(items, "Warlock", exotic, {9: {"set": "AION Renewal"}})
    assert [p.item_id for p in pieces["Class Item"]] == ["1"]
    assert pieces["Helmet"][0].set == "AION Renewal"


def test_missing_exotic_is_an_error():
    with pytest.raises(ValueError, match="Getaway Artist"):
        inventory.load_pieces([item("1", "Helmet", [0, 30, 0, 25, 20, 0])], "Warlock", {"name": "Getaway Artist"}, {})


def test_tuning_data_detection():
    assert inventory.has_tuning_data([item("1", "Helmet", [0] * 6)])
    old = item("1", "Helmet", [0] * 6)
    del old["tunedStat"]
    assert not inventory.has_tuning_data([old])


def test_base_stats_minor_stat_mod():
    it = item("1", "Helmet", [0, 30, 0, 25, 25, 0], plugs=["General Armor Mod: Minor Super Mod"])
    assert inventory.base_stats(it) == {"Weapons": 0, "Health": 30, "Class": 0, "Grenade": 25, "Super": 20, "Melee": 0}


def test_base_stats_balanced_tuning_with_stat_mod():
    it = item("1", "Helmet", [1, 1, 1, 40, 30, 25],
              plugs=["General Armor Mod: Grenade Mod", "General Armor Mod: Balanced Tuning"])
    assert inventory.base_stats(it) == {"Weapons": 0, "Health": 0, "Class": 0, "Grenade": 30, "Super": 30, "Melee": 25}


def test_base_stats_balanced_tuning_on_masterworked_piece():
    it = item("1", "Helmet", [6, 6, 6, 30, 25, 20], mw=True, plugs=["General Armor Mod: Balanced Tuning"])
    assert inventory.base_stats(it) == {"Weapons": 5, "Health": 5, "Class": 5, "Grenade": 30, "Super": 25, "Melee": 20}


def test_artifice_forged_mod_is_kept():
    it = item("1", "Helmet", [0, 30, 0, 25, 23, 0], plugs=["Artifice Armor Mod: Super Forged"])
    assert inventory.base_stats(it) == {"Weapons": 0, "Health": 30, "Class": 0, "Grenade": 25, "Super": 23, "Melee": 0}


def test_legacy_exotic_not_masterworked():
    it = item("1", "Chest", [20, 23, 4, 15, 17, 4], name="Getaway Artist", rarity="Exotic", tier=0,
              energy="0/1", tuned=None)
    p = inventory.load_pieces([it], "Warlock", {"name": "Getaway Artist"}, {})["Chest"][0]
    assert p.masterwork_todo and p.energy == 10
    assert p.stats == {"Weapons": 20, "Health": 23, "Class": 4, "Grenade": 15, "Super": 17, "Melee": 4}


def test_empty_energy_is_zero():
    p = inventory.load_pieces([item("1", "Helmet", [0, 30, 0, 25, 20, 0], energy="")], "Warlock",
                              {"name": "X"}, {}, require_exotic=False)["Helmet"][0]
    assert p.energy == 0


def test_tuning_data_empty_list():
    assert not inventory.has_tuning_data([])


def test_tier5_exotic_partial_masterwork_projects_to_five():
    it = item("1", "Chest", [2, 30, 2, 25, 20, 2], name="E", rarity="Exotic", tier=5)
    p = inventory.load_pieces([it], "Warlock", {"name": "E"}, {})["Chest"][0]
    assert p.masterwork_todo
    assert p.stats == {"Weapons": 5, "Health": 30, "Class": 5, "Grenade": 25, "Super": 20, "Melee": 5}
