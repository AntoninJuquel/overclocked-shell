"""Article HTML → Markdown: headings, paragraphs, list items, table rows, and images as `{{img:N}}` placeholders
(the source downloads them). Scripts, navigation, forms and icons (width or height under 64) are dropped."""
import re
from html.parser import HTMLParser
from urllib.parse import urljoin

SKIP = {"script", "style", "nav", "aside", "form", "iframe", "svg", "noscript", "button"}
HEADINGS = {"h1": "#", "h2": "##", "h3": "###", "h4": "####"}
BLOCKS = {"p", "li", "figcaption", "tr", "blockquote", *HEADINGS}
ICON_SIZE = 64


class _Parser(HTMLParser):
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base, self.blocks, self.images = base_url, [], []
        self.skip, self.buf, self.prefix, self.cells = 0, [], "", []

    def _flush(self):
        text = "\n".join(line.strip() for line in "".join(self.buf).split("\n")).strip()
        if text:
            self.blocks.append(self.prefix + text)
        self.buf, self.prefix = [], ""

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skip += 1
        if self.skip:
            return
        a = dict(attrs)
        if tag in BLOCKS:
            self._flush()
            self.prefix = HEADINGS[tag] + " " if tag in HEADINGS else "- " if tag == "li" else ""
        elif tag == "br":
            self.buf.append("\n")
        elif tag in ("td", "th") and self.buf:
            self.buf.append(" | ")
        elif tag == "img":
            self._image(a)

    def _image(self, a):
        def small(key):
            return (a.get(key) or "").isdigit() and int(a[key]) < ICON_SIZE
        src = a.get("data-src") or a.get("data-lazy-src") or a.get("src")
        if not src or src.startswith("data:") or small("width") or small("height"):
            return
        self._flush()
        self.blocks.append(f"{{{{img:{len(self.images)}}}}}")
        self.images.append([urljoin(self.base, src), (a.get("alt") or "").strip()])

    def handle_endtag(self, tag):
        if tag in SKIP and self.skip:
            self.skip -= 1
            return
        if self.skip:
            return
        if tag == "figcaption":
            caption = "".join(self.buf).strip()
            if self.images and not self.images[-1][1]:
                self.images[-1][1] = re.sub(r"\s+", " ", caption)
        if tag in BLOCKS:
            self._flush()

    def handle_data(self, data):
        if not self.skip:
            self.buf.append(re.sub(r"\s+", " ", data))


def to_markdown(article_html: str, base_url: str) -> tuple[str, list[tuple[str, str]]]:
    """(Markdown with {{img:N}} placeholders, [(absolute image URL, alt or caption)] in order)."""
    p = _Parser(base_url)
    p.feed(article_html)
    p.close()
    p._flush()
    out = ""
    for i, b in enumerate(p.blocks):  # list items stay together, other blocks get a blank line
        out += ("" if i == 0 else "\n" if b.startswith("- ") and p.blocks[i - 1].startswith("- ") else "\n\n") + b
    return out, [tuple(i) for i in p.images]
