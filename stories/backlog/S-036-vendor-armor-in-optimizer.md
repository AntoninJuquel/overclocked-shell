# S-036 — Vendor armor in the optimizer

**Epic:** E11 Ideas from DIM and co

## Why
`week_context` knows vendors' gear and `optimize_build` only knows owned armor, so "buy this piece, your build gains 10"
is never said. DIM's optimizer can include vendor items (`src/app/loadout-builder/loadout-builder-vendors.ts`).

## Acceptance criteria
- [ ] `optimize_build` gets an option to include armor sold this week; it stays off by default and existing calls behave
      as before
- [ ] A result using a vendor piece names the vendor, the price and when it leaves
- [ ] Vendor pieces use their real rolled stats; a piece without readable stats is left out and counted in `warnings`
- [ ] `write` refuses a result with a piece the player does not own yet, and says why
- [ ] A stale context is reported in `warnings`, as `week_context` does
- [ ] The `optimize-build` skill and the TODO mention the purchase when it beats owned armor
- [ ] `uv run pytest` passes
