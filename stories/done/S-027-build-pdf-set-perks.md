# S-027 — Build PDF set bonus perks

**Epic:** E8 Build sharing · **Spec:** docs/specs/2026-10-31-build-pdf-showcase-design.md (follows S-026)

## Why
The set box of the build PDF only says which set and how many pieces. A friend reading it wants to know what the set
does: the perk name per piece count, with its icon, as the game shows it.

## Acceptance criteria
- [x] The set perks come from the manifest (`DestinyEquipableItemSetDefinition` → `DestinySandboxPerkDefinition`), for
      `resolved.sets` or else `intent.sets`; only the perks the piece count activates
- [x] The set box lists "2 Piece | <perk>" lines; the active perk icons sit under the stats column
- [x] Their icons are cached like the others (`setperk:<name>`); an unknown set warns and never fails the export
- [x] `warlock-prismatic-getaway-buddy` shows Taken Barrier and Taken Armaments with their icons
