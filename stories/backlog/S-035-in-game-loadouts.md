# S-035 — In-game loadout slots

**Epic:** E11 Ideas from DIM and co · **Follows:** S-030

## Why
A saved build needs Claude to get back on the character. Written into an in-game loadout slot, it is one button away in
the game itself. DIM reads and writes those slots (`src/app/loadout/ingame/`); Shell ignores them (no component 206, no
`Actions/Loadouts` calls).

## Acceptance criteria
- [ ] A read tool lists a character's in-game slots: name, icon, colour and the items in each
- [ ] A tool saves what is currently equipped into a slot (`SnapshotLoadout`), with a dry run, naming what it overwrites
- [ ] A tool equips a slot (`EquipLoadout`) and a tool clears one (`ClearLoadout`), each with a dry run
- [ ] A slot can get its name, icon and colour (`UpdateLoadoutIdentifiers`)
- [ ] The `equip-build` skill offers to save the build in a slot once it is equipped, since a snapshot only takes what is
      worn
- [ ] Bungie refusals, such as an activity that blocks the change, reach the player in plain words
- [ ] `uv run pytest` passes
- [ ] Tried in game: save a build in a slot, change gear, equip the slot
