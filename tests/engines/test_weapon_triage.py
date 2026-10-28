from shell.engines.weapon_triage import triage_weapons


def gun(item_id, traits=("Outlaw", "Rampage"), barrels=("Corkscrew Rifling",), *, name="Fatebringer", hash_=100,
        rarity="Legendary", crafted=False, tier=0, locked=False, frame="Adaptive Frame", enhanced=()):
    opt = lambda n: {"name": n, "enhanced": n in enhanced}  # noqa: E731
    return {"itemId": item_id, "itemHash": hash_, "name": name, "type": "Hand Cannon", "rarity": rarity,
            "frame": frame, "crafted": crafted, "gearTier": tier, "locked": locked, "power": 2000,
            "location": "Vault", "columns": [{"label": "Barrel", "options": [opt(b) for b in barrels]},
                                             {"label": "Trait", "options": [opt(t) for t in traits]}]}


ROLLS = {100: [frozenset({"outlaw", "explosive payload"}), frozenset({"rampage"})]}
NOTES = {100: "S #2"}
NAMES = {100: "Fatebringer"}


def decide(rows, rolls=ROLLS, notes=NOTES, names=NAMES):
    return {w["itemId"]: (w["decision"], w["reason"]) for w in triage_weapons(rows, rolls, notes, names)}


def test_roll_matches_when_all_line_perks_present():
    out = decide([gun("a", traits=("Outlaw", "Explosive Payload"))])
    assert out["a"] == ("KEEP", "wishlist S #2")
    assert decide([gun("b", traits=("Outlaw", "Kill Clip"))])["b"] == ("JUNK", "roll not on the wishlist")


def test_enhanced_compared_by_name():
    out = decide([gun("a", traits=("Enhanced Outlaw", "Explosive Payload"), enhanced=("Enhanced Outlaw",))])
    assert out["a"][0] == "KEEP"


def test_name_fallback_for_reissue_hash():
    out = decide([gun("a", traits=("Rampage",), name="Fatebringer (Timelost)", hash_=999)])
    assert out["a"] == ("KEEP", "wishlist S #2")


def test_one_copy_per_trait_combo():
    rows = [gun("a", traits=("Rampage",)), gun("b", traits=("Rampage",), tier=2)]
    out = decide(rows)
    assert out["b"] == ("KEEP", "wishlist S #2")
    assert out["a"] == ("JUNK", "duplicate god roll (same traits, worse tier/enhanced)")


def test_crafted_always_kept():
    assert decide([gun("a", traits=("Kill Clip",), crafted=True)])["a"] == ("KEEP", "crafted (pattern)")


def test_exotic_one_copy_per_full_roll_including_frame():
    ex = lambda i, frame, tier=0: gun(i, name="Ergo Sum", hash_=7, rarity="Exotic", frame=frame,  # noqa: E731
                                      traits=("Sword Logic",), tier=tier)
    out = decide([ex("a", "Stormbringer"), ex("b", "Wolfpack Rounds"), ex("c", "Stormbringer", tier=3)])
    assert out["a"] == ("JUNK", "duplicate exotic")
    assert out["b"] == out["c"] == ("KEEP", "exotic (best copy)")


def test_unlisted_weapon_junk_even_if_locked():
    rows = triage_weapons([gun("a", name="Other", hash_=5, locked=True)], ROLLS, NOTES, NAMES)
    assert (rows[0]["decision"], rows[0]["reason"]) == ("JUNK", "weapon not on the wishlist")
