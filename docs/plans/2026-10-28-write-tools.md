# Write Tools (E3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shell acts on the player's account itself — lock / unlock, transfers, postmaster, equip, sockets (mods, subclass, artifact) and weapon perks — stories S-008, S-009, S-010, with no destiny-zen.

**Architecture:** One location snapshot per call (`shell/engines/locations.py`) and pure planning functions; execution goes through `BungieClient.post` with a small action runner that spaces calls and names Bungie errors. Every tool returns structured JSON: a header (`dry_run`, counts) and one entry per item / change with a `result`. Tools that move or change gear default to `dry_run=True`, so a write only happens when Claude explicitly passes `dry_run=False` after the player approved the preview (spec anti-goal: nothing acts on the account without the player's go-ahead). `set_lock` defaults to `dry_run=False` (asking for a triage is the go-ahead).

**Tech Stack:** Python 3.12, `shell.core` (BungieClient, Manifest), `shell.engines` (account, inventory, loadout), `mcp` 2.3 via `shell.mcp.tool`.

**Spec:** `docs/specs/2026-10-28-overclocked-shell-design.md`. Behaviour reference (parity, read-only): destiny-zen `src/tools/item-tools.ts`, `src/tools/socket-tools.ts`, `src/tools/perk-tools.ts`, `src/zen/sockets.ts` in `D:\Projects\dim-agent\vendor\destiny-zen`. Callers to keep working in E4: dim-agent `scripts/common.py` (`out/*_plan.json` lock batches of 50), `scripts/build/equip_plan.py` (equip plan JSON), `.claude/skills/equip-build/SKILL.md` (call order).

## Global Constraints

- Endpoints (all `POST`, authenticated, ids as JSON **strings**, `membershipType` a number):
  - `/Destiny2/Actions/Items/SetLockState/` `{state, itemId, characterId, membershipType}`
  - `/Destiny2/Actions/Items/TransferItem/` `{itemReferenceHash, stackSize: 1, transferToVault, itemId, characterId, membershipType}` — `characterId` is the source character going to the vault, the destination coming from it; character → character is always character → vault → character.
  - `/Destiny2/Actions/Items/PullFromPostmaster/` `{itemReferenceHash, stackSize: quantity, itemId ("0" for uninstanced), characterId, membershipType}`
  - `/Destiny2/Actions/Items/EquipItems/` `{itemIds, characterId, membershipType}` → `{equipResults: [{itemInstanceId, equipStatus}]}`, `equipStatus == 1` is success.
  - `/Destiny2/Actions/Items/InsertSocketPlugFree/` `{plug: {socketIndex, socketArrayType: 0, plugItemHash}, itemId, characterId, membershipType}`
- Vault items use the first character id as `characterId`.
- Spacing: 0.25 s after each successful lock / transfer / pull / equip call; 0.6 s between socket insert attempts (Bungie: 2 socket actions per second).
- Limits per call: `set_lock` 50 ids, `transfer_items` 25, `equip_items` 12, `set_sockets` 10 changes and 30 socket actions (refuse the whole call above 30), `set_perks` 50 changes, applying at most 30 (rest reported as deferred).
- Bungie error names (`ERROR_NAMES`): 1620 character not found, 1623 item not found, 1634 character not in orbit / social space, 1641 unique-equip exotic clash, 1642 no room in destination, 1645 transfer failed, 1648 uniqueness violation, 1655 can only equip in game, 1656 cannot act on an equipped item, 1660 not transferable, 1672 throttled by the game server, 1676 plug insertion rules failed (energy, or fragment slots not unlocked), 1677 socket not found, 1678 socket action not allowed, 1679 plug already in this or another socket, 1680 plug not unlocked.
- Writes do not refresh the inventory snapshot; tool descriptions tell Claude to call `refresh_inventory` after changes.
- Out of scope: in-game loadout slots (equip / snapshot / rename / clear loadout) — no story needs them.

## Review Focus

1. **Item not on the account, or uninstanced postmaster stack in `set_lock`** → `not found` / `skipped`, never a POST with a bogus id. (Tasks 1, 2)
2. **Full destination bucket (1642) when moving to a character** → one unrequested item of the same bucket is sent to the vault, the move is retried once, and the result says what was moved. (Tasks 3, 4)
3. **Player not in orbit (1634) during perk / socket changes** → stop the batch with a clear "go to orbit" result instead of failing every remaining change. (Tasks 5, 6)
4. **`dry_run` omitted on a gear-changing tool** → preview only; nothing is sent. (Tasks 3–6)
5. **Partial failures** → every item / change has its own `result`; counts in the header match. (All tasks)

---

### Task 1: Locations and action runner

**Files:**
- Create: `shell/engines/locations.py`, `shell/engines/actions.py`
- Test: `tests/engines/test_locations.py`, `tests/engines/test_actions.py`

**Interfaces:**
- Consumes: `shell.engines.loadout.item_name`, `shell.engines.inventory.CLASS_NAME`, `POSTMASTER_BUCKET`.
- Produces:
  - `LOCATION_COMPONENTS = [102, 200, 201, 205]`
  - `read_locations(profile: dict, defs: dict) -> tuple[dict[str, dict], dict[str, int]]` — `(locations, class_of)`. Location: `{"itemId", "itemHash", "bucketHash", "where": "vault"|"inventory"|"postmaster"|"equipped", "characterId", "quantity", "locked", "name"}`. Vault = instanced `profileInventory` items (`bucketHash` default 138197802); character inventory items are `postmaster` when `bucketHash == POSTMASTER_BUCKET`; uninstanced postmaster stacks get the id `pm:{characterId}:{itemHash}:{index in that character's items}` and `locked=False`; other uninstanced items are dropped. `class_of` maps character id → classType.
  - `ERROR_NAMES: dict[int, str]` (Global Constraints) and `describe(error: BungieApiError) -> str` → `f"{ERROR_NAMES[code]} ({error})"` when known, else `str(error)`.
  - `class Actions(client: BungieClient, membership: dict, sleep: Callable[[float], None] = time.sleep)` with `post(path: str, body: dict, gap: float = 0.25) -> Any` (adds `membershipType`, sleeps `gap` after success only).

- [ ] **Step 1: Write the failing tests** — `test_vault_inventory_postmaster_equipped` (fixture profile from `tests/engines/fixtures.py`: `a1` vault, `a2` postmaster with `characterId "w"`, `a3` equipped), `test_uninstanced_postmaster_stack_gets_pm_id`, `test_uninstanced_other_items_dropped`, `test_describe_known_and_unknown_codes`, `test_post_adds_membership_type_and_sleeps_after_success_only`.
- [ ] **Step 2: Run** `uv run pytest tests/engines/test_locations.py tests/engines/test_actions.py -q` — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — PASS.
- [ ] **Step 5: Commit** `git commit -m "Item locations and action runner"`

### Task 2: Lock and unlock

**Files:**
- Create: `shell/engines/locking.py`, `shell/mcp/tools/locking.py`
- Test: `tests/engines/test_locking.py`

**Interfaces:**
- Produces:
  - `set_lock(actions: Actions, locations: dict, class_of: dict, item_ids: list[str], locked: bool, dry_run: bool) -> dict` → `{"dry_run", "changed", "items": [{"itemId", "name", "result"}]}`; ids deduplicated (keeping order, after stripping quotes and spaces); `result` one of `"locked"`, `"unlocked"`, `"already locked"`, `"already unlocked"`, `"would lock"`, `"would unlock"`, `"not found"`, `"failed: <describe>"`; ids starting `pm:` are `"not found"` for lock (no POST).
  - Tool `set_lock(item_ids: list[str], locked: bool, dry_run: bool = False) -> dict` — more than 50 ids → `ToolError` "At most 50 items per call."; reads `LOCATION_COMPONENTS`.

- [ ] **Step 1: Write the failing tests** — `test_locks_and_skips_already_locked` (fake Actions recording posts; vault item → `characterId` = first character), `test_dry_run_posts_nothing`, `test_not_found_and_pm_ids_skipped`, `test_failure_named_and_batch_continues` (fake post raises `BungieApiError(error_code=1623)` for one id).
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — PASS. Manual (player present): lock then unlock one junk item; check in DIM.
- [ ] **Step 5: Commit** `git commit -m "Lock and unlock"`; tick S-008.

### Task 3: Transfers and postmaster

**Files:**
- Create: `shell/engines/moving.py`, `shell/mcp/tools/moving.py`
- Test: `tests/engines/test_moving.py`

**Interfaces:**
- Produces:
  - `move(actions, locations, item_id: str, target: str | None, requested: set[str], bucket_of: Callable[[int], int]) -> list[str]` — performs the legs (to vault from a character, then from the vault to `target`); on 1642 for the to-character leg, sends to the vault the first location with `characterId == target`, `where == "inventory"`, same bucket (`bucket_of(itemHash)`), not in `requested`, updates that location, retries once; returns notes (e.g. `"made room: sent <name> to the vault"`); raises `BungieApiError` otherwise.
  - `transfer(actions, locations, class_of, item_ids, to: str, dry_run, bucket_of) -> dict` → `{"dry_run", "moved", "items": [{"itemId", "name", "result", "notes"?}]}`; results: `"moved to <to>"`, `"would move to <to>"`, `"already there"`, `"equipped: unequip it first"`, `"in the postmaster: pull it first"`, `"not found"`, `"failed: <describe>"`.
  - `pull_postmaster(actions, locations, character_id, item_ids: list[str] | None, pull_all: bool, dry_run) -> dict` — without ids and without `pull_all`, returns the listing `{"postmaster": [{"itemId", "name", "quantity"}]}`; otherwise pulls each wanted entry (`itemId "0"` for `pm:` ids, `stackSize = quantity`).
  - `bucket_of` default in the tool: weapons from `defs["weapons"][h]["b"]`, gear from `defs["gear"][h][3]`.
  - Tools `transfer_items(item_ids: list[str], to: str, dry_run: bool = True)` (to: vault/titan/hunter/warlock; > 25 ids → ToolError) and `pull_from_postmaster(character: str, item_ids: list[str] | None = None, pull_all: bool = False, dry_run: bool = True)`.

- [ ] **Step 1: Write the failing tests** — `test_vault_to_character_one_leg`, `test_character_to_character_via_vault`, `test_full_bucket_makes_room_once` (first to-character call raises 1642, victim sent to vault, retry succeeds, note present, requested items never chosen as victim), `test_full_vault_reported_as_failure`, `test_equipped_and_postmaster_skipped`, `test_dry_run_default_posts_nothing`, `test_pull_lists_without_ids`, `test_pull_uninstanced_uses_zero_id_and_quantity`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — PASS. Manual: live dry run of a vault → Warlock move.
- [ ] **Step 5: Commit** `git commit -m "Transfers and postmaster"`

### Task 4: Equip

**Files:**
- Create: `shell/engines/equipping.py`, `shell/mcp/tools/equipping.py`
- Test: `tests/engines/test_equipping.py`

**Interfaces:**
- Consumes: `move` (Task 3).
- Produces:
  - `equip(actions, locations, class_of, character_id, item_ids, dry_run, bucket_of) -> dict` → `{"dry_run", "equipped", "moves": [{"itemId", "name", "result", "notes"?}], "equip": [{"itemId", "name", "result"}]}`. Phase 1 per item: not found / postmaster / equipped on another character → skipped; already on the character → kept; else moved (dry run: `"would move vault -> <class>"` or `"would move other character -> vault -> <class>"`). Phase 2: one `EquipItems` with the kept / moved ids in order; entries with `equipStatus == 1641` retried once with only those ids after 0.25 s; result `"equipped"` or `"not equipped: <ERROR_NAMES or error N>"`.
  - Tool `equip_items(character: str, item_ids: list[str], dry_run: bool = True)` (> 12 ids → ToolError). Subclass ids may be included.

- [ ] **Step 1: Write the failing tests** — `test_moves_then_single_equip_call`, `test_exotic_clash_retried_once`, `test_skips_postmaster_and_equipped_elsewhere`, `test_dry_run_reports_routes_and_posts_nothing`, `test_nothing_to_equip`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — PASS. Manual: live dry run equipping the Warlock's current helmet + a vault weapon.
- [ ] **Step 5: Commit** `git commit -m "Equip items"`; tick S-009.

### Task 5: Sockets

**Files:**
- Create: `shell/engines/sockets.py`, `shell/mcp/tools/sockets.py`
- Test: `tests/engines/test_sockets.py`

**Interfaces:**
- Consumes: `item_name`, `Actions`, `describe`.
- Produces:
  - `norm(name: str) -> str` — lower-case, keep `[a-z0-9]`.
  - `candidates(item_def: dict, reusable: dict, plug_sets: dict, plug_set_def: Callable[[int], dict]) -> list[list[int]]` — per socket entry `i` of `item_def["sockets"]["socketEntries"]`, in order, deduplicated, zeros dropped: live `reusable[str(i)]` hashes; for `reusablePlugSetHash` then `randomizedPlugSetHash`: live `plug_sets[str(ps)]` hashes with `canInsert is not False`, then `plug_set_def(ps)["reusablePlugItems"][].plugItemHash`; the entry's `reusablePlugItems[].plugItemHash`; `singleInitialItemHash`.
  - `plan_item(item_id, character_id, name, current: list[int], cands: list[list[int]], reusable: dict, requests: list[str | dict], defs, force: bool) -> tuple[list[dict], list[str]]` — destiny-zen rules: request = name or `{"name", "socketIndex"}`; sockets whose candidates have a hash named like the request (by `norm`); restricted to `socketIndex` if given; not `Empty…` and not `force` and a free socket already holds a matching hash → taken, note `"<X> already in socket N"`; else pick the first free socket that is empty / `Empty…` / `Default…`, else one whose current plug is not among this item's requested names, else (removals only) the first free one; hashes ordered live-insertable first. Plan entry `{"itemId", "characterId", "socketIndex", "from", "to", "hashes"}`; per item, `Empty…` targets first (stable). Notes for "no socket takes", "socket N can't take", "no free socket left".
  - `apply(actions, plans) -> list[dict]` — per plan try hashes in order (next hash only on 1676 / 1680), 0.6 s after every attempt; result `"done"` or `"failed: <describe>"`; on 1634 stop and mark the rest `"not attempted: go to orbit"`.
  - Tool `set_sockets(changes: list[{"itemId": str, "plugs": list}], dry_run: bool = True, force: bool = False)` — > 10 changes → ToolError; reads profile `[305]` once (`profilePlugSets` + that character's `characterPlugSets` merged), per item `GET /Destiny2/{type}/Profile/{id}/Item/{itemId}/?components=305,307,310` (characterId from the response, else the first character), item and plug set definitions from `GET /Destiny2/Manifest/DestinyInventoryItemDefinition/{hash}/` and `GET /Destiny2/Manifest/DestinyPlugSetDefinition/{hash}/` (memoized for the server's life); more than 30 planned actions → whole call refused. Returns `{"dry_run", "applied", "changes": [{"itemId", "name", "socketIndex", "from", "to", "result"}], "notes"}`.

- [ ] **Step 1: Write the failing tests** — `test_candidates_order_and_dedupe`, `test_already_installed_is_kept` (dim-agent relies on it), `test_prefers_empty_then_unrequested_socket`, `test_indexed_empty_on_taken_socket_skipped`, `test_empty_removals_first`, `test_apply_tries_next_hash_on_1680_only`, `test_apply_stops_on_not_in_orbit`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — PASS. Manual: live dry run of the Warlock's current subclass plugs (expect "already in socket" notes only).
- [ ] **Step 5: Commit** `git commit -m "Socket changes: mods, subclass, artifact"`

### Task 6: Weapon perks

**Files:**
- Create: `shell/engines/perks.py`, `shell/mcp/tools/perks.py`
- Test: `tests/engines/test_perks.py`

**Interfaces:**
- Consumes: `weapon_rows` (E2), `norm`, `apply` (Task 5).
- Produces:
  - `plan_perks(row: dict, character_id: str, select: list[str]) -> tuple[list[dict], list[str]]` — per name: columns with an option whose `norm` name matches; none → note "not one of its rolled options"; several columns → note "appears in more than one column"; prefer the enhanced option; a column already used in this request → note; already selected → note; option `canInsert` false → note; else plan `{"itemId", "characterId", "socketIndex", "from", "to", "hashes": [hash]}`.
  - Tool `set_perks(changes: list[{"itemId": str, "select": list[str]}], dry_run: bool = True)` — fresh profile with the inventory components, `weapon_rows`, character = the weapon's or the first character; applies at most 30 planned changes with `apply`, the rest reported as `"deferred: call again"`. Returns `{"dry_run", "applied", "changes": [{"itemId", "name", "column", "from", "to", "result"}], "notes"}`.

- [ ] **Step 1: Write the failing tests** — `test_selects_matching_column`, `test_prefers_enhanced`, `test_not_rolled_and_ambiguous_noted`, `test_already_selected_and_cannot_insert_noted`, `test_more_than_30_deferred`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — PASS. Manual: live dry run selecting a different barrel on a crafted weapon.
- [ ] **Step 5: Commit** `git commit -m "Weapon perk changes"`; tick S-010, move S-008…S-010 to `stories/done/`.
