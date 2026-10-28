"""One-time import of a dim-agent folder: build sheets and TODO data into profile/ (never deletes anything)."""
import json
import shutil
from pathlib import Path

from shell.engines.builds import sheet
from shell.engines.todo import state

TODO_FILES = ("needs.json", "sources.json", "overrides.json")


def merge_state(ours: dict, theirs: dict) -> tuple[dict, dict]:
    """Union of need ids; for an id on both sides the later `since` wins, ties go to dim-agent (theirs)."""
    merged, counts = dict(ours), {"added": 0, "updated": 0, "kept": 0}
    for need_id, entry in theirs.items():
        mine = ours.get(need_id)
        if mine is None:
            counts["added"] += 1
        elif (mine.get("since") or "") > (entry.get("since") or ""):
            counts["kept"] += 1
            continue
        elif mine != entry:
            counts["updated"] += 1
        merged[need_id] = entry
    counts["kept"] += len(set(ours) - set(theirs))
    return merged, counts


def import_dim_agent(src: Path) -> dict:
    src = Path(src)
    builds_src, todo_src = src / "builds", src / "todo"
    if not builds_src.is_dir() and not todo_src.is_dir():
        raise ValueError(f"not a dim-agent folder: {src} (no builds/ nor todo/)")
    out = {"builds": [], "invalid": [], "kept": [], "todo": [], "history": 0, "state": {}}

    imported = set()
    for file in sorted(builds_src.glob("*.json")) if builds_src.is_dir() else []:
        imported.add(file.stem)
        target = sheet.path_for(file.stem)
        try:
            sheet.save(target, sheet.load(file))
            out["builds"].append(file.stem)
        except (sheet.SheetError, ValueError):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, target)  # kept as is: check_build tells the player what to fix
            out["invalid"].append(file.stem)
    out["kept"] = sorted(p.stem for p in sheet.folder().glob("*.json") if p.stem not in imported)

    if todo_src.is_dir():
        todo = state.folder()
        for name in TODO_FILES:
            if (todo_src / name).exists():
                state.write_json(todo / name, json.loads((todo_src / name).read_text(encoding="utf-8")))
                out["todo"].append(name)
        if (todo_src / "state.json").exists():
            merged, out["state"] = merge_state(state.load(), state.load(todo_src / "state.json"))
            state.save(todo / "state.json", merged)
            out["todo"].append("state.json")
        history = todo / "history"
        for file in sorted(todo_src.glob("????-??-??*.*")):  # dated plans, French, kept as history
            history.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, history / file.name)
            out["history"] += 1
    return out
