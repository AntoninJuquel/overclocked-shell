# Read Tools (E2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shell reads the player's full inventory (armor with tuned stat, weapons with perk columns), equipped gear and artifact, and the weekly context itself — stories S-005, S-006, S-007 — with no destiny-zen.

**Architecture:** A compact definitions index (`shell/engines/defs.py`) is built once per manifest version from the full manifest tables. Pure functions turn a Bungie profile response into rows with **exactly the shape of destiny-zen's export rows** (field names included), so the dim-agent scripts port in E4 with minimal change. The inventory snapshot stays in-process (and is saved to `profile/inventory/`); Claude gets filtered, size-limited views through tools — it never receives the 600-item lists.

**Tech Stack:** Python 3.12, existing `shell.core` (BungieClient, Manifest), `mcp` 2.3 via `shell.mcp.tool`.

**Spec:** `docs/specs/2026-10-28-overclocked-shell-design.md`. Behaviour reference (parity): destiny-zen `src/zen/defs.ts`, `src/tools/armor-tools.ts`, `src/zen/inventory.ts`, `src/tools/context-tools.ts`, `src/tools/account-tools.ts` in `D:\Projects\dim-agent\vendor\destiny-zen` — read-only reference; the rules that matter are copied below.

## Global Constraints

- Row shapes and field names match destiny-zen exports exactly (camelCase: `itemId`, `itemHash`, `classType`, `gearTier`, `tunedStat`, `characterId`, `columns[].options[].canInsert`, …). Every armor row has the `tunedStat` key (value may be `null`); every armor row's `stats` comes from Bungie live values, nothing subtracted.
- Bungie profile responses: `profileInventory.data.items`, `characters.data`, `characterInventories.data[cid].items`, `characterEquipment.data[cid].items`, `itemComponents.{instances,stats,sockets,reusablePlugs}.data[instanceId]`, `characterActivities.data[cid].availableActivities`.
- Constants: `CLASS_NAME = {0: "Titan", 1: "Hunter", 2: "Warlock", 3: "Any"}`; `POSTMASTER_BUCKET = 215593132`; `ARMOR_BUCKETS = {3448274439: "Helmet", 3551918588: "Gauntlets", 14239492: "Chest", 20886954: "Legs", 1585787867: "Class Item"}`; `SUBCLASS_BUCKET = 3284755031`; `WEAPON_SLOTS = {1498876634: "Kinetic", 2465295065: "Energy", 953998645: "Power"}`; `AMMO = {1: "Primary", 2: "Special", 3: "Heavy"}`; `ELEMENTS = {1: "Kinetic", 2: "Arc", 3: "Solar", 4: "Void", 6: "Stasis", 7: "Strand"}`.
- Cosmetic plug test: case-insensitive `shader|skins|ornament|transmog|armor_skins|emote|v400\.empty|tracker` on `f"{plugCategoryIdentifier} {itemTypeDisplayName}"`.
- Tool results stay small: list tools return at most `limit` rows (default 25) plus `total` and `truncated`.
- New capabilities are new modules; the only core edit allowed is the `Manifest.table(..., keep=False)` flag (Task 1).

## Review Focus

1. **Items unknown to the definitions** (new season, redacted) → skipped, never a crash. (Tasks 3, 4)
2. **Character class not on the account** (`character="titan"` with no Titan) → one-line `No titan on this account.` tool error. (Task 2)
3. **Manifest version change** → defs index rebuilt for the new version, old index removed; the full item table is not kept in memory after the build. (Task 1)
4. **Postmaster items** → armor location `"<Class> (Postmaster)"`; weapons keep the bare class name (destiny-zen parity). (Tasks 3, 4)
5. **Filters that match hundreds of items** → `limit` respected, `total` and `truncated` reported. (Task 5)

---

### Task 1: Definitions index

**Files:**
- Modify: `shell/core/manifest.py` (add `keep: bool = True` to `table`)
- Create: `shell/engines/__init__.py`, `shell/engines/defs.py`
- Test: `tests/core/test_manifest.py`, `tests/engines/test_defs.py`

**Interfaces:**
- Produces:
  - `Manifest.table(name: str, keep: bool = True) -> dict[str, dict]` — `keep=False` returns the table without memoizing it.
  - `build_defs(items: dict, stats: dict, socket_categories: dict) -> dict` returning `{"weapons": {h: {"n","t","r","a","b","sc"}}, "gear": {h: [name, type, classType, bucketTypeHash, tierTypeName]}, "plugs": {h: {"n","t","p"}}, "misc": {h: name}, "stats": {h: name}, "socketCategories": {h: name}}` (keys are hash strings).
  - `load_defs(manifest: Manifest, cache_dir: Path | None = None) -> dict` — reads `cache/defs/<version>.json` or builds it from `DestinyInventoryItemDefinition`, `DestinyStatDefinition`, `DestinySocketCategoryDefinition` (each loaded with `keep=False`), writes atomically, deletes other files in `cache/defs/`.
  - `shell.context.Context.defs` — `cached_property` returning `load_defs(self.manifest)`.

Classification is one ordered chain on each item def (name = `displayProperties.name`, skip empty names):
1. `itemType == 3` → weapons: `n`=name, `t`=`itemTypeDisplayName`, `r`=`inventory.tierTypeName`, `a`=`equippingBlock.ammoType` or 0, `b`=`inventory.bucketTypeHash` or 0, `sc`=`[[socketCategoryHash, socketIndexes], …]` from `sockets.socketCategories`.
2. `itemType in (2, 14, 16, 21, 22, 24, 28)` or `/artifact/i` on `itemTypeDisplayName` → gear: `[name, itemTypeDisplayName, classType (default 3), bucketTypeHash (default 0), tierTypeName (default "")]`.
3. no `plug` block and (`itemType in (1, 9)` or `bucketTypeHash == 1469714392`) → misc.
4. has a `plug` block → plugs: `n`=name, `t`=`itemTypeDisplayName` or "", `p`=`plug.plugCategoryIdentifier` or "".

- [ ] **Step 1: Write the failing tests**

```python
def test_table_keep_false_not_memoized(tmp_path): ...  # second table(name, keep=False) call re-reads the file (patch json.loads count or check m._tables empty)

def test_classification_order():
    items = {"1": {"itemType": 3, "displayProperties": {"name": "Gun"}, "itemTypeDisplayName": "Auto Rifle",
                   "inventory": {"tierTypeName": "Legendary", "bucketTypeHash": 1498876634},
                   "equippingBlock": {"ammoType": 1},
                   "sockets": {"socketCategories": [{"socketCategoryHash": 4241085061, "socketIndexes": [1, 2]}]}},
             "2": {"itemType": 2, "displayProperties": {"name": "Helm"}, "itemTypeDisplayName": "Helmet",
                   "classType": 2, "inventory": {"bucketTypeHash": 3448274439, "tierTypeName": "Exotic"}},
             "3": {"itemType": 19, "displayProperties": {"name": "Mod"}, "itemTypeDisplayName": "General Armor Mod",
                   "plug": {"plugCategoryIdentifier": "enhancements.v2_general"}},
             "4": {"itemType": 0, "displayProperties": {"name": ""}, "plug": {}}}
    d = build_defs(items, {"10": {"displayProperties": {"name": "Health"}}}, {"20": {"displayProperties": {"name": "WEAPON PERKS"}}})
    assert d["weapons"]["1"] == {"n": "Gun", "t": "Auto Rifle", "r": "Legendary", "a": 1, "b": 1498876634, "sc": [[4241085061, [1, 2]]]}
    assert d["gear"]["2"] == ["Helm", "Helmet", 2, 3448274439, "Exotic"]
    assert d["plugs"]["3"] == {"n": "Mod", "t": "General Armor Mod", "p": "enhancements.v2_general"}
    assert "4" not in d["plugs"] and d["stats"] == {"10": "Health"} and d["socketCategories"] == {"20": "WEAPON PERKS"}

def test_load_defs_cached_per_version(tmp_path): ...  # fake manifest (version(), table()) → file cache/defs/v1.json; second call with a manifest whose table() raises reads the file
def test_load_defs_new_version_removes_old(tmp_path): ...
```

- [ ] **Step 2: Run** `uv run pytest tests/core/test_manifest.py tests/engines/test_defs.py -q` — Expected: new tests FAIL.
- [ ] **Step 3: Implement** the flag, `defs.py`, and `Context.defs`.
- [ ] **Step 4: Run** `uv run pytest -q` — Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Compact definitions index per manifest version"`

### Task 2: Account helpers

**Files:**
- Create: `shell/engines/account.py`
- Modify: `shell/mcp/tools/account.py` (use the helpers)
- Test: `tests/engines/test_account.py`

**Interfaces:**
- Produces:
  - `primary_membership(client: BungieClient) -> dict` — `GET /User/GetMembershipsForCurrentUser/`; the `destinyMemberships` entry whose `membershipId == primaryMembershipId`, else the first; raises `BungieApiError("No Destiny account on this Bungie.net profile.")` if none.
  - `get_profile(client: BungieClient, membership: dict, components: list[int]) -> dict` — `GET /Destiny2/{membershipType}/Profile/{membershipId}/?components=<comma list>`, authenticated.
  - `character_id(profile: dict, character: str) -> str` — first `characters.data` entry whose `classType == {"titan": 0, "hunter": 1, "warlock": 2}[character.lower()]`; raises `BungieApiError(f"No {character.lower()} on this account.")`.

- [ ] **Step 1: Write the failing tests** — `test_primary_membership_prefers_primary`, `test_primary_membership_falls_back_to_first`, `test_no_destiny_account_raises`, `test_character_id_by_class`, `test_missing_class_raises` (message `"No titan on this account."`); existing `tests/mcp/test_server.py` must keep passing.
- [ ] **Step 2: Run** `uv run pytest tests/engines/test_account.py -q` — FAIL.
- [ ] **Step 3: Implement**; `get_profile_summary` calls `primary_membership` and `get_profile(..., [200])`.
- [ ] **Step 4: Run** `uv run pytest -q` — PASS.
- [ ] **Step 5: Commit** `git commit -m "Account helpers: membership, profile, character"`

### Task 3: Armor rows

**Files:**
- Create: `shell/engines/inventory.py`
- Test: `tests/engines/test_inventory_armor.py` (fixture profile + defs built inline)

**Interfaces:**
- Consumes: defs dict (Task 1).
- Produces: `holdings(profile: dict) -> list[tuple[dict, str, str | None, bool]]` (item, location, characterId, equipped); `plug_list(sockets: list[dict], defs: dict) -> list[str]`; `stat_map(stats: dict, defs: dict) -> dict[str, int]`; `tuned_stat(reusable: dict, defs: dict) -> str | None`; `armor_rows(profile: dict, defs: dict) -> list[dict]`.

Rules (destiny-zen parity):
- `holdings` order: vault items (`"Vault"`, `None`, `False`); each character's inventory (`CLASS_NAME[classType]`, or `"<Class> (Postmaster)"` when `bucketHash == POSTMASTER_BUCKET`; cid; `False`); each character's equipment (class name, cid, `True`).
- Include an item only if it has `itemInstanceId` and `gear[itemHash]` exists with `ARMOR_BUCKETS[gear[3]]`.
- Row: `itemId`, `itemHash`, `name`=gear[0], `slot`, `classType`=`CLASS_NAME.get(gear[2], "Any")`, `rarity`=gear[4], `location`, `characterId`, `equipped`, `locked`=`state & 1`, `masterworked`=`state & 4` (bools), `power`=`primaryStat.value` or 0, `gearTier`=`instance.gearTier` (None if absent), `energy`=`f"{energyUsed}/{energyCapacity}"` or `""`, `stats` (the six keys `Weapons, Health, Class, Grenade, Super, Melee` present in `stat_map`, missing omitted), `total`=sum, `plugs`, `tunedStat`.
- `plug_list`: socket order; skip falsy `plugHash`, unknown plug, name matching `^(Empty|Default)` (case-insensitive) or cosmetic; entry `f"{t}: {n}"` or `n` when `t` is empty; duplicates kept.
- `tuned_stat`: iterate socket indexes ascending (int order); first option whose plug `p` contains `"tuning"` and name matches `^\+(\w+) / -\w+$` → the captured stat name; else `None`.

- [ ] **Step 1: Write the failing tests** — `test_armor_row_fields` (one vault exotic leg with energy, masterworked+locked state 5, stats incl. a non-armor stat that is dropped, plugs incl. an `Empty Mod Socket` and a `Shader` that are dropped, tuning options `["Balanced Tuning", "+Super / -Melee"]` → `tunedStat == "Super"`), `test_postmaster_location` (`"Warlock (Postmaster)"`), `test_equipped_from_equipment`, `test_unknown_or_non_armor_items_skipped` (weapon hash, unknown hash, missing instance id), `test_tuned_stat_none_without_tuning_socket`, `test_tuned_stat_ignores_non_tuning_category`.
- [ ] **Step 2: Run** `uv run pytest tests/engines/test_inventory_armor.py -q` — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — PASS.
- [ ] **Step 5: Commit** `git commit -m "Armor rows with tuned stat"`

### Task 4: Weapon rows

**Files:**
- Modify: `shell/engines/inventory.py`
- Test: `tests/engines/test_inventory_weapons.py`

**Interfaces:**
- Consumes: `holdings`, `stat_map` (Task 3).
- Produces: `weapon_rows(profile: dict, defs: dict) -> list[dict]`.

Rules:
- Include if `weapons[itemHash]` exists and `itemInstanceId`; locations as `holdings` but a postmaster weapon keeps the bare class name; `equipped` = holdings flag or `instance.isEquipped is True`.
- Row: `itemId`, `itemHash`, `name`, `type`=def `t`, `rarity`=def `r`, `element`=`ELEMENTS.get(damageType, "None")`, `slot`=`WEAPON_SLOTS.get(b, "")`, `ammo`=`AMMO.get(a, "")`, `power`, `gearTier`, `locked`=`state & 1`, `crafted`=`state & 8`, `equipped`, `location`, `characterId`, `frame`, `columns`, `masterwork`, `mod`, `stats`.
- Perk / intrinsic socket categories: hashes whose `socketCategories` name upper-cased is `WEAPON PERKS` / `INTRINSIC TRAITS`, fallback `{4241085061}` / `{3956125808}`; socket indexes from def `sc` in definition order.
- `frame`: intrinsic sockets' plug names (empty dropped) joined by `", "`. Plug name = `plugs[h].n`, else `f"#{h}"`, `""` for falsy.
- `columns`: per perk index `i` with a selected plug `sel`: `opts` = reusable plugs at `str(i)`; `all` = their hashes or `[sel]`; prepend `sel` if missing; skip the column if the selected name matches `/tracker/i`; `{"socketIndex": i, "label": (plugs[sel].t or "Perk") without a leading "Enhanced ", "selected", "selectedHash": sel, "options": [{"name", "hash", "enhanced": /enhanced/i on plugs[h].t, "canInsert": h == sel or that option's canInsert is not False (False if h not offered)}]}`.
- `masterwork` / `mod`: over all sockets, last plug whose name matches `^(Tier \d+: |Masterworked: )` / whose type matches `/weapon mod/i` and name not `/empty/i`; default `""`.
- `stats`: every mapped stat except `Attack`, `Power`, `Defense`, `""`.
- Sort by `(type.casefold(), name.casefold())`.

- [ ] **Step 1: Write the failing tests** — `test_weapon_row_fields` (element, slot, ammo, crafted state 9, frame, masterwork `"Masterworked: Handling"`, mod `"Backup Mag"`, Attack stat dropped), `test_columns_prepend_selected_and_flags` (selected not in options → first; enhanced flag; canInsert False kept), `test_tracker_column_skipped`, `test_postmaster_weapon_keeps_class_name`, `test_sorted_by_type_then_name`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — PASS.
- [ ] **Step 5: Commit** `git commit -m "Weapon rows with perk columns"`

### Task 5: Inventory snapshot and tools

**Files:**
- Create: `shell/mcp/tools/inventory.py`
- Test: `tests/mcp/test_inventory_tools.py`

**Interfaces:**
- Consumes: `primary_membership`, `get_profile`, `armor_rows`, `weapon_rows`, `ctx.defs`, `paths.profile_dir()`.
- Produces (MCP tools):
  - `refresh_inventory() -> dict` — one profile call with components `[102, 200, 201, 205, 300, 304, 305, 310]`; builds both row lists; writes `profile/inventory/armor.json` and `weapons.json` (atomic, `indent=1`); keeps them in memory for the server's life; returns `{"armor": n, "weapons": n, "saved_to": dir}`.
  - `find_armor(class_type: str | None = None, slot: str | None = None, name: str | None = None, rarity: str | None = None, limit: int = 25) -> dict` and `find_weapons(type: str | None = None, element: str | None = None, name: str | None = None, perk: str | None = None, limit: int = 25) -> dict` — case-insensitive filters (`name`/`perk` substring; `perk` searches every column option name), refresh first if nothing is loaded yet; return `{"total": n, "truncated": bool, "items": [...]}`. Armor items: `itemId, name, slot, classType, rarity, location, locked, gearTier, stats, total, tunedStat, plugs`; weapon items: `itemId, name, type, element, rarity, location, locked, crafted, frame, perks` (selected name per column), `masterwork, mod`.

- [ ] **Step 1: Write the failing tests** — fake `Context` (as in `tests/mcp/test_server.py`) with a MockTransport profile and a small defs dict: `test_refresh_writes_snapshot` (files exist under a patched `profile_dir`), `test_find_armor_filters_and_limit` (3 matches, `limit=2` → `total 3`, `truncated True`), `test_find_weapons_by_perk`, `test_find_loads_on_first_use`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** (snapshot state lives in the `register` closure).
- [ ] **Step 4: Run** `uv run pytest -q` — PASS. Manual: in Claude Code, "refresh my inventory" then "show my exotic warlock helmets" — counts close to the last destiny-zen export (617 armor / 465 weapons on 2026-10-23).
- [ ] **Step 5: Commit** `git commit -m "Inventory snapshot and find tools"`; tick S-005.

### Task 6: Equipped gear and artifact

**Files:**
- Create: `shell/engines/loadout.py`, `shell/mcp/tools/equipped.py`
- Test: `tests/engines/test_loadout.py`

**Interfaces:**
- Consumes: `holdings` logic is not needed; `plug_list`, `stat_map`, `character_id`, account helpers.
- Produces:
  - `equipped(profile: dict, defs: dict, cid: str) -> dict` → `{"items": [{"itemId", "name", "type", "exotic": bool, "stats" (armor only, six keys), "plugs"}], "subclass": {"name", "plugs"} | None, "artifact": {"itemId", "name"} | None, "armor_totals": {six stats}, "other_subclasses": [{"itemId", "name"}]}`. Skips types matching `/emblem|ship|sparrow|vehicle|finisher|emote|clan banner|ghost/i`; subclass = equipped item with `gear[3] == SUBCLASS_BUCKET`; artifact = equipped item whose gear type matches `/artifact/i`.
  - Tool `get_equipped(character: str) -> dict` — profile components `[200, 201, 205, 300, 304, 305]`; if an artifact is equipped, `GET /Destiny2/{type}/Profile/{id}/Item/{instanceId}/?components=305` and sets `artifact["perks"]` = names of its plugs (dropping empty / `#…` / names starting `Empty`).

- [ ] **Step 1: Write the failing tests** — `test_equipped_items_and_totals`, `test_subclass_plugs_separated`, `test_cosmetic_types_skipped`, `test_other_subclasses_from_inventory`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — PASS. Manual: "what is my warlock wearing?"
- [ ] **Step 5: Commit** `git commit -m "Equipped gear, subclass and artifact"`; tick S-006.

### Task 7: Weekly context

**Files:**
- Create: `shell/engines/context.py`, `shell/mcp/tools/weekly.py`
- Test: `tests/engines/test_context.py`

**Interfaces:**
- Produces:
  - `build_context(character: str, cid: str, milestones: dict, profile: dict, vendors: dict, generated: str) -> dict` → `{"generated", "character" (lower-case), "characterId", "milestones", "activities", "vendors"}` with destiny-zen rules: milestones = each value → `{milestoneHash, startDate|None, endDate|None, activities: (m.activities + availableQuests[].activity when present) → {activityHash, modifierHashes or []}}`; activities = `characterActivities.data[cid].availableActivities` with `isVisible is not False` → `{activityHash, modifierHashes or [], focused: isFocusedActivity is True, rewardItemHashes: unique first-seen visibleRewards[].rewardItems[].itemQuantity.itemHash}`; vendors = `vendors.data` entries with `enabled is not False` → `{vendorHash: int(key), nextRefreshDate|None, sales: [{itemHash, costs (raw)}]}` from `sales.data[key].saleItems` values.
  - Tool `refresh_context(character: str) -> dict` — profile `[200, 204]`, `GET /Destiny2/Milestones/`, `GET /Destiny2/{type}/Profile/{id}/Character/{cid}/Vendors/?components=400,402`; writes `profile/context/<UTC date>.json` (`indent=1`); returns counts `{"milestones", "activities", "focused", "vendors", "saved_to"}`.

- [ ] **Step 1: Write the failing tests** — `test_milestones_include_quest_activities`, `test_invisible_activities_dropped_and_rewards_unique`, `test_disabled_vendors_dropped_costs_raw`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — PASS. Manual: "refresh the weekly context for my warlock" → counts similar to destiny-zen's last `zen-context` export.
- [ ] **Step 5: Commit** `git commit -m "Weekly context"`; tick S-007, move S-005…S-007 to `stories/done/`.
