from datetime import datetime, timedelta, timezone, tzinfo

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
    assert d.match("Vault of Glass", ROT) is None
    assert d.match("Europa (until 2026-11-03)", ROT) == "Europa"   # a whole word inside the name


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
    start = d._local(494803, CET)
    # a saved TODO is read later: absolute weekday and times, never "now" or "today"
    assert line == f"Europa {start:%a %H:%M}–{start + timedelta(hours=1):%H:%M}, then every 7 h (UTC+01:00)"
    assert d.todo_line(ROT, ["Vault of Glass"], NOW, CET) is None


def test_unknown_destination():
    with pytest.raises(ValueError, match="Cosmodrome"):
        d.windows(ROT, "Mars", NOW, 1)


class Paris(tzinfo):
    """Europe/Paris around the 2026-10-25 change (01:00 UTC: +02:00 -> +01:00); tzdata is not installed on Windows."""
    SWITCH = datetime(2026, 10, 25, 1)

    def utcoffset(self, dt):
        local = dt.replace(tzinfo=None)
        if local < datetime(2026, 10, 25, 2) or (local < datetime(2026, 10, 25, 3) and not dt.fold):
            return timedelta(hours=2)
        return timedelta(hours=1)

    def dst(self, dt):
        return self.utcoffset(dt) - timedelta(hours=1)

    def fromutc(self, dt):
        utc = dt.replace(tzinfo=None)
        if utc < self.SWITCH:
            return (utc + timedelta(hours=2)).replace(tzinfo=self)
        local = utc + timedelta(hours=1)
        return local.replace(tzinfo=self, fold=int(local < datetime(2026, 10, 25, 3)))


def test_rows_after_a_dst_change_carry_their_offset():
    now = datetime(2026, 10, 24, 23, 30, tzinfo=timezone.utc)      # 01:30 in Paris, +02:00
    assert d.offset(now, Paris()) == "UTC+02:00"
    rows = d.schedule(ROT, now, 3, Paris())
    assert "(UTC" not in rows[0]
    assert rows[1].startswith("today 02:00–02:00:")                  # starts at +02:00, ends after the change
    assert rows[2].startswith("today 02:00–03:00 (UTC+01:00):")     # 01:00 UTC, the repeated hour
    assert d.fmt(_h(2026, 10, 25, 1), now, Paris()).endswith("(UTC+01:00)")


def _h(*args):
    return d._hour(datetime(*args, tzinfo=timezone.utc))


def test_day_label_a_week_ahead_has_the_day_of_month():
    base = datetime(2026, 10, 28, 20, 0, tzinfo=CET)
    assert d.day(base + timedelta(days=6), base) == "Tue"
    assert d.day(base + timedelta(days=7), base) == "Wed 4"


def test_stale_with_a_naive_fetched_date():
    assert d.stale({**ROT, "fetched": "2020-01-01"}, NOW)
    assert not d.stale({**ROT, "fetched": NOW.replace(tzinfo=None).isoformat()}, NOW)


def test_match_a_destination_inside_a_source_name():
    assert d.match("Exploring Europa", ROT) == "Europa"
    assert d.match("Complete activities in the Dreaming City.", ROT) == "Dreaming City"
    assert d.match("Patrols in the European Dead Zone", ROT) == "EDZ"
    assert d.match("European Gear", ROT) is None and d.match("Moonfang", ROT) is None
