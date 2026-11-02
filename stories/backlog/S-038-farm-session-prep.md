# S-038 — Get ready for a farm session

**Epic:** E11 Ideas from DIM and co

## Why
A full character sends drops to the postmaster, and a full vault blocks every transfer. Shell tracks neither. DIM's farming
mode keeps room open with a running loop (`src/app/farming/actions.ts`); a one-off action before the session gives most of
the value, so no background process.

## Acceptance criteria
- [ ] A read tool returns vault and character bucket use against their capacity, plus what sits in the postmaster
- [ ] `prepare_farm(character, free_slots)` previews moving unequipped items to the vault to leave that many free slots
      per bucket; `dry_run=false` applies it, with the same preview rule as `transfer_items`
- [ ] Locked and equipped status never changes, and nothing is dismantled
- [ ] A vault too full for the moves is reported before anything moves, pointing at the triage
- [ ] The `todo` skill offers it when the player starts a farm
- [ ] `uv run pytest` passes
