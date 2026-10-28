"""Armor Mods tab: one (name, effect) column pair per armor slot."""
import re

from ..model import Entry

ANCHORS = ("Helmet", "Arms", "Chest", "Legs", "Class Item", "Effect")
MIN_ENTRIES = 50
SLOTS = ("Helmet", "Arms", "Chest", "Legs", "Class Item")
ENERGY = re.compile(r"^(.*?)\s*\[([^\]]*?)\s*Energy\]$", re.S)


def parse(grid):
    header = next(r for r in range(grid.height) if {"Helmet", "Effect"} <= {t for _, t in grid.cells(r)})
    cols = grid.cells(header)
    groups = []  # (name column, effect column, section)
    for i, (c, title) in enumerate(cols[:-1]):
        nxt_c, nxt_title = cols[i + 1]
        if title != "Effect" and nxt_title == "Effect":
            groups.append((c, nxt_c, title.replace("-", " ")))
    entries = []
    for name_col, effect_col, section in groups:
        activity = None
        for r in range(header + 1, grid.height):
            name = grid.text(r, name_col)
            if not name or name == "-":
                continue
            effect = grid.text(r, effect_col)
            m = ENERGY.match(name)
            if not effect:
                if section in SLOTS:
                    raise ValueError(f"mod without effect: {name!r} ({section})")
                if not m:  # subheading: raid or activity name
                    activity = " ".join(name.split())
                continue
            attrs = {}
            if m:
                name, attrs["energy"] = m.group(1).strip(), m.group(2).strip()
            # "Mod\n\nEnhanced Mod": the cell holds the mod and its enhanced variant
            base, _, variant = name.partition("\n\n")
            name = " ".join(base.split())  # "Melee\nKickstart" -> "Melee Kickstart"
            if variant.strip():
                attrs["variant"] = " ".join(variant.split())
            if activity:
                attrs["activity"] = activity
            entries.append(Entry(name, section, attrs, effect))
    return entries
