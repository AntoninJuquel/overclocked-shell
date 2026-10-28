import json

import pytest

from shell.core import paths
from shell.engines.builds import rules


@pytest.mark.parametrize("slot,element,exotic,ok", [
    ("Kinetic", "Strand", False, True),
    ("Kinetic", "Void", False, False),
    ("Energy", "Void", False, True),
    ("Energy", "Stasis", False, False),
    ("Energy", "Kinetic", False, False),
    ("Energy", "Kinetic", True, True),   # Tessellation
    ("Power", "Stasis", False, True),
    ("Power", "Kinetic", False, True),
])
def test_element_fits_slot(slot, element, exotic, ok):
    assert rules.element_fits(slot, element, exotic) is ok


REAL_WEAPONS = paths.ROOT / "profile" / "inventory" / "weapons.json"


@pytest.mark.skipif(not REAL_WEAPONS.exists(), reason="no inventory snapshot")
def test_rules_hold_on_real_export():
    """Canary: every weapon of the snapshot follows its slot's element and ammo rules."""
    items = json.loads(REAL_WEAPONS.read_text(encoding="utf-8"))
    bad = [(w["name"], w["slot"], w["element"], w["ammo"]) for w in items
           if w["slot"] in rules.WEAPON_SLOTS
           and (not rules.element_fits(w["slot"], w["element"], w["rarity"] == "Exotic")
                or w["ammo"] not in rules.SLOT_AMMO[w["slot"]])]
    assert bad == []
