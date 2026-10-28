import pytest


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path, monkeypatch):
    """Build tests never read or write the real cache/ or profile/."""
    from shell.core import paths
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(paths, "profile_dir", lambda: tmp_path / "profile")
    return tmp_path


@pytest.fixture
def aegis_dir(isolated_dirs, monkeypatch):
    """Aegis data folder of the isolated cache (write it with tests.sources.aegis.conftest.write_aegis)."""
    from shell.sources.aegis import lookup
    monkeypatch.setattr(lookup, "DATA", None)
    monkeypatch.setattr(lookup, "_warned", False)
    return isolated_dirs / "cache" / "aegis"
