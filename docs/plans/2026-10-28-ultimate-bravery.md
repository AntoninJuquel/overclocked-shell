# Ultimate Bravery (E9) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (the player's usual flow) to implement
> this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** "Roll me a build" gives a random, rule-abiding build from the player's own items, like DIM's Randomize,
saved as a build sheet so the existing equip flow (plan, preview, equip on yes) applies it — story S-023.

**Behaviour reference (read 2026-10-28):** DIM `src/app/loadout-drawer/auto-loadouts.ts` (`randomLoadout`,
`randomSubclassConfiguration`) and `loadout-drawer-reducer.ts` (`randomizeLoadoutMods`): random owned subclass;
random super and abilities; aspects one by one without repeats; as many random fragments as the aspects allow;
random owned item per slot, equippable by the class, at most one exotic weapon and one exotic armor piece; random
unlocked armor mods per piece within its energy.

**Architecture:** A pure engine `shell/engines/bravery.py` rolls the parts; a tool module writes the roll as the
sheet `profile/builds/bravery.json` (validated by `sheet.save`) and returns it; a skill announces it and hands over
to the existing `equip-build` flow (`equip_plan` → preview → equip on yes). No core edits.

**Spec:** the player's description, agreed in chat 2026-10-28 (this plan's Goal and Rulings).

## Global Constraints

- Only the player's items (the inventory snapshot), only the character's class; nothing equipped without the
  usual preview and the player's yes.
- The roll must pass the sheet validation and `check_build` (subclass and fragment rules); `equip_plan` must
  report `ready` for a roll from the current snapshot.
- Tests: `uv run --no-sync pytest -q` while the MCP server runs.

## Rulings (player can override)

1. **One sheet, `bravery`**, overwritten by every roll (name "Ultimate Bravery — <date>"); keeping a roll = asking
   the Ghost to copy it under another name.
2. **No cosmetics** (ghost, sparrow, ship, emblem): not in Shell's snapshot. Deferred.
3. **Every armor mod in the manifest counts as unlocked**; slot mods only (stat mods and tunings stay as
   installed). `shortcut:` exclusive-group duplicates are not filtered; the equip preview shows a refused socket.
4. **Exactly one exotic armor piece** when the class owns any (the sheet needs `intent.exotic`); zero exotics
   allowed for weapons (DIM: at most one).
5. **Subclasses = the ones the character owns** (live: `get_equipped` gives the equipped one and
   `other_subclasses`); abilities, aspects and fragments = every one the manifest catalog knows for that
   class and element (`catalog.load_catalog(...)["subclass"]`).
6. Items in the postmaster or equipped on another character are never picked.
7. Reroll parts: `all`, `subclass`, `weapons`, `armor`, `mods` (mods reroll keeps the armor).

## Review Focus

1. A class with no owned exotic armor → one-line error, nothing written.
2. A roll whose aspects allow 0 fragments (or the catalog has fewer fragments than slots) → fragments = what fits.
3. An armor piece with energy 0 or unknown (`energy` missing / "?/?") → no slot mods for it, no crash.
4. Rerolling `mods` before any roll exists → error "roll a build first".
5. Two rolls in a row with a seeded RNG → different results only when the seed differs (tests use
   `random.Random(seed)`; the tool uses an unseeded one).

---

### Task 1: Roller engine

**Files:** Create `shell/engines/bravery.py`; Test `tests/engines/test_bravery.py`.

**Interfaces — Produces:**
- `roll_subclass(cls: str, owned_elements: list[str], idx: dict, rng) -> dict` — sheet `subclass`
  (`element, super, abilities{grenade, melee, class, jump}, aspects, fragments`); aspects: up to 2 distinct;
  fragments: `subclass.fragment_slots`-many distinct (fewer if the catalog has fewer).
- `roll_weapons(items: list[dict], rng) -> list[dict]` — one per slot Kinetic / Energy / Power
  (`{slot, itemId, name}`), at most one exotic; slots with no candidate are left out.
- `roll_armor(items: list[dict], cls: str, rng) -> list[dict]` — Helmet, Gauntlets, Chest, Legs, Class Item
  (`{slot, itemId, name}`), exactly one exotic; `ValueError("no exotic armor for <cls>")` when none.
- `roll_mods(armor_entries, armor_items, slot_mods: dict[str, dict[str, int]], rng) -> dict[str, list[str]]` —
  per slot, up to 3 random slot mods (repeats allowed, as in game) whose costs fit the piece's free energy
  (capacity from `energy` "used/capacity" minus nothing installed by Bravery).
- `slot_mods(defs) -> dict[slot, {mod name: cost}]` — armor slot mods from item definitions, category
  `enhancements.v2_head|v2_arms|v2_chest|v2_legs|v2_class_item` → Helmet / Gauntlets / Chest / Legs / Class Item,
  base mods only (the copy with a collectible, as `engines.share` does).
- Candidate items: `classType == cls` for armor (any for weapons), location not containing "Postmaster", not
  `equipped` on another class.

- [ ] **Step 1: Tests** with fixture snapshot rows and a fixture catalog `idx` (same shape as
  `tests/engines/builds/test_subclass.py` builds): `test_subclass_uses_owned_elements_and_fragment_slots`,
  `test_no_fragments_when_aspects_give_none`, `test_weapons_one_per_slot_at_most_one_exotic` (100 seeded rolls),
  `test_armor_exactly_one_exotic_and_class_only`, `test_no_exotic_armor_raises`, `test_postmaster_and_other_class_
  equipped_skipped`, `test_mods_fit_energy_and_slot`, `test_unknown_energy_gives_no_mods`, `test_slot_mods_base_copy`.
- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** `uv run --no-sync pytest -q` PASS.
- [ ] **Step 5:** `git mv` S-023 to `doing/`; commit "Ultimate Bravery roller".

### Task 2: Tool

**Files:** Create `shell/mcp/tools/bravery.py`; Test `tests/mcp/test_bravery_tool.py`.

**Interfaces:**
- Consumes: Task 1; `sheet.save`, `sheet.load`, `catalog.load_catalog`, `read_snapshot`, `equipped()` (live
  owned subclasses, as `get_equipped`).
- Produces: `roll_bravery(character: str, part: str = "all") -> dict` — writes `profile/builds/bravery.json`
  (+ `.md`); returns `{"slug": "bravery", "subclass", "weapons", "armor", "mods", "md", "snapshot"}`; errors:
  unknown character / part, no snapshot, no exotic armor, part ≠ all without an existing roll.
  Sheet: `name`, `class`, `activity: "Ultimate Bravery"`, `subclass`, `intent` (`exotic.name`,
  `armor_mods`), `resolved` (`date`, `armor` with `mods`, `weapons`).

- [ ] **Step 1: Tests** (fake client returning a profile with two subclasses, fixture snapshots, monkeypatched
  catalog and item defs, seeded RNG via a module-level `RNG` the test replaces): full roll writes a sheet that
  `sheet.load` accepts; `part="weapons"` keeps subclass and armor; `part="mods"` without a sheet errors.
- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** PASS. **Step 5:** commit "roll_bravery tool".

### Task 3: Skill

**Files:** Create `.claude/skills/ultimate-bravery/SKILL.md` (Ghost voice; `tests/test_skills.py`).

Playbook: `refresh_inventory()` → `roll_bravery(character)` → announce with flair (subclass and super first,
then the exotic, weapons, a one-liner on how cursed it looks) → "reroll X" → `roll_bravery(character, part)` →
"let's go" → follow the `equip-build` skill with slug `bravery` (`check_build`, `equip_plan`, previews, equip on
yes). Chaos is the point: never "improve" a roll, never refuse one for being weak.

- [ ] Write → `uv run --no-sync pytest tests/test_skills.py -q` → commit "ultimate-bravery skill".

### Task 4: Live check and close

- [ ] On the player's Warlock: `roll_bravery("warlock")` (direct engine call while the server runs old code), then
  `check_build("bravery")` logic and `equip_plan` logic → `ready: true`, preview only; reroll weapons once.
- [ ] One fresh review; fix; tests. Tick S-023, move to `done/`; ask before merging.
