# Situational recommender (E5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or subagent-driven-development) to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** "What's the best weapon for this?" answered from what the player owns, what they are wearing and Aegis
(story S-018): the pick, why, the owned alternatives, and what better exists that they don't own.

**Architecture:** One new engine module `shell/engines/recommend.py` (pure: snapshot rows + Aegis rows in, ranked
lines out), one tool module `shell/mcp/tools/recommend.py`, one skill `.claude/skills/recommend/`. Reuses
`read_snapshot`, `weapons.load_grades`, `weapons.aegis_label`, `aegis.lookup` (`weapon_rows`, `best`,
`tier_key`, `rows`). No live Bungie call: "equipped" comes from the weapon snapshot (`equipped`, `location`), so
the skill calls `refresh_inventory` first. No core edits.

**Tech Stack:** Python 3.12, `shell.engines.builds.weapons`, `shell.sources.aegis.lookup`, `mcp` via `shell.mcp.tool`.

## What the code does vs what the skill does

The code only does what is mechanical and testable: filter, rank, compare with equipped. Reading the situation
("Grandmaster, Overload + Barrier, Void surge, boss is Atraks") stays in the skill, which turns it into filters
using tools that already exist: `week_context` / `refresh_context` (modifiers, champions), `get_equipped` (subclass,
artifact perks, armor surge mods), the `compendium` skill (which weapon types the artifact's champion perks cover),
`rankings(view="bosses")`.

## Tool

`recommend_weapons(character, role="general", slot=None, element=None, type=None, top=5)`

- `role="general"`: owned weapons ranked by best Aegis Endgame row (`tier_key`), then wishlist grade, then name.
- `role="dps"`: owned weapons matched to Aegis `dps-sustained` rows (see ruling 2), ranked by that row's DPS;
  unmatched weapons are left out of the dps list.
- Filters `slot` (Kinetic / Energy / Power), `element`, `type` as in `weapons.select`.
- One line per weapon name (best copy: grade, then equipped, then locked), at most `top`.

Returns:
```
{"snapshot": "...",
 "equipped": ["Energy | Choir of One | Auto Rifle | Void | exotic", ...],   # the character's 3 weapons
 "picks": ["1 | <id> | Name | type | element | slot | ammo | Aegis S #2 | grade A | Warlock | note", ...],
 "not_owned": ["S #1 | Name | tab", ...],     # up to 3 Aegis entries ranked above the best owned pick
 "warnings": [...]}
```
`note` (equipped-aware, the core of "situational"): `equipped` · `swap: replaces <equipped name>` ·
`second exotic: unequip <name>` (exotic pick while another exotic weapon is equipped in another slot) ·
`in vault` / `on <class>` (the equip will transfer it).

Errors (one line, `ToolError`): no snapshot ("call refresh_inventory"), no Aegis data, unknown character / role /
slot.

## Rulings in this plan (player can override)

1. **Weapons only.** Armor, mods and subclass picks belong to builds (create-build / optimize-build). Deferred.
2. **DPS matching by archetype, not by name.** Aegis DPS rows are archetypes ("Aggressive rocket launcher", perks,
   example weapon in parentheses). An owned weapon matches a row when the row's first word is its frame's first
   word and the row's `Family` is in its type ("rocket" in "Rocket Launcher"); exotics match on their name. The
   line shows the row's perk setup so the skill can say "you have the frame, not Bait and Switch". Perk-by-perk
   matching is deferred (`shortcut:` comment).
3. **Champions are the skill's job.** The artifact's champion perks change each season and their weapon types are
   in the Compendium; the skill reads them and passes `type`. No champion table in code.
4. **`not_owned`** lists Aegis rows of the same filters ranked above the best owned pick (general role only), so
   the TODO / farm conversation can pick them up. No farm need is written.
5. **Equip is not in this tool.** The skill offers `equip_items` with its preview, as the other skills do.

## Review Focus

1. Two copies of one weapon → one line, best copy; the equipped copy wins a tie.
2. Exotic pick while another exotic is equipped → the note names the exotic to unequip.
3. A stale snapshot (older than the last game session) → the skill says so; the tool shows the snapshot time.
4. `role="dps"` on a weapon type Aegis has no row for → empty picks plus a warning, never a guessed DPS.
5. `type` filter on Aegis' Other tab (no type) does not hide owned weapons (same rule as `rankings`).

---

### Task 1: Engine — general ranking and equipped notes

**Files:** Create `shell/engines/recommend.py`, `tests/engines/test_recommend.py`

- [ ] **Step 1: Tests** on fixture snapshot rows + fixture Aegis rows (reuse `tests/engines/builds/conftest.py`'s
  isolation of `aegis.lookup.DATA`): ranking order, one line per name, swap / second-exotic / location notes,
  filters, `not_owned`.
- [ ] **Step 2:** `uv run pytest tests/engines/test_recommend.py -q` — FAIL.
- [ ] **Step 3: Implement** `recommend(items, grades, character, role="general", slot=None, element=None,
  type_=None, top=5) -> dict`.
- [ ] **Step 4:** `uv run pytest -q` — PASS.
- [ ] **Step 5:** `git mv` S-018 to `doing/`; commit "Recommender engine: owned weapons ranked by Aegis, equipped-aware".

### Task 2: Engine — DPS role

**Files:** Modify `shell/engines/recommend.py`, `tests/engines/test_recommend.py`

- [ ] **Step 1: Tests:** frame + family match, exotic name match, no match → warning, order by DPS.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** commit "Recommender: DPS role from Aegis sustained DPS".

### Task 3: Tool

**Files:** Create `shell/mcp/tools/recommend.py`, `tests/mcp/test_recommend_tool.py`

- [ ] **Step 1: Tests** like `tests/mcp/test_build_view_tools.py`: registered, returns the shape above, errors
  are one-line `ToolError`s.
- [ ] **Step 2–4:** FAIL → implement (`register(mcp, ctx)`, `_player_facing`-style error mapping) → PASS.
- [ ] **Step 5:** commit "recommend_weapons tool".

### Task 4: Skill

**Files:** Create `.claude/skills/recommend/SKILL.md` (Ghost voice link; `tests/test_skills.py` checks tool names)

Playbook: refresh inventory → read the situation (ask one question if the activity is unclear) → `get_equipped`
for subclass / surge / artifact → champions from the Compendium when relevant → `recommend_weapons` per slot that
matters → answer: the pick, one line why (Aegis tier or DPS, source and date), 2–3 owned alternatives, what to
unequip, what better exists to farm → offer an `equip_items` preview.

- [ ] **Step 1:** write it; `uv run pytest tests/test_skills.py -q` — PASS.
- [ ] **Step 2:** commit "recommend skill".

### Task 5: Live check and close

- [ ] Live, read-only on the player's account: "boss DPS on my Warlock", "general add clear, Void", "what replaces
  Corrective Measure". Equip only as a preview.
- [ ] One fresh review of the branch; fix; `uv run pytest -q`.
- [ ] Tick S-018's criteria, `git mv` to `done/`; ask the player before merging into main.
