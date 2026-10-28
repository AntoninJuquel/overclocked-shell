---
name: compendium
description: Exact Destiny 2 values and mechanics (weapon perks, exotics, armor mods, set bonuses, fragments, aspects, abilities, cooldowns, activity modifiers) from the Destiny Data Compendium converted to Markdown. Use whenever an answer or a build depends on a game value, instead of relying on memory.
---

# Destiny 2 Compendium

The community "Destiny Data Compendium" (Google Sheets) is converted to Markdown in `cache/compendium/`
(not versioned: its author's content).

1. If `cache/compendium/index.md` is missing or its "Oldest data" is more than 7 days old:
   `refresh_references(source="compendium", force=true)` (`tabs: ["<tab>"]` for a single tab). Mention to the
   player any `errors`, and any `unhandled` tab (the author added a tab nobody parses yet).
2. Read `cache/compendium/index.md`: it gives each tab's file and state. Tell the player about any failed or
   old tab the answer relies on.
3. Find the entry without loading the whole tab:
   `grep -n -e "^## " -e "^### <name>" cache/compendium/<file>.md`, then read only that section (up to the next
   `###` or `##`). The same name can appear in several sections (artifacts, classes, variants) and repeat inside
   one section (e.g. "Aggressive Frame" ×5, told apart by `detail`; "Air Superiority" ×2, by `group`): check
   `section` and the other attributes of every hit. Keyword search: `grep -n -i "<word>" cache/compendium/*.md`.
4. Some sections have a `### Notes` entry (author's remarks): read it when it concerns the question (e.g. exotic
   class item perks active only in Prismatic; enhanced mods only on Tier 4-5 weapons; catalyst traits at base
   values).
5. Quote the value saying it comes from the Compendium, with its fetch date. Keep the conventions as they are
   (`X [Y]` = PvE [PvP], `↑` = enhanced, `?` = unconfirmed: see the index).

Useful files and attributes:
- `exotic-armors.md`: `perk`; `exotic-weapons.md`: `perks`, `catalyst`, `subtitle`, `note`;
  `exotic-class.md`: `role` (left = archetype, right = tertiary stats).
- `armor-mods.md`: `energy` cost, `variant`, `activity`; `armor-perks.md`: set bonuses `2 pieces` / `4 pieces`,
  `source`, `crucible` (bonus disabled in Crucible).
- `weapon-perks.md`: `detail`, `source` (origin traits).
- `artifact-perks.md`: `order` (1 = listed first, probably the current season: the sheet has no explicit
  marker), `column`, `elements`, `weapons`.
- `subclass-<element>.md` (Arc, Solar, Void, Stasis, Strand, Prismatic): glossary, fragments (`stats`), aspects,
  abilities and supers (`info`: cooldowns, tiers). `class-abilities.md`. `subclass-prismatic.md`: also `note`.
- `game-mechanics.md`: `group`, `detail`, numeric tables (stat thresholds, etc.).

Limits: the author hides some rows, missing from the public view (counted in the index). Aspect fragment slots
are an image in the sheet: not captured (they are in the Bungie manifest). If an expected entry is missing, say
so rather than invent the value.

If a tab fails ("anchor not found", "entries found"), the sheet layout changed: the old file is kept; fix the
parser `shell/sources/compendium/parsers/<tab>.py` with a test (`uv run pytest`).
