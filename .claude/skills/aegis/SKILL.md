---
name: aegis
description: Aegis's Destiny 2 PvE endgame ratings — tiers and ranks of legendary and exotic weapons (with recommended perks and origin traits), perks, origin traits, set bonuses, artifact mods, aspects, fragments, subclasses, sustained and swap DPS, boss health, and his Shopping List (what to farm). Use whenever a build choice or an answer depends on what is viable or best, instead of relying on memory.
---

# Aegis (Endgame Analysis, Boss Damage)

Aegis's two spreadsheets (https://www.destiny2.science/) are converted in `cache/aegis/` (not versioned: their
author's content): `endgame/` (Endgame Analysis) and `boss/` (Boss Damage), one `.md` per tab for reading and one
`.json` for code. These are **ratings** (PvE endgame); exact game values come from the Compendium (`compendium`
skill).

1. If `cache/aegis/index.md` is missing or its "Oldest data" is more than 7 days old:
   `refresh_references(source="aegis", force=true)` (`tabs: ["<tab>"]` for some tabs). Relay to the player the
   `changed` lines that start with a build slug (`<build>: <tab> — <name>: …`, i.e. changes touching their builds
   in `profile/builds/`; detail in `cache/aegis/changes.md`) and offer to re-optimize those builds. `changes.md`
   is overwritten on every refresh: relay the "Builds concerned" right after a refresh, or the list is lost at
   the next one. Mention any `errors` and `unhandled` tabs.
2. Read `cache/aegis/index.md`: each tab's file, the date Aegis updated it, its state. Flag a failed or old tab
   the answer relies on.
3. Search without loading the whole tab: `grep -n -e "^## " -e "^### <name>" cache/aegis/<folder>/<file>.md`,
   then read only that section; by keyword: `grep -n -i "<word>" cache/aegis/*/*.md`. A name can repeat
   (versions of a weapon: "Zaouli's Bane" ×2; firing modes in Boss Damage): compare the attributes.
4. Quote "Aegis, tab …, updated on …"; keep his terms (tiers S > A > B > C > D > E > F, `#` = rank in the tab,
   the file's "Legend" section for his symbols).

Useful files:
- `endgame/weapons-<type>.md` (autos, bows, hcs, pulses, scouts, sidearms, smgs, bgls, fusions, glaives,
  shotguns, snipers, rocket-sidearms, traces, hgls, lfrs, lmgs, rockets, swords, other): `Energy`, `Frame`,
  `Source`, recommended perks (`Barrel`, `Mag`, `MW`, `Perk 1`, `Perk 2`, `Origin Trait`), `Notes`, `#`, `Tier`;
  `endgame/exotic-weapons.md` (`Roam`, `DPS`, `Chall`, `Speed`, `Usage`, `Tier`).
- `endgame/perks.md`, `origin-traits.md`, `set-bonuses.md` (`Bonus`, `Pcs`), `artifact-mods.md`
  (`Tier (ANALYSIS)` = Aegis's rating, `Tier (INFO)` = artifact column), `fragments.md`, `aspects.md`
  (`Subclass`, `Class`: H, T, W), `subclasses.md` (`Class`, `Super`, `Usage`, `Tier`).
- `endgame/shopping-list.md`: what to farm (`Role`, `Source`, `Priority`: high / medium / low / niche,
  `Column 1` / `Column 2` = wanted perks or archetypes, `Alternatives`); `archetypes.md`, `encounters.md`,
  `status.md` (state and last update of each tab, Aegis's announcements).
- `boss/sustained.md` and `boss/swap.md` (DPS per weapon or ability: `DPS`; `swap DPS`, `true DPS`),
  `boss/weapons.md` and `boss/abilities.md` (base damage), `boss/bosses.md` (health, mechanics, phases),
  `boss/fireteam.md` (rotations), `boss/bolt-charge.md`, `boss/pack-hunter.md`.

If a tab fails ("headers not found", "key column not found", "rows found"), the layout changed: the old file is
kept; fix the tab's `TabSpec` in `shell/sources/aegis/config.py` and `tests/sources/aegis/test_aegis_live.py`
(`uv run pytest`).
