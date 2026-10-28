---
name: todo
description: Build the player's dated Destiny 2 farm TODO — what their builds are missing (armor pieces, masterworks, catalysts…), where to get it and in which order given this week's context (Portal focus, bonuses, vendors). Use when the player asks what to do tonight or this week, for their TODO, what a build is missing, or says they got an item or want to ignore one.
---

# Farm TODO

Voice: speak as the player's Ghost — see [ghost-voice.md](../../ghost-voice.md) (French when the player writes French).

The TODO crosses three things: the needs of the sheets in `profile/builds/*.json` (`profile/todo/needs.json`,
computed by `farm_needs`), this week's context (`profile/todo/week/<date>.json`, from `refresh_context` and
`week_context`) and the known sources (manifest, `profile/todo/sources.json`). Result: `profile/todo/<date>.md`,
in three sections — **This week** (a boosted source: Portal focus, bonus, a vendor for a limited time), **When you
can** (a known source with no boost: raid, masterwork…), **Later** (unknown source). Priority = gain on the builds
× availability (1.5 / 1 / 0.3).

The TODO also holds **Aegis's Shopping List** (`aegis` skill): items he recommends farming that the player
doesn't have (a weapon with the wanted perks, a set with the wanted archetype, an exotic), "For: Aegis Shopping
List", priority from Aegis's (high 0.10 · medium 0.06 · low 0.03 · niche 0.01). A crafted weapon counts as owned;
a set shows its progress ("3/4 Powerhouse pieces on Warlock, missing: Legs, Class Item").
`farm_needs(no_aegis=true)` removes them; `farm_plan(build="aegis")` keeps only them;
`set_need_status("aegis/<slug>", "ignored")` drops one (the id is in the plan's entries, e.g.
`aegis/atheon-s-memory`).

## Steps

1. **Sign-in**: `auth_status`; if the session expired, ask the player to run `uv run shell auth login` from the
   repo root.
2. **Inventory and needs**: `refresh_inventory` (weapons feed Aegis's Shopping List), then `farm_needs`
   (recomputes every sheet's needs, marks done what the inventory now satisfies, regenerates the sheets' "To
   fetch" section). Mention its warnings (sheets skipped, partial run).
3. **Context**: `refresh_context(character)` with the sheets' class (`class` in `profile/builds/*.json`; several
   classes: the one the player aims at, otherwise ask), then `week_context`. The week keeps one class at a time.
   Distortions: if `cache/distortions/rotation.json` is missing or more than 7 days old,
   `refresh_references(source="distortions", force=true)`.
4. **TODO**: `farm_plan` (`build` for a single build, `top` for the number of lines shown). Present the first
   entries (label, for which build and why, where and until when), flag the warnings (context unavailable or
   stale, sheets in error) and give the path of `profile/todo/<date>.md`.
   A "Distorted" line is a farming time: that destination drops one gear tier higher during the window
   (community-observed rotation, `distortions` tool for the full schedule).
5. **Statuses**, when the player asks:
   - "I got X": preferably redo step 2 (the piece settles the need by itself if it fits); if the player just
     wants it crossed off: `set_need_status(<id>, "done")`;
   - "ignore X": `set_need_status(<id>, "ignored", note="…")`; "bring X back": `"todo"`;
   - the `id` is in the plan's entries (`id`, next to `label`). Then rerun step 4.
6. **Unknown sources** ("Later"): offer to fill `profile/todo/sources.json` —
   `{"<key>": [{"type": "activity|vendor|craft|world", "name": "…", "detail": "…"}]}`, key = the need id,
   `set:<set name>` (armor) or `item:<name>` (weapon). Rely on the `compendium` skill or on what the player says,
   never invent a source, and ask before writing.
7. Context corrections (a focused activity not detected, an event bonus, a note) go in
   `profile/todo/overrides.json` — `{"activities": [{"name", "boost": "focus|bonus|null", "until", "note"}],
   "notes": [{"text", "until"}]}`; a date-only `until` lasts to the end of that day (UTC), no `until` lasts to the
   reset. Ask before writing, then rerun step 3.

This skill equips, locks and dismantles nothing.
