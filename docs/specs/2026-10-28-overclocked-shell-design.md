# Overclocked Shell — design

Date: 2026-10-28 · Status: draft for review

## Intent

dim-agent became genuinely useful: Claude Code skills + Python scripts that triage the Destiny 2 vault, design /
optimize / equip builds, and produce a weekly farm TODO, backed by local reference data (Data Compendium, Aegis
spreadsheets, Bungie OpenAPI docs). It depends on **destiny-zen**, an external TypeScript MCP server vendored as a
submodule (Node build, a patched branch for the tuning stat waiting on a PR, user-level MCP registration, data
exchanged through export files on disk).

**Overclocked Shell** is the rewrite: a self-contained Destiny 2 companion, "your Ghost on steroids". The player
still talks to Claude Code; the project ships its own tools (its own MCP server talking to Bungie directly) and
skills, and is structured so new capabilities are added without touching the core.

## Goals

1. **Own Bungie layer.** OAuth, API client, manifest cache, profile reads and item actions — no destiny-zen.
2. **Feature parity with dim-agent** (first milestone, nothing new):
   - Vault cleanup: armor triage (best copy per stat distribution and set, projected masterwork stats, legacy
     excluded), weapon triage against a DIM wishlist (default Aegis, grade ≥ B), lock / unlock only — never
     dismantle; DIM tags CSV export.
   - Builds: build sheet (`.json` source of truth + `.md` view), "best in theory" design checked against game rules,
     optimizer on the current inventory (1 exotic + 4 legendaries, stat & tuning mods, all characters + vault),
     equip in game with dry run, locks and stat check.
   - Farm TODO: needs from builds + Aegis Shopping List vs inventory, weekly context (Portal focus, bonuses,
     vendors), dated TODO, statuses (todo / done / ignored).
   - Reference knowledge: Compendium, Aegis (with change tracking against builds), Bungie API docs.
3. **Extensible by construction.** Every future feature below must fit as a new *source*, *engine*, *output* or
   *tool* without core changes.
4. **Cloneable template.** Built for one player, but a fresh clone + own Bungie app + `.env` + one command gives
   another player a working setup with their Claude Code.
5. **Ghost personality.** Skills answer as a companion who knows the player's gear, not as a script runner.

### Future features (drive the architecture, not in the first milestone)

- **Situational recommender:** "best weapon / pick for this situation", accounting for what is currently equipped.
- **Fashion / wardrobes:** cosmetic loadouts (shaders, ornaments), inspiration fetched online (Reddit, posts).
- **More references:** additional tier lists and data sources.
- **PDF builds** and **shareable builds** (link; DIM loadout link where possible).
- **Ultimate Bravery builds:** random builds in the spirit of ultimate-bravery.net, respecting game rules.
- **Raid companion:** teaches encounter mechanics on demand, step by step, with schematics (room maps, roles,
  callouts) and real situations ("6 players, I'm on adds, what do I do in phase 2?"). Mechanics and maps are
  fetched from online guides and turned into structured data.

## Non-goals

- A GUI / standalone app. The interface is Claude Code chat.
- Multi-user hosting, accounts, servers. Single player per clone.
- New features in the first milestone (parity first).
- Publishing third-party content (Compendium, Aegis, guides): it stays local, gitignored, owned by its authors.

## Anti-goals (failure even if it works)

- Anything that dismantles items or acts on the account without the player's explicit go-ahead (dry run first for
  writes, as today).
- A core that must be edited to add a source / engine / output / tool.
- Setup that needs a build step, a submodule, or patching a dependency.
- The player's personal data (builds, TODO, statuses, tokens) ending up in the repo.

## Constraints

- Windows 11 primary machine; must also run on macOS / Linux (template users).
- Bungie API: OAuth confidential client (API key, client id, client secret in `.env`), tokens refreshed
  automatically; respect rate limits; reference docs already converted in dim-agent's `data/bungie-api/`.
- Existing behaviour and data formats of dim-agent are the spec for parity (its README, skills, `docs/game-rules.md`,
  build sheets, `todo/` files, tests).

## Decisions

Decided by the player:
- Name **Overclocked Shell**, repo `overclocked-shell`, new folder `D:\Projects\overclocked-shell`, fresh git repo.
- Interface stays Claude Code; the project provides its own tools.
- Port dim-agent piece by piece; keep dim-agent working until Shell replaces it; carry over the player's data
  (builds, TODO history and statuses).
- Personal data in a **gitignored** `profile/` folder (not versioned).
- Stories as **Markdown files in the repo**.
- Raid mechanics and maps fetched from online guides.
- **English** for skills, generated files (build sheets, TODO, DIM notes) and docs; the Ghost may still answer in
  French when the player writes in French. Ported dim-agent tests checking French strings are rewritten.

Claude's calls (player saw them, can still override):
- **Python 3.12**, reusing the ~12k lines of dim-agent Python; official `mcp` Python SDK for the server; `uv` to run
  (no build step). Third-party dependencies allowed where they earn their place (MCP SDK, HTTP client, PDF later) —
  dim-agent's "zero dependency" rule is dropped.
- Skills remain the per-task playbooks; tools are thin wrappers over engines and return results directly (no
  export files as the hand-off between Claude and code).
- Layout:

```
overclocked-shell/
├─ shell/                  # Python package
│  ├─ core/                # Bungie OAuth, API client, manifest cache, settings, profile paths
│  ├─ sources/             # pluggable reference data: compendium, aegis, bungie-api, guides, reddit…
│  ├─ engines/             # triage, optimizer, todo, recommender, bravery, raid…
│  ├─ outputs/             # md, pdf, share link, DIM csv/link, schematics (svg)
│  └─ mcp/                 # MCP server: tools Claude calls
├─ .claude/skills/         # playbooks + Ghost voice
├─ stories/                # backlog/ · doing/ · done/ — one .md per story
├─ docs/                   # design, ADRs, game rules
├─ examples/               # sample builds / profile for a fresh clone
├─ profile/                # player data (builds, todo, statuses) — gitignored
├─ cache/                  # downloaded / converted data, manifest — gitignored
└─ tests/
```

- Extension points, each a small interface discovered by registration (not by editing a central switch):
  - **Source:** fetch → normalize → store in `cache/`, report what changed; queryable by tools.
  - **Engine:** pure domain logic over core data + sources.
  - **Output:** renders a domain object (build, TODO, raid encounter…) to a format.
  - **Tool:** MCP wrapper exposing an engine / source / output to Claude.
- **Single cutover.** dim-agent owns the live data (builds, `todo/` files) until Shell reaches parity; Shell
  develops against a copy in its `profile/`; the last parity story re-imports the latest dim-agent data and the
  player switches. No sync between the two in the meantime.
- **MCP registration at user scope** (as destiny-zen is today), so Bungie tools stay available in other projects;
  the server resolves `.env`, `profile/` and `cache/` from its own install folder, not the launch folder.
- **Writes:** asking for a triage is the go-ahead for its lock / unlock batches (reversible, as today); equip,
  sockets / perks, transfers and postmaster keep a dry-run preview the player validates.
- **No backup of `profile/`** beyond the player's own: gitignored means not versioned, and dim-agent's git history
  for builds / TODO stays in dim-agent.
- Story file: title, goal (why), acceptance criteria, status (= folder), epic. First epics: core & auth, read tools,
  write tools, port of each dim-agent feature, then one epic per future feature.

## Left to the builder

- Exact interfaces of source / engine / output / tool, and how registration works.
- HTTP client, manifest storage format (SQLite as Bungie ships it, or JSON), token storage location.
- Mapping of the ~10 destiny-zen tools dim-agent uses (`export_armor`, `export_weapons`, `export_context`,
  `set_lock`, `equip_items`, `set_sockets`, `set_perks`, `get_equipped`, `get_artifact`, `pull_from_postmaster`)
  to Shell tools; whether to read destiny-zen source for reference.
- Order of the porting stories, test strategy (port dim-agent's pytest suite), story template details.
- Ghost voice guidelines (tone).
