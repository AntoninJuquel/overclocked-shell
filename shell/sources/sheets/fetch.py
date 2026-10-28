"""Public HTML views of a Google Sheet (tab list, one tab), with a local cache."""
import http.client
import os
import re
from datetime import datetime
from pathlib import Path

from shell.sources.web import get as _get

_TAB = re.compile(r'\{name: "((?:[^"\\]|\\.)*)", pageUrl: "[^"]*", gid: "(\d+)"')


def _unescape(s):
    s = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), s)
    return s.replace("\\/", "/").replace('\\"', '"')


def parse_tab_list(html):
    """[(tab name, gid)] in sheet order, read from the htmlview page."""
    return [(_unescape(name), gid) for name, gid in _TAB.findall(html)]


def cached(url, path, refresh, validate=None):
    """(text, stale). Serves the cache when it exists and refresh is false; otherwise downloads.
    If the download fails (or validate rejects the response) and a cache exists, serves it with
    stale=True. Without a cache, raises OSError. An invalid response is never written."""
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8"), False
    try:
        text = _get(url).decode("utf-8")
        if validate is not None and not validate(text):
            raise OSError(f"unexpected response from {url}")
    except (OSError, http.client.HTTPException, UnicodeDecodeError) as e:
        if path.exists():
            return path.read_text(encoding="utf-8"), True
        if isinstance(e, OSError):
            raise
        raise OSError(f"{url}: {e}") from e
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return text, False


def file_date(path):
    """Local modification date (YYYY-MM-DD) of a file, or None when it does not exist."""
    path = Path(path)
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()


class SheetSource:
    """A public Google Sheet: its tab list and the HTML of each tab, cached in `raw/`
    (`_tabs.html` and `<gid>.html`)."""

    def __init__(self, sheet_id, raw):
        self.url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        self.raw = Path(raw)
        self.tabs_stale = False  # True when the last list_tabs served the cache after a network failure

    def list_tabs(self, refresh=False):
        html, self.tabs_stale = cached(f"{self.url}/htmlview", self.raw / "_tabs.html", refresh,
                                       validate=lambda t: bool(_TAB.search(t)))
        tabs = parse_tab_list(html)
        if not tabs:
            raise OSError("tab list not found in the htmlview page")
        return tabs

    def tab_html(self, gid, refresh=False):
        """(html, stale) of one tab."""
        return cached(f"{self.url}/htmlview/sheet?headers=false&gid={gid}", self.raw / f"{gid}.html", refresh,
                      validate=lambda t: 'class="waffle' in t)

    def cache_date(self, gid):
        return file_date(self.raw / f"{gid}.html")
