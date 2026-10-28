from shell.engines.todo import catalog

SETS = {1: {"set": "Promised", "bonus": []}, 2: {"set": "Promised", "bonus": []},
        3: {"set": "Promised", "bonus": []}, 4: {"set": "AION", "bonus": []}, 5: {"set": "AION", "bonus": []}}
DEFS = {
    "1": {"classType": 2, "itemSubType": 26},   # Warlock Helmet
    "2": {"classType": 2, "itemSubType": 30},   # Warlock Class Item
    "3": {"classType": 0, "itemSubType": 28},   # Titan Chest
    "4": {"classType": 2, "itemSubType": 99},   # unknown subtype
}                                               # 5: missing from the manifest


def test_set_slots_for_class():
    assert catalog.set_slots(SETS, DEFS, "Warlock") == {"Promised": {"Helmet", "Class Item"}}
    assert catalog.set_slots(SETS, DEFS, "Titan") == {"Promised": {"Chest"}}
    assert catalog.set_slots(SETS, DEFS, "Hunter") == {}
