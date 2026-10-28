# References and Triage (E4, part 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shell owns dim-agent's reference data (Compendium, Aegis with change tracking, Bungie API docs, DIM wishlists) and its vault triage (armor, weapons, DIM tags CSV) — stories S-011, S-012, S-013 — with the same decisions as dim-agent on the same inventory.

**Architecture:** Port, don't rewrite. dim-agent's stdlib-only packages (`scripts/sheets`, `scripts/compendium`, `scripts/aegis`, `fetch_bungie_api.py`, the wishlist half of `triage_weapons.py`) move under `shell/sources/` with imports, paths and user-visible text changed (English) and logic untouched. A *source* is any module in `shell/sources/` exposing `NAME` and `refresh()`; a registry discovers them the way the MCP server discovers tool modules. Triage logic moves to pure engines over Shell's inventory rows (same shape as destiny-zen exports); tools read the profile, decide, save the result to `profile/triage/`, and apply locks through the existing lock engine.

**Tech Stack:** Python 3.12, stdlib (`urllib`, `html.parser`, `csv`) for the ported sources, `shell.core` (Manifest, paths), `shell.engines` (account, inventory, locations, locking, actions), `mcp` 2.3 via `shell.mcp.tool`.

**Spec:** `docs/specs/2026-10-28-overclocked-shell-design.md`. Behaviour reference (parity, read-only): `D:\Projects\dim-agent\scripts\` (`common.py`, `triage_armor.py`, `triage_weapons.py`, `to_dim_csv.py`, `fetch_*.py`, `sheets/`, `compendium/`, `aegis/`), its tests in `tests/`, and skills `.claude/skills/{armor-triage,weapon-triage,dim-export,compendium,aegis,bungie-api}/`.

## Global Constraints

- Everything written in English: rendered Markdown, report strings, error messages, CSV headers, triage reasons, DIM notes, skills. Translate dim-agent strings faithfully; do not reword rules.
- Compendium entry attribute keys become English: `rôle`→`role`, `énergie`→`energy`, `détail`→`detail`, `activité`→`activity`, `variante`→`variant`, `catalyseur`→`catalyst`, `sous-titre`→`subtitle`, `groupe`→`group`, `infos`→`info`, `ordre`→`order`, `colonne`→`column`, `éléments`→`elements`, `armes`→`weapons`, `2 pièces`/`4 pièces`→`2 pieces`/`4 pieces`; `section`, `stats` unchanged. S-014 ports `build/stats.py` and `build/artifact.py` against these keys.
- Third-party content stays local: everything fetched or rendered lives in `cache/<source>/` (gitignored). Paths: `cache/compendium/`, `cache/aegis/<sheet>/`, `cache/bungie-api/`, `cache/wishlists/`; raw downloads in a `raw/` subfolder as in dim-agent.
- Player data goes to `profile/`: triage results in `profile/triage/` (`armor.json`, `armor.csv`, `weapons.json`, `weapons.csv`, `dim_tags.csv`); Aegis change tracking reads builds from `profile/builds/*.json` (empty until S-017; the diff then lists no builds).
- No core edits: new code only in `shell/sources/`, `shell/engines/`, `shell/outputs/`, `shell/mcp/tools/`, `.claude/skills/`, `tests/`.
- Files written UTF-8 explicitly; CSVs for reading keep dim-agent's format (`;` delimiter, `utf-8-sig`); `dim_tags.csv` keeps DIM's format (`,`, `utf-8`, columns `Id, Hash, Tag, Notes`, note ≤ 1024 chars).
- Atomic writes (`.tmp` + `os.replace`) for every cache and profile file, as `sheets.fetch.cached` already does.
- Tests never hit the network: monkeypatch the HTTP getter as dim-agent's tests do. Live-data tests (`test_live`, `test_aegis_live`) read `cache/.../raw/` and skip when absent.
- Locks: asking for a triage is the go-ahead for its lock / unlock batches (no dry run). Never dismantle.
- Ghost voice and the remaining skills are S-016; this plan ports only the six skills its tools replace, plain English, Shell tools instead of destiny-zen and scripts.

## Rulings in this plan (player can override)

1. **Postmaster.** Decisions stay identical to dim-agent (postmaster armor is "postmaster (ignored)"; postmaster weapons are triaged like the rest). `apply_triage` skips any item whose location is the postmaster (`result: "postmaster (skipped)"`), since the game cannot lock postmaster items. This settles the open ruling from E2.
2. **DIM note prefix** becomes `shell: ` (was `dim-agent: `).
3. **Skills per plan.** Each E4 plan ports the skills of its features in plain English; S-016 then adds the shared Ghost voice and ports whatever is left.
4. **Wishlist download gets validation** (must contain a `dimwishlist:` line) and an atomic write through `cached()`, which dim-agent's `urlretrieve` lacked. Decisions are unaffected.

## Review Focus

1. **A fetch fails or returns an error page** (Google login page, GitHub 404 HTML) → the previous cache and rendered files stay, the report marks the source / tab `stale` or failed, nothing good is overwritten. (Tasks 1–4)
2. **Shell rows differ subtly from destiny-zen's export** (plug names, location strings, `frame`, `tunedStat`) → the parity run in Task 8 compares decisions item by item against dim-agent's own scripts; every mismatch is explained or fixed before S-012 / S-013 close. (Task 8)
3. **The saved triage is stale when applied** (item dismantled, moved, already locked by hand) → per-item `not found` / `already locked` / `postmaster (skipped)`, counts match, the batch continues. (Task 7)
4. **Wishlist perk given as a hash Shell's defs do not know** or a weapon listed under another hash (reissue, Adept) → falls back to the raw value / the name match exactly as dim-agent. (Task 6)
5. **The player imports `dim_tags.csv` over existing DIM notes and tags** → the tool result and the skill say, before the import, that DIM replaces notes and tags. (Task 7)

---

### Task 1: Source registry, sheets layer and the wishlist source

**Files:**
- Create: `shell/sources/__init__.py`, `shell/sources/web.py`, `shell/sources/sheets/{__init__,errors,fetch,grid}.py`, `shell/sources/wishlists.py`
- Test: `tests/sources/__init__.py`, `tests/sources/conftest.py`, `tests/sources/test_registry.py`, `tests/sources/test_grid.py`, `tests/sources/test_sheets_fetch.py`, `tests/sources/test_wishlists.py`

**Interfaces:**
- Produces:
  - Source contract (module docstring of `shell/sources/__init__.py`): a module or package directly under `shell/sources/` with `NAME: str` and `refresh(force: bool = False, only: list[str] | None = None) -> dict` returning `{"source": NAME, "ok": bool, "changed": list[str], "stale": list[str], "errors": list[str], "folder": str}` (`changed`: output files whose content changed or appeared, or Aegis diff lines; `only`: tab names where the source has tabs, else ignored).
  - `sources() -> dict[str, ModuleType]` — `pkgutil.iter_modules` over the package, imports each, keeps modules with `NAME` and `refresh`, keyed by `NAME`.
  - `web.get(url: str, tries: int = 4) -> bytes` — dim-agent `common._get` (User-Agent `overclocked-shell`, backoff 1/2/4 s, 60 s timeout).
  - `sheets.fetch`: `cached(url, path, refresh, validate=None) -> tuple[str, bool]`, `parse_tab_list`, `file_date`, `SheetSource` — verbatim port using `web.get`; `sheets.grid`, `sheets.errors` verbatim.
  - `write_if_changed(path: Path, text: str) -> bool` in `shell/sources/__init__.py` (atomic; True when new or different) — used by every source to fill `changed`.
  - `wishlists`: `NAME = "wishlists"`, `DEFAULT_WISHLIST` (dim-agent value), `folder() -> Path` (`cache_dir()/"wishlists"`), `fetch(source: str = DEFAULT_WISHLIST, force: bool = False) -> Path` (local path returned as is; URL cached under the sanitised basename via `cached(validate=lambda t: "dimwishlist:" in t)`), `load(path, plug_names) -> (rolls, notes, names)`, `norm_perk`, `norm_weapon` — logic verbatim from `triage_weapons.py`; `refresh()` fetches the default wishlist.

- [ ] **Step 1: Write the failing tests** — port `test_grid.py` and `test_sheets_fetch.py` (patch `shell.sources.web.get`), the `sheet_html` / `sheet` fixtures into `tests/sources/conftest.py` (drop `isolated_todo_dir`), translate asserted messages. New: `test_registry_finds_wishlists` (`"wishlists" in sources()` and every value has `refresh`), `test_load_matches_dim_rules` (a 3-weapon wishlist text: `//notes:... Tier: S. Rank: 2` → `notes[h] == "S #2"`; perk hashes mapped through `plug_names`, `Enhanced X` == `X`), `test_refresh_keeps_cache_on_invalid_download` (getter returns `b"<html>"` → previous wishlist file untouched, `wishlists.refresh()["stale"]` names it).
- [ ] **Step 2: Run** `uv run pytest tests/sources -q` — FAIL (no module).
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — PASS.
- [ ] **Step 5: Commit** `git commit -m "Source registry, sheets layer and wishlist source"`; move S-011 to `stories/doing/`.

### Task 2: Compendium source

**Files:**
- Create: `shell/sources/compendium/{__init__,fetch,model,render}.py`, `shell/sources/compendium/parsers/*.py` (all 11 modules)
- Test: `tests/sources/test_parsers.py`, `test_render.py`, `test_compendium_refresh.py` (from dim-agent `test_cli.py` + `test_fetch.py`), `test_live.py`

**Interfaces:**
- Consumes: `sheets.fetch.SheetSource`, `sheets.grid`, `write_if_changed`.
- Produces: `compendium.NAME = "compendium"`, `compendium.refresh(force, only)` — the body of `fetch_compendium.main` minus argparse/prints: per-tab isolation, unhandled-tab and stale reporting go into `errors` / `stale`, rendered files into `cache/compendium/<slug>.md` + `index.md`. `compendium.fetch` keeps `SHEET`, `TABS` lookup and uses `SheetSource(SHEET, folder/"raw")` instead of its module-level copies. Parsers and `Entry` / `TabResult` unchanged except the English attr keys (Global Constraints). `render.read_meta` parses the English header it now writes.

- [ ] **Step 1: Port the tests** with English strings and keys; `test_compendium_refresh` covers dim-agent `test_cli.py` cases as report assertions (tab failure keeps the old `.md` and lands in `errors`; unknown sheet tab listed; `only=["Exotic Armors"]` renders one tab; second identical run → `changed == []`).
- [ ] **Step 2: Run** `uv run pytest tests/sources -q` — FAIL.
- [ ] **Step 3: Implement** (copy, then rename imports / paths / strings).
- [ ] **Step 4: Run** `uv run pytest -q` — PASS.
- [ ] **Step 5: Commit** `git commit -m "Compendium source"`

### Task 3: Aegis source with change tracking

**Files:**
- Create: `shell/sources/aegis/{__init__,config,names,model,table,render,diff,lookup}.py`
- Test: `tests/sources/test_aegis_{config,table,render,diff,lookup,refresh,live}.py` (`refresh` from dim-agent `test_aegis_cli.py`)

**Interfaces:**
- Produces: `aegis.NAME = "aegis"`, `aegis.refresh(force, only, sheet: str | None = None)` — body of `fetch_aegis.main`; `changed` = the diff lines (`"<build slug>: <tab> — <name>: <describe>"`, plus unconcerned changes as `"<tab> — <name>: <describe>"`), `changes.md` rewritten each run as today; builds read from `profile_dir()/"builds"`. `aegis.lookup` (`load_tab`, `rows`, `find`, `weapon_rows`, `tier_key`, `tier_label`, `best`, `perk_names`, `TIERS`, `PERK_COLUMNS`) with `DATA` resolved lazily to `cache_dir()/"aegis"` (tests monkeypatch it, as dim-agent's autouse fixture does); `aegis.names`, `aegis.config` verbatim — S-014 / S-015 import them.

- [ ] **Step 1: Port the tests** (English strings; `isolated_aegis_dir` autouse fixture and `write_aegis` helper in `tests/sources/conftest.py`). Add `test_refresh_names_concerned_build` (a `profile/builds/x.json` with `intent.exotic.name` = a changed row's name → line starts `x:`).
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — PASS.
- [ ] **Step 5: Commit** `git commit -m "Aegis source with change tracking against builds"`

### Task 4: Bungie API docs source and the references tool

**Files:**
- Create: `shell/sources/bungie_api.py`, `shell/mcp/tools/references.py`, `.claude/skills/{compendium,aegis,bungie-api}/SKILL.md`
- Test: `tests/sources/test_bungie_api.py`, `tests/mcp/test_references_tool.py`

**Interfaces:**
- Produces:
  - `bungie_api.NAME = "bungie-api"`, `build(spec, today) -> dict[str, str]` (verbatim, English), `refresh(force, only)` writing `cache/bungie-api/`, deleting stale `*.md` as today.
  - Tool `refresh_references(source: str | None = None, force: bool = False, tabs: list[str] | None = None) -> dict` → `{"reports": [report, ...]}`; unknown source → `ToolError` listing `sources()` names. Description says what each source holds and where its Markdown lives, so Claude can Grep / Read it.
  - Skills: English ports of dim-agent's `compendium`, `aegis`, `bungie-api` skills, pointing at `cache/<source>/` and `refresh_references` instead of `python scripts/fetch_*.py`.

- [ ] **Step 1: Write the failing tests** — port `test_bungie_api.py`; `test_refresh_references_runs_named_source` (fake source module registered via monkeypatched `sources()`), `test_unknown_source_lists_known`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — PASS. Live: `refresh_references()` for all four sources; compare file lists with `D:\Projects\dim-agent\data\{compendium,aegis,bungie-api}` (same files, same row / entry counts; text differs only by translation); `test_live` / `test_aegis_live` now run against `cache/` and pass.
- [ ] **Step 5: Commit** `git commit -m "Bungie API docs source and refresh_references tool"`; move S-011 to `done/`, tick its criteria.

### Task 5: Armor triage engine

**Files:**
- Create: `shell/engines/armor_triage.py`
- Test: `tests/engines/test_armor_triage.py`

**Interfaces:**
- Consumes: `Manifest.table(name, keep=False)`; armor rows from `shell.engines.inventory.armor_rows`.
- Produces:
  - `armor_sets(manifest) -> dict[int, dict]` — `load_armor_sets` from dim-agent `common.py`, bonus text `"2 pieces: <perk>"`.
  - `triage_armor(rows: list[dict], sets: dict[int, dict]) -> list[dict]` — returns the rows (copies) enriched exactly as `triage_armor.main` does (`base`, `tuned`, `mw`, `mwTotal`, `archetype`, `profile`, `tertiary`, `spirits`, `set`, `setBonus`, `decision` `"KEEP"|"JUNK"`, `reason`), same three passes and same `rank` / `dominates` / tuning rule. Reasons in English: `"best copy {label} — MW {stats} = {total}"`, `"same stats but different tuning +{stat}"`, `"beaten by {name} T{tier} — MW {a} = {x} vs {b} = {y}"`, `"legacy (pre-Armor 3.0)"`, `"postmaster (ignored)"`; label `"{set or name} tertiary {stat}"`.
  - `lock_plan(rows: list[dict]) -> tuple[list[str], list[str]]` — `(lock, unlock)`: KEEP not locked and not postmaster; JUNK locked. Shared with weapons.

- [ ] **Step 1: Write the failing tests** — `test_legacy_always_junk`, `test_mods_removed_before_projection` (`General Armor Mod: Minor Health Mod` and `+Class / -Melee` restore base; MW projection keeps top 3, others 5), `test_dominated_copy_junk_with_reason`, `test_different_tuning_kept_same_tier_only`, `test_legendary_grouped_by_set_archetype_tertiary` (two pieces differing only by set both kept), `test_exotic_grouped_by_spirits`, `test_postmaster_kept_and_not_in_lock_plan`, `test_armor_sets_bonus_text` (two-table fake manifest).
- [ ] **Step 2: Run** `uv run pytest tests/engines/test_armor_triage.py -q` — FAIL.
- [ ] **Step 3: Implement** — a faithful port; keep dim-agent's comments translated.
- [ ] **Step 4: Run** `uv run pytest -q` — PASS.
- [ ] **Step 5: Commit** `git commit -m "Armor triage engine"`; move S-012 to `doing/`.

### Task 6: Weapon triage engine

**Files:**
- Create: `shell/engines/weapon_triage.py`
- Test: `tests/engines/test_weapon_triage.py`

**Interfaces:**
- Consumes: `wishlists.load`, `norm_perk`, `norm_weapon`; `ctx.defs["plugs"]` for `plug_names`; weapon rows from `inventory.weapon_rows`; `armor_triage.lock_plan`.
- Produces: `triage_weapons(rows: list[dict], rolls: dict, notes: dict, names: dict) -> list[dict]` — the matching, grouping and decision logic of `triage_weapons.main` unchanged (`traits`, `roll`, `enhanced`, `listed`, `grade`, `wish`, `decision`, `reason`). Reasons: `"exotic (best copy)"`, `"duplicate exotic"`, `"crafted (pattern)"`, `"duplicate god roll (same traits, worse tier/enhanced)"`, `"wishlist {grade}"`, `"weapon not on the wishlist"`, `"roll not on the wishlist"`.

- [ ] **Step 1: Write the failing tests** — `test_roll_matches_when_all_line_perks_present`, `test_enhanced_compared_by_name`, `test_name_fallback_for_reissue_hash`, `test_one_copy_per_trait_combo`, `test_crafted_always_kept`, `test_exotic_one_copy_per_full_roll_including_frame`, `test_unlisted_weapon_junk_even_if_locked`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — PASS.
- [ ] **Step 5: Commit** `git commit -m "Weapon triage engine"`; move S-013 to `doing/`.

### Task 7: Triage tools, CSV outputs, DIM export and skills

**Files:**
- Create: `shell/outputs/__init__.py`, `shell/outputs/triage_csv.py`, `shell/outputs/dim_csv.py`, `shell/mcp/tools/triage.py`, `.claude/skills/{armor-triage,weapon-triage,dim-export}/SKILL.md`
- Test: `tests/outputs/test_triage_csv.py`, `tests/outputs/test_dim_csv.py`, `tests/mcp/test_triage_tools.py`

**Interfaces:**
- Consumes: `get_profile`, `primary_membership`, `armor_rows`, `weapon_rows`, `COMPONENTS` from `shell.mcp.tools.inventory`; `read_locations`, `LOCATION_COMPONENTS`; `locking.set_lock` with `Actions` built as in `shell/mcp/tools/locking.py`.
- Produces:
  - `triage_csv.write(path: Path, kind: "armor"|"weapons", rows: list[dict]) -> None` — dim-agent CSV columns, English headers (`Decision; Class; Slot; Name; Rarity; Tier; Set; Set bonus; Archetype; Profile; Total; MW stats (W/H/C/G/S/M); MW total; Locked; Location; Reason; Id; Hash` and `Decision; Name; Type; Rarity; Tier; Crafted; Wishlist grade; Traits; Locked; Location; Reason; Id; Hash`), same sort, `yes` / empty for booleans.
  - `dim_csv.rows(triaged: list[dict], notes: bool = True) -> list[dict]`, `dim_csv.write(path, rows)` — `to_dim_csv.note_for` logic with prefix `shell: `, KEEP→`keep`, JUNK→`junk`.
  - Tools (each saves `profile/triage/<kind>.json` = `{"made": ISO time, "lock": [...], "unlock": [...], "items": [triaged rows]}` and `<kind>.csv`):
    - `triage_armor() -> dict` — fresh profile read; `{"keep", "junk", "to_lock", "to_unlock", "junk_by_reason", "keep_by_class", "junk_by_class", "review": [non-legacy JUNK that is locked now: {itemId, name, reason}] (≤ 100, `review_total`), "no_set": [names], "saved_to"}`.
    - `triage_weapons(wishlist: str | None = None, refresh_wishlist: bool = False) -> dict` — same header, `review` = JUNK locked now.
    - `apply_triage(kind: str) -> dict` — loads the saved plan, one location read, `set_lock` for `lock` then `unlock` with `dry_run=False`, items whose location is postmaster skipped (ruling 1); returns `{"locked", "unlocked", "skipped", "failed": [{itemId, name, result}]}`. No saved plan → `ToolError` "Run triage_<kind> first."
    - `export_dim_tags(notes: bool = True) -> dict` — from whichever saved triages exist → `profile/triage/dim_tags.csv`; `{"rows", "keep", "junk", "saved_to", "warning": "DIM replaces the tag and note of every imported item; an empty note erases it."}`; none saved → `ToolError`.
  - Skills: English ports of `armor-triage`, `weapon-triage`, `dim-export` (auth_status → triage tool → review → `apply_triage` → summary; rules section translated; the T5 tuning limitation dropped if Task 8 shows Shell reads `tunedStat` with an empty tuning socket, else kept).

- [ ] **Step 1: Write the failing tests** — `test_triage_csv_headers_and_sort`, `test_dim_note_prefix_set_and_grade` (grade not repeated when already in the reason), `test_triage_armor_saves_plan_and_summarises` (monkeypatched profile read + fixture rows), `test_apply_triage_skips_postmaster_and_reports_failures` (FakeActions, one 1623 error), `test_apply_without_saved_plan_errors`, `test_export_dim_tags_warns`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — PASS.
- [ ] **Step 5: Commit** `git commit -m "Triage tools, triage and DIM CSV outputs"`

### Task 8: Parity check and live apply

**Files:**
- Create: scratch only (`<scratchpad>/parity.py`), nothing committed but fixes and story moves.

- [ ] **Step 1: Snapshot.** `refresh_inventory`, then run Shell's engines offline on `profile/inventory/armor.json` / `weapons.json` (sets from the manifest, plugs from `cache/defs`).
- [ ] **Step 2: Run dim-agent on the same files.** `python D:\Projects\dim-agent\scripts\triage_armor.py <armor.json>`; for weapons, a temp `DESTINY_ZEN_HOME` holding Shell's defs as `defs-shell.json`, then `triage_weapons.py --export <weapons.json>` (default wishlist, the cached copy dim-agent already has). dim-agent writes only to its `out/`.
- [ ] **Step 3: Compare** decisions by `Id`: expected 0 mismatches; reasons equal modulo translation. Any mismatch → systematic-debugging, fix in the engine or rows, add a test, rerun.
- [ ] **Step 4: Live apply (player watching).** `triage_armor` → show summary → `apply_triage("armor")`; same for weapons; `export_dim_tags`; player spot-checks in DIM.
- [ ] **Step 5: Commit** fixes if any; move S-012 and S-013 to `done/` with criteria ticked; `git commit -m "Mark reference and triage stories done"`.

Then: one fresh whole-branch review (opus) and one fix pass; ask the player before the fast-forward merge into `main`.
