---
name: armor-triage
description: Triage the Destiny 2 armor vault — keep the best copy per stat distribution and set (projected masterwork stats), drop all legacy, then lock what to keep and unlock what to drop. Use when the player wants to sort, clean up or make room in their armor.
---

# Armor triage

Voice: speak as the player's Ghost — see [ghost-voice.md](../../ghost-voice.md) (French when the player writes French).

Goal: be able to aim at any build (stats + set bonus) while keeping as few pieces as possible. Only stat quality
counts: it does not save materials and ignores loadouts and what is equipped (if a better copy exists, that is the
one to keep).

## Steps

1. **Check the sign-in**: `auth_status`. If it expired, ask the player to run `uv run shell auth login` from the
   repo root (never handle tokens yourself).
2. **Triage**: `triage_armor` (fresh read of the vault and every character; set definitions come from the
   manifest).
3. **Review before applying**: look at `review` (pieces locked today that would be unlocked, legacy excluded),
   `junk_by_reason` and `no_set` (Armor 3.0 legendaries with no known set, grouped by name). Point out anything
   surprising. The full list with reasons is `profile/triage/armor.csv` (`;` separated).
4. **Apply**: `apply_triage("armor")` — asking for a triage is the go-ahead, no dry run. Never dismantle: the
   player cleans up with the `is:unlocked` filter.
5. **Summarize**: kept / dropped counts, main reasons, `skipped` (postmaster) and any `failed` ids.
6. **Farm needs**: `farm_needs` (kept pieces may settle needs of the build sheets; see the `todo` skill).

## Rules (to explain decisions)

- Each piece:
  - base stats = live stats minus stat mods (`X Mod` +10, `Minor X Mod` +5, tuning ±5);
  - masterwork projection: the 3 focus stats stay, the other 3 go to 5;
  - archetype, tertiary stat, Spirit perks (exotic class items);
  - **set and set bonus** (2 and 4 pieces), from `DestinyEquipableItemSetDefinition`.
- Legacy (tier 0, before Armor 3.0): **always dropped**, even with no replacement.
- Armor 3.0 legendaries: groups (class, slot, set, archetype, tertiary), all tiers together. A copy is dropped
  only if a kept copy equals or beats it **on every projected stat**.
- Armor 3.0 exotics: groups (name, Spirit perks, archetype, tertiary), same dominance rule.
- Two copies where one dominates the other are both kept if their known tuned stat differs (same tier only).
- Postmaster: ignored (and never locked).

## Known limit

When a T5's tuning socket is empty, the tuned stat may not be readable: two copies differing only by that stat
look like duplicates.
