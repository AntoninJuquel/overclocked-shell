# S-033 — Undo an equip

**Epic:** E11 Ideas from DIM and co · **Follows:** S-030

## Why
`equip_build` changes items, subclass, mods and perks in one go, and nothing brings the old setup back. DIM saves the
current state before applying a loadout and offers to undo it (`src/app/loadout-drawer/loadout-apply.ts`). That makes
trying a build cheap, which matters most for Ultimate Bravery and fun builds.

## Acceptance criteria
- [ ] A real `equip_build` run first saves the character's equipped items, subclass, artifact and plugs in `profile/`
- [ ] A dry run saves nothing
- [ ] `undo_equip(character)` previews the restore and returns a `confirm`; `dry_run=false` needs it, like `equip_build`
- [ ] Items or plugs that are no longer available are reported and skipped; the rest is restored
- [ ] Only the latest state per character is kept
- [ ] The `equip-build` skill offers the undo after equipping
- [ ] `uv run pytest` passes
- [ ] Tried in game: equip a build in orbit, undo, get the previous setup back
