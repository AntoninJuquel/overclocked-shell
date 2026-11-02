from shell.outputs import build_yaml

SHEET = {
    "name": "Warlock: Arc grenades",
    "class": "Warlock",
    "activity": None,
    "subclass": {"element": "Arc", "aspects": ["Feed the Void"], "fragments": []},
    "intent": {"stats": {"minimums": {"Grenade": 150}, "priority": ["Super"]},
               "weapons": [{"slot": "Kinetic", "exotic": True, "items": ["Song of Ir Yût"],
                            "perks": [["Physic", "Attrition Orbs"], ["No"]]}]},
    "resolved": {"weapons": [{"name": "Stand-in"}]},
    "hashes": {"item:Song of Ir Yût": 1, "item:Stand-in": 2, "stat:Grenade": 3, "setperk:Taken Barrier": 4},
}


def test_render():
    assert build_yaml.render(SHEET).splitlines() == [
        'name: "Warlock: Arc grenades"',
        "class: Warlock",
        "activity: null",
        "subclass:",
        "  element: Arc",
        "  aspects:",
        "    - Feed the Void",
        "  fragments: []",
        "intent:",
        "  stats:",
        "    minimums:",
        "      Grenade: 150",
        "    priority:",
        "      - Super",
        "  weapons:",
        "    - slot: Kinetic",
        "      exotic: true",
        "      items:",
        "        - Song of Ir Yût",
        "      perks:",
        "        - - Physic",
        "          - Attrition Orbs",
        '        - - "No"',
        "hashes:",
        '  "item:Song of Ir Yût": 1',
        '  "stat:Grenade": 3',
        '  "setperk:Taken Barrier": 4',
    ]


def test_only_the_intent_is_shared():
    text = build_yaml.render(SHEET)
    assert "resolved" not in text and "Stand-in" not in text


def test_text_that_would_change_meaning_is_quoted():
    for value in ("true", "150", "- a", "a: b", "# c", "line\nbreak", " spaced ", ""):
        assert build_yaml._scalar(value).startswith('"'), value
    assert build_yaml._scalar("Master of Arms") == "Master of Arms"
    assert build_yaml._scalar("Veteran's Wisdom") == "Veteran's Wisdom"
