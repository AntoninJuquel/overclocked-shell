import json
from urllib.parse import parse_qs, urlsplit

from shell.outputs import dim_link

LOADOUT = {"id": "x", "name": "Build é ≥", "classType": 2, "equipped": [{"hash": 1}], "unequipped": [],
           "notes": "n" * 500}


def decode(url):
    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == dim_link.BASE
    return json.loads(parse_qs(parts.query)["loadout"][0])


def test_round_trip():
    url, warnings = dim_link.url(LOADOUT)
    assert decode(url) == LOADOUT and warnings == []


def test_long_link_trims_notes_then_warns(monkeypatch):
    monkeypatch.setattr(dim_link, "MAX_LENGTH", 400)
    url, warnings = dim_link.url(LOADOUT)
    assert "notes" not in decode(url) and len(url) <= 400 and warnings == ["link too long: notes left out"]
    monkeypatch.setattr(dim_link, "MAX_LENGTH", 50)
    url, warnings = dim_link.url(LOADOUT)
    assert warnings[-1].startswith("link is ") and "may be refused" in warnings[-1]
