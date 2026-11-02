---
name: equip-build
description: Equip a saved build sheet (profile/builds/*.json) in game — armor, weapons, subclass, aspects, fragments, mods, artifact — after a preview (dry run) the player approves, lock the build's items and check the resulting stats. Use when the player wants to equip, apply or wear a build.
---

# Equip a build

Voice: speak as the player's Ghost — see [ghost-voice.md](../../ghost-voice.md) (French when the player writes French).

Nothing is ever dismantled. No action in game without the player's explicit "yes" on the dry-run summary.
**Never** pass `force: true` to `set_sockets`: it skips the "already installed" check and can lose mods.

1. **Sheet**: pick the sheet (list `profile/builds/*.json` if the player doesn't name it).
2. **Plan**: right before, `refresh_inventory` — the plan computes mod removals from the snapshot. Then
   `equip_plan(slug)` (nothing is executed): `ready`, `problems`, `warnings`, what will be written,
   `masterwork_todo`, `transfers`, `expected_armor_stats`, `snapshot`.
   - `ready: false` (`problems`): equip nothing. Item missing or no resolved armor → `optimize-build`; piece in
     the postmaster → `pull_from_postmaster` with the player's OK (`character` = the class in the armor row's
     `location` `<Class> (Postmaster)`, lowercase), then refresh and rerun; "equipped on <Class>" → the player
     unequips it there, then rerun; "subclass: …" or "artifact: …" → fix the sheet (`check_build(slug)`), then
     rerun; "perks not in the weapon's options" → fix `resolved.weapons[].perks` (`weapon_options(item_id)`),
     then rerun.
   - A tool error (sheet, no snapshot): fix the cause.
   - `warnings`: show them all to the player. Slot mods kept (slot missing from `intent.armor_mods`): if the
     player refuses a kept mod, set `intent.armor_mods.<slot>` to `[]`, `check_build(slug)`, then rerun the plan
     (no need to re-optimize); if they want other mods, go through `optimize-build` first (their energy must be
     reserved). "snapshot without the tuning stat": tunings in place are kept, real stats differ from the sheet; say so and
     propose re-optimizing after a refresh. "free energy": the piece is not filled; propose `optimize-build`
     (filler mods) before equipping. "perks to choose" or "no weapon mod": offer to choose them (`create-build`
     skill, step 8), write them in `resolved.weapons`, then `check_build(slug)` and rerun the plan. "check
     fragment slots in game": the catalog does not know which fragment sockets are active; the player confirms
     the active ones before the subclass change. Others: result more than 7 days old (offer `optimize-build`),
     no weapons, an exotic that may block, masterworks to do, missing fragments.
3. **Character** (`character` from the plan): in orbit, a social space or offline; otherwise wait.
4. **Preview**: `equip_build(slug)` (no effect; it refuses a snapshot over 15 minutes old: `refresh_inventory`, then
   again). `ready: false`: as in step 2. `stopped_at: "equip"` with `blocked`: a weapon "in the postmaster" (weapon rows
   don't mark it): pull it before asking for the "yes", with a dry run then the player's OK (`pull_from_postmaster`,
   `character` = the class `weapon_candidates` gives as its location, lowercase), then `refresh_inventory` and preview
   again; no `confirm` comes back until this is solved.
   Summarize `steps` for the player: items equipped, transfers (`transfers`), subclass, artifact and its perks, mods per
   piece (added and removed), each weapon's perks and mod, locks, and everything in `refused` (not unlocked, Enhanced
   on a weapon below Tier 4, Adept on a non-adept weapon → propose a substitute via the Compendium, without executing).
   Normal notes: "<plug> already in socket N"; removals with no effect (an empty socket emptied again, extra `Empty
   Fragment Socket`). A piece still in the vault is read on the first character, so `refused` may name plugs it can
   take once equipped: say so. A legacy piece in `masterwork_todo` (energy counted as 10): the player masterworks it
   in game before the run.
5. **Run**, after the "yes": `equip_build(slug, dry_run=false, confirm=<the preview's confirm>)`. It runs the items,
   subclass, artifact, armor mods, weapon perks, weapon mods, then locks, and stops at the first real failure:
   `stopped_at` and `blocked` say where and why, `steps` what was done. Say all of it and ask the player before going
   on; an energy failure on armor mods is a plan bug: report it, no substitute. Refused with "No preview": the plan
   changed, preview again and get a new "yes". `equip` may send an unrequested item to the vault to make room (`notes`
   in its `moves`): say so. Everything is reversible, no automatic rollback. Don't run it again right away: Bungie's
   reads lag 1–2 min; wait or check with `get_equipped`. Then `refresh_inventory`.
6. **Check**: `get_equipped`; `armor_totals` is the armor alone, to compare with `expected_armor_stats`
   (fragments already excluded). Expected gaps: masterworks not done yet (`masterwork_todo`, lower stats), a
   lagging read (read again once after 1–2 min). Also check subclass, aspects, fragments, mods, weapon perks and
   mods, artifact perks (`get_equipped` lists them). Report any other gap.
7. **End**: list the masterworks to do in game (`masterwork_todo`).
