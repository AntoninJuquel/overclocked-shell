from shell.engines.armor_triage import armor_sets, lock_plan, triage_armor

STATS = ["Weapons", "Health", "Class", "Grenade", "Super", "Melee"]


def piece(item_id, w=30, h=20, c=10, g=5, s=5, m=5, *, tier=3, name="Bastion Helm", hash_=1, plugs=(),
          archetype="Gunner", rarity="Legendary", cls="Titan", slot="Helmet", locked=False, location="Vault"):
    stats = dict(zip(STATS, (w, h, c, g, s, m)))
    return {"itemId": item_id, "itemHash": hash_, "name": name, "slot": slot, "classType": cls, "rarity": rarity,
            "location": location, "locked": locked, "gearTier": tier, "stats": stats, "total": sum(stats.values()),
            "plugs": [archetype, *plugs]}


def decided(rows, sets=None):
    return {r["itemId"]: (r["decision"], r["reason"]) for r in triage_armor(rows, sets or {})}


def test_legacy_always_junk():
    assert decided([piece("a", tier=0)])["a"] == ("JUNK", "legacy (pre-Armor 3.0)")


def test_mods_removed_before_projection():
    row = piece("a", w=30, h=25, c=10, g=10, s=5, m=0,
                plugs=["General Armor Mod: Minor Health Mod", "General Armor Mod: +Class / -Melee"])
    out = triage_armor([row], {})[0]
    assert out["base"] == {"Weapons": 30, "Health": 20, "Class": 5, "Grenade": 10, "Super": 5, "Melee": 5}
    assert out["tuned"] == "Class"
    # top 3 (Weapons, Health, Grenade) stay, the other three go to 5
    assert out["mw"] == {"Weapons": 30, "Health": 20, "Class": 5, "Grenade": 10, "Super": 5, "Melee": 5}
    assert out["tertiary"] == "Grenade" and out["profile"] == "Weapons/Health/Grenade"


def test_dominated_copy_junk_with_reason():
    out = decided([piece("a", w=30), piece("b", w=25)])
    assert out["a"] == ("KEEP", "best copy Gunner tertiary Class — MW 30/20/10/5/5/5 = 75")
    assert out["b"] == ("JUNK", "beaten by Bastion Helm T3 — MW 30/20/10/5/5/5 = 75 vs 25/20/10/5/5/5 = 70")


def test_different_tuning_kept_same_tier_only():
    def tuned(i, stat, tier=3):  # same base W30 H20 C10 G5 S5 M10, tuned +stat / -Melee
        live = dict(zip(STATS, (30, 20, 10, 5, 5, 10)))
        live[stat] += 5
        live["Melee"] -= 5
        return piece(i, *live.values(), tier=tier, plugs=[f"General Armor Mod: +{stat} / -Melee"])

    out = decided([tuned("a", "Weapons"), tuned("b", "Health")])
    assert out["b"] == ("KEEP", "same stats but different tuning +Health")
    out = decided([tuned("a", "Weapons", tier=5), tuned("b", "Health", tier=4)])
    assert out["b"][0] == "JUNK"


def test_legendary_grouped_by_set_archetype_tertiary():
    sets = {1: {"set": "Iron", "bonus": []}, 2: {"set": "Bronze", "bonus": []}}
    out = decided([piece("a", hash_=1), piece("b", hash_=2, w=25)], sets)
    assert out["a"][0] == out["b"][0] == "KEEP"
    out = decided([piece("a"), piece("b", w=25, archetype="Brawler")])
    assert out["b"][0] == "KEEP"


def test_exotic_grouped_by_spirits():
    ex = lambda i, spirit, w=30: piece(i, w=w, rarity="Exotic", name="Essentialism",  # noqa: E731
                                       plugs=[f"Intrinsic: Spirit of the {spirit}"])
    out = decided([ex("a", "Star"), ex("b", "Wormhusk", w=25), ex("c", "Star", w=25)])
    assert out["a"] == ("KEEP", "best copy Gunner tertiary Class — MW 30/20/10/5/5/5 = 75")
    assert out["b"][0] == "KEEP" and out["c"][0] == "JUNK"


def test_postmaster_kept_and_not_in_lock_plan():
    rows = triage_armor([piece("a", location="Titan (Postmaster)"), piece("b", tier=0, locked=True),
                         piece("c", hash_=9, archetype="Brawler")], {})
    assert {r["itemId"]: r["reason"] for r in rows}["a"] == "postmaster (ignored)"
    assert lock_plan(rows) == (["c"], ["b"])


def test_armor_sets_bonus_text():
    class Manifest:
        def table(self, name, keep=True):
            return {
                "DestinyEquipableItemSetDefinition": {"1": {
                    "displayProperties": {"name": "Iron"}, "setItems": [10, 11],
                    "setPerks": [{"requiredSetCount": 4, "sandboxPerkHash": 8},
                                 {"requiredSetCount": 2, "sandboxPerkHash": 7}]}},
                "DestinySandboxPerkDefinition": {"7": {"displayProperties": {"name": "Grit"}},
                                                 "8": {"displayProperties": {"name": "Resolve"}}},
            }[name]

    sets = armor_sets(Manifest())
    assert sets[10] == sets[11] == {"set": "Iron", "bonus": ["2 pieces: Grit", "4 pieces: Resolve"]}
