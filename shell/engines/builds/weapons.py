"""Weapon candidates for a build, filtered from the inventory snapshot.

One line per weapon: id | name | type | element | slot | ammo | frame | perks | wishlist grade | Aegis tier
                     | lock | location [| equipped] [| crafted].
Perks: column `selected [alt1/alt2]` (insertable alternatives), `*` = enhanced perk; `perk` searches the options
of the shown columns (not barrel, magazine…) and the frame. Order: graded weapons first (wishlist grade
S>A>B>C>D>F, then #n).
detail(): every column of one weapon (barrel, magazine… included), to choose its perks and mod:
`(selected)` = current option, `*` = enhanced, `✓` = cited by the default wishlist (DIM) for this weapon,
`A` = recommended by Aegis (Endgame Analysis); then one line per Aegis rating (tier, tab, advised masterwork,
notes). `(not insertable)` = refused by Bungie for now; the header says whether the weapon can get a full
wishlist roll. Crafted weapons: one option per column; the other perks come from the crafting table.
"""
import json
import re
from collections import defaultdict

from shell.core import paths
from shell.sources import wishlists
from shell.sources.aegis import lookup as aegis
from shell.sources.aegis.names import norm

# Weapon columns that are not build perks (Trait, Origin Trait, Intrinsic, Perk are kept).
EXCLUDED_COLUMNS = frozenset({
    "Barrel", "Magazine", "Scope", "Sight", "Bowstring", "Arrow", "Blade", "Guard", "Battery",
    "Launcher Barrel", "Haft", "Stock", "Grip", "Grips", "Rail", "Bolt", "Tang", "Handle"})
TIERS = "SABCDF"
BIG = 10 ** 9


def load_grades():
    """{itemId: wishlist grade} from profile/triage/weapons.json (empty when the triage was never run)."""
    path = paths.profile_dir() / "triage" / "weapons.json"
    if not path.exists():
        return {}
    items = json.loads(path.read_text(encoding="utf-8")).get("items", [])
    return {r["itemId"]: r["grade"] for r in items if r.get("grade")}


def _grade_key(grade):
    m = re.match(r"\s*([SABCDF])\b", grade)
    n = re.search(r"#\s*(\d+)", grade)
    return (TIERS.index(m.group(1)) if m else len(TIERS), int(n.group(1)) if n else BIG)


def _option_names(w):
    names = [w.get("frame") or ""]
    names += [o["name"] for c in w.get("columns", []) if c["label"] not in EXCLUDED_COLUMNS
              for o in c.get("options", [])]
    return names


def select(items, slot=None, element=None, type_=None, name=None, grades=None, perk=None):
    grades = grades or {}

    def ok(w):
        return ((not slot or w["slot"].lower() == slot.lower())
                and (not element or w["element"].lower() == element.lower())
                and (not type_ or type_.lower() in w["type"].lower())
                and (not name or name.lower() in w["name"].lower())
                and (not perk or any(perk.lower() in n.lower() for n in _option_names(w))))

    def key(w):
        g = grades.get(w["itemId"])
        return (g is None, *(_grade_key(g) if g is not None else (0, 0)), w["name"], w["itemId"])

    return sorted((w for w in items if ok(w)), key=key)


def _column(c):
    sel = c["selected"]
    opts = c.get("options", [])
    cur = next((o for o in opts if o["name"] == sel), None)
    text = sel + ("*" if cur and cur.get("enhanced") else "")
    if len(opts) > 1:
        alts = [o["name"] for o in opts if o.get("canInsert") and o["name"] != sel]
        if alts:
            text += f" [{'/'.join(alts)}]"
    return text


def wishlist_perks(w, rolls, by_name):
    """(normalized perks the wishlist cites for this weapon, can the weapon get a full roll)."""
    opts = {wishlists.norm_perk(o["name"]) for c in w.get("columns", []) for o in c.get("options", [])}
    hashes = [w["itemHash"]] if w.get("itemHash") in rolls else by_name.get(wishlists.norm_weapon(w["name"]), [])
    lines = [perks for h in hashes for perks in rolls[h]]
    return set().union(*lines), any(perks <= opts for perks in lines)


_wishlist = (None, None)   # ((path, st_mtime_ns, plug_names), index): the 23 MB list is only reread when it changed


def load_wishlist_index(plug_names):
    """(rolls, rolls by weapon name) of the default wishlist; (None, None) when it cannot be had."""
    global _wishlist
    try:
        path, _ = wishlists.fetch(wishlists.DEFAULT_WISHLIST)
        key = (path, path.stat().st_mtime_ns, plug_names)
        if _wishlist[0] == key:
            return _wishlist[1]
        rolls, _, names = wishlists.load(path, plug_names)
    except (OSError, ValueError):
        return None, None
    by_name = defaultdict(list)
    for h, n in names.items():
        if n:
            by_name[wishlists.norm_weapon(n)].append(h)
    _wishlist = (key, (rolls, by_name))
    return rolls, by_name


def _oneline(text):
    return re.sub(r"\s*\n\s*", " / ", text or "")


def _variant(row):
    """Lines of the `Name` cell after the first ("RotN version"), to tell two rows of a weapon apart."""
    return _oneline((row.get("Name") or "").partition("\n")[2].strip())


def aegis_label(w):
    """"S #1" (best Aegis row for this weapon, `+` when there are several), or "" when it is not rated."""
    rows = aegis.weapon_rows(w["name"])
    b = aegis.best(rows)
    return "" if b is None else aegis.tier_label(b) + ("+" if len(rows) > 1 else "")


def suggest(w, wished, recommended):
    """Default option of each column with choices, the same every time: cited by Aegis and the wishlist, then by
    Aegis, then by the wishlist; what is in place first, then column order, among equals. `wished`, `recommended`:
    perk names as `detail` compares them."""
    out = []
    for c in w.get("columns", []):
        usable = [o for o in c.get("options", []) if o.get("canInsert") is not False]
        if len(c.get("options", [])) < 2 or not usable:
            continue

        def score(o):
            cited = bool(wished) and wishlists.norm_perk(o["name"]) in wished
            return (norm(o["name"]) in recommended, cited)

        out.append(max(sorted(usable, key=lambda o: o["name"] != c["selected"]), key=score))
    return [o["name"] for o in out]


def detail(w, grades, wishlist=None):
    """Lines of a weapon's detail: header, then one line per column with all its options.
    `wishlist`: result of `wishlist_perks`, None when the wishlist is unavailable."""
    wished, full = wishlist if wishlist is not None else (None, False)
    rated = sorted(aegis.weapon_rows(w["name"]), key=aegis.tier_key)
    recommended = set().union(*(aegis.perk_names(r) for r in rated)) if rated else set()
    tier = w.get("gearTier")
    head = [w["name"], w["itemId"], w["type"], w["element"], w["slot"], f"tier {'—' if tier is None else tier}",
            f"grade {grades.get(w['itemId'], '—')}", f"mod: {w.get('mod') or '—'}"]
    if wishlist is not None:
        head.append("full wishlist roll available" if full else "no full wishlist roll")
    if w.get("masterwork"):
        head.append(w["masterwork"])
    if w.get("crafted"):
        head.append("crafted")
    if rated:
        head.append(f"Aegis {aegis.tier_label(rated[0])} ({rated[0]['_tab']})")
    lines = [" | ".join(head)]
    for c in w.get("columns", []):
        opts = []
        for o in c.get("options", []):
            text = o["name"] + ("*" if o.get("enhanced") else "")
            if wished and wishlists.norm_perk(o["name"]) in wished:
                text += " ✓"
            if norm(o["name"]) in recommended:
                text += " A"
            if o["name"] == c["selected"]:
                text += " (selected)"
            if o.get("canInsert") is False:
                text += " (not insertable)"
            opts.append(text)
        lines.append(f"  {c['label']}: {' / '.join(opts)}")
    suggested = suggest(w, wished, recommended)
    if suggested:
        lines.append(f"  suggested: {' | '.join(suggested)}")
    if wished is None:
        lines.append("  (wishlist unavailable: run the weapon-triage skill)")
    for r in rated:
        where = ", ".join(x for x in (r["_tab"], _variant(r)) if x)
        lines.append(f"  Aegis {aegis.tier_label(r)} ({where}): MW {_oneline(r.get('MW')) or '—'} · "
                     f"{_oneline(r.get('Notes')) or '—'}")
    return lines


def fmt(w, grades):
    perks = ", ".join(_column(c) for c in w.get("columns", []) if c["label"] not in EXCLUDED_COLUMNS)
    parts = [w["itemId"], w["name"], w["type"], w["element"], w["slot"], w.get("ammo") or "—",
             w.get("frame") or "—", perks or "—", f"grade {grades.get(w['itemId'], '—')}",
             f"aegis {aegis_label(w) or '—'}", "locked" if w.get("locked") else "unlocked", w.get("location", "")]
    if w.get("equipped"):
        parts.append("equipped")
    if w.get("crafted"):
        parts.append("crafted")
    return " | ".join(parts)


def candidates(items, grades, slot=None, element=None, type_=None, name=None, perk=None, limit=40):
    """fmt lines of the matching weapons, at most `limit`, then a line counting the rest."""
    if limit < 1:
        raise ValueError("limit must be >= 1")
    rows = select(items, slot, element, type_, name, grades, perk)
    if not rows:
        return ["no matching weapon"]
    lines = [fmt(w, grades) for w in rows[:limit]]
    extra = len(rows) - limit
    if extra > 0:
        lines.append(f"… {extra} more (narrow the filters or raise limit)")
    return lines
