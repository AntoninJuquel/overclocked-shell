# S-034 — Read catalysts, triumphs and materials from the account

**Epic:** E11 Ideas from DIM and co

## Why
Shell never asks Bungie for records (900), item objectives (301) or profile currencies (103), and catalyst needs in the
TODO come from what the sheets declare. The player ends up being told to farm something already done, or to masterwork
with materials they lack. DIM reads all of it (`src/app/records/catalysts.ts`, `src/app/material-counts/`).

## Acceptance criteria
- [ ] A read tool returns, for owned exotic weapons, whether the catalyst is missing, in progress (with its objective) or
      complete
- [ ] A read tool returns the materials and currencies needed for masterworks, with their counts
- [ ] A read tool returns a triumph or seal's progress by name
- [ ] `farm_needs` settles a catalyst need by itself once the account shows it complete
- [ ] `equip_plan` and `optimize_build` say when `masterwork_todo` is more than the player can afford
- [ ] Costs come from the manifest, not from hard-coded values
- [ ] `uv run pytest` passes
