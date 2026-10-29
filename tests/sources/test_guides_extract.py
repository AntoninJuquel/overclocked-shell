import json

import pytest

from shell.sources.guides import extract, sites


def test_div_inside_a_table_cell_keeps_the_row():
    md, _ = extract.to_markdown("<table><tr><td><div>A</div></td><td><div>B</div></td></tr></table>", "https://x.y/")
    assert md == "A | B"

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


def test_unclosed_nav_stops_at_the_end_of_its_parent():
    md, _ = extract.to_markdown("<div><nav><a>Home</a></div><h2>Atraks</h2><p>Kept.</p>", "https://x.com/")
    assert md == "## Atraks\n\nKept."
    md, _ = extract.to_markdown("<section><nav><ul><li>Menu</li></ul></nav><p>A</p></section><p>B</p>", "https://x/")
    assert md == "A\n\nB"


def test_srcset_and_picture_source_images():
    html = ('<img srcset="/a-400.jpg 400w, /a-800.jpg 800w" alt="A">'
            '<picture><source srcset="/b.webp 1x, /b2.webp 2x"><img alt="B"></picture><img alt="none">')
    _, images = extract.to_markdown(html, "https://x.com/g")
    assert images == [("https://x.com/a-400.jpg", "A"), ("https://x.com/b.webp", "B")]


def test_divs_and_small_headings_are_blocks():
    md, _ = extract.to_markdown("<div>One</div><div>Two</div><h5>Five</h5><h6>Six</h6><ul><li><div>Item</div></li></ul>",
                                "https://x/")
    assert md == "One\n\nTwo\n\n##### Five\n\n###### Six\n\n- Item"


def test_alt_brackets_escaped():
    _, images = extract.to_markdown('<img src="/a.png" alt="Map [left]">', "https://x/")
    assert images == [("https://x/a.png", r"Map \[left\]")]


def test_nested_skips_and_void_tags_inside_a_skip():
    md, images = extract.to_markdown('<nav><aside>x</aside>y</nav><p>Kept.</p>'
                                     '<nav>a<br>b<img src="https://x/i.png">c</nav><p>Too.</p>', "https://x/")
    assert md == "Kept.\n\nToo." and images == []


def test_stray_close_inside_a_skip_does_not_end_it():
    # a <nav> closes the open <p> (HTML rule), so the </p> inside the nav closes nothing
    md, _ = extract.to_markdown("<p>Before<nav>menu</p>still menu</nav><p>Kept.</p>", "https://x/")
    assert md == "Before\n\nKept."


def test_list_item_paragraphs_keep_their_dash():
    md, _ = extract.to_markdown("<ul><li><p>A</p></li><li><p>B</p></li></ul>", "https://x/")
    assert md == "- A\n- B"


def test_picture_srcset_used_once_even_unclosed():
    _, images = extract.to_markdown('<picture><source srcset="https://x/a.png 400w"><img alt="A">'
                                    '<p>text</p><img alt="none">', "https://x/")
    assert images == [("https://x/a.png", "A")]


def test_alt_backslashes_escaped_before_brackets():
    _, images = extract.to_markdown(r'<img src="/a.png" alt="C:\dir\"><img src="/b.png" alt="a]b">'
                                    '<img src="/c.png" alt="see [map">', "https://x/")
    assert [alt for _, alt in images] == [r"C:\\dir\\", r"a\]b", r"see \[map"]
