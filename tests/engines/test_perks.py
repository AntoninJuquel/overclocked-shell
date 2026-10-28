from shell.engines.perks import plan_perks


def option(name, h, enhanced=False, can=True):
    return {"name": name, "hash": h, "enhanced": enhanced, "canInsert": can}


ROW = {"itemId": "g1", "name": "Gun", "characterId": None, "columns": [
    {"socketIndex": 1, "label": "Barrel", "selected": "Arrowhead Brake", "selectedHash": 11,
     "options": [option("Arrowhead Brake", 11), option("Corkscrew Rifling", 12), option("Hammer-Forged", 13, can=False)]},
    {"socketIndex": 3, "label": "Trait", "selected": "Outlaw", "selectedHash": 20,
     "options": [option("Outlaw", 20), option("Kill Clip", 21), option("Kill Clip", 22, enhanced=True)]},
    {"socketIndex": 4, "label": "Trait", "selected": "Rampage", "selectedHash": 30,
     "options": [option("Rampage", 30), option("Kill Clip", 31)]},
]}


def test_selects_matching_column():
    plans, notes = plan_perks(ROW, "w", ["corkscrew rifling"])
    assert plans == [{"itemId": "g1", "characterId": "w", "name": "Gun", "column": "Barrel", "socketIndex": 1,
                      "from": "Arrowhead Brake", "to": "Corkscrew Rifling", "hashes": [12]}] and notes == []


def test_prefers_enhanced_but_ambiguous_columns_skipped():
    row = {**ROW, "columns": ROW["columns"][:2]}
    plans, _ = plan_perks(row, "w", ["Kill Clip"])
    assert plans[0]["hashes"] == [22]
    plans, notes = plan_perks(ROW, "w", ["Kill Clip"])
    assert plans == [] and notes == ['"Kill Clip" appears in more than one column']


def test_not_rolled_and_shared_column_noted():
    plans, notes = plan_perks(ROW, "w", ["Firefly", "Corkscrew Rifling", "Arrowhead Brake"])
    assert [p["to"] for p in plans] == ["Corkscrew Rifling"]
    assert notes == ['"Firefly" is not one of its rolled options',
                     '"Arrowhead Brake" shares the Barrel column with another requested perk']


def test_already_selected_and_cannot_insert_noted():
    plans, notes = plan_perks(ROW, "w", ["Outlaw", "Hammer-Forged"])
    assert plans == [] and notes == ['"Outlaw" is already selected',
                                     '"Hammer-Forged" can\'t be selected right now (Bungie)']
