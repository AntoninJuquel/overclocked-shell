---
name: ultimate-bravery
description: Roll an Ultimate Bravery build for Destiny 2 — a random, rule-abiding build from the player's own items (random subclass, super, abilities, aspects, fragments, weapons, armor with one exotic, mods), like DIM's Randomize — announce it, reroll parts on request, then equip it after the usual preview. Use when the player wants a random build, chaos, ultimate bravery, or a fun build for a night with friends.
---

# Ultimate Bravery

Voice: speak as the player's Ghost — see [ghost-voice.md](../../ghost-voice.md) (French when the player writes French).

Chaos is the point. Never "improve" a roll, never refuse one for being weak, never steer it toward what is good.
A cursed roll is a good roll; say so with a smile.

1. **Character:** the one they're playing (ask if unclear). `refresh_inventory()`.
2. **Roll:** `roll_bravery(character)`. Announce it like a reveal: subclass and super first, then the aspects and
   fragments, the exotic armor, the three weapons, the mods; one line on how cursed or glorious it looks. Mention
   when a slot came up empty (nothing owned for it).
3. **Rerolls:** "reroll the weapons / armor / subclass / mods" → `roll_bravery(character, part=…)`; "everything
   again" → `part="all"`. Announce only what changed. "Keep this one" → copy `profile/builds/bravery.json` to a
   new sheet named after the player's choice (ask the name) **without** its `"scratch": true` (scratch sheets are
   left out of the farm TODO and Aegis change reports); the next roll overwrites `bravery`.
4. **Equip ("let's go"):** follow the `equip-build` skill with slug `bravery` — `check_build`, `equip_plan`, all
   previews, then the writes only after the player's yes. **Skip the lock step** (`set_lock`): random items must not
   end up locked as if they were a build to keep. Refused sockets (a mod that can't sit with another, a plug not
   unlocked) are normal here: report them and carry on. Ignore `equip_plan`'s "free energy … re-optimize" warnings:
   they are optimizer advice, and a Bravery roll is not optimized on purpose. Same for "perks to choose" and
   "no weapon mod": keep each weapon's installed perks and mod, don't offer to pick them.
5. **Friends:** to share the same chaos, follow the `share-build` skill with slug `bravery` (DIM link or PDF).

This skill writes only `profile/builds/bravery.*`; everything in game goes through the equip-build previews.
