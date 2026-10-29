# Cosmetics without a collectible (S-025) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (the player's usual flow). Steps use
> checkbox (`- [ ]`) syntax.

**Goal:** `fashion_check` answers owned / not owned for ornaments and shaders that have no collectible, from the
profile's plug sets, instead of always "unknown" — story S-025.

**Spec:** agreed in chat 2026-10-29 (design played back, player: "Yes, plan it").

**Checked live 2026-10-29 (read-only, components 200 / 305 / 800):** of 1,475 named cosmetics without a
collectible (1,437 ornaments, 38 shaders), 461 are listed in `profilePlugSets` (61 `canInsert: true`), 470 sit in
no listed entry although a plug set that can hold them is on the profile, 539 are in no plug set definition or one
the profile lacks. Character plug sets hold 5 of them, none insertable. Against Collections (cosmetics that have a
collectible): `canInsert: true` → owned every time; absent from a present set → not owned 1,366 / 1,390 (98%);
listed but `canInsert: false` → 28 owned, so ambiguous.

**Architecture:** extend the fashion feature (engine + tool), no new tool, no core edits.
- `shell/engines/fashion.py`: `build_index` takes the plug set definitions and stores, per shader / ornament,
  `sets` — the plug sets that can hold it. `owned` gets a `plugs` argument
  `{"insertable": set[int], "listed": set[int], "sets": set[int]}` (plug hashes insertable, plug hashes listed,
  plug set hashes present, profile and character scopes merged).
- `shell/mcp/tools/fashion.py`: `collectibles_state` asks for component 305 in the same profile call and returns
  that `plugs` dict as a third value (character scope: the look's class only, like the collectibles).

## Global Constraints

- Rule order in `owned`: inventory (unchanged) → Collections when the collectible is in the state (unchanged) →
  plug sets: insertable → True; not listed and `entry["sets"] & plugs["sets"]` → False; else None.
- My call: the plug-set rule also covers a cosmetic whose collectible is missing from the profile's state (same
  "the profile doesn't say" case today); a collectible the state knows is never overridden.
- `plugs=None` (old callers, tests) behaves exactly as today.
- Tests: `uv run --no-sync pytest -q`; every step test-first.

---

### Task 1: Engine (`shell/engines/fashion.py`, `tests/engines/test_fashion.py`)

- [x] Failing tests: `build_index(ITEMS, COLLECTIBLES, PLUG_SETS)` gives a fixture ornament without collectible
      `sets == {900}`; `owned` with `plugs` → True when insertable, False when set 900 is present and the plug not
      listed, None when listed but not insertable, None when set 900 is absent, None when the plug is in no set.
      A cosmetic with a known collectible ignores `plugs`.
- [x] Implement: `build_index(items, collectibles, plug_sets=None)` → `{plug hash: set of set hashes}` from
      `reusablePlugItems`, stored on shader / ornament entries as `sets`; `owned(entry, state, inventory, plugs=None)`;
      `check(..., plugs=None)` passes it through.

### Task 2: Tool (`shell/mcp/tools/fashion.py`, `tests/mcp/test_fashion_tool.py`)

- [x] Failing tests: `collectibles_state` with a fake profile carrying `profilePlugSets` and `characterPlugSets`
      (component 305 requested) returns the merged `plugs`; the class's character only; no character of the class →
      profile plug sets only. `fashion_check` reports `owned: true` / `false` for a no-collectible ornament through
      the fake (update the three `collectibles_state` monkeypatches to the 3-value shape).
- [x] Implement: components `[200, 305, 800]`; build `plugs`; `fashion_check` passes the plug set table
      (`DestinyPlugSetDefinition`) to `build_index` and `plugs` to `check`. Docstring: owned may come from plug sets.

### Task 3: Skill and story

- [x] `.claude/skills/fashion/SKILL.md` step 3: `owned: null` now means neither Collections nor the plug sets say
      (mostly old Armor 1.0 ornaments) — still "unknown", never "missing". `tests/test_skills.py` green.
- [x] Move S-025 to `doing/` at start, `done/` when its criteria pass.

### Task 4: Live check (read-only)

- [x] `fashion_check` on my account for a look with no-collectible ornaments — one the plug sets say I own
      (e.g. Lost Pacific Helmet), one not owned, one of the unknown group — and compare with what the game shows.
      No `save_as`, no `set_sockets`. Done 2026-10-29 (Warlock): Solstice Gloves (Resplendent) owned, Venetian Mail
      not owned, Lustrous Robes (Unkindled) unknown.

### Finish

- [ ] Full suite, one fresh review, ask the player before merging (no remote, no push).
