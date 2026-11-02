---
name: share-build
description: Share a saved Destiny 2 build sheet (profile/builds/*.json) — a printable PDF and / or a DIM loadout link a friend opens in DIM to get the gear, subclass and mods. Use when the player wants to print, send, export or share a build, or get it into DIM.
---

# Share a build

Voice: speak as the player's Ghost — see [ghost-voice.md](../../ghost-voice.md) (French when the player writes French).

1. **Pick the sheet** (list `profile/builds/*.json` if the player doesn't name it). `check_build(slug)`: if it
   reports problems, say so before sharing — a friend gets exactly what the sheet says.
2. **What they want:** a PDF (to print or send as a file), a DIM link (to open in DIM), or both. Default: both.
3. **PDF:** `build_pdf(slug)` (in-game layout with icons, the build as designed: the intent, not the player's
   substitutes; the first export downloads the icons, later ones work offline). Give the file path. A "no Unicode
   font" warning means some symbols were simplified (≥ became >=).
4. **DIM link:** `refresh_inventory()` first (the link uses the resolved pieces' instance ids), then
   `build_dim_link(slug)`. Give the link, then say in one or two lines what it does not carry:
   - weapon perks: the friend's copies have their own rolls; the wanted perks are in the loadout notes;
   - the artifact and set bonuses: in the notes too;
   - any `warnings` (a piece no longer in the inventory, an unknown mod: left out, named in the notes).
   Opening the link in DIM shows the loadout; nothing is equipped until the person applies it in DIM.
5. **Never post the link or the PDF anywhere yourself** (Discord, Reddit, email): hand them to the player.
