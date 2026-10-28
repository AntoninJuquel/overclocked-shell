---
name: create-build
description: Create a Destiny 2 build with the player, interactively — from an idea or an exotic, an activity, their current build or a build found elsewhere — the best in theory without looking at the inventory, then apply it to their inventory (armor and weapons, listing the concessions) and save the sheet in profile/builds/. Use when the player wants to create, imagine, reproduce or adapt a build.
---

# Create a build

Conversation: **one question at a time**, with 2–3 argued options when possible. Every mechanic or value comes
from the Compendium (`compendium` skill), quoted with its date; if an entry is missing, say so rather than
invent. Names in English, as in game (fragments too: "Spark of Shock").

**Two phases, never mixed:**
- **Intent (steps 1–6): the best build in theory.** Only game data (Compendium), Aegis's ratings (`aegis` skill:
  what is viable and best in PvE endgame) and the equipment rules ([docs/game-rules.md](../../../docs/game-rules.md):
  1 exotic weapon and 1 exotic armor, elements per weapon slot, sets…) count. **No inventory reads**: not
  ownership, unlocks, wishlist grades, nor "you already have…" as an argument. Every choice is the best for the
  concept and the activity, not the easiest to get.
- **Resolution (steps 7–8): applying it to the inventory.** The optimizer and the weapon views make the
  concessions. Every gap between intent and result is **listed** ("ideal weapon missing → substitute X, what we
  lose"), never silently pushed back into the intent.

**Preparation**: Compendium up to date (`compendium` skill), Aegis up to date (`aegis` skill), and
[docs/game-rules.md](../../../docs/game-rules.md) read. `refresh_inventory` and wishlist grades
(`optimize-build` skill, step 5): only before step 7.

## 1. Starting point
Recognise the way in and pre-fill what you can:
- **idea or exotic**: build around it ("Arc grenade spam", "Getaway Artist");
- **activity**: offer 2–3 concepts (subclass + exotic + gameplay loop in one sentence), the player picks one;
- **current build**: `get_equipped` with `character` = `hunter`, `titan` or `warlock` → subclass (super,
  abilities, aspects, fragments), exotic, mods, weapons; it is the concept's starting point, not a constraint:
  ask what they want to improve;
- **build found elsewhere**: read the link (WebFetch) or the text, turn it into an intent; fix it if it breaks a
  game rule or if the Compendium shows better.

## 2. Class and exotic
- Exotic armor: the best for the concept per `exotic-armors.md`, without checking ownership (step 7).
- Exotic class item (Solipsism, etc.): pick the two perks → `intent.exotic.perks`, with the exact in-game plug
  names, without the `Intrinsic: ` prefix (the Compendium's spelling can differ: "Spirit of Inmost Light" /
  "Spirit of the Inmost Light"); the optimizer then only keeps the copy that has them (Compendium reminder: their
  perks only apply in Prismatic).

## 3. Subclass
1. Every option in the game is allowed; what is not unlocked is flagged at step 7.
2. Super and abilities (`grenade`, `melee`, `class`, `jump`): only those that matter for the concept.
3. `subclass_options(class_type, element)` (elements: Arc, Solar, Void, Stasis, Strand, Prismatic): aspects with
   their fragment slots, fragments with their stat bonuses (Compendium), each with its Aegis tier
   (`· Aegis S #1`); `rankings(view="subclasses", class_type=…)` ranks subclasses. An aspect or fragment outside
   Aegis's S/A tiers needs the concept to justify it.
4. Two aspects, then as many fragments as slots (sum of both aspects), each justified by the Compendium. Remind
   the fragments' effect on stats.

## 4. Stats
Stats: `Weapons`, `Health`, `Class`, `Grenade`, `Super`, `Melee`. Propose **minimums** (integers 0–200) and a
**priority order** from the concept, have them validated. Each minimum and rank is justified by a numbered
effect in `game-mechanics.md` (regeneration up to 100, "enhanced" bonus beyond) or a cooldown from the subclass
files: no round threshold without a reason. Fragment bonuses are counted by the optimizer.

## 5. Constraints
- Sets: compare **all** `armor-perks.md` bonuses useful to the concept and activity (`crucible` attribute for
  PvP), with their Aegis tier (`rankings(view="sets")`), then keep the best combination (4 pieces, 2 + 2, 2 alone
  or none), without looking at owned pieces: `{"set": "<name>", "pieces": 2|4}`, at most 4 pieces in all (the
  exotic is not part of them). Leaving pieces free is a choice to justify (the missing bonus is worth less than
  the stat margin). Name as in the manifest, sometimes with a "Set" suffix the Compendium lacks ("Smoke Jumper
  Set"): on an unknown name, `optimize_build` fails and suggests the right name when it finds one.
- Utility mods per slot (`Helmet`, `Gauntlets`, `Chest`, `Legs`, `Class Item`; the Compendium's "Arms" section is
  `Gauntlets`; effects in `armor-mods.md`, full in-game name: "Arc Siphon"): their energy is reserved before stat
  mods. At equip time (`equip-build`), for a slot with no wanted mod: ask the player whether to keep the mods
  already on the chosen pieces (often leftovers from old builds; leave the slot out, those that fit the energy
  are kept) or clear the slot (`[]`). **At most 3 mods per slot, and the same mod can go several times on one
  piece** (e.g. `["Void Weapon Surge", "Void Weapon Surge"]`): consider duplicates, checking in `armor-mods.md`
  whether the mod stacks (some don't, or with diminishing returns).
- Filler mods (`intent.armor_mods_fill`, same slots): per slot, a list ordered by priority of mods useful to the
  concept (duplicates allowed, including a mod already in `armor_mods`), to **fill the energy left** on each piece
  after stat mods. The optimizer takes, in the free utility sockets, the combination that uses the most energy,
  then the best ranked. Goal: 0 unused energy on every piece (a Tier 5 piece has 11 energy); so plan mods of
  various costs, including 1-cost mods, at the end of the list. Stat mods come first (a stat deficit or priority
  is never sacrificed to filling).
- Weapons, one per slot (`Kinetic`, `Energy`, `Power`): `role` ("add clear", "boss DPS"…) and the ideal weapon in
  theory, respecting [docs/game-rules.md](../../../docs/game-rules.md) (elements per slot, ammo, a single exotic):
  `element`, `type` ("Sniper Rifle"), `ammo` (`Primary`, `Special`, `Heavy`), `exotic` (`true` for an exotic) and
  `wanted` (a precise weapon or the target perks, e.g. "Repulsor Brace + Destabilizing Rounds"). Consider an
  exotic weapon: the exotic armor does not take its place. `check_build` refuses an impossible element or ammo
  for the slot, and more than one exotic. Pick the ideal weapon among Aegis's best for the role:
  `rankings(view="weapons", type="<type>", element=…)` (recommended perks and origin trait),
  `rankings(view="exotic-weapons")`; for a boss DPS role, `rankings(view="dps-sustained")` and
  `rankings(view="dps-swap")` (Boss Damage), and `rankings(view="bosses", activity="<activity>")` for health and
  damage phase. Carry the recommended perks into `wanted`.
- Artifact: compare the Compendium's artifacts (`artifact_options()`, with each perk's Aegis tier `(S)`;
  `rankings(view="artifact")`; effects in `artifact-perks.md`; past seasons' artifacts stay equippable and every
  character has them all) and keep the best for the concept, with its 7 perks:
  `{"name": "<artifact>", "perks": [...]}` in `intent.artifact`. Sockets: at most 2 column-3 perks, at most 5
  column-2-or-3 perks ([docs/game-rules.md](../../../docs/game-rules.md)). Think of the activity's champions
  (stunning perks).

## 6. Write the sheet
`profile/builds/<slug>.json` (slug: lowercase ASCII name with dashes; never overwrite an existing sheet without
the player's OK), without `resolved`:

```json
{
  "name": "Warlock Arc grenades",
  "class": "Warlock",
  "activity": "GM Nightfall",
  "concept": "One sentence about the gameplay loop.",
  "subclass": {
    "element": "Arc",
    "super": "Stormtrance",
    "abilities": {"grenade": "Storm Grenade", "melee": "Chain Lightning"},
    "aspects": ["Electrostatic Mind", "Lightning Surge"],
    "fragments": ["Spark of Shock", "Spark of Magnitude", "Spark of Ions", "Spark of Discharge",
                  "Spark of Amplitude"]
  },
  "intent": {
    "exotic": {"name": "Getaway Artist"},
    "stats": {"minimums": {"Grenade": 150, "Health": 70}, "priority": ["Class", "Super"]},
    "sets": [],
    "armor_mods": {"Helmet": ["Arc Siphon"]},
    "armor_mods_fill": {"Helmet": ["Heavy Ammo Finder", "Arc Siphon", "Ashes to Assets"],
                        "Legs": ["Arc Weapon Surge", "Arc Weapon Surge", "Recuperation"]},
    "artifact": {"name": "NPA Repulsion Regulator", "perks": ["Amped Up", "..."]},
    "weapons": [
      {"slot": "Kinetic", "role": "precision", "element": "Strand", "type": "Sniper Rifle", "ammo": "Special"},
      {"slot": "Energy", "role": "add clear", "element": "Arc", "exotic": true, "wanted": "Ex Diris"},
      {"slot": "Power", "role": "boss DPS", "type": "Rocket Launcher", "wanted": "Bait and Switch"}
    ]
  }
}
```

Then `check_build(slug)` and fix until `ok` is true: it validates the format (an invalid sheet writes nothing),
checks aspects and fragments for the class and element (no duplicates, no more fragments than slots; the
expected name is given when only case or prefix differs), the super and abilities, the artifact and its perks
(column rules), and regenerates the `.md`. It accepts empty fragment slots: make sure they are all filled. A super
or ability missing from the sheet stays as in game at equip time.

## 7. Armor
First `refresh_inventory` (preparation) and list the gaps with the intent: exotic not owned
(`find_armor(name=…, class_type=…)`), super, aspect or fragment not unlocked (the player checks in game: Shell has
no unlock read). For each gap, propose a substitute and say what we lose; the intent does not change unless the
player asks.

`optimize_build(slug, top=3)`. Present the 3 combinations: final stats, stat mods and tuning, utility mods of each
piece (`mods`: the intent's then the fillers), unused energy (`energy_left`), masterworks to do, transfers. A
piece with `energy_left` > 0: propose other filler mods for its slot (cheaper, or a duplicate), update
`intent.armor_mods_fill`, `check_build` again (step 6) and rerun; accept free energy only if no useful mod fits,
and say so. `complete: false`, `feasible: false` and the tuning warning: as in the `optimize-build` skill
(step 3) — never pass `force` without the player's explicit OK. The player picks N →
`optimize_build(slug, write=true, pick=N)` (writes `resolved.date`, `armor` and `stats`, regenerates the `.md`;
refused when result N is infeasible). An intent set not found in the inventory: leave the intent as it is,
propose an owned substitute (the class's sets per slot, except the exotic's) and rerun the calculation then the
write with `sets=["Name:2", …]` or `no_sets=true`; applied sets are recorded in `resolved.sets`. After any change
to the sheet (thresholds, fragments, sets…), run `check_build` again, then this step.

## 8. Weapons
For each slot: `weapon_candidates` as in the `optimize-build` skill (step 5: filters, columns, grades), filtered
from the intent (`slot`, `element`, `type`, `name`, `perk`); the first column is the weapon id. If the ideal
weapon is there, offer it first. Otherwise say so and offer 2–3 substitutes by widening the filters, with what we
lose against the ideal (element, perk, synergy, wishlist grade). The player decides.

Then, for each chosen weapon, its **perks** and **mod**: `weapon_options(item_id)` lists all its columns (barrel,
magazine, battery, traits…) with all their options: `(selected)` = in place, `*` = enhanced, `✓` = cited by the
wishlist for this weapon, `A` = recommended by Aegis (and, at the end, its tier, recommended masterwork and notes).
- `perks`: for **every** column with several options (Tier 5 weapons: often 2 barrel and magazine options and 3
  per trait), the best option for the weapon's role in this build (effects in `weapon-perks.md`), considering the
  intent's `wanted` and the `✓`; exact option names, at most one per column, never one marked "not insertable".
  Also list options already in place that we keep: `perks` describes the full wanted configuration. Crafted
  weapon: one option per column, nothing to choose.
- `mod`: the best weapon mod for the role ("Weapon Mods" section of `weapon-perks.md`: Backup Mag, Targeting
  Adjuster…). "Enhanced" mods only go on Tier 4 and 5 weapons, "Adept" mods only on adept weapons. `null` only if
  no mod helps (justify it in `why`).
The equip plan (`equip-build`) warns about a weapon with no `perks` although it has choices, or with no mod.

Add to the JSON's `resolved` (after step 7, without touching the rest):
- `weapons`: one entry per slot, at most one per `slot`: `slot` (`Kinetic`, `Energy`, `Power`), `itemId` (the id
  from `weapon_candidates`, as text) and `name` required; `perks` (wanted options), `mod` (weapon mod name, or
  `null`) and `why` optional;
- `rationale`: a list of texts, the build's key reasons, one per entry, then one "Gap: …" entry per concession
  made to the inventory (steps 7 and 8);
- `gaps`: one entry per gap that is not an armor piece (ideal weapon not owned, missing catalyst, artifact perk,
  aspect…): `kind` (`weapon`, `catalyst` or `upgrade`), `target` (item name, in English) and `effects` (what we
  would gain, a list of texts). Armor gaps are computed by the farm needs, don't put them here.

Then `check_build(slug)` (validates and regenerates the `.md`), and `farm_needs` (farm needs of every sheet,
"To fetch" section).

## 9. End
Show the sheet's `.md`, remind the masterworks to do in game, and offer to equip it (`equip-build` skill). This
skill equips nothing and dismantles nothing. If the player stops before step 7, say the incomplete sheet stays in
`profile/builds/` and offer to delete it (`.json` and `.md`), only with their OK.
