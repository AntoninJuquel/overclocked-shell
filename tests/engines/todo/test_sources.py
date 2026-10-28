import json

import pytest

from shell.engines.todo import sources


def dn(name, **kw):
    return {"displayProperties": {"name": name}, **kw}


ITEMS = {
    "1": dn("Promised Victory Hood", classType=2, itemSubType=26, collectibleHash=11),
    "2": dn("Promised Victory Bond", classType=2, itemSubType=30, collectibleHash=12),
    "3": dn("Smoke Jumper Hood", classType=2, itemSubType=26, collectibleHash=13),
    "4": dn("Collective Obligation", classType=3, itemSubType=13, collectibleHash=14),
    "5": dn("Collective Obligation Catalyst"),
    "6": dn("Promised Victory Helm", classType=0, itemSubType=26, collectibleHash=11),
}
COLL = {
    "11": {"sourceString": 'Source: "Salvation\'s Edge" Raid'},
    "12": {"sourceString": 'Source: "Salvation\'s Edge" Raid'},
    "13": {"sourceString": "Random Perks: This item cannot be reacquired from Collections."},
    "14": {"sourceString": 'Source: "Vow of the Disciple" Raid'},
}
SETS = {1: {"set": "Promised"}, 2: {"set": "Promised"}, 3: {"set": "Smoke Jumper Set"}, 6: {"set": "Promised"}}
SE = {"type": "activity", "kind": "raid", "name": "Salvation's Edge", "detail": 'Source: "Salvation\'s Edge" Raid'}
VOW = {"type": "activity", "kind": "raid", "name": "Vow of the Disciple", "detail": 'Source: "Vow of the Disciple" Raid'}


def test_parse_source_string():
    assert sources.parse_source_string('Source: "Salvation\'s Edge" Raid') == SE
    assert sources.parse_source_string("Source: Nightfall strikes") == {"type": "world", "name": "Nightfall strikes"}
    assert sources.parse_source_string("Random Perks: This item cannot be reacquired from Collections.") is None
    assert sources.parse_source_string(None) is None
    assert sources.parse_source_string("  ") is None


def raid(kind, name, detail):
    return {"type": "activity", "kind": kind, "name": name, "detail": detail}


@pytest.mark.parametrize("text, expected", [
    ("Source: Last Wish raid.", raid("raid", "Last Wish", "Source: Last Wish raid.")),
    ('Source: Dungeon "Duality"', raid("dungeon", "Duality", 'Source: Dungeon "Duality"')),
    ('Complete the "Shattered Throne" dungeon.',
     raid("dungeon", "Shattered Throne", 'Complete the "Shattered Throne" dungeon.')),
    ('Source: "Salvation\'s Edge" Raid', raid("raid", "Salvation's Edge", 'Source: "Salvation\'s Edge" Raid')),
    ("Complete the Garden of Salvation raid", raid("raid", "Garden of Salvation", "Complete the Garden of Salvation raid")),
    ('Acquired from the raid "Crown of Sorrow."',
     raid("raid", "Crown of Sorrow", 'Acquired from the raid "Crown of Sorrow."')),
    ("Source: Sundered Doctrine", {"type": "world", "name": "Sundered Doctrine"}),
    ("Source: Vesper's Host", {"type": "world", "name": "Vesper's Host"}),
    ("Source: Pantheon", {"type": "world", "name": "Pantheon"}),
    ('Source: "Master" Triumph in Nightfalls', {"type": "world", "name": '"Master" Triumph in Nightfalls'}),
    ('Complete the "Vault of Glass" raid to unlock this in Eververse\nThen buy it with Bright Dust.',
     {"type": "world", "name": 'Complete the "Vault of Glass" raid to unlock this in Eververse'}),
    ("Source: Last Wish raid.\nSecond line", raid("raid", "Last Wish", "Source: Last Wish raid.")),
])
def test_parse_source_string_real_strings(text, expected):
    assert sources.parse_source_string(text) == expected


def test_build_index():
    idx = sources.build_index(ITEMS, COLL, SETS)
    assert idx["by_set"][("Promised", "Warlock", "Helmet")] == [SE]
    assert idx["by_set"][("Promised", "Warlock", "Class Item")] == [SE]
    assert idx["by_set"][("Promised", "Titan", "Helmet")] == [SE]
    assert ("Smoke Jumper Set", "Warlock", "Helmet") not in idx["by_set"]
    assert idx["by_name"]["Collective Obligation"] == [VOW]
    assert "Collective Obligation Catalyst" not in idx["by_name"]


def test_load_sources(tmp_path):
    assert sources.load_sources(tmp_path / "absent.json") == {}
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"set:Smoke Jumper Set": [{"type": "activity", "name": "Portal"}]}), encoding="utf-8")
    assert sources.load_sources(path) == {"set:Smoke Jumper Set": [{"type": "activity", "name": "Portal"}]}
    for bad in ([], {"k": {}}, {"k": [{"name": "x"}]}, {"k": ["x"]}):
        path.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(ValueError):
            sources.load_sources(path)


E = "2026-10-13T17:00:00Z"
HOOD = {"hash": 1, "name": "Promised Victory Hood", "type": "armor", "class": "Warlock", "slot": "Helmet",
        "set": "Promised", "tier": "Legendary"}
CO = {"hash": 4, "name": "Collective Obligation", "type": "weapon", "class": None, "slot": "Pulse Rifle",
      "set": None, "tier": "Exotic"}
CTX = {
    "reset": {"start": "2026-10-06T17:00:00Z", "end": E},
    "activities": [
        {"hash": 7, "name": "Salvation's Edge: Standard", "boosts": [], "until": E, "rewards": []},
        {"hash": 8, "name": "Garden of Salvation", "boosts": [], "until": E, "rewards": []},
        {"hash": 9, "name": "Contest of Elders: Matchmade", "boosts": ["focus"], "until": E, "rewards": [HOOD]},
        {"hash": 10, "name": "Contest of Elders: Matchmade", "boosts": ["focus"], "until": E, "rewards": [HOOD]},
    ],
    "vendors": [
        {"name": "Weekly: Vanguard Arms Rewards", "until": E,
         "items": [{**HOOD, "costs": [{"name": "Glimmer", "quantity": 5000}]}]},
        {"name": "Tenet of Bravery", "until": None, "items": [{**CO, "costs": []}]},
    ],
}
INDEX = sources.build_index(ITEMS, COLL, SETS)


def need(kind, target, nid="x"):
    return {"id": nid, "kind": kind, "label": "L", "target": target,
            "builds": [{"build": "b", "gain": {"stats": {}, "effects": [], "score": 0.1}}]}


def armor(slot="Helmet", set_="Promised"):
    return need("armor", {"class": "Warlock", "slot": slot, "set": set_, "archetypes": ["Demolitionist"],
                          "tertiaries": None}, nid=f"armor/Warlock/{slot}/{set_ or '-'}/Demolitionist/*")


def test_permanent_sources_from_manifest():
    assert sources.permanent_sources(armor(), INDEX, {}) == [SE]
    assert sources.permanent_sources(armor(slot="Legs"), INDEX, {}) == [SE]   # another slot of the set
    assert sources.permanent_sources(armor(set_="Smoke Jumper Set"), INDEX, {}) == []
    assert sources.permanent_sources(armor(set_=None), INDEX, {}) == [sources.ANY_LEGENDARY]
    assert sources.permanent_sources(need("weapon", {"name": "Collective Obligation"}), INDEX, {}) == [VOW]
    assert sources.permanent_sources(need("catalyst", {"name": "Collective Obligation"}), INDEX, {}) == []
    assert sources.permanent_sources(need("masterwork", {"itemId": "9", "name": "X", "slot": "Helmet"}),
                                     INDEX, {}) == [sources.MASTERWORK]
    assert sources.permanent_sources(need("upgrade", {"name": "Unto the Breach"}), INDEX, {}) == []


def test_permanent_sources_manual_first():
    portal = [{"type": "activity", "name": "Portal"}]
    manual = {"set:Smoke Jumper Set": portal, "catalyst/collective-obligation": [VOW],
              "armor/Warlock/Helmet/Promised/Demolitionist/*": portal}
    assert sources.permanent_sources(armor(set_="Smoke Jumper Set"), INDEX, manual) == portal
    assert sources.permanent_sources(armor(), INDEX, manual) == portal
    cat = need("catalyst", {"name": "Collective Obligation"}, nid="catalyst/collective-obligation")
    assert sources.permanent_sources(cat, INDEX, manual) == [VOW]


def test_dated_sources():
    out = sources.dated_sources(armor(), CTX, [SE])
    assert out == [
        {"type": "activity", "name": "Salvation's Edge: Standard", "boost": None, "until": E},
        {"type": "activity", "name": "Contest of Elders: Matchmade", "boost": "focus", "until": E},
        {"type": "vendor", "name": "Weekly: Vanguard Arms Rewards", "boost": "sale", "until": E,
         "costs": [{"name": "Glimmer", "quantity": 5000}]},
    ]
    weapon = need("weapon", {"name": "Collective Obligation"})
    assert sources.dated_sources(weapon, CTX, [VOW]) == [
        {"type": "vendor", "name": "Tenet of Bravery", "boost": None, "until": None, "costs": []}]
    assert sources.dated_sources(armor(set_=None), CTX, [sources.ANY_LEGENDARY]) == []
    assert sources.dated_sources(armor(), None, [SE]) == []


def test_catalyst_does_not_match_its_weapon():
    cat = need("catalyst", {"name": "Collective Obligation"}, nid="catalyst/collective-obligation")
    assert sources.dated_sources(cat, CTX, []) == []
    ctx = {**CTX, "activities": [{"name": "Vow", "boosts": [], "until": E, "rewards": [CO]}]}
    assert sources.dated_sources(cat, ctx, []) == []


def test_kiosk_source_is_not_boosted():
    weapon = need("weapon", {"name": "Collective Obligation"})
    ctx = {"vendors": [{"name": "Lightfall Exotics", "until": None, "items": [CO]}]}
    out = sources.dated_sources(weapon, ctx, [])
    assert out == [{"type": "vendor", "name": "Lightfall Exotics", "boost": None, "until": None, "costs": []}]
    assert sources.availability(out) == 1.0


def test_only_raids_and_dungeons_are_prefix_matched():
    ctx = {"activities": [{"name": "Pantheon: Atraks", "boosts": [], "until": E, "rewards": []}]}
    assert sources.dated_sources(armor(), ctx, [{"type": "world", "name": "Pantheon"}]) == []


def test_dated_sources_tolerates_missing_keys():
    ctx = {"activities": [{"name": "Salvation's Edge: Master", "until": E}], "vendors": [{"name": "V", "until": E}]}
    assert sources.dated_sources(armor(), ctx, [SE]) == [
        {"type": "activity", "name": "Salvation's Edge: Master", "boost": None, "until": E}]


def test_availability():
    assert sources.availability([{"boost": "focus"}, SE]) == 1.5
    assert sources.availability([{"boost": "sale"}]) == 1.5
    assert sources.availability([SE, {"boost": None}]) == 1.0
    assert sources.availability([]) == 0.3


def aegis(name, type_, source="", nid=None):
    return need("aegis", {"name": name, "type": type_, "source": source}, nid=nid or f"aegis/{name.lower()}")


def test_aegis_permanent_sources():
    got = sources.permanent_sources(aegis("Collective Obligation", "weapon", "Vow of the Disciple, Xur"), INDEX, {})
    assert got == [VOW, {"type": "activity", "name": "Xur", "detail": "Aegis Shopping List"}]
    promised = sources.permanent_sources(aegis("Promised", "set", "Salvation's Edge"), INDEX, {})
    assert promised == [SE]                                    # same name as the manifest source: no duplicate
    assert sources.permanent_sources(aegis("Truth", "weapon", "N/A"), INDEX, {}) == []
    manual = {"item:Truth": [{"type": "vendor", "name": "Kiosk"}]}
    assert sources.permanent_sources(aegis("Truth", "weapon", "Kiosk"), INDEX, manual) == manual["item:Truth"]


def test_aegis_matches_context_items():
    assert sources._matches(aegis("Promised", "set"), HOOD)
    assert sources._matches(aegis("Promised Victory Hood", "exotic"), HOOD)
    assert not sources._matches(aegis("Smoke Jumper", "set"), HOOD)


def test_aegis_sources_match_names_in_normalized_form():
    index = {"by_set": {}, "by_name": {"Zaouli’s Bane (Adept)": [VOW]}}
    got = sources.permanent_sources(aegis("Zaouli's Bane", "weapon"), index, {})
    assert got == [VOW]
    assert sources.permanent_sources(aegis("zaouli's bane", "weapon"), index, {}) == [VOW]


def test_load_sources_default_path_is_profile_todo(isolated_dirs):
    path = isolated_dirs / "profile" / "todo" / "sources.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"item:Truth": [{"type": "vendor", "name": "Kiosk"}]}), encoding="utf-8")
    assert sources.load_sources() == {"item:Truth": [{"type": "vendor", "name": "Kiosk"}]}
