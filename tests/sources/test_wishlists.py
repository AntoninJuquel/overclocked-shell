from shell.sources import wishlists
from shell.sources.sheets import fetch

WISHLIST = """title: test
//Fatebringer
//notes: Tier: S. Rank: 2. Something else.
dimwishlist:item=111&perks=1,2
dimwishlist:item=111&perks=3
//Other Gun
dimwishlist:item=-1&perks=4
dimwishlist:item=222
garbage line
"""


def test_load_matches_dim_rules(tmp_path):
    path = tmp_path / "w.txt"
    path.write_text(WISHLIST, encoding="utf-8")
    rolls, notes, names = wishlists.load(path, {"1": "Enhanced Outlaw", "2": "Explosive Payload"})
    assert rolls[111] == [frozenset({"outlaw", "explosive payload"}), frozenset({"3"})]
    assert notes == {111: "S #2"}
    assert names == {111: "Fatebringer", -1: "Other Gun", 222: "Other Gun"}
    assert rolls[222] == [frozenset()]


def test_norms():
    assert wishlists.norm_perk("Enhanced Rampage ") == "rampage"
    assert wishlists.norm_weapon("Fatebringer (Timelost)") == "fatebringer"


def test_local_path_returned_as_is(tmp_path):
    assert wishlists.fetch(str(tmp_path / "mine.txt")) == tmp_path / "mine.txt"


def test_url_cached_under_basename(monkeypatch, isolated_cache):
    monkeypatch.setattr(fetch, "_get", lambda url: WISHLIST.encode())
    path = wishlists.fetch("https://example.com/a/My List.txt")
    assert path == isolated_cache / "cache" / "wishlists" / "My_List.txt"
    assert "dimwishlist:" in path.read_text(encoding="utf-8")


def test_refresh_keeps_cache_on_invalid_download(monkeypatch, isolated_cache):
    monkeypatch.setattr(fetch, "_get", lambda url: WISHLIST.encode())
    first = wishlists.refresh()
    assert first["ok"] and first["changed"] and first["stale"] == []
    monkeypatch.setattr(fetch, "_get", lambda url: b"<html>404</html>")
    report = wishlists.refresh(force=True)
    path = wishlists.folder() / wishlists.cache_name(wishlists.DEFAULT_WISHLIST)
    assert report["stale"] == [path.name] and report["changed"] == []
    assert "dimwishlist:" in path.read_text(encoding="utf-8")
