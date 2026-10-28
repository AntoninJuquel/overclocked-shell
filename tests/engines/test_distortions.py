from datetime import datetime, timedelta, timezone

import pytest

from shell.engines import distortions as d
from tests.sources.test_distortions import ORDER

ROT = {"order": ORDER, "anchor_hour": 494803, "anchor_index": 5}   # Europa during hour 494803
CET = timezone(timedelta(hours=1))
NOW = datetime.fromtimestamp(494803 * 3600 + 1800, timezone.utc)  # half past, Europa active


def test_active_before_and_after_the_anchor():
    assert d.active(ROT, 494803) == "Europa"
    assert d.active(ROT, 494804) == "Nessus" and d.active(ROT, 494805) == "Cosmodrome"
    assert d.active(ROT, 494802) == "Moon" and d.active(ROT, 494803 - 7 * 1000) == "Europa"


def test_match_aliases():
    assert d.match("Throne World", ROT) == "Savathun's Throne World"
    assert d.match("savathun’s throne world", ROT) == "Savathun's Throne World"
    assert d.match("European Dead Zone", ROT) == "EDZ" and d.match("Europa", ROT) == "Europa"
    assert d.match("Vault of Glass", ROT) is None and d.match("Europa (until 2026-11-03)", ROT) is None


def test_windows_and_formatting():
    assert d.windows(ROT, "Europa", NOW, 2) == [494803, 494810]
    assert d.windows(ROT, "Nessus", NOW, 1) == [494804]
    local = NOW.astimezone(CET)
    assert d.fmt(494803, NOW, CET) == f"now until {local.replace(minute=0) + timedelta(hours=1):%H:%M}"
    start = (local.replace(minute=0) + timedelta(hours=1))
    assert d.fmt(494804, NOW, CET) == f"{d.day(start, local)} {start:%H:%M}–{start + timedelta(hours=1):%H:%M}"
    assert d.offset(NOW, CET) == "UTC+01:00"


def test_day_labels():
    base = datetime(2026, 10, 28, 20, 0, tzinfo=CET)
    assert d.day(base, base) == "today" and d.day(base + timedelta(days=1), base) == "tomorrow"
    assert d.day(base + timedelta(days=2), base) == "Fri"


def test_schedule_and_todo_line():
    rows = d.schedule(ROT, NOW, 3, CET)
    assert [r.split(" ")[-1] for r in rows] == ["Europa", "Nessus", "Cosmodrome"] and rows[0].startswith("now until")
    line = d.todo_line(ROT, ["Europa", "Vault of Glass", "Europa"], NOW, CET)
    assert line == f"Europa {d.fmt(494803, NOW, CET)}, then every 7 h (UTC+01:00)"
    assert d.todo_line(ROT, ["Vault of Glass"], NOW, CET) is None


def test_unknown_destination():
    with pytest.raises(ValueError, match="Cosmodrome"):
        d.windows(ROT, "Mars", NOW, 1)
