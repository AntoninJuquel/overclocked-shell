"""Distortion schedule from the cached rotation (sources.distortions): which destination is Distorted at a given
hour, its next windows, in local time. Pure: hours are Unix epoch hours (UTC), `tz` only changes the display.
"""
from datetime import datetime, timedelta, timezone

PERIOD = 7
ALIASES = {"european dead zone": "edz"}


def _key(name):
    s = name.replace("’", "'").strip().lower()
    s = s.removeprefix("savathun's ")
    return ALIASES.get(s, s)


def active(rot, hour: int) -> str:
    return rot["order"][((hour - rot["anchor_hour"]) % PERIOD + rot["anchor_index"]) % PERIOD]


def match(name: str, rot) -> str | None:
    """The rotation's destination this source name designates, or None ("Throne World" = "Savathun's Throne
    World", "European Dead Zone" = "EDZ")."""
    return next((d for d in rot["order"] if _key(d) == _key(name)), None)


def _hour(now: datetime) -> int:
    return int(now.timestamp() // 3600)


def windows(rot, destination: str, now: datetime, count: int = 2) -> list[int]:
    """Start hours of the destination's next `count` windows, the current one included."""
    if destination not in rot["order"]:
        raise ValueError(f"not a Distortion destination: {destination} (destinations: {', '.join(rot['order'])})")
    first = next(h for h in range(_hour(now), _hour(now) + PERIOD) if active(rot, h) == destination)
    return [first + PERIOD * i for i in range(count)]


def _local(hour, tz):
    return datetime.fromtimestamp(hour * 3600, timezone.utc).astimezone(tz)


def day(when: datetime, now: datetime) -> str:
    delta = (when.date() - now.date()).days
    return {0: "today", 1: "tomorrow"}.get(delta, f"{when:%a}")


def fmt(hour: int, now: datetime, tz=None) -> str:
    """"now until 22:00", "today 21:00–22:00", "tomorrow 03:00–04:00", "Fri 03:00–04:00"."""
    start, end = _local(hour, tz), _local(hour + 1, tz)
    if hour == _hour(now):
        return f"now until {end:%H:%M}"
    return f"{day(start, now.astimezone(tz))} {start:%H:%M}–{end:%H:%M}"


def offset(now: datetime, tz=None) -> str:
    z = now.astimezone(tz).strftime("%z")
    return f"UTC{z[:3]}:{z[3:]}"


def schedule(rot, now: datetime, hours: int, tz=None) -> list[str]:
    """One line per hour from the current one: "<when>: <destination>"."""
    return [f"{fmt(h, now, tz)}: {active(rot, h)}" for h in range(_hour(now), _hour(now) + hours)]


def todo_line(rot, source_names, now: datetime, tz=None) -> str | None:
    """"Europa today 21:00–22:00, then every 7 h (UTC+01:00)" for the destinations among a need's sources."""
    found = list(dict.fromkeys(d for d in (match(n, rot) for n in source_names) if d))
    if not found:
        return None
    parts = [f"{d} {fmt(windows(rot, d, now, 1)[0], now, tz)}" for d in found]
    return f"{'; '.join(parts)}, then every {PERIOD} h ({offset(now, tz)})"


def stale(rot, now: datetime, days: int = 7) -> bool:
    return now - datetime.fromisoformat(rot["fetched"]) > timedelta(days=days)
