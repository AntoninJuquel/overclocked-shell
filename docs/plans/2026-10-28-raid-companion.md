# Raid companion (E10) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (the player's usual flow) to implement
> this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On demand, the Ghost shows a Deep Stone Crypt encounter on the player's second monitor — schematic map
first with the guides' callout names and the player's spot highlighted, then their role's steps for the phase —
built from three community guides cached locally (story S-024).

**Architecture:** A `guides` source caches each guide as Markdown plus its in-article images. The Ghost (skill)
reads them and writes one structured encounter file per encounter in `profile/raids/`; an engine validates it and
applies the player's callout renames; two outputs draw the SVG map and the self-reloading HTML page; one tool
module exposes check / show / rename. No core edits, no new dependency.

**Tech Stack:** Python 3.12 stdlib (`html.parser`, `json`, `urllib.parse`), `shell.sources.web.get`,
`shell.sources.write_if_changed` / `report`, `mcp` via `shell.mcp.tool`.

**Spec:** `docs/specs/2026-10-28-raid-companion-design.md`.

## Global Constraints

- No new dependency; Windows primary, macOS / Linux must work; the page is plain HTML + inline SVG opened as a local
  file.
- Guide text and images live in gitignored `cache/guides/`; encounter files and renames in gitignored
  `profile/raids/`; nothing is published.
- **Positions only from a guide's text or images**; a spot without one is listed beside the map, never drawn.
- **Callout names = the guides' labels**; the player's renames replace them on display only.
- Guide precedence when they disagree: steps and roles from the freshest guide (Grindout), numbered callouts from
  Shacknews where the freshest does not number, Overgear to fill gaps; every disagreement recorded and shown.
- English for files and skill; game names in English.
- Tests: `uv run --no-sync pytest -q` while the MCP server runs (memory: uv sync locked by the server).

## Decided here (the spec left them to the builder)

1. **Guides config** (in `shell/sources/guides/__init__.py`):
   `GUIDES = {"deep-stone-crypt": {"grindout": "https://grindout.com/destiny-2/guides/deep-stone-crypt",
   "shacknews": "https://www.shacknews.com/article/121651/deep-stone-crypt-raid-guide-destiny-2",
   "overgear": "https://overgear.com/guides/destiny2/deep-stone-crypt-raid-guide/"}}` and
   `ENCOUNTERS = {"deep-stone-crypt": ["desolation", "crypt-security", "atraks-1", "descent", "taniks-reborn",
   "taniks-abomination"]}`.
2. **Per-site extraction** (checked on the live pages 2026-10-28):
   - `grindout`: the article HTML is `props.guide.description` in the JSON of `<script data-page="app">`; date
     `props.guide.updated_at` ("20 Jul 2026").
   - `shacknews`: the element `<article id="detail-view">`; date JSON-LD `"dateModified"`.
   - `overgear`: the element `<div class="entry-content"…>`; date `<meta property="article:modified_time">`, else
     JSON-LD `"dateModified"`.
   Dates normalized to `YYYY-MM-DD`.
3. **Markdown shape:** `# <title>` then headings (`##`/`###`), paragraphs, `- ` list items, and images as
   `![<alt or following figcaption>](<guide>/img-NN.<ext>)` at their place; script, style, nav, aside, form,
   iframe and svg dropped. Images whose `width` or `height` attribute is below 64 are icons: skipped. A failed image
   download keeps `![<alt> (image unavailable)]()`.
4. **Cache layout:** `cache/guides/<raid>/<guide>.md` (first line `<!-- source: URL · updated: YYYY-MM-DD ·
   fetched: … -->`), `cache/guides/<raid>/<guide>/img-NN.<ext>`, `cache/guides/<raid>/index.md` (guide, url,
   updated, fetched, image count).
5. **Encounter file** `profile/raids/<raid>/<encounter>.json`, map grid 0–100 per floor:
   ```
   {"raid", "encounter", "name",
    "sources": [{"guide", "updated"}],
    "floors": [{"id", "name", "rooms": [{"id", "name", "x", "y", "w", "h"}]}],
    "spots": [{"id", "name", "kind", "floor", "room"?, "pos": [x, y] | null, "pos_source": str | null,
               "sources": [guide]}],
    "roles": [{"id", "name", "count"}],
    "phases": [{"id", "name", "summary", "steps": {role_id: [str]}, "spots": [spot_id], "sources": [guide]}],
    "conflicts": [str], "gaps": [str]}
   ```
   `kind` is one of `plate`, `panel`, `terminal`, `bucket`, `zone`, `spawn`, `door`, `other`.
6. **Renames:** `profile/raids/<raid>/callouts.json` = `{spot_id: name}`.
7. **Page:** `profile/raids/live.html`, `<meta http-equiv="refresh" content="3">`; the player opens it once in a
   browser on the second monitor. Stateless tools: the skill passes role and phase each call.

## Review Focus

1. A guide page changes shape (container or JSON missing) → that guide reports an error and keeps its previous
   cache; the other guides still refresh.
2. An image fails to download (404, timeout) → Markdown keeps the alt text marked unavailable; refresh does not fail.
3. A spot with a position but no `pos_source` → `raid_check` fails (anti-goal: invented positions).
4. A rename for a spot id the rebuilt encounter no longer has → ignored with a warning, never a crash.
5. `raid_show` with an unknown role → error listing the roles; no phase → the first phase.

---

### Task 1: Guide extraction

**Files:** Create `shell/sources/guides/__init__.py` (config only in this task), `shell/sources/guides/extract.py`,
`shell/sources/guides/sites.py`; Test: `tests/sources/test_guides_extract.py`.

**Interfaces — Produces:**
- `sites.article(site: str, html: str) -> tuple[str, str | None]` — (article HTML, date `YYYY-MM-DD` or None);
  `ValueError("<site>: article not found")` when the container / JSON is missing.
- `extract.to_markdown(article_html: str, base_url: str) -> tuple[str, list[tuple[str, str]]]` — (Markdown with
  image placeholders `{{img:N}}`, [(absolute image URL, alt text)] in order).

- [ ] **Step 1: Tests** with small fixture strings shaped like each site (copy the real wrappers from decision 2):
  `test_grindout_json_article_and_date` (date "20 Jul 2026" → "2026-07-20"), `test_shacknews_article_and_date`,
  `test_overgear_article_and_modified_meta`, `test_missing_container_raises`,
  `test_markdown_headings_lists_paragraphs`, `test_scripts_nav_and_icons_dropped` (img width="24" skipped),
  `test_images_in_order_with_alt_or_figcaption_and_absolute_urls` (relative `/storage/x.jpg` joined to the page URL).
- [ ] **Step 2:** `uv run --no-sync pytest tests/sources/test_guides_extract.py -q` — FAIL.
- [ ] **Step 3: Implement** with `html.parser.HTMLParser` (one parser class collecting blocks; `html.unescape`
  is automatic with `convert_charrefs`).
- [ ] **Step 4:** `uv run --no-sync pytest -q` — PASS.
- [ ] **Step 5:** `git mv` S-024 to `doing/`; commit "Guide extraction for raid guides".

### Task 2: Guides source (fetch, images, cache, changes)

**Files:** Modify `shell/sources/guides/__init__.py`; Modify `shell/mcp/tools/references.py` (docstring line for
`guides`); Test: `tests/sources/test_guides_source.py`.

**Interfaces:**
- Consumes: Task 1.
- Produces: `NAME = "guides"`; `refresh(force=False, only=None) -> dict` (sources contract; `only` = raid slugs);
  `folder() -> Path` (`cache/guides`); `guide_path(raid, guide) -> Path`.

Behaviour: without `force` and with a cached `.md`, the guide is not downloaded. Per guide: page → `sites.article` →
`to_markdown` → download each image with `web.get` (best-effort: a failure gives the unavailable placeholder and
is not an error) → write `.md` with `write_if_changed`; `changed` lists `<raid>/<guide>.md` when its
text changed. Page download error with a cache → `stale`; `ValueError` from `sites.article` → `errors`, cache kept.
`index.md` rewritten each refresh.

- [ ] **Step 1: Tests** (monkeypatch `web.get` with a dict of URL → bytes or exception):
  `test_refresh_writes_markdown_images_and_index`, `test_cached_guide_not_downloaded_without_force`,
  `test_changed_only_when_text_changes`, `test_reshaped_page_errors_and_keeps_cache` (Review Focus 1),
  `test_image_failure_keeps_alt_unavailable` (Review Focus 2), `test_page_error_with_cache_is_stale`,
  `test_registered_source`.
- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** PASS.
- [ ] **Step 5:** commit "Guides source: raid guides cached as Markdown with their images".

### Task 3: Encounter engine (validate, names)

**Files:** Create `shell/engines/raids.py`; Test: `tests/engines/test_raids.py`.

**Interfaces — Produces:**
- `folder(raid: str) -> Path` (`profile/raids/<raid>`), `load(raid, encounter) -> dict` (FileNotFoundError /
  ValueError with a one-line message).
- `check(enc: dict, guides: set[str]) -> list[str]` — problems; empty = valid. Rules: required keys; ids unique per
  kind; role counts sum to 6; every `steps` key is a role id; every phase spot and spot floor / room exists;
  `pos` within 0–100 **requires** `pos_source` (Review Focus 3); every spot and phase cites ≥1 source, each in
  `guides`; `sources[].guide` in `guides`.
- `names(enc, renames: dict) -> tuple[dict[str, str], list[str]]` — spot id → display name (rename or guide name),
  warnings for renames whose id is gone (Review Focus 4).
- `load_renames(raid) -> dict`, `save_rename(raid, spot_id, name: str | None) -> dict` (None removes).

- [ ] **Step 1: Tests:** a valid fixture encounter (Crypt Security-shaped, two floors) passes; one test per rule
  above with the exact problem text asserted (e.g. `"spot panel-l3: position without pos_source"`,
  `"roles: counts sum to 5, not 6"`); `test_names_apply_renames_and_warn_on_missing_ids`; rename save / remove
  round trip.
- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** PASS. **Step 5:** commit "Raid encounter files: check and
  callout renames".

### Task 4: Map and live page outputs

**Files:** Create `shell/outputs/raid_map.py`, `shell/outputs/raid_page.py`; Test: `tests/outputs/test_raid_page.py`.

**Interfaces:**
- Consumes: Task 3 `names`.
- Produces: `raid_map.svg(enc: dict, floor_id: str, names: dict, highlight: set[str]) -> str` — rooms as labelled
  rectangles, placed spots as markers with their display names, highlighted spots in the accent colour, the text
  "Schematic — positions from the guides" in a corner.
  `raid_page.render(enc, names, role_id: str, phase_id: str) -> str` — full HTML: meta refresh 3, title
  `<encounter> — <phase> — <role>`, one SVG per floor that has a spot of the phase (else every floor), "Not on the
  map" list (phase spots without `pos`), the role's steps as an ordered list, the full role split as a small table,
  conflicts and gaps, sources with dates. `raid_page.write(path, html)`.
- All text HTML-escaped (`html.escape`); colours as CSS variables with a dark default (second monitor in a dim room).

- [ ] **Step 1: Tests:** `test_svg_draws_placed_spots_only_and_labels_names`, `test_svg_highlights`,
  `test_page_has_refresh_steps_role_table_unplaced_conflicts_sources`, `test_page_escapes_text`
  (a step `"<b>x</b>"` appears escaped).
- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** PASS. **Step 5:** commit "Raid map and live page".

### Task 5: Tools

**Files:** Create `shell/mcp/tools/raids.py`; Test: `tests/mcp/test_raid_tools.py`.

**Interfaces — Produces:**
- `raid_check(raid: str, encounter: str) -> dict` — `{"ok", "problems", "file"}`; guides = files in
  `cache/guides/<raid>/`.
- `raid_show(raid: str, encounter: str, role: str, phase: str | None = None) -> dict` — writes
  `profile/raids/live.html`; returns `{"page", "encounter", "phase", "role", "steps", "spots", "not_on_map",
  "conflicts", "gaps", "warnings", "phases", "roles"}`; unknown role / phase → ToolError listing the valid ones
  (Review Focus 5); invalid file → ToolError with the first problems.
- `raid_rename(raid: str, spot_id: str, name: str | None) -> dict` — `{"renames"}`; unknown spot id in every
  encounter of the raid → ToolError.
- Role and phase match by id or case-insensitive name.

- [ ] **Step 1: Tests** for each tool, errors included. **Step 2:** FAIL. **Step 3:** implement. **Step 4:** PASS.
- [ ] **Step 5:** commit "raid_check, raid_show and raid_rename tools".

### Task 6: Skill

**Files:** Create `.claude/skills/raid-companion/SKILL.md` (Ghost voice link; `tests/test_skills.py`).

Playbook:
1. **Guides:** `refresh_references(source="guides")` if `cache/guides/<raid>/index.md` is missing or older than
   30 days.
2. **Build an encounter file** when missing or asked: read that encounter's section in each guide's Markdown;
   look at its images with the Read tool when placing spots; apply the precedence rule; record every disagreement
   in `conflicts` and what no guide covers in `gaps`; a spot is placed only from a guide's text or image
   (`pos_source` says which: "shacknews image 4", "grindout text"), otherwise `pos: null`; callout names are the
   guides' labels. Write the file, then `raid_check` until ok. Tell the player what is unplaced and what conflicts.
3. **Show:** `raid_show(raid, encounter, role, phase)`; first time, ask the player to open `profile/raids/live.html`
   on their second monitor (it reloads itself). Answer in chat with the steps, short; mention conflicts that touch
   their role.
4. **Follow the raid:** "next phase", "I'm on adds now" → `raid_show` again with the new phase / role.
5. **Renames:** "we call it left 2" → `raid_rename`.
6. Never invent a mechanic, position or callout; say "not in the guides" instead.

- [ ] Write → `uv run --no-sync pytest tests/test_skills.py -q` → commit "raid-companion skill".

### Task 7: Deep Stone Crypt, live

- [ ] `refresh_references(source="guides")` live; read `cache/guides/deep-stone-crypt/index.md` (3 guides, dates,
  image counts).
- [ ] Build the six DSC encounter files following the skill (this is the skill's own test); `raid_check` ok for each.
- [ ] `raid_show("deep-stone-crypt", "crypt-security", "scanner")`; look at the page in the browser pane; the player
  opens it on their second monitor and judges it.
- [ ] One fresh review of the branch; fix; tests. Tick S-024, move to `done/`; ask before merging.
