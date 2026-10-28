# Raid companion — design (S-024, E10)

Date: 2026-10-28 · Status: draft for review

## Intent

The player raids mostly through **LFG with strangers**. The raid lead hands out roles in a minute and uses the
standard strat and callouts; nobody explains at length. The player wants the Ghost to give, on demand, an
encounter's **mechanics, roles and callouts, with a map of where everything is**, so they can follow the lead
without a 40-minute video.

Success: before or during an encounter, the player says "Crypt Security, I'm Scanner" and a page on their
**second monitor** shows the encounter map with the callout names LFG uses and their spot highlighted, with their
steps for the current phase under it. "Next phase" or "now I'm on adds" updates the page.

## Goals

1. **Deep Stone Crypt first, every encounter:** Desolation (sparrows), Crypt Security, Atraks-1, Descent,
   Taniks Reborn, Taniks the Abomination. Other raids later in the same format, by adding guide URLs.
2. **Per encounter:** phases; the standard role split for 6 players; each role's steps per phase; named spots
   (plates, panels, terminals, buckets, zones) with their callout names; a schematic map per room / floor.
3. **Map first** (the player chose it over a phase-first layout): one map per encounter (one per floor when there
   are several), callout labels on it, the player's spot highlighted; their role's steps below.
4. **Live page on a second monitor:** a local HTML page the player keeps open; it reloads by itself when the Ghost
   rewrites it (different phase, role or encounter).
5. **Answers in chat too:** "6 players, I'm on adds, what do I do in phase 2?" gets a short Ghost answer in chat and
   the page update.
6. **Callout renames:** the player can rename a spot to what their groups say ("left plate 2"); renames persist
   across rebuilds of the encounter file.

## Non-goals

- Faithful level geometry or copies of the guides' images. Maps are **schematics** (rooms, sides, floors,
  labelled spots in roughly the right places) and say so.
- Live tracking of the game state (Bungie's API does not expose encounter phases).
- Dungeons, voice output, a phone layout (second monitor only for now).
- Publishing guide content anywhere.

## Anti-goals (failure even if it works)

- **Invented mechanics.** A step, spot or callout that no guide supports. What the guides don't cover is marked
  "not in the guides".
- A map that looks authoritative and is wrong, with nothing telling the player it is a schematic.
- Silent disagreement between guides: when they differ (count of panels, order of steps), the player sees it.

## Sources (decided)

Player-chosen guides, each fetched and kept locally (gitignored `cache/`), never published:

| Guide | Updated | Gives |
|---|---|---|
| Grindout — https://grindout.com/destiny-2/guides/deep-stone-crypt | Jul 2026 | per-role bullet steps, zone names (upper / lower, Ground / Space, Orange / Blue / Spawn) |
| Shacknews — https://www.shacknews.com/article/121651/deep-stone-crypt-raid-guide-destiny-2 | written Nov 2020, modified Feb 2026 | numbered callouts (basement panels 1–5 per side, Nuclear Core buckets 1–6 clockwise), captioned images |
| Overgear — https://overgear.com/guides/destiny2/deep-stone-crypt-raid-guide/ | Jan 2024 | clear prose for every encounter |

Hubs for later raids: https://grindout.com/destiny-2/guides, https://www.shacknews.com/article/101225/destiny-2-complete-strategy-guide,
https://overgear.com/guides/destiny2/raids-d2/. The three DSC pages are static HTML (checked).

**Precedence when guides disagree** (decided with the player's sources in mind): steps and roles from the freshest
guide (Grindout), numbered callouts from Shacknews where the freshest guide does not number, Overgear to fill
gaps; every disagreement recorded in the encounter file and shown.

## How it works (decided)

1. **Guide source** — a new source module fetches the configured guide pages per raid, extracts the readable text
   (headings, paragraphs, lists, image captions / alt text) with the page's own date, and stores it as Markdown per
   guide, like the Compendium. It also **downloads each guide's in-article images** into `cache/` and references
   them from the Markdown at their place in the text, so the Ghost can look at them when placing spots (decided by
   the player). Images are never shown on the page or published. Change reporting like the other sources.
2. **Encounter files are written by the Ghost**, not parsed: guides are prose, no parser can turn them into roles
   and positions. A skill playbook has Claude read the cached guides for one encounter, cross-check them, and write
   a structured encounter file; a tool validates it. Done once per encounter; the player can ask to rebuild after
   a guide changes.
3. **Encounter file** (one per encounter, player data, gitignored `profile/raids/<raid>/<encounter>.json`):
   sources used (with dates), floors / rooms, spots (id, guide name, kind, room, optional schematic position and
   where that position comes from: a guide's text or image), roles (name, count of 6), phases (summary, steps per
   role, spots involved), conflicts between guides, gaps.
   - **Positions** (decided by the player): only from a guide's text or images. A spot no guide locates has no
     position: it is listed beside the map, not drawn. The Ghost never places a spot from its own memory.
   - **Callout names** (decided by the player): the guides' own labels by default (Shacknews' "panel 3", Grindout's
     "Orange"); no LFG names the guides don't use. The player's renames (below) replace them on display.
4. **Renames** in a separate file per raid (`profile/raids/<raid>/callouts.json`, spot id → player's name), applied
   on display, so rebuilding an encounter keeps them.
5. **Rendering** — an output module draws the schematic map as SVG from the encounter file; another writes the live
   HTML page (map first, then role steps for the phase, conflicts / gaps in a small footer, "schematic" label,
   sources with dates). The page reloads itself every few seconds.
6. **Tools** (thin, as elsewhere): validate an encounter file; render the page for (raid, encounter, role, phase)
   and return its path plus the steps as text; rename a callout.
7. **Skill** `raid-companion`: build an encounter file from the guides; answer role / phase questions in chat and
   update the page; renames; tell the player to open the page once on the second monitor.

## Constraints

- Windows primary, macOS / Linux must work; no new dependency (stdlib HTML parsing and downloads; the page is
  plain HTML + inline SVG, opened as a local file in any browser).
- Offline after the guides are fetched.
- No core edits: new modules in sources / engines / outputs / mcp/tools, a new skill.
- English for files and skill; the Ghost answers in French when the player writes French; game names stay English.

## Left to the builder

- Exact encounter-file schema and the map coordinate system (a grid per floor is fine).
- How the page reloads (meta refresh or a script) and the reload interval.
- Text extraction details per site (navigation, ads, comment sections stripped).
- Tool names and signatures; how "current phase / role" is remembered between calls.
- Which DSC encounters ship in the first build (all six are the goal; order can follow the raid).
