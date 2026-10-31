# S-026 — Build PDF showcase

**Epic:** E8 Build sharing · **Plan:** docs/plans/2026-10-31-build-pdf-showcase.md ·
**Spec:** docs/specs/2026-10-31-build-pdf-showcase-design.md

## Why
The build PDF goes to friends and other players. It should look appealing and be laid out like the game's own
Character and subclass screens, with the real icons, so a player follows it without thinking.

## Acceptance criteria
- [x] Page 1 is A4 landscape in the in-game layout: subclass panel top left, weapons down the left (perks on one row,
      weapon mod on a row below), artifact bottom left, armor down the right (mods on one row), stats column, build
      text in the middle
- [x] Every item, perk, mod, ability, aspect, fragment, artifact perk and stat shows its manifest icon
- [x] Text that doesn't fit the middle continues on page 2
- [x] A missing icon, a missing inventory snapshot or Bungie being unreachable never fails the export (placeholder +
      warning); a sheet exported once re-exports offline with its icons
- [ ] `warlock-prismatic-getaway-buddy` exported and checked by eye against the approved mockup
