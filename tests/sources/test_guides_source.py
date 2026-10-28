import json

import pytest

from shell.sources import guides, sources
from tests.sources.test_guides_extract import grindout_page

URLS = guides.GUIDES["deep-stone-crypt"]
JPEG, PNG, WEBP = b"\xff\xd8\xff\xe0rest", b"\x89PNG\r\n\x1a\nrest", b"RIFF\x00\x00\x00\x00WEBPrest"
SHACK = ('<script type="application/ld+json">{"dateModified":"2026-02-01T00:00:00Z"}</script>'
         '<article id="detail-view"><h2>Disable Crypt Security</h2><p>Panels 1 to 5.</p>'
         '<img src="/img/basement.jpg" alt="Basement"></article>')
OVER = ('<meta property="article:modified_time" content="2024-01-10T08:46:36+00:00">'
        '<div class="entry-content"><h2>Second Encounter Crypt Security</h2><p>Upstairs.</p></div></main>')
GRIND = grindout_page('<h2>Crypt Security</h2><p>Scanner upstairs.</p><img src="/storage/a.png" alt="">'
                      '<figure><img src="https://cdn.x/b.webp"><figcaption>Fuses</figcaption></figure>')


@pytest.fixture
def web(monkeypatch):
    """The fake internet: URL -> bytes or an exception to raise."""
    pages = {URLS["grindout"]: GRIND.encode(), URLS["shacknews"]: SHACK.encode(), URLS["overgear"]: OVER.encode(),
             "https://grindout.com/storage/a.png": PNG, "https://cdn.x/b.webp": WEBP,
             "https://www.shacknews.com/img/basement.jpg": JPEG, "_tries": {}}

    def get(url, tries=4):
        pages["_tries"][url] = tries
        v = pages[url]
        if isinstance(v, Exception):
            raise v
        return v

    monkeypatch.setattr(guides.web, "get", get)
    return pages


def md(name):
    return guides.guide_path("deep-stone-crypt", name).read_text(encoding="utf-8")


def test_registered_source():
    assert "guides" in sources()


def test_refresh_writes_markdown_images_and_index(web):
    r = guides.refresh()
    assert r["ok"] and sorted(r["changed"]) == ["deep-stone-crypt/grindout.md", "deep-stone-crypt/overgear.md",
                                                "deep-stone-crypt/shacknews.md"]
    text = md("grindout")
    assert text.startswith(f"<!-- source: {URLS['grindout']} · updated: 2026-07-20 -->\n")
    assert "![](grindout/img-00.png)" in text and "![Fuses](grindout/img-01.webp)" in text
    folder = guides.folder() / "deep-stone-crypt"
    assert (folder / "grindout" / "img-01.webp").read_bytes() == WEBP
    assert "![Basement](shacknews/img-00.jpg)" in md("shacknews") and "updated: 2024-01-10" in md("overgear")
    index = (folder / "index.md").read_text(encoding="utf-8")
    assert "| shacknews | 2026-02-01 |" in index and "| 2 |" in index


def test_cached_guide_not_downloaded_without_force(web):
    guides.refresh()
    for url in URLS.values():
        web[url] = RuntimeError("must not download")
    assert guides.refresh()["changed"] == []


def test_changed_only_when_text_changes(web):
    guides.refresh()
    assert guides.refresh(force=True)["changed"] == []
    web[URLS["overgear"]] = OVER.replace("Upstairs.", "Upstairs and basement.").encode()
    assert guides.refresh(force=True)["changed"] == ["deep-stone-crypt/overgear.md"]


def test_reshaped_page_errors_and_keeps_cache(web):
    guides.refresh()
    before = md("shacknews")
    web[URLS["shacknews"]] = b"<div>new layout</div>"
    web[URLS["overgear"]] = OVER.replace("Upstairs.", "Basement.").encode()
    r = guides.refresh(force=True)
    assert not r["ok"] and r["errors"] == ["deep-stone-crypt/shacknews: shacknews: article not found (page layout changed)"]
    assert md("shacknews") == before and r["changed"] == ["deep-stone-crypt/overgear.md"]


def test_image_failure_keeps_alt_unavailable(web):
    web["https://www.shacknews.com/img/basement.jpg"] = OSError("404")
    r = guides.refresh()
    assert r["ok"] and "![Basement (image unavailable)]()" in md("shacknews")


def test_page_error_with_cache_is_stale(web):
    guides.refresh()
    web[URLS["grindout"]] = OSError("offline")
    r = guides.refresh(force=True)
    assert r["ok"] and r["stale"] == ["deep-stone-crypt/grindout.md"]


def test_page_error_without_cache_is_an_error(web):
    web[URLS["grindout"]] = OSError("offline")
    r = guides.refresh(only=["deep-stone-crypt"])
    assert r["errors"] == ["deep-stone-crypt/grindout: offline"]


def test_unknown_raid():
    assert guides.refresh(only=["vault-of-nope"])["errors"] == [
        "unknown raid: vault-of-nope (raids: deep-stone-crypt)"]




def test_image_type_from_magic_bytes_and_html_is_unavailable(web):
    web["https://grindout.com/storage/a.png"] = b"RIFF\x00\x00\x00\x00WEBPrest"
    web["https://cdn.x/b.webp"] = b"<html>error page</html>"
    guides.refresh()
    text = md("grindout")
    assert "![](grindout/img-00.webp)" in text and "![Fuses (image unavailable)]()" in text


def test_image_failure_keeps_the_previous_guide_and_is_stale(web):
    web["https://grindout.com/storage/a.png"], web["https://cdn.x/b.webp"] = PNG, JPEG
    guides.refresh()
    before = md("grindout")
    web[URLS["grindout"]] = GRIND.replace("Scanner upstairs.", "Scanner upstairs now.").encode()
    web["https://cdn.x/b.webp"] = OSError("cdn down")
    r = guides.refresh(force=True)
    assert r["stale"] == ["deep-stone-crypt/grindout.md"] and md("grindout") == before
    assert (guides.folder() / "deep-stone-crypt" / "grindout" / "img-01.jpg").read_bytes() == JPEG


def test_images_downloaded_once_without_retries(web):
    guides.refresh()
    assert {t for u, t in web["_tries"].items() if u not in URLS.values()} == {1}


def test_only_http_images(web):
    from shell.sources.guides import extract
    _, images = extract.to_markdown('<img src="file:///C:/secret.png"><img src="DATA:image/png;base64,x">'
                                    '<img src="https://a.b/c.png">', "https://grindout.com/x")
    assert images == [("https://a.b/c.png", "")]


def test_index_fetched_is_the_fetch_date_not_the_change_date(web, monkeypatch):
    guides.refresh()
    monkeypatch.setattr(guides, "_today", lambda: "2027-01-01")
    guides.refresh(force=True)                                   # same text: nothing changed, but fetched today
    index = (guides.folder() / "deep-stone-crypt" / "index.md").read_text(encoding="utf-8")
    assert index.count("| 2027-01-01 |") == 3
