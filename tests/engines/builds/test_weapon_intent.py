from shell.engines.builds import weapon_intent


def plug(name, type_name="Trait"):
    return {"displayProperties": {"name": name}, "itemTypeDisplayName": type_name,
            "plug": {"plugCategoryIdentifier": "frames"}}


DEFS = {
    "1": {"displayProperties": {"name": "Rifle"}, "itemType": 3, "sockets": {"socketEntries": [
        {"randomizedPlugSetHash": 7}, {"randomizedPlugSetHash": 8}, {"reusablePlugItems": [{"plugItemHash": 40}]}]}},
    "2": {"displayProperties": {"name": "Reissue"}, "itemType": 3, "collectibleHash": 1, "sockets": {"socketEntries": [
        {"randomizedPlugSetHash": 7}]}},
    "3": {"displayProperties": {"name": "Reissue"}, "itemType": 3, "sockets": {"socketEntries": [
        {"randomizedPlugSetHash": 8}]}},
    "10": plug("Physic"), "11": plug("Physic", "Enhanced Trait"), "12": plug("Attrition Orbs"),
    "20": plug("Master of Arms"), "40": plug("Ballistics", "Weapon Mod"),
}
SETS = {"7": {"reusablePlugItems": [{"plugItemHash": 11}, {"plugItemHash": 10}, {"plugItemHash": 12}]},
        "8": {"reusablePlugItems": [{"plugItemHash": 20}]}}


def weapon(**fields):
    return {"slot": "Kinetic", **fields}


def opts(*names):
    return list(names)


def run(w, hashes=None):
    return weapon_intent.normalize([w], DEFS, SETS, {} if hashes is None else hashes)


def test_hashes_with_alternatives_and_plain_copy():
    w = weapon(items=opts("Rifle"), perks=[opts("Physic", "Attrition Orbs"), opts("Master of Arms")], mods=opts("Ballistics"))
    hashes = {}
    assert run(w, hashes) == []
    assert hashes == {"item:Rifle": 1, "perk:Physic": 10, "perk:Attrition Orbs": 12, "perk:Master of Arms": 20,
                      "perk:Ballistics": 40}


def test_option_the_weapon_cannot_roll():
    w = weapon(items=opts("Rifle"), perks=[opts("Nope")])
    assert run(w) == ["Kinetic: Nope is not an option of Rifle"]


def test_alternatives_must_share_a_column():
    w = weapon(items=opts("Rifle"), perks=[opts("Physic", "Master of Arms")])
    assert run(w) == ["Kinetic: Physic / Master of Arms: no free column of Rifle has them all"]


def test_two_columns_cannot_use_one_socket():
    w = weapon(items=opts("Rifle"), perks=[opts("Physic"), opts("Attrition Orbs")])
    assert run(w) == ["Kinetic: Attrition Orbs: no free column of Rifle has them all"]


def test_unknown_weapon():
    assert run(weapon(items=opts("Nope"))) == ["Kinetic: unknown weapon: Nope"]


def test_copy_that_can_roll_the_perks():
    hashes = {}
    assert run(weapon(items=opts("Reissue"), perks=[opts("Master of Arms")]), hashes) == []
    assert hashes["item:Reissue"] == 3


def test_perks_without_a_weapon():
    hashes = {}
    assert run(weapon(perks=[opts("Physic")], mods=opts("Unknown")), hashes) == ["Kinetic: unknown perk or mod: Unknown"]
    assert hashes["perk:Physic"] == 10


def test_missing_mods_only_where_a_mod_fits():
    hashes = {"item:Rifle": 1, "item:Reissue": 2}
    with_socket = weapon(items=["Rifle"])
    chosen = weapon(slot="Energy", items=["Rifle"], mods=["Ballistics"])
    exotic = weapon(slot="Power", items=["Reissue"])
    perks_only = weapon(slot="Power", perks=[["Physic"]])
    assert weapon_intent.missing_mods([with_socket, chosen, exotic, perks_only], DEFS, SETS, hashes) == [
        "Kinetic: Rifle has a mod socket but no mod is chosen"]


def test_helpers():
    w = weapon(perks=[opts("Physic", "Attrition Orbs"), opts("Master of Arms")], mods=opts("Ballistics"))
    assert weapon_intent.options(w) == ["Physic", "Attrition Orbs", "Master of Arms", "Ballistics"]
    assert weapon_intent.is_named(w) and not weapon_intent.is_named(weapon(wanted="free text"))
