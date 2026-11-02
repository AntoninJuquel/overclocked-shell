"""YAML export of a build sheet, to share: the build as designed (no `resolved`, no hash of what only it names).

No YAML dependency: sheets hold only objects, lists, text, numbers, booleans and null, and a JSON string is a valid YAML
double-quoted scalar.
"""
import json
import re

PLAIN = re.compile(r"[A-Za-z][\w .'+-]*\w")  # no quoting needed
RESERVED = {"true", "false", "null", "yes", "no", "on", "off", "y", "n"}
ALWAYS_KEPT = ("stat:", "setperk:")  # names the sheet doesn't spell out


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def shareable(s: dict) -> dict:
    """The sheet without `resolved`, and its hash table without the names only `resolved` holds."""
    out = {k: v for k, v in s.items() if k not in ("resolved", "hashes")}
    if s.get("hashes"):
        names = set(_strings(out))
        out["hashes"] = {k: h for k, h in s["hashes"].items()
                         if k.startswith(ALWAYS_KEPT) or k.split(":", 1)[1] in names}
    return out


def _scalar(v):
    if isinstance(v, str):
        plain = PLAIN.fullmatch(v) and v.lower() not in RESERVED
        return v if plain else json.dumps(v, ensure_ascii=False)
    return json.dumps(v)  # numbers, true, false, null; empty [] and {}


def _is_block(v):
    return isinstance(v, (dict, list)) and bool(v)


def _lines(value, indent=0):
    pad = " " * indent
    out = []
    if isinstance(value, dict):
        for k, v in value.items():
            if _is_block(v):
                out += [f"{pad}{_scalar(k)}:", *_lines(v, indent + 2)]
            else:
                out.append(f"{pad}{_scalar(k)}: {_scalar(v)}")
    else:
        for v in value:
            if _is_block(v):
                first, *rest = _lines(v, indent + 2)
                out += [f"{pad}- {first.lstrip()}", *rest]
            else:
                out.append(f"{pad}- {_scalar(v)}")
    return out


def render(s: dict) -> str:
    return "\n".join(_lines(shareable(s))) + "\n"
