import json

import pytest

from shell.sources.guides import extract, sites

ARTICLE = """
<h2>Crypt Security</h2>
<p>Two floors: upstairs and the <b>basement</b>.</p>
<script>var x = 1;</script>
<nav><a href="/">Home</a></nav>
<ul><li>Scanner calls the panels</li><li>Operator shoots them</li></ul>
<img src="/storage/icons/arc.jpg" width="16" height="16" alt="arc">
<figure><img src="/storage/guide-images/160/basement.jpg" width="800" height="450" alt="">
<figcaption>Basement panels, left side</figcaption></figure>
<p>Then<br>damage.</p>
<img data-src="https://cdn.example/x.png" alt="Fuses">
"""


def test_markdown_headings_lists_paragraphs():
    md, _ = extract.to_markdown(ARTICLE, "https://grindout.com/destiny-2/guides/deep-stone-crypt")
    assert md.startswith("## Crypt Security\n\nTwo floors: upstairs and the basement.\n\n")
    assert "- Scanner calls the panels\n- Operator shoots them" in md
    assert "Then\ndamage." in md


def test_scripts_nav_and_icons_dropped():
    md, images = extract.to_markdown(ARTICLE, "https://grindout.com/x")
    assert "var x" not in md and "Home" not in md and "arc.jpg" not in str(images)


def test_images_in_order_with_alt_or_figcaption_and_absolute_urls():
    md, images = extract.to_markdown(ARTICLE, "https://grindout.com/destiny-2/guides/deep-stone-crypt")
    assert images == [("https://grindout.com/storage/guide-images/160/basement.jpg", "Basement panels, left side"),
                      ("https://cdn.example/x.png", "Fuses")]
    assert md.index("{{img:0}}") < md.index("Basement panels, left side") < md.index("{{img:1}}")


def grindout_page(description, updated="20 Jul 2026"):
    data = {"component": "Guide", "props": {"guide": {"description": description, "updated_at": updated}}}
    return f'<html><script data-page="app" type="application/json">{json.dumps(data)}</script></html>'


def test_grindout_json_article_and_date():
    html, date = sites.article("grindout", grindout_page("<section><h2>Intro</h2></section>"))
    assert html == "<section><h2>Intro</h2></section>" and date == "2026-07-20"


def test_shacknews_article_and_date():
    page = ('<script type="application/ld+json">{"datePublished":"2020-11-26T15:45:00-08:00",'
            '"dateModified":"2026-02-01T18:34:15-08:00"}</script><div>menu</div>'
            '<article id="detail-view"><h2>Crypt Security</h2></article><footer>f</footer>')
    html, date = sites.article("shacknews", page)
    assert html == '<article id="detail-view"><h2>Crypt Security</h2></article>' and date == "2026-02-01"


def test_overgear_article_and_modified_meta():
    page = ('<meta property="article:modified_time" content="2024-01-10T08:46:36+00:00">'
            '<main id="main"><div class="guide-banner__content">banner</div>'
            '<div class="entry-content"><h2>First encounter</h2></div></main><footer>f</footer>')
    html, date = sites.article("overgear", page)
    assert html.startswith('<div class="entry-content"><h2>First encounter</h2>') and "banner" not in html
    assert "footer" not in html and date == "2024-01-10"


@pytest.mark.parametrize("site,page", [("grindout", "<html></html>"), ("shacknews", "<div></div>"),
                                       ("overgear", "<main></main>"), ("nope", "")])
def test_missing_container_raises(site, page):
    with pytest.raises(ValueError, match=site):
        sites.article(site, page)
