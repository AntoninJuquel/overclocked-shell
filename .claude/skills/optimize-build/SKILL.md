---
name: optimize-build
description: Re-optimize a saved build sheet (profile/builds/*.json) on the current inventory — armor pieces, stat mods, tuning, weapons — and show what changes. Use when the player wants to update, improve or check an existing build.
---

# Re-optimize a build

Voice: speak as the player's Ghost — see [ghost-voice.md](../../ghost-voice.md) (French when the player writes French).

A build sheet = `profile/builds/<slug>.json` (source of truth) + `profile/builds/<slug>.md` (regenerated view).
`intent` is the player's intention (exotic, subclass, stat thresholds and priorities, sets, utility mods, weapon
roles): never change it here without their OK. `resolved` is the last dated result.

1. Pick the sheet (list `profile/builds/*.json` if the player doesn't name it) and read its `.md`.
2. Refresh the data: `refresh_inventory`. If the Compendium is more than 7 days old, follow the `compendium`
   skill (fragment stat bonuses). If Aegis is more than 7 days old, follow the `aegis` skill; in any case read
   `cache/aegis/changes.md`: a "Builds concerned" line for this sheet (tier or rank change of a weapon, aspect,
   fragment, set or artifact perk) goes to the player, with the best options for the same role (`rankings`).
   Never change the intent without their OK.
3. `optimize_build(slug, top=3)`. Special cases:
   - A tool error (sheet, exotic, fragment, unknown mod, no snapshot): fix the cause; nothing is written.
   - "no valid combination" warning (no results): a set requirement the inventory can't meet, or
     utility mods beyond the pieces' energy. Explain which; write nothing. For a set: don't change
     `intent.sets` (it is the theoretical target); propose an owned substitute and rerun with
     `sets=["Name:2", …]` or `no_sets=true`. If `resolved.sets` exists, it is the substitute already chosen: try
     the intent first (the player may have got the pieces), then go back to that substitute.
   - `complete: false` (search stopped): the 200,000-evaluation limit was reached, the result is approximate. Say
     so; propose tightening the `intent` (required set, fewer relevant stats) before relying on it.
   - `feasible: false` with results: no combination reaches the thresholds; the results are the least bad. Show
     the `deficit` per stat and propose adjusting a threshold, a fragment or a set constraint. Never write such a
     result: `write` refuses it; pass `force` only with the player's explicit OK, once the deficit was shown.
   - The "snapshot without the tuning stat" warning: tunings are ignored, so stats and ranking are underestimated. Say it clearly
     before concluding anything.
4. Compare #1 with `resolved`: replaced pieces, gain or loss per stat, utility mods per piece (`mods`),
   masterworks to do, transfers. If nothing changes, say so and stop. Energy: each result gives `energy_left`
   per piece. A piece > 0, or a sheet with no `intent.armor_mods_fill`: propose filler mods (`create-build`
   skill, step 5: duplicates allowed, various costs, effects in `armor-mods.md`); with the player's OK add them
   to the intent, `check_build(slug)`, then rerun step 3.
5. Weapons: grades come from the last weapon triage (`profile/triage/weapons.json`); run the `weapon-triage`
   skill first, otherwise every grade shows "—". For each weapon in `intent.weapons`,
   `weapon_candidates(slot=…, element=…, type=…, perk=…)` filtered from its `element`, `type`, `items` and `perks` (the
   intent describes the ideal weapon; a substitute is a concession to flag). Weapons are sorted by wishlist grade
   (S first). The `aegis` column gives Aegis's tier and rank (`S #1`; `+`: several versions rated);
   `weapon_options` marks `A` the perks he recommends. Perks column: `selected [alt1/alt2]` = perk in place and
   insertable alternatives, `*` = enhanced; a weapon whose alternative is the wanted perk is usable (to switch in
   game). `perk` searches the displayed options and the frame; `slot` and `element` only accept known values.
   Only flag a `resolved` weapon gone from the inventory, a candidate with a clearly better grade, or an ideal
   weapon of the intent now owned, with the reason. Crafted weapons: only the selected options are listed. Weapon
   rows do not mark the postmaster: check the location before equipping.
   Perks and mod of each weapon in `resolved.weapons` (new or not): `weapon_options(item_id)`, then check `perks`
   (one wanted option per column with several options, all columns) and `mod`, as in the `create-build` skill
   (step 8); fill them in when missing.
6. After the player's OK: if weapons, their perks or mod change, first update `resolved.weapons` /
   `resolved.rationale` in the JSON; then call once `optimize_build(slug, write=true, pick=N)` (`pick` defaults to
   1) with the same `sets` / `no_sets` as the chosen calculation: it keeps weapons and rationale, records applied
   sets in `resolved.sets` (removed without `sets`, the intent applying as is) and regenerates the `.md`. Keep
   one "Gap: …" reason per concession in `resolved.rationale`. Update `resolved.gaps` (non-armor gaps: `kind`
   `weapon` / `catalyst` / `upgrade`, `target`, `effects`) if a missing weapon or catalyst is now owned, or a new
   one is missing. Then `farm_needs` to recompute the farm needs. Don't rerun the optimizer only to regenerate the `.md`: after a manual JSON edit,
   `check_build(slug)` validates and regenerates it.
7. Nothing is equipped here: offer the `equip-build` skill.

Reminders: names (mods, aspects, fragments, weapons) stay in English in the sheet, in the player's game language
(`game_terms`) when you speak; never dismantle; quote the Compendium for
every mechanic invoked.
