"""Statuses of TODO entries (profile/todo/state.json): todo / done / ignored, kept from one run to the next."""
import json
import os
from pathlib import Path

from shell.core import paths

STATUSES = ("todo", "done", "ignored")


def folder() -> Path:
    """profile/todo/, resolved at call time."""
    return paths.profile_dir() / "todo"


def write_json(path, data):
    """Atomic write, UTF-8, indented, ending with a newline."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load(path=None):
    path = Path(path) if path is not None else folder() / "state.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, state):
    write_json(path, dict(sorted(state.items())))


def set_status(state, need_id, status, today, note=None, auto=False):
    """Changes an entry's status; the existing note is kept when `note` is None (an empty string clears it).
    `auto` marks a done set by `sync` (not by the player)."""
    if status not in STATUSES:
        raise ValueError(f"unknown status: {status!r} ({', '.join(STATUSES)})")
    entry = {"status": status, "since": today}
    if note is None:
        note = state.get(need_id, {}).get("note")
    if note:
        entry["note"] = note
    if auto:
        entry["auto"] = True
    state[need_id] = entry
    return state


def sync(state, ids, today, mark_done=True, keep=()):
    """New ids → todo. With `mark_done`, a todo id missing from `ids` becomes done with `auto` (the inventory
    meets the need). An auto done whose id reappears goes back to todo. Manual done and ignored entries are
    never changed. `keep`: id prefixes never auto-marked done (their needs could not be computed this time)."""
    ids = set(ids)
    for need_id in sorted(ids - state.keys()):
        set_status(state, need_id, "todo", today)
    for need_id in sorted(ids):
        entry = state[need_id]
        if entry["status"] == "done" and entry.get("auto"):
            set_status(state, need_id, "todo", today)
    if mark_done:
        for need_id, entry in state.items():
            if entry["status"] == "todo" and need_id not in ids and not need_id.startswith(tuple(keep)):
                set_status(state, need_id, "done", today, auto=True)
    return state
