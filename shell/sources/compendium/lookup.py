"""Finds Compendium entries (cache/compendium/<tab>.md, `## section` then `### name`) by name, whatever the spelling."""
import difflib
import re

from shell.sources.aegis.names import norm
from shell.sources.compendium import folder

FETCHED = re.compile(r"fetched on (\d{4}-\d{2}-\d{2})")
NOISE = re.compile(r"\b(the|of|a|an)\b", re.I)


def _key(name):
    """Names compared without small words: "Spirit of Inmost Light" = "Spirit of the Inmost Light"."""
    return norm(NOISE.sub(" ", name))


def entries(file=None):
    """Every entry: {file, section, name, fetched, text}."""
    out = []
    for path in sorted(folder().glob("*.md")):
        if path.stem == "index" or file not in (None, path.stem):
            continue
        text = path.read_text(encoding="utf-8")
        fetched = FETCHED.search(text)
        section, current = "", None
        for line in text.splitlines():
            if line.startswith("### "):
                current = {"file": path.stem, "section": section, "name": line[4:].strip(),
                           "fetched": fetched and fetched.group(1), "lines": []}
                out.append(current)
            elif line.startswith("## "):
                section, current = line[3:].strip(), None
            elif current is not None:
                current["lines"].append(line)
    for e in out:
        e["text"] = "\n".join(e.pop("lines")).strip()
    return out


def _words(name):
    return set(re.findall(r"\w+", NOISE.sub(" ", name).lower()))


def find(name, file=None, limit=10):
    """{"matches", "partial", "more", "suggestions"}: entries of this name, else those containing it, else (`partial`)
    those whose name is part of it: the Compendium has "Siphon" for "Arc Siphon", "Shock" for "Spark of Shock".
    `suggestions`: the closest names when nothing matches exactly."""
    every = entries(file)
    key, words = _key(name), _words(name)
    found = [e for e in every if _key(e["name"]) == key] or [e for e in every if key and key in _key(e["name"])]
    partial = not found
    if partial:
        found = sorted((e for e in every if _words(e["name"]) and _words(e["name"]) <= words),
                       key=lambda e: -len(_words(e["name"])))
    names = {_key(e["name"]): e["name"] for e in every} if partial else {}
    return {"matches": found[:limit], "partial": partial and bool(found), "more": max(0, len(found) - limit),
            "suggestions": [names[k] for k in difflib.get_close_matches(key, sorted(names), n=5, cutoff=0.6)]}
