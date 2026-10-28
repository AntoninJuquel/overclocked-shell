---
name: dim-export
description: Generate a DIM-importable CSV of tags (keep / junk) and notes from the armor and weapon triage results. Use when the player wants to see the triage in DIM, export tags or import into DIM.
---

# Export tags to DIM

Voice: speak as the player's Ghost — see [ghost-voice.md](../../ghost-voice.md) (French when the player writes French).

1. Check that a recent triage exists (`profile/triage/armor.json` and / or `weapons.json`). Otherwise run the
   `armor-triage` / `weapon-triage` skills first (at least up to the triage tool).
2. `export_dim_tags` → `profile/triage/dim_tags.csv` (KEEP → `keep`, JUNK → `junk`, note = `shell: <reason>`
   + set / wishlist grade).
3. Warn the player **before** they import: DIM replaces each imported item's note with the `Notes` column (an
   empty note erases theirs) and overwrites the existing tag (e.g. a `favorite` becomes `keep`).
   `notes: false` does not prevent erasing notes, it only writes empty ones.
4. Give the steps: DIM → Settings → Spreadsheets → import tags and notes → pick `profile/triage/dim_tags.csv`.
   Then `tag:junk` in DIM's search lists what can go.
