# Destiny 2 equipment rules

These are the game's hard constraints, which every build must respect before even looking at the inventory.
Each rule names its source. Rules marked **[checked]** are verified by `shell/engines/builds/rules.py` or
`sheet.py`: a sheet that breaks them is refused.

Values (damage, cooldowns, effects) are not here: they are in the Compendium (`compendium` skill).

## Exotics

| Rule | Source |
|---|---|
| **1 exotic weapon** equipped at a time. **[checked]** | Manifest: `equippingBlock.uniqueLabel = "exotic_weapon"` (checked on Alethonym, 2026-10-07) |
| **1 exotic armor piece** equipped at a time, exotic class items included (Solipsism…). | Manifest: `uniqueLabel = "exotic_armor"` (checked on Contraverse Hold and Solipsism, 2026-10-07) |
| An exotic armor piece and an exotic weapon can be worn together. | The two labels differ |
| Exotic class item perks only apply in Prismatic. | Compendium, `exotic-class.md` (Notes) |

## Weapons

| Slot | Possible elements | Ammo | Source |
|---|---|---|---|
| Kinetic | Kinetic, Stasis, Strand | Primary or Special | Weapon inventory **[checked]** |
| Energy | Arc, Solar, Void (Kinetic: exotics only, e.g. Tessellation) | Primary or Special | Weapon inventory **[checked]** |
| Power | all | Heavy | Weapon inventory **[checked]** |

- Consequence: a **Void, Solar or Arc** weapon never goes in Kinetic, and a **Stasis or Strand** weapon never in
  Energy. A Void build that wants two Void weapons puts the second one in Power.
- Kinetic and Energy each accept a Special: two special weapons can be equipped together.
- A sheet cannot have two weapons for the same slot. **[checked]**
- Each weapon has one weapon mod socket. "Enhanced" mods only go on Tier 4 and 5 weapons (Compendium,
  `weapon-perks.md`, Weapon Mods); "Adept" mods only on adept weapons.
- A random-roll weapon can have several options per column (Tier 5: often 2 barrel and magazine options, 3 per
  trait, per the 2026-10-09 weapon inventory); you switch freely between them (`set_perks`).
- The canary `tests/engines/builds/test_rules.py` checks these rules on the latest inventory snapshot: if Bungie
  adds an exception, the test fails and the rule must be updated here and in `rules.py`.

## Armor

| Rule | Source |
|---|---|
| 5 slots: Helmet, Gauntlets, Chest, Legs, Class Item. The exotic takes one. | Game |
| 2- and 4-piece set bonuses. The exotic does not count: at most 4 set pieces (2 + 2 or 4). **[checked]** | Compendium, `armor-perks.md` |
| Stats from 0 to 200. Past 100, each stat gives an "enhanced" bonus (see `game-mechanics.md`). **[checked]** | Compendium, `game-mechanics.md` |
| 3 utility mod sockets per piece (Armor 3.0), limited by the piece's energy (11 on a Tier 5 piece). These mods are specific to their slot (`Gauntlets` = the Compendium's "Arms" section). **[checked]** | `rules.py` (`UTILITY_SOCKETS`), armor inventory (`energy`) |
| The same utility mod can go several times on one piece, as long as energy allows; whether its effect stacks depends on the mod. | `set_sockets` (duplicates accepted); Compendium, `armor-mods.md` |

## Artifact

| Rule | Source |
|---|---|
| 1 artifact equipped. Past seasons' artifacts stay equippable, and each character has an instance of each. | Compendium (`artifact-perks.md`, Notes); account inventory (7 artifacts per character, 2026-10-07) |
| 7 perk sockets. Sockets 0–1 only take column 1, sockets 2–4 columns 1–2, sockets 5–6 columns 1–3: **at most 2 column-3 perks and 5 column-2-or-3 perks**. **[checked]** | Artifact sockets read with options (2026-10-07); `rules.py`, `artifact.py` |
| Artifact perks are disabled in Competitive and Trials. | Compendium (Notes) |

## Subclass

| Rule | Source |
|---|---|
| 2 aspects. | Manifest, via the build catalog |
| Fragment slots = sum of the two aspects' slots. **[checked]** | Manifest, via `check_build` |
| Active fragment sockets come first; the following ones are disabled (e.g. Voidwalker: sockets 7–12, 5 slots → 7–11 active). **[checked]** | Manifest (`socketEntries`), via `equip_plan` |
| Fragments of the subclass element (Prismatic: Facets), no duplicates. **[checked]** | Manifest, via `check_build` |
| Super, grenade, melee, class ability and jump: one of each. | Game |
