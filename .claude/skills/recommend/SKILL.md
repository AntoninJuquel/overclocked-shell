---
name: recommend
description: Recommend the best Destiny 2 weapon the player owns for a situation (an activity, a boss DPS phase, add clear, champions, an element or surge, a weapon to replace), given what their character is wearing — the pick, why, owned alternatives, what to swap out and what better exists to farm. Use when the player asks what to use, what is best for an encounter, or what should replace an equipped weapon.
---

# Recommend a weapon for a situation

Voice: speak as the player's Ghost — see [ghost-voice.md](../../ghost-voice.md) (French when the player writes French).

The tool ranks; you read the situation. Never invent a DPS value, a tier or a champion rule: they come from Aegis,
the Compendium or the account.

1. **Situation.** Character (ask if unclear, else the one they named last), activity or encounter, role (boss
   damage → `role="dps"`; anything else → `general`), the slot or weapon to replace. One question if the activity
   is unclear; otherwise assume and say what you assumed.
2. **Fresh data.** `refresh_inventory()`. If it fails, say the picks come from the snapshot of `<snapshot>` (in
   every `recommend_weapons` result) and that locations and swaps may be out of date. If Aegis is more than 7
   days old, follow the `aegis` skill.
3. **What they wear.** `get_equipped(character)`: subclass, aspects and fragments (an element synergy they
   give comes from the Compendium, not memory), leg-armor Weapon Surge mods (prefer that element), active
   artifact perks.
4. **Constraints from the situation**, each turned into tool filters:
   - Champions: the activity's modifiers (`week_context()` after `refresh_context(character)` for this week's
     activities) and which weapon types the active artifact perks cover (`compendium` skill, artifact perks) →
     `type`.
   - Boss: `rankings(view="bosses", activity=…)` for health and phases; boss DPS comes from
     `recommend_weapons(role="dps")`.
   - Element: a surge or an activity's surge → `element`, when the player cares about it.
5. **Rank.** `recommend_weapons(character, role, slot, element, type)`, once per slot that matters (usually the
   slot to replace, or Power for DPS). If a `dps` call warns that a weapon has no Aegis DPS row, say it is
   unrated, don't guess its DPS.
6. **Answer** (lead with the decision):
   - The pick and one line why: Aegis tier (or DPS and the setup Aegis measured), the reason for this situation.
     Quote "Aegis, <tab>, updated …".
   - What changes: the `swap` / `second exotic` notes (which weapon comes off), where it is (vault, other
     character). For a DPS setup, the perks Aegis measured that their roll lacks (`weapon_options(item_id)`).
   - 2–3 owned alternatives, one line each.
   - `not_owned`: one line, "worth farming", offered to the TODO (`todo` skill) — never added silently.
7. **Offer to equip.** `equip_items(character, [ids])` previews by default: show it, call again with
   `dry_run=false` only after the player's yes, then `refresh_inventory()`.
