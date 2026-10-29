# Overclocked Shell

Destiny 2 companion for Claude Code: a Python MCP server (`shell/mcp`, declared in `.mcp.json`) plus skills
(`.claude/skills/`).
Design: `docs/specs/2026-10-28-overclocked-shell-design.md`. Everything is written in English.
When talking to the player about their Destiny 2 account, speak as their Ghost: `.claude/ghost-voice.md` (French when
they write French).

## Layout

- `shell/core/` — paths, settings, Bungie OAuth, API client, manifest cache
- `shell/sources/` — pluggable reference data (fetch → normalize → `cache/` → what changed)
- `shell/engines/` — domain logic (triage, optimizer, todo…)
- `shell/outputs/` — renderers (md, pdf, share links, DIM, svg)
- `shell/mcp/tools/` — one module per tool group, each with `register(mcp, ctx)`
- `profile/` (player data, tokens) and `cache/` are gitignored; paths resolve from the install root (`shell.core.paths`)

**A new capability is a new module** in sources / engines / outputs / mcp/tools. Never edit core to add one.

## Work

Stories live in `stories/` (see `stories/README.md`); move a story to `doing/` when starting, `done/` when its
acceptance criteria pass. Tests: `uv run pytest`. Writes to the player's account need a dry run first, except
lock / unlock asked for by a triage.
