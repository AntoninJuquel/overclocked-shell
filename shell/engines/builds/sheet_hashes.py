"""The sheet's `hashes` table: {"<kind>:<name>": manifest hash} for every name it holds, rebuilt by check_build.

Kinds: item, perk (weapon plugs), mod (armor mods), plug (subclass), artifact, stat, set, setperk.
"""
from shell.engines import build_icons, share
from shell.engines.builds import weapon_intent
from shell.engines.share import _category, _copy_key, _is_armor_mod, _name

ITEM_KINDS = ("item", "perk", "mod", "plug", "artifact")  # those with a page of their own on light.gg


def fill(s: dict, defs: dict, socket_types: dict, stat_defs: dict, set_defs: dict, perk_defs: dict,
         plug_sets: dict) -> list[str]:
    """Rebuilds `s["hashes"]`; returns the problems of the intent's weapons. A name the manifest doesn't know stays out
    (the other checks report it). `resolved` pieces are matched by name, not by the player's copy."""
    table = s["hashes"] = {}
    intent, res = s["intent"], s.get("resolved") or {}
    problems = weapon_intent.normalize(intent.get("weapons") or [], defs, plug_sets, table)
    build_icons.refs(s, defs, socket_types, stat_defs, set_defs, perk_defs, hashes=table)

    def put(key, d):
        if d and d.get("hash"):
            table.setdefault(key, d["hash"])

    cls = share.CLASS_TYPES[s["class"]]
    armor = build_icons._index(defs, lambda d: d.get("itemType") == 2 and d.get("classType") == cls, _copy_key)
    weapons = build_icons._index(defs, lambda d: d.get("itemType") == 3, _copy_key)
    plugs = build_icons._index(defs, lambda d: d.get("plug") and not _is_armor_mod(_category(d)))
    mods = share.mod_index(defs)
    for a in res.get("armor") or []:
        put(f"item:{a['name']}", armor.get(a["name"]))
    mod_names = [*(n for m in (intent.get("armor_mods_fill") or {}).values() for n in m),
                 *(n for a in res.get("armor") or [] for n in [a.get("stat_mod"), a.get("tuning"), *(a.get("mods") or [])] if n)]
    for n in mod_names:
        if n in mods:
            table.setdefault(f"mod:{n}", mods[n])
    for w in res.get("weapons") or []:
        put(f"item:{w['name']}", weapons.get(w["name"]))
        for n in [*(w.get("perks") or []), *([w["mod"]] if w.get("mod") else [])]:
            put(f"perk:{n}", plugs.get(n))

    by_name = {_name(d): (h, d) for h, d in set_defs.items() if _name(d)}
    for e in [*(intent.get("sets") or []), *(res.get("sets") or [])]:
        h, d = by_name.get(e["set"], (None, {}))
        if h:
            table[f"set:{e['set']}"] = int(h)
        for p in d.get("setPerks") or []:
            perk = perk_defs.get(str(p["sandboxPerkHash"])) or {}
            if _name(perk) and p["requiredSetCount"] <= e["pieces"]:
                table[f"setperk:{_name(perk)}"] = p["sandboxPerkHash"]
    return problems


def links(hashes: dict, url: str, lang: str) -> dict:
    """{key: page url} of what has a page of its own."""
    return {k: url.format(lang=lang, hash=h) for k, h in hashes.items() if k.split(":")[0] in ITEM_KINDS}
