# S-037 — Richer inventory search

**Epic:** E11 Ideas from DIM and co

## Why
`find_armor` filters on class, slot, name and rarity only, so "my locked T5 Helmets with high Discipline in the vault" means
paging through results by hand, which is slow and costs tokens. DIM has around a hundred filters
(`src/app/search/items/search-filters/`). Claude only needs plain parameters for the common ones, not a query language.

## Acceptance criteria
- [ ] `find_armor` also filters on set, gear tier, minimum per stat, tuning, masterworked, locked and location
- [ ] `find_weapons` also filters on frame, gear tier, crafted, masterworked, locked and location
- [ ] Both can return duplicates only, as DIM's `is:dupe`
- [ ] Both can return only items used by a saved build, as DIM's `is:inloadout`
- [ ] Calls without the new parameters return what they return today
- [ ] `uv run pytest` passes
