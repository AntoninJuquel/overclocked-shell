from shell.sources import sources, write_if_changed


def test_registry_finds_wishlists():
    found = sources()
    assert "wishlists" in found
    assert all(callable(m.refresh) for m in found.values())


def test_write_if_changed(tmp_path):
    f = tmp_path / "a" / "x.md"
    assert write_if_changed(f, "one") is True
    assert write_if_changed(f, "one") is False
    assert write_if_changed(f, "two") is True
    assert f.read_text(encoding="utf-8") == "two"
    assert not list(f.parent.glob("*.tmp"))
