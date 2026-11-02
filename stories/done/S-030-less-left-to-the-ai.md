# S-030 — Mechanical steps done by the tools, not by Claude

**Epic:** E1 Foundation · **Follows:** S-029

## Why
The Python engines give the same result every time; the variation comes from what the skills leave to Claude: ordering
seven write calls by hand, date arithmetic on an index file, grepping Markdown for a name, comparing results by eye. The
player gets the same answer more often, for fewer tokens, when the tools do those steps.

## Acceptance criteria
- [x] `equip_build(slug)` previews a sheet's writes and returns a `confirm` code; `dry_run=false` needs that code,
      refuses a plan that changed since the preview and a snapshot over 15 minutes old, runs the writes in order and
      stops at the first real failure, saying what was done
- [x] `refresh_references(max_age_days=N)` skips a source with fresh data; the skills no longer compute dates
- [x] `compendium_lookup(name)` finds every copy of an entry whatever the spelling, flags a partial match, suggests
      close names; the `compendium` skill uses it
- [x] `optimize_build` results carry `vs_resolved`: pieces replaced, mods changed, stats gained or lost
- [x] `weapon_options` gives a `suggested` option per column with choices, the same for the same weapon
- [x] `rankings` shows 25 lines by default; `create-build` asks for more where it compares everything
- [x] A plan no longer reports "no free socket" when the asked plugs are installed in another order
- [x] `uv run pytest` passes
- [ ] `equip_build` tried in game: preview, then a run in orbit
