"""One-time import of a dim-agent folder: build sheets and TODO data into profile/ (never deletes anything).

dim-agent's version replaces Shell sheets of the same name and Shell's needs / sources / overrides files; sheets only
in Shell are kept, statuses are merged, and an invalid dim-agent sheet never replaces a valid Shell one.
"""
import json
import shutil
from pathlib import Path

from shell.engines.builds import sheet
from shell.engines.todo import state

TODO_FILES = ("needs.json", "sources.json", "overrides.json")


def _rank(entry: dict) -> tuple[bool, str]:
    """A status the player set (ignored, or done by hand) beats an automatic one; then the later `since`."""
    manual = entry.get("status") == "ignored" or (entry.get("status") == "done" and not entry.get("auto"))
    return manual, entry.get("since") or ""


def merge_state(ours: dict, theirs: dict) -> tuple[dict, dict]:
    """Union of need ids; for an id on both sides dim-agent's entry wins only if it ranks higher (ties stay Shell's,
    the tool used from now on)."""
    merged, counts = dict(ours), {"added": 0, "updated": 0, "kept": 0}
    for need_id, entry in theirs.items():
        mine = ours.get(need_id)
        if mine is None:
            counts["added"] += 1
        elif _rank(entry) <= _rank(mine):
            counts["kept"] += 1
            continue
        else:
            counts["updated"] += 1
        merged[need_id] = entry
    counts["kept"] += len(set(ours) - set(theirs))
    return merged, counts


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        raise ValueError(f"unreadable {path}: {e}; nothing imported") from e


def _import_sheet(file: Path) -> bool:
    """True when the sheet is valid and saved; an invalid one is copied as is, beside a valid Shell sheet if any."""
    target = sheet.path_for(file.stem)
    try:
        sheet.save(target, sheet.load(file))
        return True
    except (sheet.SheetError, ValueError):
        pass
    try:
        sheet.load(target)
        target = target.with_name(f"{file.stem}.dim-agent.json")  # keep the player's working sheet
    except (sheet.SheetError, ValueError, OSError):
        target.with_suffix(".md").unlink(missing_ok=True)  # its view no longer matches the copied JSON
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(file, target)
    return False


def import_dim_agent(src: Path) -> dict:
    src = Path(src)
    builds_src, todo_src = src / "builds", src / "todo"
    if not builds_src.is_dir() and not todo_src.is_dir():
        raise ValueError(f"not a dim-agent folder: {src} (no builds/ nor todo/)")
    out = {"builds": [], "invalid": [], "kept": [], "todo": [], "history": 0, "state": {}}

    # read every TODO file before writing anything, so a broken one leaves profile/ untouched
    todo_data = {n: _read_json(todo_src / n) for n in (*TODO_FILES, "state.json") if (todo_src / n).exists()}

    imported = set()
    for file in sorted(builds_src.glob("*.json")) if builds_src.is_dir() else []:
        imported.add(file.stem)
        out["builds" if _import_sheet(file) else "invalid"].append(file.stem)
    out["kept"] = sorted(p.stem for p in sheet.folder().glob("*.json")
                         if p.stem not in imported and not p.stem.endswith(".dim-agent"))

    if todo_src.is_dir():
        todo = state.folder()
        for name in TODO_FILES:
            if name in todo_data:
                state.write_json(todo / name, todo_data[name])
                out["todo"].append(name)
        if "state.json" in todo_data:
            merged, out["state"] = merge_state(state.load(), todo_data["state.json"])
            state.save(todo / "state.json", merged)
            out["todo"].append("state.json")
        history = todo / "history"
        for file in sorted(todo_src.glob("????-??-??*.*")):  # dated plans, French, kept as history
            history.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, history / file.name)
            out["history"] += 1
    return out
