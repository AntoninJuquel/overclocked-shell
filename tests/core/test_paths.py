from pathlib import Path


def test_paths_ignore_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from shell.core import paths

    assert paths.ROOT == Path(paths.__file__).resolve().parents[2]
    assert paths.profile_dir() == paths.ROOT / "profile"
    assert paths.cache_dir() == paths.ROOT / "cache"
    assert paths.env_file() == paths.ROOT / ".env"
