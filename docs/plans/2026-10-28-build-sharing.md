# Build sharing (E8) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A saved build sheet becomes (S-021) a printable, sendable **PDF** and (S-022) a **DIM loadout link** a
friend opens in DIM to get the gear, subclass and mods — stories S-021 and S-022.

**Architecture:** Two output modules and one engine module, one tool module, one skill. No core edits.
- `shell/outputs/build_pdf.py` — renders the sheet's existing Markdown view (`build_md.render`) to PDF: headings,
  bullets, paragraphs, the Result table. Reusing the view keeps PDF and `.md` identical in content.
- `shell/engines/share.py` — sheet + inventory snapshot + item definitions → a DIM `Loadout` object (dim-api
  `api/shapes/loadouts.ts`) plus warnings for what could not be resolved.
- `shell/outputs/dim_link.py` — `Loadout` → `https://app.destinyitemmanager.com/loadouts?loadout=<url-encoded JSON>`.
  DIM decodes this form itself (DIM `src/app/loadout/loadout-share/loadout-import.ts`, `decodeUrlLoadout`): no DIM
  API key, no dim.gg short link, nothing leaves the machine until the player shares the link.
- `shell/mcp/tools/share.py` — `build_pdf(slug)` and `build_dim_link(slug)`.
- `.claude/skills/share-build/SKILL.md`.

**Tech Stack:** Python 3.12, **fpdf2** (new dependency, `uv add fpdf2`; pure Python, Unicode TTF fonts, `table()`),
`shell.engines.builds` (sheet, snapshot), `shell.outputs.build_md`, `Manifest.table(..., keep=False)`.

## Global Constraints

- Read-only for the account. Writes only `profile/builds/<slug>.pdf`.
- Sheets keep their own language (the player's sheets have French free text): the PDF prints text as stored.
- A sheet without `resolved` still gets a PDF (intent only) and a link with the subclass and mods only, plus a
  warning; never an error.

## Rulings in this plan (player can override)

1. **PDF = the Markdown view, printed.** No new layout or images (no item icons). Font: the first Unicode TTF
   found among Arial (Windows / macOS) and DejaVu Sans (Linux), regular + bold; none found → Helvetica with
   characters outside Latin-1 replaced (`≥` → `>=`, `×` → `x`, `—` → `-`, `·` → `-`) and a warning.
   `shortcut:` comment — bundle a font if a template user hits it.
2. **The link carries:** `classType`; `equipped` = the resolved armor and weapons as `{id, hash}` (DIM falls back to
   the hash for a friend who does not own that instance) + the subclass item `{hash, socketOverrides}` (super,
   abilities, aspects, fragments by socket index); `parameters.mods` = the resolved armor mods (slot mods, stat
   mods, tunings; hashes may repeat); `parameters.exoticArmorHash`; `parameters.statConstraints` in the intent's
   priority order with `minStat` from its minimums; `notes` = concept, weapons with perks, stats (≤ 1,000 chars).
3. **Not in the link:** weapon perks as socket overrides (a friend's copy has other rolls: they go in `notes`), the
   artifact (`artifactUnlocks` needs the season number: in `notes`), set bonuses (in `notes`), shaders.
4. **Name → hash** from `DestinyInventoryItemDefinition`, read per call like `week_context`. Subclass plugs: among
   plugs of the socket's own `plugCategoryIdentifier` (from its initial plug). Armor mods: among plugs whose
   category starts with `enhancements.` and whose name matches; several matches → the one Bungie still allows
   (`plug.insertionRules` empty and not `itemTypeDisplayName` "Deprecated…"), then highest hash; unresolved names
   → a warning, kept in `notes`.
5. **Stat hashes** are constants (Weapons, Health, Class, Grenade, Super, Melee), checked against
   `DestinyStatDefinition` in the live check.

## Review Focus

1. A sheet without `resolved` → PDF of the intent, link with subclass and mods, warning; no crash.
2. An item of the sheet missing from the snapshot (dismantled) → left out of `equipped`, warning names it.
3. Two fragments of a class with disabled fragment sockets → overrides target the active sockets
   (`idx[element]["fragment_sockets"]`, as `equip_plan` does).
4. A mod name with several definitions → the current one, not a deprecated copy.
5. URL round trip: `json.loads(unquote(query))` equals the Loadout; the link stays under ~8,000 characters for the
   player's sheets (browsers and Discord accept it); longer → `notes` trimmed first, then a warning.
6. PDF with French text, `≥`, `·`, `×`, `—` and a `|` inside a cell renders without an fpdf2 encoding error.

---

### Task 1: PDF output

**Files:** Create `shell/outputs/build_pdf.py`, `tests/outputs/test_build_pdf.py`; `uv add fpdf2`.

- [ ] **Step 1: Tests:** a rendered example sheet (`examples/builds/…json` through `build_md.render`) writes a
  file starting with `%PDF`; text extraction not needed — assert fpdf2 received the headings / table rows (render
  to an in-memory `FPDF` and inspect, or monkeypatch `cell` / `multi_cell`); fallback font path replaces `≥`.
- [ ] **Step 2:** `uv run pytest tests/outputs/test_build_pdf.py -q` — FAIL.
- [ ] **Step 3: Implement** `render(md_text) -> bytes` and `write(path, md_text) -> list[str]` (warnings).
- [ ] **Step 4:** `uv run pytest -q` — PASS.
- [ ] **Step 5:** `git mv` S-021 and S-022 to `doing/`; commit "Build sheet to PDF".

### Task 2: Loadout engine and DIM link output

**Files:** Create `shell/engines/share.py`, `shell/outputs/dim_link.py`, `tests/engines/test_share.py`,
`tests/outputs/test_dim_link.py`.

- [ ] **Step 1: Tests** on a fixture sheet, snapshot rows and a small fake item-definition table: equipped ids and
  hashes, subclass socket overrides (incl. fragment sockets), mods with a deprecated duplicate, exotic hash, stat
  constraints, missing item warning, no `resolved`, notes cap; link round trip and length rule.
- [ ] **Step 2:** FAIL. **Step 3:** implement `loadout(s, armor_items, weapon_items, defs, idx) -> (dict,
  warnings)` and `dim_link.url(loadout) -> str`. **Step 4:** `uv run pytest -q` — PASS.
- [ ] **Step 5:** commit "DIM loadout link from a build sheet".

### Task 3: Tools

**Files:** Create `shell/mcp/tools/share.py`, `tests/mcp/test_share_tools.py`.

- `build_pdf(slug)` → `{"pdf": path, "warnings": [...]}` (regenerates the `.md` view first, like `check_build`).
- `build_dim_link(slug)` → `{"url", "length", "items", "mods", "warnings", "snapshot"}`; needs `refresh_inventory`.
- Errors: unknown slug (lists existing ones), no snapshot, invalid sheet → one-line `ToolError`.

- [ ] Steps: tests → FAIL → implement → PASS → commit "build_pdf and build_dim_link tools".

### Task 4: Skill

**Files:** Create `.claude/skills/share-build/SKILL.md` (Ghost voice; `tests/test_skills.py`).

Playbook: pick the sheet → `check_build` → PDF and / or link → give the file path and the link, say what the link
does not carry (perks are the player's roll, artifact, sets — they are in the notes) → never post it anywhere.

- [ ] Steps: write → `uv run pytest tests/test_skills.py -q` → commit "share-build skill".

### Task 5: Live check and close

- [ ] On the player's sheets (read-only): PDF of `warlock-prismatic-getaway-buddy` opened and checked by eye;
  stat hashes checked against `DestinyStatDefinition`; DIM link decoded back and every hash named; the player
  opens one link in DIM themselves (nothing is applied by opening).
- [ ] One fresh review; fix; `uv run pytest -q`. Tick both stories, move to `done/`; ask before merging.
