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
   `equip_plan(slug)` (nothing is executed). Keys: `ready`, `problems`, `warnings`, `character`, `equip`,
   `subclass` (`element`, `item`, `plugs`), `armor_sockets` (`{itemId, slot, name, plugs}`), `weapon_perks`
   (`{itemId, name, select}`: options to select), `weapon_sockets` (`{itemId, name, plugs}`: weapon mod to
   insert), `artifact` (`{name, plugs}` or `null`), `lock`, `masterwork_todo`, `transfers`,
   `expected_armor_stats`, `snapshot`.
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
   `get_equipped(character)` → `subclass.itemId` when the equipped subclass is `subclass.item`, else the id of
   that item in `other_subclasses`. If `artifact`: the id of the artifact named `artifact.name` — `get_equipped().artifact` when it is the one
   equipped, else its entry in `other_artifacts` (each character has every artifact); it is then equipped with
   the other items through `equip_items`.
4. **Preview** (`dry_run: true`, no effect):
   - `equip_items`: `character`, `item_ids` = `equip` + the subclass id + the artifact id when it is not
     equipped yet (12 at most). A weapon "in the
     postmaster" (weapon rows don't mark it): pull it before asking for the "yes", with a dry run then the player's OK
     (`pull_from_postmaster`, `character` = the class `weapon_candidates` gives as its location, lowercase), then
     redo this dry run;
   - `set_sockets` subclass, alone: `changes: [{itemId: <subclass id>, plugs: subclass.plugs}]`. Fragments come
     with their `socketIndex` (active sockets, from the manifest);
   - `set_sockets` artifact, separate call (if `artifact`): `[{itemId: <artifact id>, plugs: artifact.plugs}]`;
   - `set_sockets` armor, separate call: `{itemId, plugs}` of each `armor_sockets` entry; limits: 10 changes,
     30 socket actions per call;
   - `set_perks` (if `weapon_perks`): `changes: [{itemId, select}]`;
   - `set_sockets` weapons, separate call (if `weapon_sockets`): `{itemId, plugs}` of each entry; a refused mod
     (not unlocked, Enhanced on a weapon below Tier 4, Adept on a non-adept weapon): propose a substitute from
     the Compendium, without executing;
   - `set_lock`: `item_ids: lock`, `locked: true`, **`dry_run: true`** (it acts by default).
   Summarize for the player: items equipped, transfers (`transfers`), subclass, artifact and its perks, mods per
   piece (added and removed), each weapon's perks and mod, locks, and any refused plug (not unlocked →
   substitute via the Compendium, without executing). Normal notes: "<plug> already in socket N"; removals with
   no effect (an empty socket emptied again, extra `Empty Fragment Socket`). A piece still in the vault is read
   on the first character: if its dry run refuses a plug, redo it after `equip_items`. A legacy piece in
   `masterwork_todo` (energy counted as 10): the player masterworks it in game before the armor `set_sockets`.
5. **Run**, after the "yes", in this order, each with `dry_run: false`: `equip_items`; `set_sockets` subclass;
   `set_sockets` artifact; `set_sockets` armor; `set_perks`; `set_sockets` weapons; `set_lock`. `equip_items` may
   send an unrequested item to the vault to make room: say so. If `equip_items` partly fails: stop, say what was
   done and ask the player before going on. An energy failure on `set_sockets` is a plan bug: stop and report
   it, no substitute. A failure on a no-effect removal doesn't matter. Everything is reversible, no automatic
   rollback. Don't rerun `set_sockets` right away: Bungie's reads lag 1–2 min; wait or check with
   `get_equipped`.
6. **Check**: `get_equipped`; `armor_totals` is the armor alone, to compare with `expected_armor_stats`
   (fragments already excluded). Expected gaps: masterworks not done yet (`masterwork_todo`, lower stats), a
   lagging read (read again once after 1–2 min). Also check subclass, aspects, fragments, mods, weapon perks and
   mods, artifact perks (`get_equipped` lists them). Report any other gap.
7. **End**: list the masterworks to do in game (`masterwork_todo`).
