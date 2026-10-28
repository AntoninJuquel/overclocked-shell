import pytest


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path, monkeypatch):
    """TODO tests never read or write the real cache/, profile/ or Aegis data."""
    from shell.core import paths
    from shell.sources.aegis import lookup
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(paths, "profile_dir", lambda: tmp_path / "profile")
    monkeypatch.setattr(lookup, "DATA", None)
    monkeypatch.setattr(lookup, "_warned", False)
    return tmp_path
