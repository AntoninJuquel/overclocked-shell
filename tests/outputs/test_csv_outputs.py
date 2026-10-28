import csv

from shell.outputs import dim_csv, triage_csv

ARMOR = [
    {"decision": "KEEP", "classType": "Titan", "slot": "Helmet", "name": "B", "rarity": "Legendary", "gearTier": 3,
     "set": "Iron", "setBonus": ["2 pieces: Grit"], "archetype": "Gunner", "profile": "Weapons/Health/Class",
     "total": 70, "mw": {"Weapons": 30, "Health": 20, "Class": 10, "Grenade": 5, "Super": 5, "Melee": 5},
     "mwTotal": 75, "locked": True, "location": "Vault", "reason": "best copy", "itemId": "1", "itemHash": 11},
    {"decision": "JUNK", "classType": "Titan", "slot": "Helmet", "name": "A", "rarity": "Legendary", "gearTier": 0,
     "set": None, "setBonus": [], "archetype": None, "profile": "x", "total": 60,
     "mw": {"Weapons": 5, "Health": 5, "Class": 5, "Grenade": 5, "Super": 5, "Melee": 5},
     "mwTotal": 30, "locked": False, "location": "Vault", "reason": "legacy (pre-Armor 3.0)", "itemId": "2",
     "itemHash": 12},
]
WEAPON = {"decision": "KEEP", "name": "Fatebringer", "type": "Hand Cannon", "rarity": "Legendary", "gearTier": 0,
          "crafted": False, "grade": "S #2", "frame": "Adaptive", "traits": ("outlaw", "rampage"), "locked": False,
          "location": "Vault", "reason": "wishlist S #2", "itemId": "3", "itemHash": 13}


def read(path, delimiter):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f, delimiter=delimiter))


def test_triage_csv_headers_and_sort(tmp_path):
    triage_csv.write(tmp_path / "armor.csv", "armor", ARMOR)
    rows = read(tmp_path / "armor.csv", ";")
    assert rows[0][:4] == ["Decision", "Class", "Slot", "Name"] and rows[0][-3:] == ["Reason", "Id", "Hash"]
    assert [r[0] for r in rows[1:]] == ["JUNK", "KEEP"]
    keep = rows[2]
    assert keep[7] == "2 pieces: Grit" and keep[11] == "30/20/10/5/5/5" and keep[13] == "yes"
    triage_csv.write(tmp_path / "weapons.csv", "weapons", [WEAPON])
    rows = read(tmp_path / "weapons.csv", ";")
    assert rows[0][6] == "Wishlist grade" and rows[1][7] == "outlaw | rampage" and rows[1][5] == ""


def test_dim_note_prefix_set_and_grade():
    out = dim_csv.rows([ARMOR[0], WEAPON, {**WEAPON, "reason": "crafted (pattern)", "itemId": "4"}])
    assert out[0] == {"Id": "1", "Hash": "11", "Tag": "keep", "Notes": "shell: best copy · set Iron"}
    assert out[1]["Notes"] == "shell: wishlist S #2"  # grade already in the reason
    assert out[2]["Notes"] == "shell: crafted (pattern) · wishlist S #2"
    assert dim_csv.rows([ARMOR[1]], notes=False)[0] == {"Id": "2", "Hash": "12", "Tag": "junk", "Notes": ""}


def test_dim_csv_write_format(tmp_path):
    dim_csv.write(tmp_path / "dim.csv", dim_csv.rows([{**ARMOR[0], "reason": "x" * 2000}]))
    rows = read(tmp_path / "dim.csv", ",")
    assert rows[0] == ["Id", "Hash", "Tag", "Notes"] and len(rows[1][3]) == 1024
