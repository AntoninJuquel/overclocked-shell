"""Article HTML → Markdown: headings, paragraphs, list items, table rows, and images as `{{img:N}}` placeholders
(the source downloads them). Scripts, navigation, forms and icons (width or height under 64) are dropped."""
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

SKIP = {"script", "style", "nav", "aside", "form", "iframe", "svg", "noscript", "button"}
HEADINGS = {"h1": "#", "h2": "##", "h3": "###", "h4": "####", "h5": "#####", "h6": "######"}
BLOCKS = {"p", "div", "li", "figcaption", "tr", "blockquote", *HEADINGS}
# flow tags that close an open <p> (HTML rule), so a later </p> closes nothing
CLOSES_P = {"div", "blockquote", "ul", "ol", "table", "figure", "section", "nav", "aside", "form", "hr", "pre",
            "p", *HEADINGS}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
ICON_SIZE = 64


class _Parser(HTMLParser):
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base, self.blocks, self.images = base_url, [], []
        self.buf, self.prefix, self.cells = [], "", []
        # open tags; `skip` is the stack depth of the skipped element, so an unclosed <nav> ends with its parent
        self.stack, self.skip, self.srcset = [], None, None

    def _flush(self):
        text = "\n".join(line.strip() for line in "".join(self.buf).split("\n")).strip()
        if text:
            self.blocks.append(self.prefix + text)
        self.buf, self.prefix = [], ""

    def handle_starttag(self, tag, attrs):
        inside = self.stack[self.skip or 0:]   # never close a <p> opened before a skipped element
        if tag in CLOSES_P and "p" in inside:
            del self.stack[len(self.stack) - 1 - self.stack[::-1].index("p"):]
        if tag not in VOID:
            self.stack.append(tag)
        if tag in SKIP and self.skip is None:
            self.skip = len(self.stack) - 1
        if self.skip is not None:
            return
        a = dict(attrs)
        if tag in BLOCKS and not self._cell_div(tag):
            pending = "" if "".join(self.buf).strip() else self.prefix   # <li><div>: keep the dash
            self._flush()
            self.prefix = HEADINGS[tag] + " " if tag in HEADINGS else "- " if tag == "li" else pending
        elif tag == "source":
            self.srcset = a.get("srcset")
        elif tag == "br":
            self.buf.append("\n")
        elif tag in ("td", "th") and self.buf:
            self.buf.append(" | ")
        elif tag == "img":
            self._image(a)

    def _image(self, a):
        def small(key):
            return (a.get(key) or "").isdigit() and int(a[key]) < ICON_SIZE
        first = (a.get("srcset") or a.get("data-srcset") or self.srcset or "").split(",")[0].split()  # "url 400w"
        self.srcset = None   # one <source> per <img>, even in an unclosed <picture>
        src = a.get("data-src") or a.get("data-lazy-src") or a.get("src") or (first[0] if first else None)
        url = urljoin(self.base, src or "")
        # only web images: a file: or data: URL in a guide page must never be read
        if not src or urlsplit(url).scheme.lower() not in ("http", "https") or small("width") or small("height"):
            return
        self._flush()
        self.blocks.append(f"{{{{img:{len(self.images)}}}}}")
        self.images.append([url, (a.get("alt") or "").strip()])

    def handle_endtag(self, tag):
        if tag in self.stack:   # closes everything opened inside it, unclosed tags included
            del self.stack[len(self.stack) - 1 - self.stack[::-1].index(tag):]
            if self.skip is not None and len(self.stack) <= self.skip:
                self.skip = None
                if tag in SKIP:
                    return
        if self.skip is not None:
            return
        if tag == "picture":
            self.srcset = None
        if tag == "figcaption":
            caption = "".join(self.buf).strip()
            if self.images and not self.images[-1][1]:
                self.images[-1][1] = re.sub(r"\s+", " ", caption)
        if tag in BLOCKS and not self._cell_div(tag):
            self._flush()

    def _cell_div(self, tag):
        """A <div> inside a table cell is not a block: the row stays one line."""
        return tag == "div" and ("td" in self.stack or "th" in self.stack)

    def handle_data(self, data):
        if self.skip is None:
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
    # alts go inside ![...]: backslashes first, so an alt ending in "\" can't escape the "]"
    return out, [(url, alt.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")) for url, alt in p.images]
