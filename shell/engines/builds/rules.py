"""Game equipping rules the code can check (source: docs/game-rules.md)."""

WEAPON_SLOTS = ["Kinetic", "Energy", "Power"]
WEAPON_ELEMENTS = ["Kinetic", "Arc", "Solar", "Void", "Stasis", "Strand"]
SLOT_ELEMENTS = {
    "Kinetic": ("Kinetic", "Stasis", "Strand"),
    "Energy": ("Arc", "Solar", "Void"),
    "Power": tuple(WEAPON_ELEMENTS),
}
# Exceptions reserved for exotics (e.g. Tessellation: Kinetic in the Energy slot)
EXOTIC_SLOT_ELEMENTS = {"Energy": ("Kinetic",)}
SLOT_AMMO = {"Kinetic": ("Primary", "Special"), "Energy": ("Primary", "Special"), "Power": ("Heavy",)}
# manifest equippingBlock.uniqueLabel: one equipped item per label
MAX_EXOTIC_WEAPONS = 1
MAX_EXOTIC_ARMOR = 1
# Slot (utility) mod sockets per armor piece (Armor 3.0); the same mod can go in several of them, within
# the piece's energy
UTILITY_SOCKETS = 3
# Highest column each artifact perk socket accepts (get_artifact with options, 2026-10-07)
ARTIFACT_SOCKET_COLUMNS = (1, 1, 2, 2, 2, 3, 3)


def element_fits(slot, element, exotic=False):
    """Can a weapon of this element go in this slot?"""
    if element in SLOT_ELEMENTS.get(slot, ()):
        return True
    return bool(exotic) and element in EXOTIC_SLOT_ELEMENTS.get(slot, ())
