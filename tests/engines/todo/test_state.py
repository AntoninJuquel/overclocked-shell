import pytest

from shell.engines.todo import state


def test_folder_and_default_path_resolve_at_call_time(isolated_dirs):
    assert state.folder() == isolated_dirs / "profile" / "todo"
    state.save(state.folder() / "state.json", {"a": {"status": "todo", "since": "2026-10-07"}})
    assert state.load() == {"a": {"status": "todo", "since": "2026-10-07"}}


def test_load_missing_file_is_empty(tmp_path):
    assert state.load(tmp_path / "state.json") == {}


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "todo" / "state.json"
    state.save(path, {"a": {"status": "todo", "since": "2026-10-07"}})
    assert state.load(path) == {"a": {"status": "todo", "since": "2026-10-07"}}
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_set_status_keeps_note_and_rejects_unknown():
    st = {"a": {"status": "todo", "since": "2026-10-01", "note": "not a priority"}}
    state.set_status(st, "a", "ignored", "2026-10-07")
    assert st["a"] == {"status": "ignored", "since": "2026-10-07", "note": "not a priority"}
    with pytest.raises(ValueError):
        state.set_status(st, "a", "maybe", "2026-10-07")


def test_sync_adds_new_and_marks_vanished_done():
    st = {"old": {"status": "todo", "since": "2026-10-01"},
          "gone-ignored": {"status": "ignored", "since": "2026-10-01"},
          "manual-done": {"status": "done", "since": "2026-10-02"}}
    state.sync(st, ["new", "manual-done"], "2026-10-07")
    assert st["new"] == {"status": "todo", "since": "2026-10-07"}
    assert st["old"] == {"status": "done", "since": "2026-10-07", "auto": True}
    assert st["gone-ignored"]["status"] == "ignored"
    assert st["manual-done"] == {"status": "done", "since": "2026-10-02"}


def test_sync_without_mark_done_keeps_todo():
    st = {"old": {"status": "todo", "since": "2026-10-01"}}
    state.sync(st, [], "2026-10-07", mark_done=False)
    assert st["old"]["status"] == "todo"


def test_set_status_empty_note_clears_it():
    st = {"a": {"status": "todo", "since": "2026-10-01", "note": "not a priority"}}
    state.set_status(st, "a", "todo", "2026-10-07", note="")
    assert st["a"] == {"status": "todo", "since": "2026-10-07"}


def test_sync_reopens_auto_done_that_reappears():
    st = {"a": {"status": "todo", "since": "2026-10-01", "note": "n"}}
    state.sync(st, [], "2026-10-02")
    assert st["a"] == {"status": "done", "since": "2026-10-02", "note": "n", "auto": True}
    state.sync(st, ["a"], "2026-10-07")
    assert st["a"] == {"status": "todo", "since": "2026-10-07", "note": "n"}


def test_sync_never_reopens_manual_done_or_ignored():
    st = {}
    state.set_status(st, "d", "done", "2026-10-01")
    state.set_status(st, "i", "ignored", "2026-10-01")
    state.sync(st, ["d", "i"], "2026-10-07")
    assert st["d"] == {"status": "done", "since": "2026-10-01"}
    assert st["i"] == {"status": "ignored", "since": "2026-10-01"}


def test_set_status_drops_auto_flag():
    st = {"a": {"status": "done", "since": "2026-10-01", "auto": True}}
    state.set_status(st, "a", "done", "2026-10-07")
    assert st["a"] == {"status": "done", "since": "2026-10-07"}


def test_sync_keep_protects_prefixed_ids_from_auto_done():
    st = {"aegis/truth": {"status": "todo", "since": "a"}, "armor/x": {"status": "todo", "since": "a"}}
    state.sync(st, [], "b", keep=("aegis/",))
    assert st["aegis/truth"]["status"] == "todo" and st["armor/x"]["status"] == "done"
