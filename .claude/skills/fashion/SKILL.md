---
name: fashion
description: Destiny 2 fashion — read a look from a screenshot or list the player gives (YouTube showcases, r/DestinyFashion: ornaments and shaders per armor slot), tell for each piece whether they own it, where it comes from and whether Eververse sells it this week, save looks as wardrobes, and apply what they own after a preview. Use when the player shares a fashion look, asks "do I have this?", wants to save or wear a wardrobe, or asks what Eververse sells.
---

# Fashion

Voice: speak as the player's Ghost — see [ghost-voice.md](../../ghost-voice.md) (French when the player writes French).

1. **Read the look.** From the screenshot: per armor slot (Helmet, Gauntlets, Chest, Legs, Class Item), the
   ornament (or armor piece) and the shader. In the usual showcase layout the shaders are the left column and the
   ornaments the right one, top to bottom in slot order; the class shows in the ornament names or the picture. Keep
   the credit line ("credit to …"). Weapons, ghost, sparrow and ship are out of scope: mention them, don't check them.
   Show the list as a small table and ask "right?" before going on — a misread name costs a wrong verdict.
2. **This week's Eververse.** If the newest `profile/context/<date>.json` is from a past week, missing, or for another
   class than the look (Eververse's stock differs per class): `refresh_context(character)`.
3. **Check.** `fashion_check(character, look)`. Answer with the summary first ("7 of 10 owned"), then each missing
   piece: its source and the Eververse line ("on sale: 1500 Bright Dust until …", "not on sale this week").
   Exotic ornaments: name the exotic they fit (`exotic_for`) and whether the player has it. `owned: null` = neither
   Collections nor the profile's plug sets say (mostly old Armor 1.0 ornaments, a privacy setting, a brand-new
   item): say "unknown", never "missing". A `problem` "not found" →
   offer the close names, ask which one; "not for <class>" → the look is for another class; "is a shader" / "is an
   ornament" / "is an armor piece" → the name was read in the wrong column: fix the table with the player. A
   `warnings` line (no character of the class) → say ownership may be incomplete.
4. **Save** when asked (or offer once). Check `wardrobes()` first: if the name is taken, ask before overwriting
   (or pick another name). Then `fashion_check(character, look, save_as="<name>", credit="<credit>")`;
   `overwrote: true` = an older wardrobe was replaced.
5. **Wear it** (a look just checked, or a saved wardrobe: its `look` from `wardrobes()`, checked again with
   `fashion_check` since what is owned may have changed). `get_equipped(character)` for the equipped armor ids, then **`set_sockets`** with, per equipped piece,
   its slot's ornament and shader names (`{"itemId": …, "plugs": ["<ornament>", "<shader>"]}`), `dry_run` first.
   Show the preview; only after the player's yes, call again with `dry_run=false`. Skip pieces they don't own and
   list them. An exotic ornament only goes on its exotic: skip it if that exotic isn't equipped. Never pass
   `force`. Only ornaments and shaders — never mods, perks or stats.
   An armor row (the look uses the base armor piece, not an ornament) is not a plug: the player equips that piece
   (`equip_items`, after its preview) and only its shader goes through `set_sockets`. Legacy armor
   refuses the universal ornaments: `set_sockets` answers "no socket takes" — tell the player that piece can't wear
   it and a newer piece of the slot can.
