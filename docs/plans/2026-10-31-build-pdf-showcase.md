# Build PDF showcase (S-026) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** `build_pdf` produces an A4 landscape PDF laid out like the in-game Character / subclass screens with the
real manifest icons, build text in the middle, overflow on page 2 — story S-026.

**Architecture:** three modules plus wiring, no core edits.
- `shell/engines/build_icons.py` (new): sheet + manifest tables + inventory snapshot → `{key: icon path}` (the
  manifest's relative `/common/destiny2_content/icons/…` paths). Reuses `share.py`'s subclass / mod resolution.
- `shell/sources/icons.py` (new): icon paths → local files in `cache/icons/`, with an index for offline re-exports.
- `shell/outputs/build_pdf.py` (rewritten): sheet + `{key: local Path}` → PDF bytes. Pure, no network.
- `shell/mcp/tools/share.py` `build_pdf` wires them, never failing on icons.

**Tech Stack:** Python 3, fpdf2 2.8.9 (`image`, `elliptic_clip`, `LinearGradient` / `RadialGradient`), httpx.
Pillow is there (fpdf2 dependency) but not needed.

**Spec:** docs/specs/2026-10-31-build-pdf-showcase-design.md (layout approved from the brainstorm mockup
`.superpowers/brainstorm/556-1793447410/content/layout-v3.html`: open it next to your output).

## Global Constraints

- No new dependency, no edit in `shell/core/`.
- Icon key format, shared by every task: `"<kind>:<name>"`, kinds `item` (armor / weapon, by the sheet's `name`),
  `subclass` (e.g. `subclass:Prismatic Warlock`), `plug` (super, abilities, aspects, fragments), `mod` (armor slot
  mods, stat mods, tunings), `perk` (weapon perks and weapon mods), `artifact` (the artifact and its perks), `stat`
  (`stat:Grenade`…). Missing from the dict = no icon.
- Icon URL = `https://www.bungie.net` + path; local file = `cache/icons/<basename of path>`.
- The export never raises for an icon, a snapshot or the network; each problem is one warning string.
- `build_md` and the `.md` view are untouched; `build_pdf` still regenerates the `.md` first (`sheet_mod.save`).
- Tests: `uv run --no-sync pytest -q` (the MCP server may hold the venv lock); test-first every task.

## Review Focus

- Sheet without `resolved` (intent only): page 1 renders subclass + intent mods by slot + weapon roles, empty
  slots stay empty — test in Task 3.
- Very long text (concept + 9 rationale bullets + 3 long whys, ~2,600 chars, French accents): middle shrinks to the
  7 pt floor then a page 2 appears, nothing drawn outside the page — test in Task 3.
- A name that matches several definitions (`Time Dilation` is an emblem and a mod; `Song of Flame` exists as Solar
  and Prismatic super): the kind filter picks the right one — test in Task 1.
- Corrupt / truncated icon file in the cache (a failed earlier write) or a non-image response: placeholder +
  warning, not a crash — tests in Tasks 2 and 3.
- Network down with nothing cached ever: PDF still produced, all placeholders, one warning not fifty — test in Task 4.

---

### Task 1: Icon references (`shell/engines/build_icons.py`)

**Files:**
- Create: `shell/engines/build_icons.py`, `tests/engines/test_build_icons.py`
- Modify: `shell/engines/share.py` — rename `_subclass` → `subclass_item`, `_mod_index` → `mod_index` (public, both
  now have two callers); update its call sites and `tests/engines/test_share.py` if it references them.

**Interfaces:**
- Produces: `refs(s: dict, defs: dict, socket_types: dict, stat_defs: dict, armor_items: list[dict],
  weapon_items: list[dict]) -> tuple[dict[str, str], list[str]]` — `{key: "/common/destiny2_content/icons/x.jpg"}`,
  warnings. `defs` = DestinyInventoryItemDefinition, `stat_defs` = DestinyStatDefinition, both by hash string.

Rules:
- `item:<name>`: `resolved.armor` + `resolved.weapons`; hash from the snapshot row whose `itemId` matches
  (`itemHash`); no row → name lookup among `itemType` 2 (armor) / 3 (weapon) using `share._copy_key` order, and the
  warning `"<slot>: <name> not in the inventory snapshot: icon by name"`. Also the intent exotic
  (`item:<intent.exotic.name>`, armor of the sheet's class) when not resolved.
- `subclass:<item name>` and `plug:<name>`: `share.subclass_item(...)` gives the subclass hash and
  `socketOverrides` hashes; key plugs by their definition's name. Its `unknown` names are warnings.
- `mod:<name>`: `share.mod_index(defs)` for every `stat_mod`, `tuning`, `mods` of `resolved.armor`, else
  `intent.armor_mods` values (and `armor_mods_fill`).
- `perk:<name>`: weapon `perks` + `mod` of `resolved.weapons`; lookup restricted to definitions with a `plug`
  whose `plugCategoryIdentifier` is not `enhancements.*` / armor tuning (weapon plugs), lowest hash wins.
- `artifact:<name>`: `intent.artifact.name` among `itemTypeDisplayName == "Artifact"`, its `perks` among
  `"Artifact Perk"`.
- `stat:<name>` for the six `share.STAT_HASHES` from `stat_defs`.
- A name found with no `displayProperties.icon` counts as not found (warning `"no icon: <key>"`).

- [ ] **Step 1: Write the failing tests** in `tests/engines/test_build_icons.py`, reusing `DEFS`, `SOCKET_TYPES`,
      `ARMOR`, `WEAPONS` from `tests/engines/test_share.py` plus `SHEET` from `tests/engines/builds/test_sheet.py`
      (add `displayProperties.icon` to the fixture plugs you assert on via a local deep copy):
  - `test_subclass_and_plugs`: `refs[...]["plug:Storm Grenade"]` is the Prismatic grenade's icon,
    `"plug:Song of Flame"` the Prismatic copy's (hash 11, not Solar 10), `"subclass:Prismatic Warlock"` present.
  - `test_item_icon_from_snapshot_hash`: an armor row whose snapshot `itemHash` points to definition A while another
    definition B has the same name → A's icon, no warning.
  - `test_item_without_snapshot_falls_back_to_name`: empty `armor_items` → icon by name + the warning text above.
  - `test_mod_kind_filter`: a fixture emblem named `Time Dilation` (itemType 14, own icon) and the mod
    `Time Dilation` (`enhancements.v2_class_item`) → `"mod:Time Dilation"` is the mod's icon.
  - `test_tuning_label_maps`: `"+Grenade / -Weapons"` with category `core.gear_systems.armor_tiering.plugs.tuning.mods`
    → `"mod:+Grenade / -Weapons"` present.
  - `test_weapon_perk_artifact_and_stats`: `perk:Physic`, `artifact:Hunter's Journal`, `artifact:Shieldcrush`,
    `stat:Grenade` present.
  - `test_unknown_names_warn`: a fragment `Facet of Nothing` → absent key and a warning naming it.
- [ ] **Step 2:** `uv run --no-sync pytest tests/engines/test_build_icons.py -q` → fails (module missing).
- [ ] **Step 3:** do the `share.py` renames, then implement `refs` per the rules above.
- [ ] **Step 4:** `uv run --no-sync pytest tests/engines -q` → all pass (share tests included).
- [ ] **Step 5:** commit `S-026: icon references for a build sheet (reuses the DIM link's resolution)`.

### Task 2: Icon cache (`shell/sources/icons.py`)

**Files:**
- Create: `shell/sources/icons.py`, `tests/sources/test_icons.py`

**Interfaces:**
- Produces:
  - `folder() -> Path` = `paths.cache_dir() / "icons"`.
  - `local(refs: dict[str, str], download=None) -> tuple[dict[str, Path], list[str]]` — for each key, the file
    `folder() / basename(path)`; downloads missing files with `download(url) -> bytes` (default: `httpx.get(url,
    timeout=10, follow_redirects=True)`, `raise_for_status`, `.content`), at most 8 at a time
    (`concurrent.futures.ThreadPoolExecutor(8)`); writes via a `.tmp` + `os.replace`; merges `{key: path}` into
    `folder() / "index.json"`. A failed download leaves the key out with the warning `"icon download failed: <key>"`;
    after 3 failures, stops trying the rest and warns once `"icons: Bungie unreachable, <n> icons missing"`.
  - `indexed() -> dict[str, str]` — the index content (`{}` when absent or unreadable): the offline refs.
- A file is valid only if it starts with a PNG (`\x89PNG`) or JPEG (`\xff\xd8`) signature; an invalid cached file is
  re-downloaded, an invalid download is a failure.

- [ ] **Step 1: Write the failing tests** (`monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path)`; a fake
      `download` that counts calls and returns `b"\x89PNG..."`):
  - `test_downloads_once_then_uses_cache`: two `local` calls with the same refs → `download` called once per file;
    both results map the key to an existing file.
  - `test_index_serves_offline`: after one `local`, `indexed()` returns the refs; `local(indexed(), download=boom)`
    (raises) returns all keys, no warnings.
  - `test_failure_is_a_warning`: `download` raising for one key → that key absent, `"icon download failed: <key>"`.
  - `test_unreachable_warns_once`: 20 keys, `download` always raising → empty result, one
    `"icons: Bungie unreachable, …"` warning, `download` called ≤ 3 + 8 times.
  - `test_invalid_file_redownloaded`: a cached file containing `b"<html>"` → downloaded again.
- [ ] **Step 2:** run `uv run --no-sync pytest tests/sources/test_icons.py -q` → fails.
- [ ] **Step 3:** implement.
- [ ] **Step 4:** same command → pass.
- [ ] **Step 5:** commit `S-026: icon cache with an offline index`.

### Task 3: Showcase renderer (`shell/outputs/build_pdf.py`, rewritten)

**Files:**
- Modify (rewrite): `shell/outputs/build_pdf.py`; `tests/outputs/test_build_pdf.py` (Markdown-parsing tests go,
  font tests stay adapted)

**Interfaces:**
- Consumes: the key format (Global Constraints); `shell.engines.builds.stats.STATS` for stat order.
- Produces: `render(s: dict, icons: dict[str, Path], fonts="auto", compress=True) -> tuple[bytes, list[str]]` and
  `write(path: Path, s: dict, icons: dict[str, Path]) -> list[str]`. Keep `find_fonts`, `FONT_CANDIDATES`,
  `NO_FONT`, the `clean` / `SIMPLER` fallback logic.

Layout (A4 landscape, 297 × 210 mm, all positions absolute — no flowing text except the middle):
- Background: full-page gradient by `subclass.element`: Prismatic `#c46aa6 → #6b3f77 → #2a2433`, Solar
  `#d9823f → #6e3a2a → #2a2226`, Arc `#6fb6e0 → #2f5a7a → #1e2632`, Void `#a36ad6 → #4b2f6e → #221d2e`, Stasis
  `#7a9ee8 → #34497a → #1d2233`, Strand `#5fd39a → #2b6b52 → #1c2a26`; unknown → Prismatic.
- Top bar 0–14 mm: name 16 pt bold white, `CLASS · ACTIVITY` 7 pt caps.
- Subclass panel (x 6–110, y 16–90): emblem circle 10 mm + `<ELEMENT> <CLASS>` 14 pt bold + `<CLASS> SUBCLASS`;
  super in a 24 mm square rotated 45° (draw the rotated square with `pdf.rotation`, icon upright inside);
  sections `ABILITIES` (class, jump, melee, grenade), `ASPECTS`, `FRAGMENTS`: 6.5 pt caps label, 0.3 mm rule,
  10 mm square icons, 1 mm gap.
- Weapons (x 6–110, y 94–165): per weapon an icon 15 mm (gold `#e9cf55` border if `intent.weapons[slot].exotic`
  or the item is the sheet's exotic weapon), name 8 pt bold + first two perks 6.5 pt to its right; to its left,
  right-aligned toward it, perks as 6 mm circles on one row (`elliptic_clip`), the weapon `mod` as a 6 mm square
  (gold-ish border `#c9b46a`) on the row under.
- Artifact (x 6–110, y 170–204): 13 mm icon, name, perks as 6.5 mm circles on one row.
- Middle (x 114–214, y 16–204): concept (italic, boxed `#1a1420` 70 %), `WHY IT WORKS` bullets (`resolved.rationale`),
  `WEAPONS` (`name: why`), then the set box (`ARMOR SET BONUS · <set> ×<pieces>` per `resolved.sets` else
  `intent.sets`). 8 pt; if it doesn't fit, retry 7.5 / 7 pt; still too long → cut at a whole bullet, `(continued
  on page 2)`, the rest on page 2 (same background, single text column 8 pt), followed by "To fetch" when the tool
  passes needs (not in this story: keep page 2 to overflow text).
- Stats (x 216–232, y 40–150): six rows `value` 9 pt + 4 mm `stat:` icon, Weapons, Health, Class, Grenade, Super,
  Melee order (`STATS`), thin box around. The set-bonus icons the mockup shows under it are left out (no set perk
  resolution in Task 1): the middle's set box names the perks.
- Armor (x 234–291, y 18–200): five rows (Helmet, Gauntlets, Chest, Legs, Class Item), 15 mm icon (exotic gold),
  to its right one row of 7 mm squares: tuning, stat mod (gold border), slot mods.
- Missing icon for a key: a `#00000055` square / circle of the same size with the name in 4 pt inside, plus the
  warning `"no icon: <key>"` once per key. An icon file fpdf can't read → same placeholder, warning
  `"bad icon file: <key>"`.
- No `resolved`: weapons column shows `intent.weapons` roles as text in empty 15 mm frames; armor rows show the
  intent exotic in its slot and `intent.armor_mods[slot]` as mod squares; stats column hidden.

- [ ] **Step 1: Write the failing tests** (fixture: `SHEET` from `tests/engines/builds/test_sheet.py` plus a resolved
      variant; icons = a dict of tiny valid PNGs written to `tmp_path` — make one with fpdf-free bytes, e.g. a 1×1 PNG
      constant):
  - `test_page_one_is_landscape_with_images`: `render(sheet, icons, fonts=None, compress=False)` → bytes start
    `%PDF`, contain `/MediaBox [0 0 841.89 595.28]`, `/Subtype /Image` at least once, and the names
    `b"DECATUR 02"`, `b"Feed the Void"` are NOT required as text (icons) but the build name is.
  - `test_missing_icons_are_placeholders`: `icons={}` → PDF produced; warnings include `"no icon: plug:Feed the
    Void"`; no warning repeats.
  - `test_bad_icon_file`: an icon path containing `b"<html>"` → `"bad icon file: <key>"`, PDF produced.
  - `test_long_text_overflows_to_page_two`: rationale of 30 × 200-char bullets → page count 2 (`/Count 2`),
    `b"continued on page 2"` in the bytes.
  - `test_short_text_single_page`: the fixture → `/Count 1`.
  - `test_intent_only_sheet`: sheet without `resolved` → PDF produced, no exception.
  - keep `test_unicode_font_keeps_symbols` and the Latin-1 fallback warning test, adapted to the new signature.
- [ ] **Step 2:** `uv run --no-sync pytest tests/outputs/test_build_pdf.py -q` → fails.
- [ ] **Step 3:** rewrite `build_pdf.py` per the layout. Module docstring: what the page shows and that it is pure.
- [ ] **Step 4:** same command → pass.
- [ ] **Step 5:** render the real Getaway Buddy sheet with real icons (a throwaway script in the scratchpad calling
      Task 1 + 2 + 3) and compare by eye to `layout-v3.html`; fix positions until it matches.
- [ ] **Step 6:** commit `S-026: build PDF in the in-game layout`.

### Task 4: Wire the tool, skill, story

**Files:**
- Modify: `shell/mcp/tools/share.py` (`build_pdf`), `tests/mcp/test_share_tools.py`,
  `.claude/skills/share-build/SKILL.md` (PDF line: "in-game layout with icons; first export downloads icons"),
  `stories/doing/S-026-build-pdf-showcase.md` → `stories/done/` with boxes ticked.

**Interfaces:**
- Consumes: `build_icons.refs`, `icons.local`, `icons.indexed`, `build_pdf.write`.

`build_pdf(slug)`:
1. `_load`, `sheet_mod.save` (as today).
2. Snapshot: `read_snapshot("armor")` / `("weapons")`, `FileNotFoundError` → `[]` + warning
   `"no inventory snapshot: item icons by name (call refresh_inventory)"`.
3. `refs` from the manifest tables (`DestinyInventoryItemDefinition`, `DestinySocketTypeDefinition`,
   `DestinyStatDefinition`, all `keep=False`); on `BungieApiError` / `httpx.HTTPError` / `OSError` →
   `icons.indexed()` + warning `"Bungie unreachable: icons from the cache only"`.
4. `icons.local(refs)` → files; `build_pdf.write(pdf, s, files)`.
5. Return `{"pdf": ..., "warnings": [...all...]}` (same shape as today).
Docstring updated (in-game layout, icons cached in cache/icons/).

- [ ] **Step 1: Failing tests** in `tests/mcp/test_share_tools.py` (extend `FakeManifest` with
      `DestinyStatDefinition`; monkeypatch `shell.sources.icons` default download to return a 1×1 PNG):
  - `test_build_pdf` (existing) still passes and the PDF has `/Subtype /Image`.
  - `test_build_pdf_without_snapshot_warns`: no `profile/inventory/` → warning with `refresh_inventory`.
  - `test_build_pdf_offline_uses_index`: first call online; second with a manifest whose `table` raises
    `BungieApiError` and a download that raises → PDF produced with images, warning `"Bungie unreachable: …"`.
  - `test_build_pdf_offline_never_cached`: both failing from the start → PDF produced, warnings ≤ 3 lines.
- [ ] **Step 2:** `uv run --no-sync pytest tests/mcp/test_share_tools.py -q` → fails.
- [ ] **Step 3:** implement; update the skill line.
- [ ] **Step 4:** `uv run --no-sync pytest -q` → whole suite passes.
- [ ] **Step 5:** export `warlock-prismatic-getaway-buddy` through the tool path; the player checks it by eye.
- [ ] **Step 6:** `git mv` the story to `stories/done/`, tick boxes; commit
      `S-026: build_pdf uses the showcase layout; story done`.
