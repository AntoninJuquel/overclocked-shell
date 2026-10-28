# Ghost Voice and Cutover (E4, part 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every skill speaks with one Ghost voice (French when the player writes French), the player's latest dim-agent builds and TODO data move into `profile/`, a fresh clone gets examples, and destiny-zen is retired — stories S-016 and S-017, closing E4.

**Architecture:** One voice guide, `.claude/ghost-voice.md`, linked from every skill and from `CLAUDE.md`; a test keeps every skill linked to it. The import is an engine (`shell/engines/dim_import.py`) behind a CLI subcommand, since it runs once per machine: sheets go through `sheet.load` / `sheet.save` (migration + English `.md`), TODO files are copied, `state.json` is merged. `examples/` holds a sample sheet and empty TODO templates.

**Tech Stack:** Python 3.12, `shell.engines.builds.sheet`, `shell.engines.todo.state`, argparse in `shell/cli.py`.

**Spec:** `docs/specs/2026-10-28-overclocked-shell-design.md` (Goals 4–5, Decisions: single cutover, English with French answers).

## Global Constraints

- All ten dim-agent skills are already ported (aegis, armor-triage, bungie-api, compendium, create-build, dim-export, equip-build, optimize-build, todo, weapon-triage); S-016 adds the voice, not new skills.
- The voice never changes a skill's safety rules (dry run first, the player's explicit yes, never dismantle, never `force`).
- Item, perk, mod and activity names stay in English, as in game, whatever language the Ghost answers in.
- The import never deletes: it overwrites `profile/builds/<slug>.*` with the dim-agent version and keeps sheets that exist only in Shell; dim-agent's folders are read only.
- Unregistering destiny-zen changes the player's user-level Claude Code config: done only with the player's go-ahead, at the end.

## Rulings in this plan (player can override)

1. **Voice guide location:** `.claude/ghost-voice.md`, one line at the top of each skill ("Voice: …") and a pointer in `CLAUDE.md`, rather than copying the guide into every skill.
2. **Import as a CLI command** (`uv run shell import dim-agent <path>`), not an MCP tool: it runs once.
3. **`state.json` merge:** union of ids; for an id in both, the entry with the later `since` wins, ties go to dim-agent. Keeps the status set live in Shell (aegis/exodus-down ignored) and everything dim-agent changed since.
4. **History:** dim-agent's dated TODOs (`todo/<date>.{json,md}`, French) are copied to `profile/todo/history/` untouched; `needs.json`, `sources.json`, `overrides.json` replace Shell's (needs are recomputed by the next `farm_needs` anyway).
5. **Example sheet:** the player's Getaway Buddy intent (no `resolved`), renamed "Example — Warlock Prismatic grenades"; templates `examples/todo/sources.json` = `{}` and `overrides.json` = `{"activities": [], "notes": []}`.

## Review Focus

1. **A dim-agent sheet that no longer validates** → copied as is with a warning naming it; the import continues. (Task 2)
2. **Running the import twice** → same result, no duplicated history, no status lost. (Task 2)
3. **A Shell-only sheet** (created after the copy) → kept. (Task 2)
4. **A skill added later without the voice line** → the test fails. (Task 1)
5. **A wrong path** (not a dim-agent folder) → one-line error, nothing written. (Task 2)

---

### Task 1: Ghost voice

**Files:**
- Create: `.claude/ghost-voice.md`, `tests/test_skills.py`
- Modify: every `.claude/skills/*/SKILL.md` (one line under the title), `CLAUDE.md` (one line)

- [ ] **Step 1: Write the failing test** — `test_every_skill_links_the_ghost_voice` (each `SKILL.md` contains `ghost-voice.md`), `test_skill_descriptions_are_english` (no accented French in front matter), `test_skills_name_existing_tools` (names called as `` `name(`` exist in `build_server(Context())`).
- [ ] **Step 2: Run** `uv run pytest tests/test_skills.py -q` — FAIL (no voice links).
- [ ] **Step 3: Write the guide** — who the Ghost is (the player's companion who knows their gear, not a script runner), tone (warm, brief, confident, a touch of Ghost humour, never at the player's expense), language (answer in the player's language — French when they write French —, game names in English), what to say (results and choices, not tool names or file paths unless asked; quote sources: Compendium date, Aegis tab), what never changes (safety rules). Add the voice line to every skill and the `CLAUDE.md` pointer.
- [ ] **Step 4: Run** `uv run pytest -q` — PASS.
- [ ] **Step 5: Commit** `git commit -m "Ghost voice shared by every skill"`; S-016 to `done/`.

### Task 2: dim-agent import

**Files:**
- Create: `shell/engines/dim_import.py`, `tests/engines/test_dim_import.py`
- Modify: `shell/cli.py` (subcommand `import dim-agent PATH`)

**Interfaces:**
- Produces: `import_dim_agent(src: Path) -> dict` → `{"builds": [slugs], "invalid": [slugs], "kept": [Shell-only slugs], "todo": [files], "history": n, "state": {"added", "updated", "kept"}}`; `merge_state(ours: dict, theirs: dict) -> tuple[dict, dict]` (merged, counts). `ValueError("not a dim-agent folder: …")` when `src/builds` and `src/todo` are both missing.

- [ ] **Step 1: Write the failing tests** — `test_sheets_migrated_and_rendered_in_english`, `test_invalid_sheet_copied_with_warning`, `test_shell_only_sheet_kept`, `test_state_merge_later_since_wins`, `test_history_copied_once` (run twice → same files), `test_wrong_folder_writes_nothing`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** (atomic writes via `state.write_json`; sheets via `sheet.load` / `sheet.save`, `SheetError` → copy raw + `invalid`).
- [ ] **Step 4: Run** `uv run pytest -q` — PASS.
- [ ] **Step 5: Commit** `git commit -m "Import dim-agent builds and TODO data"`

### Task 3: Examples and README

**Files:**
- Create: `examples/builds/example-warlock-prismatic-grenades.json`, `examples/todo/{sources,overrides}.json`, `examples/README.md`
- Modify: `README.md` (Start, Switching from dim-agent), `tests/test_skills.py` → add `test_example_sheet_validates`

- [ ] **Step 1: Write the failing test** `test_example_sheet_validates` (`sheet.load` on the example).
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Write the examples and README sections** (fresh clone: copy `examples/` into `profile/` or ask for a new build; dim-agent users: `uv run shell import dim-agent <path>`, then remove destiny-zen).
- [ ] **Step 4: Run** `uv run pytest -q` — PASS.
- [ ] **Step 5: Commit** `git commit -m "Examples and switching guide"`

### Task 4: Cutover (player present)

- [ ] **Step 1:** `uv run shell import dim-agent D:\Projects\dim-agent`; show the summary; `check_build` on every sheet; `farm_needs` then `farm_plan` — the TODO still shows Exodus Down as ignored.
- [ ] **Step 2:** With the player's go-ahead: `claude mcp remove destiny-zen -s user`; confirm Shell's tools still load in this project.
- [ ] **Step 3:** Commit; S-017 to `done/` with criteria ticked; E4 complete.

Then: one fresh whole-branch review (opus) and one fix pass; ask the player before the fast-forward merge into `main`.
