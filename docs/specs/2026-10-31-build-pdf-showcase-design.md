# Build PDF showcase: the in-game look

Status: approved layout (brainstorm 2026-10-31), story S-026.
Mockup that was approved: `.superpowers/brainstorm/556-1793447410/content/layout-v3.html` (gitignored; real icons, the
Getaway Buddy sheet).

## Why

The build PDF (`build_pdf`, `shell/outputs/build_pdf.py`) is today the Markdown view printed: text and one table. The
player sends it to friends and other players. It should be **appealing**, and laid out **like the game's own screens**
so a player follows it without thinking: the weapon is where they expect a weapon, the fragments look like
fragments.

## Goals

- Page 1 is one A4 **landscape** page arranged like the in-game **Character** screen, with the real game icons
  (Bungie manifest) for every item, perk, mod, ability, aspect, fragment, artifact perk and stat.
- The build's text (concept, why it works, each weapon's why) sits in the middle, where the Guardian stands in game.
- It works offline after the first export (icons cached).

## Non-goals

- The Guardian model, the in-game screenshot art, Transcendence, the Ghost: the sheet doesn't hold them / we
  can't get them.
- Changing the build sheet JSON, the Markdown view (`build_md`) or the DIM link.
- An HTML or image export; a template system; options for layouts.

## Anti-goals (failure even if it works)

- A layout that doesn't match the game's positions (weapons not on the left, armor not on the right…).
- An export that fails because an icon is missing or Bungie is unreachable: it must degrade, never fail.
- A new heavyweight dependency (headless browser, HTML→PDF engine): fpdf2 2.8.9 + Pillow (already installed) do it.

## Page 1 layout (decided with the player)

Mirrors `layout-v3.html`. A4 landscape, dark purple gradient background (my call: tinted by the subclass element,
Prismatic = pink / purple as in game).

- **Top bar:** build name (big, bold); under it `CLASS · ACTIVITY` (activity when set).
- **Top left — subclass panel**, laid out like the in-game subclass screen: round subclass emblem + `PRISMATIC
  WARLOCK` / `WARLOCK SUBCLASS`; the **super** in a large diamond (rotated square) on the left; `ABILITIES` row
  (class ability, jump, melee, grenade — game order), `ASPECTS` row, `FRAGMENTS` row, each a section label with a
  rule under it and square icons.
- **Left column — weapons**, Kinetic, Energy, Power top to bottom. Per weapon: the icon (gold border if exotic),
  name and a short perk line beside it; to its left, right-aligned toward the icon, **one horizontal row of round
  perk icons** and **under it one row of square weapon-mod icons** (as in the weapon inspect screen).
- **Bottom left — artifact**: its icon, name, one row of its chosen perk icons.
- **Right column — armor**: helmet, arms, chest, legs, class item top to bottom (exotic gold border); to the right of
  each, **one horizontal row of its mods** in game order: tuning, stat mod (gold border), then the slot mods (my
  call, as on the in-game armor screen). The tuning label in the sheet ("Balanced Tuning", "+Grenade / -Weapons")
  maps to its tuning plug (`armor_tiering.plugs.tuning` category, as `share._is_armor_mod` already knows); when it
  doesn't map, it shows as small text under the row.
- **Stats column** between the middle and the armor, as in game: six stats (Weapons, Health, Class, Grenade, Super,
  Melee) with their manifest icons and values (`resolved.stats`), the set-bonus icons under it.
- **Middle — build text**: concept, `WHY IT WORKS` (rationale bullets), `WEAPONS` (each weapon's why), then the
  `ARMOR SET BONUS` box (set name × pieces, perk names per piece count).

When the sheet has no `resolved` part, page 1 shows what the intent has (subclass, exotic, mods by slot, weapon
roles) and leaves empty slots empty (my call).

## Page 2 and overflow

Text that doesn't fit the middle continues on page 2 (text-only, same dark theme, my call). Also on page 2 when
present: "To fetch" (needs) and the footer line. Font size of the middle may drop to a floor (~7 pt) before
overflowing.

## Where the pictures come from

- **Manifest**: every icon is `displayProperties.icon` (relative path, prefix `https://www.bungie.net`).
  - Armor / weapons: the item hash from the inventory snapshot (as `share.loadout` does with `itemId`), else name
    lookup. Use the ornament icon when the instance has one is **out** (my call: base icon).
  - Subclass emblem, super, abilities, aspects, fragments, armor mods: reuse the name → hash resolution of
    `shell/engines/share.py` (`_subclass`, `_mod_index`): extract it so both the DIM link and the PDF use it
    rather than copy it.
  - Weapon perks / weapon mods: name lookup restricted to plugs (perks, barrels, magazines, origin traits, weapon
    mods); artifact and its perks: `itemTypeDisplayName` "Artifact" / "Artifact Perk".
  - Stats: `DestinyStatDefinition` icons by the hashes in `share.STAT_HASHES`.
  - Name lookups must filter by kind: a bare name match is ambiguous (e.g. "Time Dilation" is also an Emblem).
- **destiny-icons** (`justrealmilk/destiny-icons@394ed05`): not needed for the approved page (my call). Keep it as the
  source if a glyph the manifest lacks (element / ammo) is added later.
- **Cache**: icons downloaded once to `cache/icons/<file name>` (gitignored `cache/`), reused offline. Downloads go
  through `httpx` like the rest of the Bungie layer, bounded concurrency, short timeout.
- **Offline** (my call): `Manifest.version()` always hits the network, so offline the manifest can't resolve
  names. The icon module keeps its own index `cache/icons/index.json` (`kind:name` → icon file) next to the icons;
  offline, it resolves from that index only. A sheet exported once re-exports offline; anything new falls to the
  missing-icon path. Core is not edited.
- **Inventory snapshot** (my call): armor and weapon icons come from the snapshot's item hash when the snapshot has
  the `itemId` (the exact copy: Timelost, reissues); otherwise name lookup plus a warning. A missing snapshot never
  fails the export.
- **Missing icon** (no match, download failed): a dark empty square with the name in small text; a warning in the
  tool result. The export never fails for an icon.

## Code shape (CLAUDE.md rules)

- New renderer `shell/outputs/build_showcase.py` (or the existing `build_pdf.py` rewritten: builder's call) taking
  the sheet, a `{name/slot: local icon path}` mapping and returning `(bytes, warnings)`. Pure: no network.
- Icon resolution + download as a new module (e.g. `shell/sources/icons.py` or `shell/engines/…`), not in core.
- `build_pdf` tool (`shell/mcp/tools/share.py`) wires them: load sheet → resolve hashes (manifest, inventory snapshot)
  → fetch icons → render. Same return shape plus icon warnings. The share-build skill text updated if its wording
  about the PDF changes.
- The current Markdown-printed PDF code: replaced (my call). The Markdown file stays for reading in the editor.

## Tests

- Renderer: renders a sheet with and without `resolved`, with missing icons, with long text (page 2 appears), with
  Helvetica fallback; output is a valid PDF with images.
- Icon resolution: name → icon for each kind with a small fake manifest, including the ambiguous-name case.
- Cache: second call does no network; with the network down, a sheet exported once renders its icons from
  `cache/icons/index.json`.
- A real export of `warlock-prismatic-getaway-buddy` looked at by eye against the mockup.

## Left to the builder

Exact sizes, spacing, colours and fonts (Arial / DejaVu as today), gradients via fpdf2 or a Pillow-rendered
background image, circle clipping for perk icons, whether `build_pdf.py` is rewritten in place or replaced.
