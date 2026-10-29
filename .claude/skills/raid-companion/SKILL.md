---
name: raid-companion
description: Teach a Destiny 2 raid encounter on demand (Deep Stone Crypt first) — phases, the standard 6-player role split, the player's steps for their role, callouts, and a schematic map on a live page for their second monitor — built from community guides cached locally. Use when the player asks how an encounter works, what their role does, what to do in a phase, or wants the raid map.
---

# Raid companion

Voice: speak as the player's Ghost — see [ghost-voice.md](../../ghost-voice.md) (French when the player writes French).

The player mostly raids in LFG: the lead hands out roles fast and uses the standard strat. Give them what lets them
follow: their role's steps for the current phase, the callout names, and where things are.

**Never invent a mechanic, a position or a callout.** Everything comes from the cached guides; what they don't cover
is "not in the guides". Raid and encounter ids: `deep-stone-crypt`; `desolation`, `crypt-security`, `atraks-1`,
`descent`, `taniks-reborn`, `taniks-abomination`.

1. **Guides.** If `cache/guides/<raid>/index.md` is missing or its guides were fetched more than 30 days ago:
   `refresh_references(source="guides", tabs=["<raid>"], force=true)`. Mention errors (a guide whose page changed
   keeps its last copy) and quote each guide with its `updated` date when it matters.
2. **Encounter file** — `profile/raids/<raid>/<encounter>.json`. Build it when it is missing or the player asks to
   rebuild (after a guide changed):
   - Read that encounter's section in every `cache/guides/<raid>/<guide>.md` (grep the headings first). Look at
     the images of that section with the Read tool (`cache/guides/<raid>/<guide>/img-NN.*`) before placing spots.
   - **Precedence:** steps and roles from the freshest guide (see `index.md`), numbered callouts from the guide
     that numbers them (Shacknews for DSC) when the freshest does not, the others to fill gaps. Every disagreement
     goes in `conflicts` ("Shacknews (2026-02-01): 5 panels per side; Grindout (2026-07-20) does not number them").
     What no guide covers goes in `gaps`.
   - **Positions:** a spot gets `pos` [x, y] on its floor's 0-100 grid only from a guide's text or image, with
     `pos_source` saying which, starting with the guide ("shacknews image 4", "grindout text: left of the door"); otherwise `pos: null` —
     it is listed beside the map, not drawn. Never from memory. Rooms (`x, y, w, h`) follow the same rule and stay
     coarse (sides, floors, zones).
   - **Spot ids** are unique across the raid (renames are per raid): prefix them with the encounter
     (`cs-panel-dark-1`, `ta-bucket-3`).
   - **Names:** the guides' own labels ("Panel 3 (left)", "Orange zone"). No LFG names the guides don't use.
   - Roles: the standard split for 6 (counts sum to 6). Steps: short, imperative, in the order they happen.
   - Format: `{"raid", "encounter", "name", "sources": [{"guide", "updated"}], "floors": [{"id", "name",
     "rooms": [{"id", "name", "x", "y", "w", "h"}]}], "spots": [{"id", "name", "kind", "floor", "room"?,
     "pos", "pos_source", "sources": [guide]}], "roles": [{"id", "name", "count"}], "phases": [{"id", "name",
     "summary", "steps": {role_id: [step]}, "spots": [spot_id], "sources": [guide]}], "conflicts", "gaps"}`;
     `kind`: plate, panel, terminal, bucket, zone, spawn, door, other.
   - Write it, then `raid_check(raid, encounter)` until `ok`. Tell the player what is not placed and what the
     guides disagree on.
3. **Show.** `raid_show(raid, encounter, role, phase)`. The first time, ask the player to open
   `profile/raids/live.html` in a browser on their second monitor: it reloads by itself. In chat, give the steps
   short (that's what they read mid-fight) and any conflict that touches their role.
4. **Follow the raid.** "Next phase", "I'm on adds now", "what does Operator do?" → `raid_show` again with the new
   phase or role; answer in one or two lines.
5. **Renames.** "We call it left 2" → `raid_rename(raid, spot_id, "left 2")`; it shows on every page of the raid
   and survives rebuilds. "Back to the guide's name" → `raid_rename(raid, spot_id)`.

This skill reads guides and writes only `profile/raids/`; it never touches the account.
