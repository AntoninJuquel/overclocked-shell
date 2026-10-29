# Minor findings sweep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (the player's usual flow). Steps use
> checkbox (`- [ ]`) syntax.

**Goal:** Close the minor findings the six feature reviews deferred (S-018 … S-024, S-019), each with a test that
fails first, in one branch; drop the ones that turned out not to be bugs or are features of their own.

**Spec:** the review reports, as summarised to the player at each merge (2026-10-28 / 29).

## Triage (player can override)

**Dropped — not a bug:** Jötunn in the Boss Damage cache (stored correctly as `J\xf6tunn`; the reviewer's console
couldn't print it).

**Deferred — a feature, not a fix:** cosmetics without a collectible always "unknown" (needs profile plug sets,
component 305 — a story of its own); flagging encounter files when a guide changes is kept (cheap, Task 4).

**Kept — 31 fixes in 6 tasks, one per feature.** Each line: the failure → the fix.

## Global Constraints

- No behaviour change beyond the listed fixes; no core edits; tests `uv run --no-sync pytest -q` (or plain
  `uv run` once Claude Code restarted).
- Every fix: a test that fails first (skill-only lines are checked by `tests/test_skills.py`).

---

### Task 1: Recommender (`shell/engines/recommend.py`, `.claude/skills/recommend/SKILL.md`)

1. Legendary trace rifles never match their DPS row (row "Trace rifle" has no frame) → a family whose rows have no
   frame word matches on family alone.
2. `type="fusion"` also returns Linear Fusion Rifles → exact type match when the argument equals a full type name
   ("Fusion Rifle"), substring otherwise (unchanged).
3. `not_owned` drops Aegis' Other-tab rows under a `type` filter → keep them last, marked, as `rankings` does; test
   for an owned weapon rated only in Other.
4. General picks don't name the Aegis tab → label `Aegis S #1 (Autos)`.
5. Empty result after filters is silent → warning "no owned weapon matches the filters".
6. Skill: second exotic → pass the replacement for the other slot in the same `equip_items` call.

### Task 2: Build sharing (`shell/engines/share.py`, `shell/outputs/build_pdf.py`)

1. A mod name with no collectible copy can resolve to a deprecated copy → sort key adds `"Deprecated" in
   itemTypeDisplayName` before the hash.
2. Exotic fallback (sheet without `resolved`) picks an arbitrary copy → same collectible-first key, filtered on the
   sheet's class.
3. Escaped bullets keep their backslash in the PDF (`- \-10 Weapons`) → unescape bullets like paragraphs.
4. A paragraph starting with an unescaped `|` becomes a one-row table → a table needs its `|---|` separator line.
5. Glyphs missing from the Unicode font are dropped silently → `SIMPLER` applied on both font paths for the
   characters Arial lacks (✓, ★) — map them to text.

### Task 3: Distortions (`shell/engines/distortions.py`, `shell/sources/distortions.py`, `shell/engines/todo/plan.py`,
`shell/mcp/tools/distortions.py`)

1. One UTC offset for a schedule crossing a DST change → a row whose offset differs from the header carries its own
   `(UTC±hh:mm)`.
2. "Wed" is ambiguous at 168 h → weekday + day of month beyond 6 days (`Wed 4`).
3. `stale()` crashes on a naive `fetched` → treat naive as UTC.
4. The TODO never says the rotation is old → `_add_distortions` adds the stale warning.
5. A reshaped page reports `errors` without `stale` while the cache is still used → both.
6. "Exploring Europa" / "Complete activities in the Dreaming City" don't match → a source name that contains a
   destination as a whole word matches.
7. `destination=""` is silently ignored → ToolError listing the destinations.

### Task 4: Raid companion (`shell/sources/guides/extract.py`, `shell/engines/raids.py`, `shell/outputs/raid_page.py`,
`shell/mcp/tools/raids.py`)

1. An unclosed `<nav>`/`<iframe>` drops the rest of the article → skip depth resets at the end of the container
   (block-level close of the parent) — test with an unclosed nav before a heading.
2. `srcset`-only images and `<picture><source>` are dropped → first `srcset` URL as fallback.
3. `<div>` and `<h5>`/`<h6>` text runs into the next block → `div` is a block, `h5`/`h6` become `#####`/`######`.
4. An alt containing `]` breaks the Markdown image → escape `]` in alts.
5. `check` doesn't validate names, step lists or room coordinates (raw TypeError at render) → rules for `name`
   on spots / roles / phases, `steps` values are lists of text, room `x y w h` numbers within 0-100.
6. A malformed `callouts.json` crashes `raid_show` / `raid_rename` → ValueError with a one-line message (ToolError).
7. `live.html` and renames are written non-atomically → `write_if_changed`-style tmp + replace.
8. Encounter files are not flagged when a guide changes → `raid_show` warns when a source's `updated` differs from
   `cache/guides/<raid>/index.md`.

### Task 5: Ultimate Bravery (`shell/engines/bravery.py`, `shell/mcp/tools/bravery.py`)

1. Artifact-only mods (no collectible) are rolled as unlocked → `slot_mods` keeps only defs with a collectible.
2. A slot with no legendary is left out and an equipped exotic there can clash → allow an exotic there when no
   legendary exists, re-picking so that only one exotic remains; else error.
3. The live subclass call runs before the "no exotic armor" check → roll armor first.
4. Missing tests: a failed roll writes nothing; fewer catalog fragments than slots; `part="armor"`, `"subclass"`,
   `"mods"` success paths.

### Task 6: Fashion (`shell/engines/fashion.py`, `shell/mcp/tools/fashion.py`, `.claude/skills/fashion/SKILL.md`)

1. A name that exists as another kind says "not found (close: same name)" → "is a shader" / "is an ornament".
2. Armor rows match the inventory by one hash → by normalized name among the snapshot's armor.
3. Saving a wardrobe overwrites silently → `overwrote: true` in the result; the skill asks before overwriting.
4. No character of the look's class → profile-scoped ownership still answered, with a warning.
5. Skill: armor rows need the piece equipped (not `set_sockets`); legacy armor refusing universal ornaments
   explained.

### Close

- [ ] One fresh review of the branch; fix; tests; ask before merging.
