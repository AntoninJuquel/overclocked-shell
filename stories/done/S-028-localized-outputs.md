# S-028 — Game names in the player's language

**Epic:** E1 Foundation · **Follows:** S-026, S-027

## Why
The player plays Destiny 2 and DIM in French, but Shell's outputs mix languages: French text from the Ghost with
English game names ("Tenir la Storm Grenade…", "Hood of the Great Hunt", "Helmet", "Grenade Mod"). Like DIM, the names
should come from the Bungie manifest in the player's language, so a sheet, a PDF or an answer uses the words the
game shows.

Saved data stays canonical English (build JSON, triage, TODO, Aegis and compendium caches): matching against English
sources depends on it. Names are translated only when shown.

## Acceptance criteria
- [x] `SHELL_LANGUAGE` in `.env` (default `en`; one of Bungie's manifest languages, as in DIM's settings)
- [x] The manifest downloads a table in a given language; each language caches in its own folder, and a new version
      only replaces that language's folder
- [x] A lexicon (English name → localized name, by hash) is built once per manifest version from items, plugs, stats,
      buckets, damage types, weapon / armor type names, sets and set perks; an English name with several
      translations keeps the most frequent one
- [x] A translator replaces every known English name in a text (whole words, longest first, ALL CAPS too) plus a
      small table of output labels per language (`fr` only for now)
- [x] The build sheet `.md` view and the build PDF show names and labels in the configured language
- [x] MCP tool `game_terms(names)` returns the localized names, and lists the ones the manifest doesn't know
- [x] `ghost-voice.md`: game names in the player's game language, from `game_terms`, never translated by hand
- [x] With `SHELL_LANGUAGE=fr`, `warlock-prismatic-getaway-buddy` renders its `.md` and PDF with French game names
