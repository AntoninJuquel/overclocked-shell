"""Parser registry: Sheet tab name -> (.md file slug, parser module)."""
from ..model import ParseError
from ._common import first_line
from . import armor_mods, armor_perks, artifact_perks, class_abilities, exotic_armors, exotic_class, exotic_weapons, game_mechanics, subclass, weapon_perks

TABS = {
    "Armor Mods": ("armor-mods", armor_mods),
    "Armor Perks": ("armor-perks", armor_perks),
    "Artifact Perks": ("artifact-perks", artifact_perks),
    "Exotic Armors": ("exotic-armors", exotic_armors),
    "Exotic Class": ("exotic-class", exotic_class),
    "Exotic Weapons": ("exotic-weapons", exotic_weapons),
    "Weapon Perks": ("weapon-perks", weapon_perks),
    "Arc": ("subclass-arc", subclass),
    "Solar": ("subclass-solar", subclass),
    "Void": ("subclass-void", subclass),
    "Stasis": ("subclass-stasis", subclass),
    "Strand": ("subclass-strand", subclass),
    "Prismatic": ("subclass-prismatic", subclass),
    "Class Abilities": ("class-abilities", class_abilities),
    "Game Mechanics": ("game-mechanics", game_mechanics),
}


def is_ignored(name):
    """Tabs deliberately not handled (landing page, archives)."""
    return name == "Landing" or name.startswith("OLD ")


def run(tab, module, grid):
    """Checks the tab's anchors, runs its parser and checks the entry count."""
    texts = {t for r in range(grid.height) for _, t in grid.cells(r)}
    known = texts | {first_line(t) for t in texts}
    for anchor in module.ANCHORS:
        if anchor not in known:
            raise ParseError(tab, f'anchor not found: "{anchor}"')
    try:
        entries = list(module.parse(grid))
    except (StopIteration, ValueError, IndexError, KeyError, AttributeError, TypeError) as e:
        raise ParseError(tab, f"unexpected structure ({e!r})") from e
    if len(entries) < module.MIN_ENTRIES:
        raise ParseError(tab, f"{len(entries)} entries found, at least {module.MIN_ENTRIES} expected")
    return entries
