"""Game names in the player's language, as DIM shows them: English name → localized name, matched by hash between the
English manifest and the manifest in the configured language, plus a small table of output labels per language
(`locale/<lang>.json`). Saved data stays English; outputs translate when they render.

Cached in cache/lexicon.json ({lang, version, terms}), rebuilt when the language or the manifest version changes, so
renderers without a manifest at hand (`sheet.save`) read it with `cached()`.
"""
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

from shell.core import paths

# (table, extra name fields besides displayProperties.name)
TABLES = [
    ("DestinyInventoryItemDefinition", ("itemTypeDisplayName",)),
    ("DestinyStatDefinition", ()), ("DestinyInventoryBucketDefinition", ()), ("DestinyDamageTypeDefinition", ()),
    ("DestinyClassDefinition", ()), ("DestinyEquipableItemSetDefinition", ()), ("DestinySandboxPerkDefinition", ()),
    ("DestinyActivityDefinition", ()), ("DestinyActivityModifierDefinition", ()),
]
LOCALE_DIR = Path(__file__).parent / "locale"
_ALNUM = re.compile(r"[^\W_]")   # letters / digits bound a name, not _ (md italics)
_NAME_START = re.compile(r"(?<![^\W_]).", re.S)


def _names(table: dict, extra) -> dict[tuple[str, str], str]:
    out = {}
    for h, d in table.items():
        name = (d.get("displayProperties") or {}).get("name")
        if name:
            out[(h, "name")] = name
        for f in extra:
            if d.get(f):
                out[(h, f)] = d[f]
    return out


def build(en_manifest, local_manifest) -> dict[str, str]:
    """{English name: localized name} for every name that differs; an English name with several translations keeps
    the most frequent one."""
    seen = defaultdict(Counter)
    for name, extra in TABLES:
        en = _names(en_manifest.table(name, keep=False), extra)   # tables read one at a time: the item table is huge
        local = _names(local_manifest.table(name, keep=False), extra)
        for key, english in en.items():
            other = local.get(key)
            if other and other != english and len(english) > 2:
                seen[english.strip()][other.strip()] += 1
    return {en: c.most_common(1)[0][0] for en, c in seen.items()}


def labels(lang: str) -> dict[str, str]:
    file = LOCALE_DIR / f"{lang}.json"
    return json.loads(file.read_text(encoding="utf-8")) if file.exists() else {}


def _file() -> Path:
    return paths.cache_dir() / "lexicon.json"


def load(en_manifest, lang: str) -> dict[str, str]:
    """Terms for `lang` (labels included), from the cache or built from the manifests (downloads the `lang` tables
    once per manifest version)."""
    if lang == "en":
        _write({"lang": "en", "version": None, "terms": {}})
        return {}
    version = en_manifest.version()
    try:
        cached = json.loads(_file().read_text(encoding="utf-8"))
        if cached.get("lang") == lang and cached.get("version") == version:
            return cached["terms"]
    except (OSError, ValueError):
        pass
    from shell.core.manifest import Manifest
    terms = {**build(en_manifest, Manifest(en_manifest.client, en_manifest.root.parent, lang)), **labels(lang)}
    _write({"lang": lang, "version": version, "terms": terms})
    return terms


def local_table(en_manifest, lang: str, name: str) -> dict:
    """Manifest table `name` in `lang`, for texts the terms don't hold (descriptions)."""
    if lang == "en":
        return en_manifest.table(name, keep=False)
    from shell.core.manifest import Manifest
    return Manifest(en_manifest.client, en_manifest.root.parent, lang).table(name, keep=False)


def _write(data):
    file = _file()
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, file)


def cached() -> dict[str, str]:
    """The last terms `load` wrote ({} if none: English)."""
    try:
        return json.loads(_file().read_text(encoding="utf-8"))["terms"]
    except (OSError, ValueError, KeyError):
        return {}


_current = (None, None)


def current():
    """`translator(cached())`, compiled again only when the cache file changes."""
    global _current
    file = _file()
    try:
        stat = file.stat()
        key = (file, stat.st_mtime_ns, stat.st_size)   # two quick writes can share a timestamp
    except OSError:
        key = (file, None)
    if _current[0] != key:
        _current = (key, translator(cached()))
    return _current[1]


def translator(terms: dict[str, str]):
    """str → str replacing every known English name (whole words, longest first; ALL CAPS too). Identity if empty."""
    if not terms:
        return lambda t: t
    full = {**{k.upper(): v.upper() for k, v in terms.items()}, **terms}
    # not one regex of every name: with 40,000 of them it takes seconds to compile and tries them all at each position
    lengths = defaultdict(set)
    for k in full:
        lengths[k[0]].add(len(k))
    lengths = {c: sorted(v, reverse=True) for c, v in lengths.items()}

    def translate(text):
        if not text:
            return text
        out, done = [], 0
        for start in _NAME_START.finditer(text):
            p = start.start()
            if p < done:
                continue
            for n in lengths.get(text[p], ()):
                name = text[p:p + n]
                if name in full and not _ALNUM.match(text, p + n):
                    out += [text[done:p], full[name]]
                    done = p + n
                    break
        out.append(text[done:])
        return "".join(out)
    return translate


def lookup(terms: dict[str, str], names: list[str]) -> tuple[dict[str, str], list[str]]:
    """({name: localized}, unknown names). Exact names, case-insensitive."""
    folded = {k.casefold(): v for k, v in terms.items()}
    found = {n: folded[n.strip().casefold()] for n in names if n.strip().casefold() in folded}
    return found, [n for n in names if n not in found]
