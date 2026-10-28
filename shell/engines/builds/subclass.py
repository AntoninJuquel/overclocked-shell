"""Aspects and fragments of a subclass: sheet check against the catalog's subclass index, and the options list."""
from shell.engines.builds import stats as stats_mod
from shell.engines.builds.catalog import KIND_LABELS, build_index  # noqa: F401  (build_index: tests and callers)
from shell.engines.builds.stats import STATS, FragmentNotFound, fragment_stats
from shell.sources.aegis import lookup as aegis

MAX_ASPECTS = 2


def _duplicates(names, key=lambda n: n):
    seen, dup = set(), []
    for n in names:
        if key(n) in seen and n not in dup:
            dup.append(n)
        seen.add(key(n))
    return dup


def _n(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"


def _known_aspect(name, known):
    """Exact name of the aspect (case-insensitive comparison), or None."""
    for k in known:
        if k.lower() == name.lower():
            return k
    return None


def fragment_slots(s, idx):
    """Fragment slots of a sheet: sum of the MAX_ASPECTS best known aspects."""
    sub = s["subclass"]
    known = idx[sub["element"]]["aspects"][s["class"]]
    slots = sorted((known[n] for n in dict.fromkeys(sub.get("aspects", [])) if n in known), reverse=True)
    return sum(slots[:MAX_ASPECTS])


def check(s, idx):
    """Problems of a sheet's subclass (empty list = valid)."""
    cls, sub = s["class"], s["subclass"]
    element = sub["element"]
    aspects, fragments = sub.get("aspects", []), sub.get("fragments", [])
    known_aspects = idx[element]["aspects"][cls]
    known_fragments = idx[element]["fragments"]
    by_key = {stats_mod.fragment_key(n).lower(): n for n in known_fragments}
    problems = []
    if not aspects:
        problems.append("no aspect")
    if len(aspects) > MAX_ASPECTS:
        problems.append(f"{_n(len(aspects), 'aspect')} (at most {MAX_ASPECTS})")
    problems += [f"duplicate aspect: {n}" for n in _duplicates(aspects)]
    unknown_aspect = False
    for n in aspects:
        if n in known_aspects:
            continue
        unknown_aspect = True
        hint = _known_aspect(n, known_aspects)
        problems.append(f"unknown aspect for {cls} {element}: {n}" + (f" (expected name: {hint})" if hint else ""))
    problems += [f"duplicate fragment: {n}"
                 for n in _duplicates(fragments, lambda n: stats_mod.fragment_key(n).lower())]
    for n in fragments:
        if n in known_fragments:
            continue
        hint = by_key.get(stats_mod.fragment_key(n).lower())
        problems.append(f"unknown fragment for {element}: {n}" + (f" (expected name: {hint})" if hint else ""))
    known = idx[element]["abilities"][cls]
    given = [("super", sub.get("super"))] + [(k, (sub.get("abilities") or {}).get(k))
                                             for k in ("grenade", "melee", "class", "jump")]
    for kind, n in given:
        if not n or n in known[kind]:
            continue
        hint = _known_aspect(n, known[kind])
        problems.append(f"unknown {kind} for {cls} {element}: {n}" + (f" (expected name: {hint})" if hint else ""))
    if not unknown_aspect:
        slots = fragment_slots(s, idx)
        if len(fragments) > slots:
            problems.append(f"{_n(len(fragments), 'fragment')} for {_n(slots, 'slot')}")
    return problems


def _fmt_stats(stats):
    return " · ".join(f"{stats[k]:+d} {k}" for k in STATS if stats.get(k)) or "—"


def _aegis(slug, name):
    """" · Aegis S #1" of an aspect or fragment (Endgame Analysis), "" when it is not rated."""
    b = aegis.best(aegis.find("endgame", slug, name))
    return f" · Aegis {aegis.tier_label(b)}" if b else ""


def list_text(idx, cls, element):
    lines = [f"Aspects {cls} {element} (fragment slots, Aegis tier):"]
    lines += [f"- {n}: {slots}{_aegis('aspects', n)}" for n, slots in sorted(idx[element]["aspects"][cls].items())]
    for kind, label in KIND_LABELS.items():
        lines.append(f"{label}: " + (", ".join(sorted(idx[element]["abilities"][cls][kind])) or "—"))
    lines += ["", f"Fragments {element} (stat bonuses from the compendium, Aegis tier):"]
    names = sorted(idx[element]["fragments"])
    file = f"subclass-{element.lower()}.md"
    if not (stats_mod.compendium_dir() / file).exists():
        lines.append(f"compendium missing ({file}): run refresh_references(source=\"compendium\")")
        names = []
    for name in names:
        try:
            stats = _fmt_stats(fragment_stats([name], element, cls))
        except FragmentNotFound:
            stats = "? (not in the compendium)"
        except ValueError as e:
            stats = f"? ({e})"
        lines.append(f"- {name}: {stats}{_aegis('fragments', name)}")
    return "\n".join(lines)
