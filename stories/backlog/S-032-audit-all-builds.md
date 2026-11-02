# S-032 — Audit every saved build

**Epic:** E11 Ideas from DIM and co

## Why
Builds rot quietly: an item is dismantled, a mod retires, a better piece drops. `check_build`, `equip_plan` and
`optimize_build` can each tell, one build at a time. DIM's Loadout Analyzer (`src/app/loadout-analyzer/types.ts`) shows the
value of asking all at once: the player learns which builds need attention without opening them one by one.

## Acceptance criteria
- [ ] `audit_builds` reads the snapshot once and returns, per sheet, a list of findings; it writes nothing
- [ ] Findings cover: missing items, invalid mods or plugs, empty or excess fragment slots, armor needing a masterwork,
      stat minimums not met, seasonal mods at risk, strictly better stats available
- [ ] "Strictly better" means every stat is equal or higher, with the build's exotic and set bonuses kept
- [ ] Reuses `check_build`, `equip_plan` and `optimize_build` logic instead of repeating their rules
- [ ] A sheet that cannot be analyzed reports why, and the audit carries on with the others
- [ ] A skill (new, or `optimize-build`) answers "are my builds still good?" from it
- [ ] `uv run pytest` passes
