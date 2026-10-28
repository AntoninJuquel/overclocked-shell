"""Bungie API OpenAPI spec (source of https://bungie-net.github.io/) as Markdown in cache/bungie-api/:
index.md, one endpoints-<tag>.md per endpoint group and one schemas-<namespace>.md per schema namespace.
Regenerated files fully replace the previous ones."""
import json
import re
from collections import defaultdict

from shell.core import paths
from shell.sources import report, write_if_changed
from shell.sources.sheets.fetch import cached, file_date

NAME = "bungie-api"
SPEC_URL = "https://raw.githubusercontent.com/Bungie-net/api/master/openapi.json"
SITE = "https://bungie-net.github.io/"
BASE_URL = "https://www.bungie.net/Platform"
METHODS = ("get", "post", "put", "delete", "patch")


def folder():
    return paths.cache_dir() / "bungie-api"


def _valid(text):
    try:
        spec = json.loads(text)
    except ValueError:
        return False
    return isinstance(spec, dict) and "paths" in spec and "schemas" in spec.get("components", {})


def ref_name(ref):
    """'#/components/schemas/Destiny.DamageType' -> 'Destiny.DamageType'."""
    return ref.rsplit("/", 1)[-1]


def type_str(s):
    """Readable type of an OpenAPI schema (with Bungie's x-* extensions)."""
    if not s:
        return "?"
    if "$ref" in s:
        t = ref_name(s["$ref"])
    elif s.get("allOf"):
        t = " & ".join(type_str(x) for x in s["allOf"])
    elif "x-enum-reference" in s:
        t = "enum " + ref_name(s["x-enum-reference"]["$ref"])
        if s.get("x-enum-is-bitmask"):
            t += " (bitmask)"
    elif s.get("type") == "array":
        inner = type_str(s.get("items"))
        t = f"({inner})[]" if " " in inner else inner + "[]"
    elif s.get("type") == "object" and "additionalProperties" in s:
        key = type_str(s.get("x-dictionary-key", {"type": "string"}))
        t = f"map<{key}, {type_str(s['additionalProperties'])}>"
    elif s.get("type") in ("integer", "number"):
        t = s.get("format") or s["type"]
    elif s.get("type") == "string" and s.get("format"):
        t = s["format"]
    else:
        t = s.get("type", "object")
    if "x-mapped-definition" in s:
        t += " → " + ref_name(s["x-mapped-definition"]["$ref"])
    if s.get("nullable"):
        t += "?"
    return t


def clean(text):
    """Description on a single Markdown line (Bungie's \\r\\n become spaces)."""
    return re.sub(r"\s+", " ", text or "").strip()


MIN_GROUP = 5  # a smaller Destiny namespace joins its parent


def group_schemas(names):
    """{logical file: [schemas]}. Destiny: namespace of at most 3 levels, small ones moving up to their
    parent. Generics with no namespace (SingleComponentResponseOf…, SearchResultOf…): 'Generics'.
    Everything else (forums, clans, accounts…): 'BungieNet'."""
    groups = defaultdict(list)
    for name in names:
        parts = name.split(".")[:-1]
        if parts and parts[0] == "Destiny":
            groups[".".join(parts[:3])].append(name)
        elif not parts and "Of" in name:
            groups["Generics"].append(name)
        else:
            groups["BungieNet"].append(name)
    for depth in (3, 2):
        for key in [k for k in groups if k.count(".") == depth - 1 and len(groups[k]) < MIN_GROUP]:
            groups[key.rsplit(".", 1)[0]].extend(groups.pop(key))
    return groups


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "misc"


def render_schema(name, s):
    out = [f"### {name}" + (" (enum)" if "x-enum-values" in s else ""), ""]
    if s.get("description"):
        out += [clean(s["description"]), ""]
    if s.get("x-mobile-manifest-name"):
        out += [f"Manifest definition: table `{name.rsplit('.', 1)[-1]}`"
                f" (mobile: `{s['x-mobile-manifest-name']}`).", ""]
    if "x-enum-values" in s:
        if s.get("x-enum-is-bitmask"):
            out += ["Bitmask: values combine.", ""]
        for v in s["x-enum-values"]:
            desc = clean(v.get("description"))
            out.append(f"- `{v['numericValue']}` {v['identifier']}" + (f" — {desc}" if desc else ""))
        out.append("")
        return out
    props = s.get("properties") or {}
    if not props and s.get("type") != "object":
        out += [f"Type: `{type_str(s)}`", ""]
    for pname, p in props.items():
        line = f"- `{pname}` (`{type_str(p)}`)"
        desc = clean(p.get("description"))
        if p.get("x-destiny-component-type-dependency"):
            desc = re.sub(r"\s*COMPONENT TYPE: \w+$", "", desc)
            desc += f" [component: {p['x-destiny-component-type-dependency']}]"
        out.append(line + (f" — {desc.strip()}" if desc.strip() else ""))
    if props:
        out.append("")
    return out


def response_type(spec, op):
    """Type of the Response field an endpoint returns (standard Bungie envelope)."""
    resp = op.get("responses", {}).get("200", {})
    if "$ref" in resp:
        resp = spec["components"]["responses"].get(ref_name(resp["$ref"]), {})
    schema = resp.get("content", {}).get("application/json", {}).get("schema", {})
    return type_str(schema.get("properties", {}).get("Response")) if schema else "?"


def render_endpoint(spec, path, method, op):
    out = [f"### {op['operationId']}" + (" (deprecated)" if op.get("deprecated") else ""), "",
           f"`{method.upper()} {path}`", ""]
    if op.get("description"):
        out += [clean(op["description"]), ""]
    if op.get("x-preview"):
        out += ["Preview: may change without notice.", ""]
    scopes = sorted({sc for sec in op.get("security", []) for v in sec.values() for sc in v})
    if scopes:
        out += ["OAuth required, scopes: " + ", ".join(f"`{sc}`" for sc in scopes), ""]
    for k, v in (op.get("x-documentation-attributes") or {}).items():
        out += [f"{k}: {v}", ""]
    params = sorted(op.get("parameters", []), key=lambda p: (p["in"] != "path", p["name"]))
    if params:
        out.append("Parameters:")
        for p in params:
            req = ", required" if p.get("required") else ""
            desc = clean(p.get("description"))
            out.append(f"- `{p['name']}` ({p['in']}, `{type_str(p.get('schema'))}`{req})"
                       + (f" — {desc}" if desc else ""))
        out.append("")
    body = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
    if body:
        out += [f"Body: `{type_str(body)}`", ""]
    out += [f"Response: `{response_type(spec, op)}`", ""]
    return out


def build(spec, today):
    """{file name: content} for the whole spec."""
    info = spec.get("info", {})
    head = lambda title: [f"# {title}", "", f"Bungie API {info.get('version', '?')} — generated on {today}"
                          f" from {SPEC_URL}. Do not edit: `refresh_references(source='bungie-api', force=True)`.", ""]
    files, rows = {}, []

    by_tag = defaultdict(list)
    for path, item in spec["paths"].items():
        for method in METHODS:
            if method in item:
                op = item[method]
                by_tag[(op.get("tags") or [""])[0] or "Root"].append((path, method, op))
    for tag in sorted(by_tag):
        ops = sorted(by_tag[tag], key=lambda x: x[2]["operationId"])
        fname = f"endpoints-{slug(tag)}.md"
        lines = head(f"Endpoints {tag}") + [f"Base: `{BASE_URL}` + path.", ""]
        for path, method, op in ops:
            lines += render_endpoint(spec, path, method, op)
        files[fname] = "\n".join(lines)
        rows.append((f"Endpoints {tag}", fname, len(ops)))

    by_group = group_schemas(spec["components"]["schemas"])
    for group in sorted(by_group):
        names = sorted(by_group[group])
        fname = f"schemas-{slug(group)}.md"
        lines = head(f"Schemas {group}")
        for name in names:
            lines += render_schema(name, spec["components"]["schemas"][name])
        files[fname] = "\n".join(lines)
        rows.append((f"Schemas {group}", fname, len(names)))

    index = head("Bungie.net API (Markdown)") + [
        f"Readable docs: {SITE} · source: {SPEC_URL}",
        "",
        "Basics:",
        f"- Requests go to `{BASE_URL}` + path, with a mandatory `X-API-Key` header; endpoints with"
        " scopes also need an OAuth token (`Authorization: Bearer`).",
        "- Every response is an envelope `{Response, ErrorCode, ThrottleSeconds, ErrorStatus, Message,"
        " MessageData}`: the type shown as \"Response\" is that of `Response`. `ErrorCode`:"
        " enum `Exceptions.PlatformErrorCodes` (1 = Success).",
        "- Manifest definitions (`Destiny.Definitions.*Definition`) are referenced by `hash` (uint32);"
        " a `uint32 → X` type is a hash to resolve in table X.",
        "- `GetProfile`/`GetCharacter`/`GetItem` only return the requested components"
        " (`?components=`, enum `Destiny.DestinyComponentType`); every response property names its"
        " `[component: …]`.",
        "",
        "Searching:",
        "- a schema or an enum: `grep -n \"^### Destiny.DamageType\" cache/bungie-api/*.md`"
        " (full name) or `grep -n \"^### .*InventoryItemDefinition\" cache/bungie-api/*.md`, then read"
        " the section up to the next `###`;",
        "- an endpoint: `grep -n \"^### Destiny2.GetProfile\" cache/bungie-api/endpoints-*.md`;",
        "- by keyword: `grep -n -i \"<word>\" cache/bungie-api/*.md`.",
        "",
        "Type notation: `X[]` array, `map<K, V>` dictionary, `X?` nullable,"
        " `uint32 → Def` hash to a definition, `enum E (bitmask)` combinable flags.",
        "",
        "| Content | File | Entries |",
        "|---|---|---|",
    ] + [f"| {title} | [{f}]({f}) | {n} |" for title, f, n in rows] + [""]
    files["index.md"] = "\n".join(index)
    return files


def refresh(force: bool = False, only: list[str] | None = None) -> dict:
    raw = folder() / "raw" / "openapi.json"
    try:
        text, stale = cached(SPEC_URL, raw, force, validate=_valid)
    except OSError as e:
        return report(NAME, folder(), errors=[f"spec download failed: {e}"])
    # dated by the download, so an unchanged spec renders unchanged files
    files = build(json.loads(text), file_date(raw))
    for old in folder().glob("*.md"):
        if old.name not in files:
            old.unlink()
    changed = [name for name, content in files.items() if write_if_changed(folder() / name, content)]
    return report(NAME, folder(), changed=changed, stale=["openapi.json"] if stale else [])
