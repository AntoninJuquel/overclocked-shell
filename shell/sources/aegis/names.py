"""Item name normalization, to match Aegis, the inventory and build sheets."""
import re


def first_line(text):
    """First line of a cell ("Zaouli's Bane\\nPantheon version" -> "Zaouli's Bane")."""
    return (text or "").split("\n", 1)[0].strip()


def norm(name):
    """Comparison key: first line, without weapon variant suffix, straight apostrophes, collapsed spaces,
    case ignored."""
    s = re.sub(r"\s*\((Adept|Timelost|Harrowed|Baroque)\)$", "", first_line(name), flags=re.I)
    s = s.replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", s).strip().casefold()


def strip_set(name):
    """Set name without the manifest's "set" suffix ("smoke jumper set" -> "smoke jumper")."""
    return re.sub(r"\s+set$", "", name)
