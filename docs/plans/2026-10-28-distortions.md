# Live rotations: Distortions (E7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shell knows the hourly Distortion rotation (the Distorted destination drops one gear tier higher), so the
player can ask "what's Distorted tonight?" and the farm TODO shows when each destination need is next Distorted —
story S-020, renamed "Live rotations: Distortions".

**Why this shape:** Bungie does not publish the rotation (checked: current manifest and the week's raw context have
no Distortion activity, modifier or milestone). The trackers compute it: a fixed order of 7 destinations, one per
hour, from an anchor hour verified in game (wewantdestiny3.com/distortion-tracker: `ROTATION`, `ANCHOR_HOUR`,
`ANCHOR_INDEX`; current order Cosmodrome → EDZ → Dreaming City → Savathun's Throne World → Moon → Europa → Nessus).

**Architecture:** No core edits.
- `shell/sources/distortions.py` — a source (`NAME`, `refresh`): downloads the tracker page with `sources.web.get`,
  extracts the three constants, writes `cache/distortions/rotation.json` (`order`, `anchor_hour`, `anchor_index`,
  `source`, `fetched`) only when valid; reports a change of order or anchor. Discovered by `refresh_references`.
- `shell/engines/distortions.py` — pure: `active(rotation, hour)`, `windows(rotation, destination, now, count)`,
  `schedule(rotation, now, hours)`, `match(name, rotation)` (source name → destination, aliases below).
- `shell/mcp/tools/distortions.py` — `distortions(hours=24, destination=None)`.
- `shell/engines/todo/plan.py` — `run` adds the next windows to entries whose sources include a destination;
  `render_md` prints them. (An engine, not core: one call and one line.)
- `.claude/skills/todo/SKILL.md` — one line: "Distorted" lines are farming times; refresh the rotation with the
  other references. No new skill: the tool's description is enough for "what's Distorted tonight?".

## Rulings in this plan (player can override)

1. **Times, not ranking:** the TODO shows the next windows; priorities do not change (every destination comes back
   within 7 h, a boost would be noise).
2. **Local time** of the machine, with its UTC offset, e.g. `Distorted today 21:00–22:00 (UTC+01:00), then every
   7 h`. The TODO's week line stays in UTC as today.
3. **Source = the tracker page's constants**, refreshed with the other references (7-day rule like Aegis, in the
   TODO skill's refresh step). Page unreachable or constants not found → the last cached rotation, `stale`; no
   cache → the tool says so and the TODO leaves the line out with a warning. No hard-coded fallback.
4. **Destination aliases:** "Savathun's Throne World" = "Throne World"; "EDZ" = "European Dead Zone"; case and
   apostrophes ignored (`aegis.names.norm`-style). Any other source name is not a destination.
5. **The page's content beyond the three constants is not stored** (third-party page; facts only).
6. Eververse moves to S-019 (fashion): add it there as an acceptance criterion.

## Review Focus

1. Anchor arithmetic for hours before the anchor (negative difference) and across a DST change (UTC hours, local
   display only).
2. The page changes shape (constants renamed, order of 6 or 8 names) → refresh refuses it, keeps the cache, reports
   an error; never writes a broken rotation.
3. A need with several sources (Europa + a vendor) → one Distorted line for Europa only.
4. A TODO run without a cached rotation → no crash, one warning.

---

### Task 1: Source

**Files:** Create `shell/sources/distortions.py`, `tests/sources/test_distortions.py`.

- [ ] **Step 1: Tests** with a saved snippet of the page (fixture string, not the whole page): constants parsed;
  `rotation.json` written; unchanged second refresh → `changed: []`; changed order → `changed`; page without the
  constants or with ≠ 7 names → error, cache kept; download error → `stale` from cache; no cache + error → error.
- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** `uv run pytest -q` PASS (`--no-sync` while the MCP
  server runs).
- [ ] **Step 5:** `git mv` S-020 to `doing/`, rename it "Live rotations: Distortions" with criteria (rotation as a
  source, "what's Distorted" tool, times in the TODO); add the Eververse criterion to S-019; commit
  "Distortions source".

### Task 2: Engine and tool

**Files:** Create `shell/engines/distortions.py`, `shell/mcp/tools/distortions.py`, `tests/engines/test_distortions.py`,
`tests/mcp/test_distortions_tool.py`.

- `distortions(hours=24, destination=None)` → `{"now": "Europa until 22:00 (UTC+01:00)", "schedule": ["21:00–22:00
  Europa", …], "next": [...] when destination, "source", "fetched", "warnings"}`; `hours` 1–168.
- [ ] Tests (anchor, negative offset, local formatting with a fixed tz, alias match, unknown destination error) →
  FAIL → implement → PASS → commit "Distortion schedule tool".

### Task 3: TODO integration

**Files:** Modify `shell/engines/todo/plan.py`, `.claude/skills/todo/SKILL.md` (one line + refresh step);
tests in `tests/engines/todo/test_plan.py`.

- [ ] Tests: an entry with source Europa gets `Distorted: …` in the Markdown; a vendor-only entry does not; no
  cached rotation → warning, no line → FAIL → implement → PASS → commit "Distorted times in the farm TODO".

### Task 4: Live check and close

- [ ] `refresh_references(source="distortions")` live; compare `distortions()` with both tracker pages for the
  current and next hour; run the TODO on the player's profile (writes only `profile/todo/`) and read the Europa
  entry.
- [ ] One fresh review; fix; tests. Tick S-020, move to `done/`; ask before merging.
