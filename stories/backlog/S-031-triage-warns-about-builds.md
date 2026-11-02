# S-031 — Triage warns about items used by builds

**Epic:** E11 Ideas from DIM and co

## Why
`equip_build` locks a build's items, and a triage can then unlock them: it only looks at quality, on purpose. A player who
next dismantles `tag:junk` in DIM breaks a build without being told. DIM can always see this with `is:inloadout`. The rule
stays; the player just gets to see the consequence.

## Acceptance criteria
- [ ] `triage_armor` and `triage_weapons` list every JUNK item used by a saved build sheet, with the sheets using it
- [ ] Decisions do not change: such an item stays JUNK and `apply_triage` still unlocks it
- [ ] The `armor-triage` and `weapon-triage` skills show that list to the player before applying
- [ ] The DIM CSV note of such an item names its builds
- [ ] A triage with no saved build, or a sheet that names an item the player no longer owns, still works
- [ ] `uv run pytest` passes
