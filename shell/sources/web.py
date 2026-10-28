"""Plain HTTP GET for public reference data (Google Sheets, GitHub): no Bungie key involved."""
import time
import urllib.error
import urllib.request


def get(url: str, tries: int = 4) -> bytes:
    """GET with a User-Agent and retries (hosts sometimes answer with a passing 500)."""
    req = urllib.request.Request(url, headers={"User-Agent": "overclocked-shell"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.URLError:
            if attempt == tries - 1:
                raise
            time.sleep(2 ** attempt)
