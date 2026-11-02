# S-040 — Armor coverage: what the vault is missing

**Epic:** E11 Ideas from DIM and co · **Follows:** S-012

## Why
The triage says which pieces to keep, not which holes remain. Its goal is to be able to aim at any build, so the next
question is which set and stat distributions the player cannot reach yet. `Mijago/D2ArmorPicker` has cluster and
investigation pages along those lines.

## Acceptance criteria
- [ ] `armor_coverage(class_type)` returns, per set and slot, the distributions owned (archetype, tertiary) and the ones
      missing, using the same grouping as the triage
- [ ] Only pieces the triage keeps count
- [ ] Legacy armor is left out, as in the triage
- [ ] Results can be narrowed to one set
- [ ] The `todo` skill can turn a hole the player cares about into a farm need
- [ ] `uv run pytest` passes
