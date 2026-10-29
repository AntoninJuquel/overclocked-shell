import json

import pytest

from shell.engines.dim_import import import_dim_agent, merge_state
from tests.engines.builds.test_sheet import RESOLVED, SHEET


@pytest.fixture
def profile(tmp_path, monkeypatch):
    from shell.core import paths
    monkeypatch.setattr(paths, "profile_dir", lambda: tmp_path / "profile")
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path / "cache")
    return tmp_path / "profile"


def dim_folder(tmp_path, sheets=None, state=None):
    src = tmp_path / "dim-agent"
    (src / "builds").mkdir(parents=True)
    (src / "todo").mkdir()
    for slug, s in (sheets or {"a": SHEET}).items():
        (src / "builds" / f"{slug}.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    (src / "todo" / "state.json").write_text(json.dumps(state or {}), encoding="utf-8")
    (src / "todo" / "needs.json").write_text('{"needs": []}', encoding="utf-8")
    (src / "todo" / "sources.json").write_text("{}", encoding="utf-8")
    (src / "todo" / "2026-10-21.md").write_text("# TODO du 2026-10-21", encoding="utf-8")
    return src


def test_sheets_migrated_and_rendered_in_english(tmp_path, profile):
    sheet = json.loads(json.dumps({**SHEET, "resolved": RESOLVED}))
    for piece in sheet["resolved"]["armor"]:
        piece["masterwork"] = "à faire"
    result = import_dim_agent(dim_folder(tmp_path, {"a": sheet}))
    assert result["builds"] == ["a"] and result["invalid"] == []
    saved = json.loads((profile / "builds" / "a.json").read_text(encoding="utf-8"))
    assert [p["masterwork"] for p in saved["resolved"]["armor"]] == ["todo"]
    assert "## Intent" in (profile / "builds" / "a.md").read_text(encoding="utf-8")


def test_invalid_sheet_copied_with_warning(tmp_path, profile):
    result = import_dim_agent(dim_folder(tmp_path, {"bad": {"name": "x"}}))
    assert result["invalid"] == ["bad"] and result["builds"] == []
    assert json.loads((profile / "builds" / "bad.json").read_text(encoding="utf-8")) == {"name": "x"}


def test_shell_only_sheet_kept(tmp_path, profile):
    (profile / "builds").mkdir(parents=True)
    (profile / "builds" / "mine.json").write_text("{}", encoding="utf-8")
    result = import_dim_agent(dim_folder(tmp_path))
    assert result["kept"] == ["mine"] and (profile / "builds" / "mine.json").exists()


def test_state_merge_later_since_wins():
    ours = {"x": {"status": "ignored", "since": "2026-10-28"}, "y": {"status": "todo", "since": "2026-10-21"},
            "z": {"status": "done", "since": "2026-10-01"}}
    theirs = {"x": {"status": "todo", "since": "2026-10-21"}, "y": {"status": "done", "since": "2026-10-21"},
              "w": {"status": "todo", "since": "2026-10-20"}}
    merged, counts = merge_state(ours, theirs)
    assert {k: v["status"] for k, v in merged.items()} == {"x": "ignored", "y": "done", "z": "done", "w": "todo"}
    assert counts == {"added": 1, "updated": 1, "kept": 2}


def test_history_copied_once(tmp_path, profile):
    src = dim_folder(tmp_path)
    first, second = import_dim_agent(src), import_dim_agent(src)
    assert first["history"] == second["history"] == 1
    assert [p.name for p in (profile / "todo" / "history").iterdir()] == ["2026-10-21.md"]
    assert sorted(first["todo"]) == ["needs.json", "sources.json", "state.json"]


def test_wrong_folder_writes_nothing(tmp_path, profile):
    with pytest.raises(ValueError, match="not a dim-agent folder"):
        import_dim_agent(tmp_path / "nowhere")
    assert not profile.exists()


def test_invalid_sheet_never_replaces_a_valid_one(tmp_path, profile):
    import_dim_agent(dim_folder(tmp_path, {"x": SHEET}))
    result = import_dim_agent(dim_folder(tmp_path / "2", {"x": {"name": "broken"}}))
    assert result["invalid"] == ["x"]
    assert json.loads((profile / "builds" / "x.json").read_text(encoding="utf-8"))["name"] == SHEET["name"]
    assert json.loads((profile / "builds" / "x.dim-agent.json").read_text(encoding="utf-8")) == {"name": "broken"}


def test_bad_todo_file_writes_nothing(tmp_path, profile):
    src = dim_folder(tmp_path)
    (src / "todo" / "needs.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="needs.json"):
        import_dim_agent(src)
    assert not profile.exists()


def test_bom_files_are_read(tmp_path, profile):
    src = dim_folder(tmp_path)
    (src / "builds" / "a.json").write_text(json.dumps(SHEET), encoding="utf-8-sig")
    (src / "todo" / "sources.json").write_text("{}", encoding="utf-8-sig")
    assert import_dim_agent(src)["builds"] == ["a"]


def test_manual_status_beats_automatic_and_ties_stay_with_shell():
    ours = {"tie": {"status": "ignored", "since": "2026-10-28"},
            "auto": {"status": "done", "since": "2026-10-27", "auto": True},
            "both": {"status": "done", "since": "2026-10-20"}}
    theirs = {"tie": {"status": "todo", "since": "2026-10-28"},
              "auto": {"status": "ignored", "since": "2026-10-25"},
              "both": {"status": "ignored", "since": "2026-10-22"}}
    merged, _ = merge_state(ours, theirs)
    assert {k: v["status"] for k, v in merged.items()} == {"tie": "ignored", "auto": "ignored", "both": "ignored"}
