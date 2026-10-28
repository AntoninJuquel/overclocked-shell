"""Reference data sources, discovered like MCP tool modules: any module or package directly under
shell/sources/ with `NAME` and `refresh` is a source.

Contract: `refresh(force: bool = False, only: list[str] | None = None) -> dict` fetches (from its cache
unless `force`), normalizes, writes into `cache/<NAME>/` and returns
`{"source", "ok", "changed", "stale", "errors", "folder"}`:
- changed: output files that appeared or changed (Aegis: its diff lines)
- stale: inputs served from the cache after a failed or invalid download
- only: tab names, for sources that have tabs; ignored otherwise
"""
import importlib
import os
import pkgutil
from pathlib import Path
from types import ModuleType


def sources() -> dict[str, ModuleType]:
    found = {}
    for info in pkgutil.iter_modules(__path__):
        module = importlib.import_module(f"{__name__}.{info.name}")
        if hasattr(module, "NAME") and hasattr(module, "refresh"):
            found[module.NAME] = module
    return found


def write_if_changed(path: Path, text: str) -> bool:
    """Atomic write; True when the file is new or its content changed."""
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return True


def report(name: str, folder: Path, changed=(), stale=(), errors=()) -> dict:
    return {"source": name, "ok": not errors, "changed": list(changed), "stale": list(stale),
            "errors": list(errors), "folder": str(folder)}
