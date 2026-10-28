# Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A cloneable Python project whose MCP server signs in to Bungie on its own (no destiny-zen) and exposes its first tools to Claude Code: `auth_status` and `get_profile_summary`.

**Architecture:** `shell/core` holds paths, settings, OAuth, the Bungie HTTP client and the manifest cache, all resolved from the install folder (never the launch folder). `shell/mcp` builds a FastMCP server that discovers tool modules in `shell/mcp/tools/` — adding a tool means adding a module. A `shell` CLI handles the one-time sign-in.

**Tech Stack:** Python 3.12, `uv`, `mcp` (official SDK, FastMCP), `httpx`, `python-dotenv`, `cryptography` (self-signed localhost cert); dev: `pytest`.

**Spec:** `docs/specs/2026-10-28-overclocked-shell-design.md` — this plan covers its "Own Bungie layer" goal (stories S-001 → S-004). Later epics get their own plans.

## Global Constraints

- Python `>=3.12`; run with `uv run …`; no build step, no submodule.
- Everything in English (code, messages, docs).
- `.env`, `profile/`, `cache/`, `.venv/` are gitignored; nothing personal is committed.
- Paths (`.env`, `profile/`, `cache/`) resolve from the package's install root, not `os.getcwd()`.
- Bungie OAuth: confidential client; authorize `https://www.bungie.net/en/oauth/authorize`; token `https://www.bungie.net/platform/app/oauth/token/` with HTTP Basic (client id / secret); redirect `https://localhost:7777/callback` by default (`BUNGIE_REDIRECT_URL` overrides; must be `https://localhost|127.0.0.1`).
- API base `https://www.bungie.net/Platform`; every call sends `X-API-Key`; authenticated calls add `Authorization: Bearer …`.
- Tokens stored at `profile/auth/tokens.json`; access token refreshed when it expires within 120 s.
- Manifest tables cached at `cache/manifest/<version>/<Table>.json` (English `jsonWorldComponentContentPaths`).

## Review Focus

1. **Refresh token expired / never signed in** → tools return a one-line message telling the player to run `uv run shell auth login`, not a traceback. (Task 3, Task 6)
2. **Missing `.env` values** → error names each missing variable and the `.env` path. (Task 2)
3. **Bungie maintenance / throttling** (ErrorCode 5, 35, 36, HTTP 5xx) → retried up to 3 times honouring `ThrottleSeconds`, then a `BungieApiError` carrying the code. (Task 4)
4. **Server started from another folder** (user-scope MCP) → still finds `.env`, `profile/`, `cache/`. (Task 1, Task 2)
5. **Interrupted manifest download** → never leaves a truncated table that later loads as valid; writes are atomic. (Task 5)

---

### Task 1: Project skeleton and paths

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `README.md`, `CLAUDE.md`, `shell/__init__.py`, `shell/core/__init__.py`, `shell/core/paths.py`
- Test: `tests/core/test_paths.py`

**Interfaces:**
- Produces: `shell.core.paths.ROOT: Path` (repo root = parent of the `shell` package); `profile_dir() -> Path`, `cache_dir() -> Path`, `env_file() -> Path` — all under `ROOT`, created on demand by callers, not on import.

- [ ] **Step 1: Write the failing test**

```python
def test_paths_ignore_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from shell.core import paths
    assert paths.ROOT == Path(paths.__file__).resolve().parents[2]
    assert paths.profile_dir() == paths.ROOT / "profile"
    assert paths.cache_dir() == paths.ROOT / "cache"
    assert paths.env_file() == paths.ROOT / ".env"
```

- [ ] **Step 2: Run** `uv run pytest tests/core/test_paths.py -v` — Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `pyproject.toml` (name `overclocked-shell`, package `shell`, deps above, `[project.scripts] shell = "shell.cli:main"`, `shell-mcp = "shell.mcp.server:main"`, `[dependency-groups] dev = ["pytest"]`), `.gitignore` (`.env`, `profile/`, `cache/`, `.venv/`, `__pycache__/`), `.env.example` (`BUNGIE_API_KEY=`, `BUNGIE_CLIENT_ID=`, `BUNGIE_CLIENT_SECRET=`, commented `BUNGIE_REDIRECT_URL=`), `paths.py`. `README.md`: install (clone, register a Bungie app — confidential, redirect `https://localhost:7777/callback`, scopes read + move/equip items — copy `.env`, `uv sync`, `uv run shell auth login`, `claude mcp add overclocked-shell --scope user -- uv run --directory <abs path> shell-mcp`). `CLAUDE.md`: layout from the spec, "a new capability = a new module in sources/engines/outputs/mcp/tools; never edit core to add one", stories workflow (`stories/README.md`).
- [ ] **Step 4: Run** `uv run pytest -v` — Expected: PASS.
- [ ] **Step 5: Commit** `git add -A && git commit -m "Project skeleton and install-root paths"`

### Task 2: Settings

**Files:**
- Create: `shell/core/settings.py`
- Test: `tests/core/test_settings.py`

**Interfaces:**
- Consumes: `paths.env_file()`
- Produces: `@dataclass(frozen=True) Settings(api_key: str, client_id: str, client_secret: str, redirect_url: str)`; `load_settings(env_file: Path | None = None) -> Settings` (defaults to `paths.env_file()`; real environment variables win over the file); `class SettingsError(Exception)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_loads_from_file(tmp_path, monkeypatch):
    for k in ("BUNGIE_API_KEY", "BUNGIE_CLIENT_ID", "BUNGIE_CLIENT_SECRET", "BUNGIE_REDIRECT_URL"):
        monkeypatch.delenv(k, raising=False)
    env = tmp_path / ".env"
    env.write_text("BUNGIE_API_KEY=k\nBUNGIE_CLIENT_ID=1\nBUNGIE_CLIENT_SECRET=s\n")
    s = load_settings(env)
    assert (s.api_key, s.client_id, s.client_secret) == ("k", "1", "s")
    assert s.redirect_url == "https://localhost:7777/callback"

def test_missing_values_are_named(tmp_path, monkeypatch):
    ...  # same delenv; file with only BUNGIE_API_KEY=k
    with pytest.raises(SettingsError) as e:
        load_settings(env)
    assert "BUNGIE_CLIENT_ID" in str(e.value) and "BUNGIE_CLIENT_SECRET" in str(e.value)
    assert str(env) in str(e.value)
```

- [ ] **Step 2: Run** `uv run pytest tests/core/test_settings.py -v` — Expected: FAIL.
- [ ] **Step 3: Implement** with `dotenv_values(env_file)` merged under `os.environ` (do not mutate `os.environ`).
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "Settings from the install-root .env"` (add new files first).

### Task 3: Token store and OAuth

**Files:**
- Create: `shell/core/auth.py`
- Test: `tests/core/test_auth.py`

**Interfaces:**
- Consumes: `Settings`, `paths.profile_dir()`
- Produces:
  - `@dataclass Tokens(access_token: str, refresh_token: str, access_expires_at: float, refresh_expires_at: float, membership_id: str)` (epoch seconds).
  - `class NotSignedIn(Exception)` — message always ends with ``Run `uv run shell auth login`.``
  - `class OAuth(settings: Settings, token_file: Path | None = None, http: httpx.Client | None = None, clock: Callable[[], float] = time.time)` with `authorize_url(state: str) -> str`, `exchange_code(code: str) -> Tokens`, `access_token() -> str`, `status() -> dict` (`signed_in`, `membership_id`, `access_expires_at`, `refresh_expires_at` as ISO strings, `token_file`). Default token file `profile_dir() / "auth" / "tokens.json"`; save is atomic (write temp file, `os.replace`).

- [ ] **Step 1: Write the failing tests** (use `httpx.Client(transport=httpx.MockTransport(handler))` and a fake clock)

```python
def test_exchange_code_stores_tokens(tmp_path): ...
    # handler asserts Basic auth header == base64("1:s"), form grant_type=authorization_code, code=abc
    # returns {"access_token":"a","expires_in":3600,"refresh_token":"r","refresh_expires_in":7776000,"membership_id":"42"}
    assert json.loads(token_file.read_text())["membership_id"] == "42"

def test_access_token_refreshes_near_expiry(tmp_path): ...
    # stored access_expires_at = now + 60 → one POST with grant_type=refresh_token; returns new "a2"
    assert oauth.access_token() == "a2"

def test_access_token_cached_when_fresh(tmp_path): ...
    # access_expires_at = now + 600 → handler never called

def test_expired_refresh_raises_not_signed_in(tmp_path): ...
    with pytest.raises(NotSignedIn, match="uv run shell auth login"): oauth.access_token()

def test_no_tokens_raises_not_signed_in(tmp_path): ...

def test_missing_refresh_token_mentions_confidential(tmp_path): ...
    # token response without refresh_token → RuntimeError containing "Confidential"
```

- [ ] **Step 2: Run** `uv run pytest tests/core/test_auth.py -v` — Expected: FAIL.
- [ ] **Step 3: Implement** `auth.py` (behaviour mirrors destiny-zen `src/auth/oauth.ts`, reference only).
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Bungie OAuth with token refresh"`

### Task 4: Sign-in command

**Files:**
- Create: `shell/cli.py`, `shell/core/signin.py`
- Test: `tests/core/test_signin.py`

**Interfaces:**
- Consumes: `OAuth`, `load_settings`
- Produces: `parse_callback(path: str, expected_path: str, expected_state: str) -> str` (returns the code; raises `ValueError` on wrong path, missing code or state mismatch); `self_signed_cert(dir: Path) -> tuple[Path, Path]` (cert, key for `localhost` + `127.0.0.1`); `run_signin(settings: Settings, oauth: OAuth) -> Tokens` (HTTPS `http.server` on `127.0.0.1:<port>`, opens the authorize URL with `webbrowser`, serves one callback, prints the browser-warning hint, stops); `shell.cli.main()` with subcommands `auth login` and `auth status`.

- [ ] **Step 1: Write the failing tests**

```python
def test_parse_callback_ok():
    assert parse_callback("/callback?code=abc&state=xyz", "/callback", "xyz") == "abc"

@pytest.mark.parametrize("path", ["/callback?code=abc&state=bad", "/other?code=abc&state=xyz", "/callback?state=xyz"])
def test_parse_callback_rejects(path):
    with pytest.raises(ValueError): parse_callback(path, "/callback", "xyz")

def test_self_signed_cert_loads(tmp_path):
    cert, key = self_signed_cert(tmp_path)
    ssl.create_default_context(ssl.Purpose.CLIENT_AUTH).load_cert_chain(cert, key)
```

- [ ] **Step 2: Run** `uv run pytest tests/core/test_signin.py -v` — Expected: FAIL.
- [ ] **Step 3: Implement.** Cert/key written under `profile/auth/`; reject a non-`https://localhost|127.0.0.1` redirect with a clear message; port in use → message naming the port and `BUNGIE_REDIRECT_URL`.
- [ ] **Step 4: Run** tests — PASS. Then manual check: `uv run shell auth login` with the real `.env` → browser flow completes, `uv run shell auth status` prints `signed_in: True`.
- [ ] **Step 5: Commit** `git commit -m "Sign-in command with local HTTPS callback"`

### Task 5: Bungie client and manifest

**Files:**
- Create: `shell/core/bungie.py`, `shell/core/manifest.py`
- Test: `tests/core/test_bungie.py`, `tests/core/test_manifest.py`

**Interfaces:**
- Consumes: `Settings`, `OAuth`, `paths.cache_dir()`
- Produces:
  - `class BungieApiError(Exception)` with `.error_code: int | None`, `.status: str | None`.
  - `class BungieClient(settings: Settings, oauth: OAuth | None, http: httpx.Client | None = None, sleep: Callable[[float], None] = time.sleep)` with `get(path: str, params: dict | None = None, auth: bool = False) -> Any` and `post(path: str, body: dict) -> Any` (always authenticated). Both prefix `https://www.bungie.net/Platform`, return the unwrapped `Response`, raise `BungieApiError` when `ErrorCode != 1`.
  - `class Manifest(client: BungieClient, cache_dir: Path | None = None)` with `version() -> str` and `table(name: str) -> dict[str, dict]` (memoized per instance; files at `cache/manifest/<version>/<name>.json`, written atomically; older version folders deleted when a new version is downloaded).

- [ ] **Step 1: Write the failing tests**

```python
def test_get_unwraps_and_sends_api_key(): ...   # handler asserts X-API-Key == "k"; returns {"ErrorCode":1,"Response":{"x":1}}
def test_auth_get_sends_bearer(): ...           # fake OAuth.access_token() -> "a"; header "Bearer a"
def test_error_code_raises(): ...               # {"ErrorCode":1601,"ErrorStatus":"DestinyAccountNotFound"} → BungieApiError.error_code == 1601, no retry
def test_throttle_retried_then_ok(): ...        # first {"ErrorCode":36,"ThrottleSeconds":2}, then ok → sleep called with 2
def test_maintenance_gives_up_after_3_retries(): ...  # always ErrorCode 5 → 4 calls total, BungieApiError(5)
def test_http_503_retried(): ...

def test_table_downloads_once_per_version(tmp_path): ...  # second Manifest instance reads file, no HTTP for the table
def test_new_version_removes_old_folder(tmp_path): ...
def test_no_partial_file_on_failure(tmp_path): ...       # table download raises → no <name>.json left behind
```

- [ ] **Step 2: Run** `uv run pytest tests/core -v` — Expected: new tests FAIL.
- [ ] **Step 3: Implement.** Retry on ErrorCode 5/35/36 and HTTP 5xx / timeouts: up to 3 retries, wait `max(ThrottleSeconds, 2**attempt)`. The manifest index (`/Destiny2/Manifest/`) is fetched once per instance; table files come from `https://www.bungie.net` + `jsonWorldComponentContentPaths.en[name]`.
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "Bungie client with retries and manifest cache"`

### Task 6: MCP server with tool discovery

**Files:**
- Create: `shell/context.py`, `shell/mcp/__init__.py`, `shell/mcp/server.py`, `shell/mcp/tools/__init__.py`, `shell/mcp/tools/account.py`
- Test: `tests/mcp/test_server.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `@dataclass Context` with lazily built `settings`, `oauth`, `client`, `manifest` (`functools.cached_property`), so the server starts even when `.env` is incomplete.
  - Tool module contract: each module in `shell/mcp/tools/` defines `register(mcp: FastMCP, ctx: Context) -> None`. `build_server(ctx: Context) -> FastMCP` imports every module of the package via `pkgutil.iter_modules` and calls `register`. `main()` runs it over stdio.
  - Tools in `account.py`: `auth_status() -> dict` (= `OAuth.status()`); `get_profile_summary() -> dict` — `GET /User/GetMembershipsForCurrentUser/` (auth), picks `primaryMembershipId`'s membership (else the first), then `GET /Destiny2/{type}/Profile/{id}/?components=200` → `{"display_name", "membership_type", "membership_id", "characters": [{"character_id", "class", "light"}]}` with class names from `DestinyClassDefinition`.
  - `NotSignedIn` and `SettingsError` raised inside a tool become a one-line tool error with their message (no traceback).

- [ ] **Step 1: Write the failing tests**

```python
def test_discovers_tools():
    names = {t.name for t in asyncio.run(build_server(Context()).list_tools())}
    assert {"auth_status", "get_profile_summary"} <= names

def test_not_signed_in_is_one_line(monkeypatch):
    # Context whose oauth.access_token raises NotSignedIn
    # call_tool("get_profile_summary") → error text contains "uv run shell auth login" and no "Traceback"

def test_profile_summary_shape(): ...  # Context with BungieClient on MockTransport + fake Manifest.table("DestinyClassDefinition")
```

- [ ] **Step 2: Run** `uv run pytest tests/mcp -v` — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -v` — PASS. Manual: register with `claude mcp add overclocked-shell --scope user -- uv run --directory D:\Projects\overclocked-shell shell-mcp`, restart Claude Code in another folder, ask "what are my characters?" → `get_profile_summary` answers.
- [ ] **Step 5: Commit** `git commit -m "MCP server with tool discovery and account tools"`; move stories S-001…S-004 to `stories/done/`.
