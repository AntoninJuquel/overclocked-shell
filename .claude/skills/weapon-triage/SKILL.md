---
name: weapon-triage
description: Triage Destiny 2 weapons against a DIM wishlist (default MrCharles' Aegis list, grade >= B) — keep god rolls, crafted weapons and one copy per exotic roll, then lock / unlock. Use when the player wants to sort their weapons or apply a wishlist.
---

# Weapon triage

Voice: speak as the player's Ghost — see [ghost-voice.md](../../ghost-voice.md) (French when the player writes French).

## Steps

1. `auth_status` (if expired: the player runs `uv run shell auth login` from the repo root).
2. `triage_weapons` — `wishlist`: a local path or URL of a DIM wishlist, default MrCharles' Aegis B+. URLs are
   cached in `cache/wishlists/`; `refresh_wishlist: true` re-downloads.
3. Review `review` (weapons locked today that would be unlocked) and the reasons; full list in
   `profile/triage/weapons.csv`.
4. `apply_triage("weapons")`. Never dismantle.
5. Summarize, naming `skipped` (postmaster) and any `failed` ids.

## Rules

- DIM matching: a roll matches a line when all its perks are among the weapon's options (all columns); enhanced
  perks compare by name. Falls back to the weapon name (reissues, Adept…) when the hash is not listed.
- Only roll quality counts: neither what is equipped nor loadouts protect a weapon.
- Legendaries kept: crafted, or a wishlist roll (one copy per trait combination).
- Not on the wishlist (grade too low or not covered): dropped, even if it was locked.
- Exotics: one copy per full roll, random exotic perk included (Ergo Sum: Stormbringer, Wolfpack Rounds…, read
  from the `frame` field, missing from the perk columns).
