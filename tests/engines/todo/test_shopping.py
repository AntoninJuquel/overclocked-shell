from shell.engines.todo import shopping

WEAPON_NAMES = {"refurbished a499", "choir of one", "lotus-eater"}
SET_NAMES = {"promised", "smoke jumper"}


def row(name, role, prio="high", c1="N/A", c2="N/A", alts="N/A", source="Somewhere"):
    return {"_name": name, "Name": name, "Role": role, "Priority": prio, "Column 1": c1, "Column 2": c2,
            "Alternatives": alts, "Source": source}


def weapon(name, options, rarity="Legendary"):
    return {"name": name, "rarity": rarity,
            "columns": [{"label": "Trait", "selected": options[0], "options": [{"name": o} for o in options]}]}


def piece(name, slot, arch, cls="Warlock", h=1, tier=5, char="c1"):
    return {"name": name, "slot": slot, "classType": cls, "itemHash": h, "gearTier": tier, "characterId": char,
            "plugs": [arch, "Upgrade Armor"]}


SETS = {1: {"set": "Promised Set", "bonus": []}, 2: {"set": "Smoke Jumper Set", "bonus": []}}
ARMOR = [piece("Promised Hood", "Helmet", "Specialist"), piece("Promised Gloves", "Gauntlets", "Gunner"),
         piece("Promised Robes", "Chest", "Bulwark"), piece("Star-Eater Scales", "Legs", "Gunner", cls="Hunter", h=9)]


def run(rows, armor=ARMOR, weapons=()):
    return run3(rows, armor, weapons)[:2]


def run3(rows, armor=ARMOR, weapons=()):
    return shopping.shopping_needs(rows, armor, list(weapons) if weapons is not None else None, SETS,
                                   WEAPON_NAMES, SET_NAMES)


def test_constants():
    assert shopping.BUILD == "aegis" and shopping.LABEL == "Aegis Shopping List"


def test_weapon_needs_perks_of_both_columns():
    r = row("Refurbished A499", "heavy DPS sniper", c1="Snapshot Sights\nLone Wolf", c2="Aggregate Charge\nEnvious Assassin")
    needs, _ = run([r], weapons=[weapon("Refurbished A499", ["Snapshot Sights", "Firefly"])])
    assert [n["id"] for n in needs] == ["aegis/refurbished-a499"]
    n = needs[0]
    assert n["kind"] == "aegis" and n["label"] == "Aegis: Refurbished A499"
    assert n["target"] == {"name": "Refurbished A499", "type": "weapon", "source": "Somewhere"}
    gain = n["builds"][0]
    assert gain["build"] == "aegis" and gain["gain"]["score"] == 0.10
    assert gain["gain"]["effects"] == ["Aegis role: heavy DPS sniper (priority high)",
                                       "perks: Snapshot Sights or Lone Wolf + Aggregate Charge or Envious Assassin"]
    owned, _ = run([r], weapons=[weapon("Refurbished A499", ["Lone Wolf", "Envious Assassin"])])
    assert owned == []


def test_exotic_weapon_is_owned_by_name():
    assert run([row("Choir of One", "exotic roam", c1="Onslaught")], weapons=[weapon("Choir of One", ["x"], "Exotic")])[0] == []


def test_set_needs_enough_slots_of_wanted_archetypes():
    four = row("Promised", "general DR", c1="Specialist/Gunner/Skirmisher/Powerhouse")
    two = row("Promised", "general DR (2 pcs.)", c1="Specialist/Gunner/Skirmisher/Powerhouse")
    assert [n["target"]["type"] for n in run([four])[0]] == ["set"]       # only 2 slots
    assert run([two])[0] == []
    assert "archetype: Specialist/Gunner/Skirmisher/Powerhouse" in run([four])[0][0]["builds"][0]["gain"]["effects"]


def test_exotic_armor_and_class_filter():
    assert run([row("Star-Eater Scales", "hunter DPS")])[0] == []                       # owned
    assert [n["id"] for n in run([row("Celestial Nighthawk", "hunter DPS")])[0]] == ["aegis/celestial-nighthawk"]
    assert run([row("Wormgod Caress", "titan roam")])[0] == []                          # no Titan


def test_alternatives_duplicates_and_missing_weapons_export():
    rows = [row("Lotus-Eater", "energy rocket sidearm", "medium", alts="Returned Memory\nStar-Eater Scales"),
            row("Lotus-Eater", "energy StL special", "high")]
    needs, warnings = run(rows, weapons=[])
    assert len(needs) == 1 and needs[0]["builds"][0]["gain"]["score"] == 0.10
    effects = needs[0]["builds"][0]["gain"]["effects"]
    assert "owned alternatives: Star-Eater Scales" in effects
    assert effects.count("Aegis role: energy StL special (priority high)") == 1
    needs, warnings = run(rows, weapons=None)
    assert needs == [] and "2 weapon(s)" in warnings[0]


def test_unknown_priority_is_skipped():
    assert run([row("Celestial Nighthawk", "hunter DPS", prio="")])[0] == []


def test_crafted_weapon_counts_as_owned():
    r = row("Refurbished A499", "heavy DPS sniper", c1="Lone Wolf", c2="Envious Assassin")
    crafted = {**weapon("Refurbished A499", ["Firefly"]), "crafted": True}
    assert run([r], weapons=[crafted])[0] == []
    assert len(run([r], weapons=[weapon("Refurbished A499", ["Firefly"])])[0]) == 1


def test_weapon_columns_are_checked_against_their_own_trait_socket():
    r = row("Refurbished A499", "heavy DPS sniper", c1="Lone Wolf", c2="Envious Assassin")
    cols = lambda a, b: {"name": "Refurbished A499", "rarity": "Legendary", "columns": [
        {"label": "Barrel", "options": [{"name": "Full Bore"}]},
        {"label": "Trait", "options": [{"name": n} for n in a]},
        {"label": "Trait", "options": [{"name": n} for n in b]}]}
    assert run([r], weapons=[cols(["Lone Wolf"], ["Envious Assassin"])])[0] == []
    # Envious Assassin only in the 1st column: does not satisfy Column 2
    assert len(run([r], weapons=[cols(["Lone Wolf", "Envious Assassin"], ["Firefly"])])[0]) == 1


def test_set_need_shows_progress():
    four = row("Promised", "general DR", c1="Specialist/Gunner/Skirmisher/Powerhouse")
    effects = run([four])[0][0]["builds"][0]["gain"]["effects"]
    assert "progress: 2/4 pieces Specialist/Gunner/Skirmisher/Powerhouse on Warlock, missing: Chest, Legs, Class Item" in effects
    none = row("Smoke Jumper", "general DR", c1="Powerhouse")
    assert "progress: no pieces" in run([none])[0][0]["builds"][0]["gain"]["effects"]


def test_result_is_incomplete_only_when_weapons_were_skipped():
    r = row("Choir of One", "exotic roam", c1="Onslaught")
    assert run3([r], weapons=None)[2] is False
    assert run3([r], weapons=[])[2] is True


def test_unknown_name_in_the_weapons_export_is_a_weapon_not_exotic_armor():
    r = row("Mystery Gun", "kinetic DPS", c1="Snapshot Sights")
    assert shopping.kind_of("Mystery Gun", WEAPON_NAMES, SET_NAMES) == "exotic"
    assert shopping.kind_of("Mystery Gun", WEAPON_NAMES, SET_NAMES, [weapon("Mystery Gun", ["x"])]) == "weapon"
    needs, _ = run([r], weapons=[weapon("Mystery Gun", ["Firefly"])])
    assert needs[0]["target"]["type"] == "weapon"
    assert run([r], weapons=[weapon("Mystery Gun", ["Snapshot Sights"])])[0] == []
