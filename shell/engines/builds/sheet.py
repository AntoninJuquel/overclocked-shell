"""Build sheet: validation, loading, saving (the JSON is the source of truth, plus a regenerated Markdown view)."""
import json
import os
import re
import unicodedata
from pathlib import Path

from shell.core import paths
from shell.engines.builds.rules import (ARTIFACT_SOCKET_COLUMNS, MAX_EXOTIC_WEAPONS, SLOT_AMMO, SLOT_ELEMENTS,
                                        UTILITY_SOCKETS, WEAPON_ELEMENTS, WEAPON_SLOTS, element_fits)
from shell.engines.builds.stats import CAP, CLASSES, ELEMENTS, SLOTS, STATS
from shell.outputs import build_md


class SheetError(ValueError):
    """Invalid sheet; the message starts with the field at fault."""


def _check(cond, field, message):
    if not cond:
        raise SheetError(f"{field}: {message}")


def _text(value):
    return isinstance(value, str) and value.strip() != ""


ABILITY_KINDS = ("grenade", "melee", "class", "jump")
GAP_KINDS = ("weapon", "catalyst", "upgrade")
MASTERWORK_MIGRATION = {"à faire": "todo", "fait": "done"}  # dim-agent's French values


def folder() -> Path:
    return paths.profile_dir() / "builds"


def path_for(slug: str) -> Path:
    return folder() / f"{slug}.json"


def _opt_text(d, key, field):
    """Optional text: absent, None or a string."""
    _check(d.get(key) is None or isinstance(d[key], str), field, "text expected")


def _int(value):
    return type(value) is int  # excludes booleans


def _text_list(value, field):
    _check(isinstance(value, list) and all(_text(x) for x in value), field, "list of names expected")


def validate_sets(sets, field):
    """List of sets {set, pieces}: 2 or 4 pieces, no duplicate, 4 pieces at most (the exotic is not one of them)."""
    _check(isinstance(sets, list), field, "list expected")
    names = set()
    for i, entry in enumerate(sets):
        _check(isinstance(entry, dict) and _text(entry.get("set")), f"{field}[{i}].set", "set name required")
        _check(entry["set"] not in names, f"{field}[{i}].set", "duplicate set")
        names.add(entry["set"])
        _check(_int(entry.get("pieces")) and entry["pieces"] in (2, 4), f"{field}[{i}].pieces", "must be 2 or 4")
    _check(sum(e["pieces"] for e in sets) <= 4, field, "at most 4 set pieces (the exotic is not one of them)")


def _validate_resolved(res):
    _check(isinstance(res, dict), "resolved", "object expected")
    _opt_text(res, "date", "resolved.date")
    armor = res.get("armor", [])
    _check(isinstance(armor, list), "resolved.armor", "list expected")
    seen = set()
    for i, a in enumerate(armor):
        f = f"resolved.armor[{i}]"
        _check(isinstance(a, dict), f, "object expected")
        _check(a.get("slot") in SLOTS, f"{f}.slot", f"must be one of {', '.join(SLOTS)}")
        _check(a["slot"] not in seen, f"{f}.slot", "duplicate slot")
        seen.add(a["slot"])
        for key in ("name", "itemId"):
            _check(_text(a.get(key)), f"{f}.{key}", "text required")
        for key in ("masterwork", "stat_mod", "tuning"):
            _opt_text(a, key, f"{f}.{key}")
        if "mods" in a:
            _text_list(a["mods"], f"{f}.mods")
            _check(len(a["mods"]) <= UTILITY_SOCKETS, f"{f}.mods", f"at most {UTILITY_SOCKETS} slot mods")
    weapons = res.get("weapons", [])
    _check(isinstance(weapons, list), "resolved.weapons", "list expected")
    seen_weapons = set()
    for i, w in enumerate(weapons):
        f = f"resolved.weapons[{i}]"
        _check(isinstance(w, dict), f, "object expected")
        _check(w.get("slot") in WEAPON_SLOTS, f"{f}.slot", f"must be one of {', '.join(WEAPON_SLOTS)}")
        _check(w["slot"] not in seen_weapons, f"{f}.slot", "duplicate slot")
        seen_weapons.add(w["slot"])
        for key in ("name", "itemId"):
            _check(_text(w.get(key)), f"{f}.{key}", "text required")
        _opt_text(w, "why", f"{f}.why")
        _opt_text(w, "mod", f"{f}.mod")
        if "perks" in w:
            _text_list(w["perks"], f"{f}.perks")
            _check(len(set(w["perks"])) == len(w["perks"]), f"{f}.perks", "duplicate perk")
    stats = res.get("stats", {})
    _check(isinstance(stats, dict), "resolved.stats", "object expected")
    for stat, value in stats.items():
        _check(stat in STATS, f"resolved.stats.{stat}", f"unknown stat (stats: {', '.join(STATS)})")
        _check(_int(value) and value >= 0, f"resolved.stats.{stat}", "non-negative integer expected")
    if "sets" in res:
        validate_sets(res["sets"], "resolved.sets")
    gaps = res.get("gaps", [])
    _check(isinstance(gaps, list), "resolved.gaps", "list expected")
    seen_gaps = set()
    for i, g in enumerate(gaps):
        f = f"resolved.gaps[{i}]"
        _check(isinstance(g, dict), f, "object expected")
        _check(g.get("kind") in GAP_KINDS, f"{f}.kind", f"must be one of {', '.join(GAP_KINDS)}")
        _check(_text(g.get("target")), f"{f}.target", "text required")
        try:
            key = (g["kind"], slug(g["target"]))
        except ValueError:
            raise SheetError(f"{f}.target: name without a usable character") from None
        _check(key not in seen_gaps, f, "duplicate gap")
        seen_gaps.add(key)
        effects = g.get("effects", [])
        _check(isinstance(effects, list) and all(isinstance(e, str) for e in effects), f"{f}.effects",
               "list of texts expected")
    rationale = res.get("rationale", [])
    _check(isinstance(rationale, list), "resolved.rationale", "list expected")
    for i, r in enumerate(rationale):
        _check(isinstance(r, str), f"resolved.rationale[{i}]", "text expected")


def validate(s):
    _check(isinstance(s, dict), "sheet", "must be a JSON object")
    _check(_text(s.get("name")), "name", "name required")
    _check(s.get("class") in CLASSES, "class", f"must be one of {', '.join(CLASSES)}")
    _opt_text(s, "activity", "activity")
    _opt_text(s, "concept", "concept")
    sub = s.get("subclass")
    _check(isinstance(sub, dict), "subclass", "object required")
    _check(sub.get("element") in ELEMENTS, "subclass.element", f"must be one of {', '.join(ELEMENTS)}")
    _opt_text(sub, "super", "subclass.super")
    abilities = sub.get("abilities", {})
    _check(isinstance(abilities, dict), "subclass.abilities", "object expected")
    for kind, name in abilities.items():
        _check(kind in ABILITY_KINDS, f"subclass.abilities.{kind}", f"unknown kind ({', '.join(ABILITY_KINDS)})")
        _check(_text(name), f"subclass.abilities.{kind}", "name expected")
    for key in ("aspects", "fragments"):
        _text_list(sub.get(key, []), f"subclass.{key}")
    intent = s.get("intent")
    _check(isinstance(intent, dict), "intent", "object required")
    exotic = intent.get("exotic")
    _check(isinstance(exotic, dict) and _text(exotic.get("name")), "intent.exotic.name", "exotic name required")
    _text_list(exotic.get("perks", []), "intent.exotic.perks")
    st = intent.get("stats", {})
    _check(isinstance(st, dict), "intent.stats", "object required")
    minimums = st.get("minimums", {})
    _check(isinstance(minimums, dict), "intent.stats.minimums", "object expected")
    for stat, value in minimums.items():
        field = f"intent.stats.minimums.{stat}"
        _check(stat in STATS, field, f"unknown stat (stats: {', '.join(STATS)})")
        _check(_int(value) and 0 <= value <= CAP, field, f"must be an integer between 0 and {CAP}")
    prio = st.get("priority", [])
    _check(isinstance(prio, list) and all(isinstance(p, str) and p in STATS for p in prio) and len(set(prio)) == len(prio),
           "intent.stats.priority", "list of distinct stats expected")
    validate_sets(intent.get("sets", []), "intent.sets")
    for key in ("armor_mods", "armor_mods_fill"):
        mods = intent.get(key, {})
        _check(isinstance(mods, dict), f"intent.{key}", "object expected")
        for slot, mod_names in mods.items():
            _check(slot in SLOTS, f"intent.{key}.{slot}", f"unknown slot ({', '.join(SLOTS)})")
            _text_list(mod_names, f"intent.{key}.{slot}")
    for slot, mod_names in intent.get("armor_mods", {}).items():
        _check(len(mod_names) <= UTILITY_SOCKETS, f"intent.armor_mods.{slot}",
               f"at most {UTILITY_SOCKETS} slot mods")
    weapons = intent.get("weapons", [])
    _check(isinstance(weapons, list), "intent.weapons", "list expected")
    seen_weapons = set()
    for i, w in enumerate(weapons):
        f = f"intent.weapons[{i}]"
        _check(isinstance(w, dict), f, "object expected")
        slot = w.get("slot")
        _check(slot in WEAPON_SLOTS, f"{f}.slot", f"must be one of {', '.join(WEAPON_SLOTS)}")
        _check(slot not in seen_weapons, f"{f}.slot", "duplicate slot")
        seen_weapons.add(slot)
        for key in ("role", "wanted", "type"):
            _opt_text(w, key, f"{f}.{key}")
        _check(w.get("exotic") is None or isinstance(w["exotic"], bool), f"{f}.exotic", "true or false expected")
        if w.get("element") is not None:
            _check(w["element"] in WEAPON_ELEMENTS, f"{f}.element", f"must be one of {', '.join(WEAPON_ELEMENTS)}")
            _check(element_fits(slot, w["element"], w.get("exotic")), f"{f}.element",
                   f"not possible in {slot} (possible elements: {', '.join(SLOT_ELEMENTS[slot])})")
        if w.get("ammo") is not None:
            _check(w["ammo"] in SLOT_AMMO[slot], f"{f}.ammo", f"not possible in {slot} ({', '.join(SLOT_AMMO[slot])})")
    _check(sum(1 for w in weapons if w.get("exotic")) <= MAX_EXOTIC_WEAPONS, "intent.weapons",
           f"at most {MAX_EXOTIC_WEAPONS} exotic weapon at a time")
    art = intent.get("artifact")
    if art is not None:
        _check(isinstance(art, dict) and _text(art.get("name")), "intent.artifact.name", "artifact name required")
        _text_list(art.get("perks", []), "intent.artifact.perks")
        _check(len(art.get("perks", [])) <= len(ARTIFACT_SOCKET_COLUMNS), "intent.artifact.perks",
               f"at most {len(ARTIFACT_SOCKET_COLUMNS)} perks")
    if "resolved" in s:
        _validate_resolved(s["resolved"])
    return s


def migrate(s) -> dict:
    """dim-agent sheets: French masterwork values become "todo" / "done"; free text is left as written."""
    res = s.get("resolved") if isinstance(s, dict) else None
    armor = res.get("armor") if isinstance(res, dict) else None
    for a in armor if isinstance(armor, list) else []:
        if isinstance(a, dict) and a.get("masterwork") in MASTERWORK_MIGRATION:
            a["masterwork"] = MASTERWORK_MIGRATION[a["masterwork"]]
    return s


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise SheetError(f"sheet: invalid JSON ({e})") from e
    except UnicodeDecodeError as e:
        raise SheetError(f"sheet: invalid encoding, UTF-8 expected ({e})") from e
    return validate(migrate(data))


def _atomic_write(path, text):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def save(path, s, needs_dir: Path | None = None):
    """Writes the sheet (JSON) and regenerates its Markdown view next to it; nothing is written if the sheet is invalid."""
    validate(s)
    path = Path(path)
    js = json.dumps(s, indent=2, ensure_ascii=False) + "\n"
    md = build_md.render(s, path.name, needs_for(path.stem, needs_dir))
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, js)
    _atomic_write(path.with_suffix(".md"), md)


def slug(name):
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    result = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    if not result:
        raise ValueError(f"name without a usable character for a file: {name!r}")
    return result


def needs_for(slug, needs_dir: Path | None = None):
    """[(need, gain)] of sheet `slug` in profile/todo/needs.json, without the entries done or ignored
    (profile/todo/state.json), largest gain first. Empty list when the needs were never computed."""
    needs_dir = Path(needs_dir) if needs_dir is not None else paths.profile_dir() / "todo"
    try:
        state = json.loads((needs_dir / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    try:
        needs = json.loads((needs_dir / "needs.json").read_text(encoding="utf-8"))["needs"]
        out = [(n, b["gain"]) for n in needs if state.get(n["id"], {}).get("status") not in ("done", "ignored")
               for b in n["builds"] if b["build"] == slug]
        return sorted(out, key=lambda ng: -ng[1]["score"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):   # needs.json missing or malformed
        return []
