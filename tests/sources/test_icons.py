from shell.core import paths
from shell.sources import icons

PNG = b"\x89PNG\r\n-fake"


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "cache_dir", lambda: tmp_path)


def _counting(fail=()):
    calls = []

    def download(url):
        calls.append(url)
        if any(f in url for f in fail) or fail == "all":
            raise OSError("down")
        return PNG

    download.calls = calls
    return download


REFS = {"perk:a": "/common/destiny2_content/icons/a.png", "perk:b": "/common/destiny2_content/icons/b.png"}


def test_downloads_once_then_uses_cache(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    dl = _counting()
    first, _ = icons.local(REFS, download=dl)
    second, _ = icons.local(REFS, download=dl)
    assert len(dl.calls) == 2
    assert dl.calls[0].startswith("https://www.bungie.net/common/")
    assert all(p.exists() for p in first.values()) and first == second


def test_index_serves_offline(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    icons.local(REFS, download=_counting())
    assert icons.indexed() == REFS

    def boom(url):
        raise AssertionError("offline")

    got, warnings = icons.local(icons.indexed(), download=boom)
    assert set(got) == set(REFS) and warnings == []


def test_failure_is_a_warning(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    got, warnings = icons.local(REFS, download=_counting(fail=["b.png"]))
    assert set(got) == {"perk:a"}
    assert warnings == ["icon download failed: perk:b"]


def test_unreachable_warns_once(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    refs = {f"perk:{i}": f"/x/{i}.png" for i in range(20)}
    dl = _counting(fail="all")
    got, warnings = icons.local(refs, download=dl)
    assert got == {}
    assert sum(w.startswith("icons: Bungie unreachable") for w in warnings) == 1
    assert len(dl.calls) <= 11


def test_invalid_file_redownloaded(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    (tmp_path / "icons").mkdir()
    (tmp_path / "icons" / "a.png").write_bytes(b"<html>")
    dl = _counting()
    got, _ = icons.local({"perk:a": REFS["perk:a"]}, download=dl)
    assert len(dl.calls) == 1 and got["perk:a"].read_bytes() == PNG


def test_shared_ref_downloaded_once(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    dl = _counting()
    refs = {"mod:x": "/i/same.png", "perk:y": "/i/same.png"}
    got, warnings = icons.local(refs, download=dl)
    assert len(dl.calls) == 1 and warnings == []
    assert got["mod:x"] == got["perk:y"] and got["mod:x"].exists()


def test_non_dict_index_is_ignored(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    (tmp_path / "icons").mkdir()
    (tmp_path / "icons" / "index.json").write_text("[]")
    assert icons.indexed() == {}
    got, warnings = icons.local(REFS, download=_counting())
    assert set(got) == set(REFS) and warnings == []
    assert icons.indexed() == REFS
