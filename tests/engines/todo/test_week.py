import json
from datetime import datetime, timezone

import pytest

from shell.engines.todo import week


def dn(name):
    return {"displayProperties": {"name": name}}


TABLES = {
    "milestones": {"10": dn("Last Wish")},
    "activities": {"1": dn("Last Wish: Standard"), "2": dn("Grandmaster: The Glassway"), "3": dn("Patrol"),
                   "4": dn("Nightfall: The Glassway"), "5": dn("Strike: The Disgraced"),
                   "9": dn("Grandmaster: The Glassway")},
    "modifiers": {"5": dn("Exotic Drop Rate Boosts Gained"), "6": dn("Shielded Foes"),
                  "7": dn("Double Nightfall Drops"), "8": dn("Doubles Rules")},
    "vendors": {"20": dn("Weekly: Vanguard Arms Rewards"), "21": dn("Tenet of Bravery"), "23": dn("Hunter Vendor")},
    "items": {
        "100": {**dn("Promised Cover"), "itemType": 2, "classType": 2, "itemSubType": 26,
                "inventory": {"tierTypeName": "Legendary"}},
        "101": {**dn("Fafnir"), "itemType": 3, "classType": 3, "itemTypeDisplayName": "Linear Fusion Rifle",
                "inventory": {"tierTypeName": "Exotic"}},
        "102": {**dn("Glimmer"), "itemType": 0},
        "103": {**dn("Hunter Mask"), "itemType": 2, "classType": 1, "itemSubType": 26,
                "inventory": {"tierTypeName": "Legendary"}},
        "104": {**dn("Wanderer Cloak"), "itemType": 2, "classType": 3, "itemSubType": 30},
    },
}
SETS = {100: {"set": "Promised", "bonus": []}}
NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)   # Wednesday
PROMISED = {"hash": 100, "name": "Promised Cover", "type": "armor", "class": "Warlock", "slot": "Helmet",
            "set": "Promised", "tier": "Legendary"}
FAFNIR = {"hash": 101, "name": "Fafnir", "type": "weapon", "class": None, "slot": "Linear Fusion Rifle",
          "set": None, "tier": "Exotic"}
CLOAK = {"hash": 104, "name": "Wanderer Cloak", "type": "armor", "class": None, "slot": "Class Item",
         "set": None, "tier": None}


def test_folder():
    from shell.core import paths
    assert week.folder() == paths.profile_dir() / "todo" / "week"


def test_item_info():
    assert week.item_info(TABLES["items"], SETS, 100) == PROMISED
    assert week.item_info(TABLES["items"], SETS, 101) == FAFNIR
    assert week.item_info(TABLES["items"], SETS, 104) == CLOAK
    assert week.item_info(TABLES["items"], SETS, 102) is None
    assert week.item_info(TABLES["items"], SETS, 999) is None


def test_parse_time_returns_aware_utc():
    utc = timezone.utc
    assert week.parse_time("2026-10-10") == datetime(2026, 10, 10, 23, 59, 59, tzinfo=utc)
    assert week.parse_time("2026-10-10T17:00:00") == datetime(2026, 10, 10, 17, tzinfo=utc)
    assert week.parse_time("2026-10-10T17:00:00.000Z") == datetime(2026, 10, 10, 17, tzinfo=utc)
    assert week.parse_time("2026-10-10T19:00:00+02:00") == datetime(2026, 10, 10, 17, tzinfo=utc)
    for bad in ("tomorrow", "", None, 3):
        with pytest.raises(ValueError):
            week.parse_time(bad)


def test_reset_window_from_milestones():
    ms = [{"startDate": "2026-10-06T17:00:00Z", "endDate": "2026-10-13T17:00:00Z"},
          {"startDate": "2026-10-06T17:00:00Z", "endDate": "2026-10-13T17:00:00Z"},
          {"startDate": None, "endDate": "2026-10-08T17:00:00Z"}]
    assert week.reset_window(ms, NOW) == ("2026-10-06T17:00:00Z", "2026-10-13T17:00:00Z")


def test_reset_window_normalises_dates_and_pairs_start_with_end():
    ms = [{"startDate": "2026-06-09T17:00:00Z", "endDate": "2026-10-13T17:00:00Z"},     # seasonal
          {"startDate": "2026-06-09T17:00:00Z", "endDate": "2026-10-13T17:00:00.000Z"},
          {"startDate": "2026-10-06T17:00:00Z", "endDate": "2026-10-13T17:00:00Z"},     # weekly
          {"startDate": "2026-10-06T17:00:00.000Z", "endDate": "2026-10-13T17:00:00.000Z"},
          {"startDate": "2026-10-06T17:00:00.000Z", "endDate": "2026-10-13T17:00:00Z"}]
    assert week.reset_window(ms, NOW) == ("2026-10-06T17:00:00Z", "2026-10-13T17:00:00Z")


def test_reset_window_start_comes_from_milestones_with_the_chosen_end():
    ms = [{"startDate": "2026-06-09T17:00:00Z", "endDate": "2026-12-01T17:00:00Z"},
          {"startDate": "2026-06-09T17:00:00Z", "endDate": "2026-12-02T17:00:00Z"},
          {"startDate": "2026-06-09T17:00:00Z", "endDate": "2026-12-03T17:00:00Z"},
          {"startDate": "2026-10-06T17:00:00Z", "endDate": "2026-10-13T17:00:00Z"},
          {"startDate": "2026-10-06T17:00:00Z", "endDate": "2026-10-13T17:00:00Z"}]
    assert week.reset_window(ms, NOW) == ("2026-10-06T17:00:00Z", "2026-10-13T17:00:00Z")


def test_reset_window_fallback_is_tuesday_17_utc():
    assert week.reset_window([], NOW) == ("2026-10-06T17:00:00Z", "2026-10-13T17:00:00Z")
    tuesday_morning = datetime(2026, 10, 13, 10, tzinfo=timezone.utc)
    assert week.reset_window([], tuesday_morning) == ("2026-10-06T17:00:00Z", "2026-10-13T17:00:00Z")
    tuesday_evening = datetime(2026, 10, 13, 18, tzinfo=timezone.utc)
    assert week.reset_window([], tuesday_evening) == ("2026-10-13T17:00:00Z", "2026-10-20T17:00:00Z")


def test_boosts():
    assert week.boosts(True, ["Shielded Foes"]) == ["focus"]
    assert week.boosts(False, ["Exotic Drop Rate Boosts Gained"]) == []   # permanent raid counter
    assert week.boosts(False, ["Double Nightfall Drops"]) == ["bonus"]
    assert week.boosts(False, ["Double Bonus Focus"]) == ["bonus"]
    assert week.boosts(False, ["Increased Rewards"]) == ["bonus"]
    assert week.boosts(False, ["Doubles Rules"]) == []                      # game rule
    assert week.boosts(True, ["Double Rewards"]) == ["focus", "bonus"]
    assert week.boosts(False, ["Shielded Foes", "Boosts Gained"]) == []


RAW = {
    "generated": "2026-10-07T10:00:00.000Z", "character": "warlock", "characterId": "c1",
    "milestones": [{"milestoneHash": 10, "startDate": "2026-10-06T17:00:00Z", "endDate": "2026-10-13T17:00:00Z",
                    "activities": [{"activityHash": 1, "modifierHashes": [5, 6]}]}],
    "activities": [
        {"activityHash": 2, "focused": True, "modifierHashes": [6], "rewardItemHashes": [100, 102, 103]},
        {"activityHash": 3, "focused": False, "modifierHashes": [8], "rewardItemHashes": []},
        {"activityHash": 1, "focused": False, "modifierHashes": [5], "rewardItemHashes": [100]},
        {"activityHash": 4, "focused": False, "modifierHashes": [7], "rewardItemHashes": []},
        {"activityHash": 5, "focused": False, "modifierHashes": [], "rewardItemHashes": [103]},
    ],
    "vendors": [
        {"vendorHash": 20, "nextRefreshDate": "2026-10-13T17:00:00Z",
         "sales": [{"itemHash": 100, "costs": [{"itemHash": 102, "quantity": 5000}]},
                   {"itemHash": 102, "costs": []}, {"itemHash": 103, "costs": []}]},
        {"vendorHash": 21, "nextRefreshDate": "9999-12-31T23:59:59Z",
         "sales": [{"itemHash": 101, "costs": []}, {"itemHash": 104}]},
        {"vendorHash": 22, "nextRefreshDate": None, "sales": [{"itemHash": 102, "costs": []}]},
        {"vendorHash": 23, "nextRefreshDate": "2026-10-13T17:00:00Z", "sales": [{"itemHash": 103, "costs": []}]},
    ],
}


def test_build_context():
    ctx = week.build_context(RAW, TABLES, SETS, NOW)
    assert ctx["date"] == "2026-10-07" and ctx["character"] == "warlock"
    assert ctx["reset"] == {"start": "2026-10-06T17:00:00Z", "end": "2026-10-13T17:00:00Z"}
    assert ctx["activities"] == [
        {"hash": 2, "name": "Grandmaster: The Glassway", "sources": ["portal"], "boosts": ["focus"],
         "modifiers": ["Shielded Foes"], "rewards": [PROMISED], "until": "2026-10-13T17:00:00Z"},
        {"hash": 4, "name": "Nightfall: The Glassway", "sources": ["portal"], "boosts": ["bonus"],
         "modifiers": ["Double Nightfall Drops"], "rewards": [], "until": "2026-10-13T17:00:00Z"},
        {"hash": 1, "name": "Last Wish: Standard", "sources": ["milestone", "portal"], "boosts": [],
         "modifiers": ["Exotic Drop Rate Boosts Gained", "Shielded Foes"], "rewards": [PROMISED],
         "until": "2026-10-13T17:00:00Z", "milestone": "Last Wish"},
    ]
    assert ctx["vendors"] == [
        {"hash": 21, "name": "Tenet of Bravery", "until": None,
         "items": [{**FAFNIR, "costs": []}, {**CLOAK, "costs": []}]},
        {"hash": 20, "name": "Weekly: Vanguard Arms Rewards", "until": "2026-10-13T17:00:00Z",
         "items": [{**PROMISED, "costs": [{"name": "Glimmer", "quantity": 5000}]}]},
    ]
    assert ctx["notes"] == [] and ctx["warnings"] == []


@pytest.mark.parametrize("kiosk", ["Lightfall Exotics", "Forsaken Exotics", "Legacy Gear", "Season of the Deep",
                                   "Episode: Echoes", "Strange Gear Offers"])
def test_build_context_kiosks_are_permanent(kiosk):
    tables = {**TABLES, "vendors": {**TABLES["vendors"], "30": dn(kiosk)}}
    raw = {**RAW, "vendors": [{"vendorHash": 30, "nextRefreshDate": "2026-10-13T17:00:00Z",
                               "sales": [{"itemHash": 101, "costs": []}]}]}
    assert week.build_context(raw, tables, SETS, NOW)["vendors"][0]["until"] is None


def test_build_context_without_character_keeps_all_classes():
    ctx = week.build_context({**RAW, "character": None}, TABLES, SETS, NOW)
    assert any(a["hash"] == 5 for a in ctx["activities"])
    assert any(v["hash"] == 23 for v in ctx["vendors"])


def test_build_context_warns_on_context_before_reset():
    ctx = week.build_context({**RAW, "generated": "2026-10-05T10:00:00.000Z"}, TABLES, SETS, NOW)
    assert ctx["warnings"] and "reset" in ctx["warnings"][0] and "refresh_context" in ctx["warnings"][0]


def test_build_context_warns_on_previous_week_context():
    raw = {**RAW, "generated": "2026-09-30T10:00:00.000Z",
           "milestones": [{**RAW["milestones"][0], "startDate": "2026-09-29T17:00:00Z",
                           "endDate": "2026-10-06T17:00:00Z"}]}
    ctx = week.build_context(raw, TABLES, SETS, NOW)
    assert ctx["warnings"] == ["context from 2026-09-30: week ended 2026-10-06, call refresh_context"]


def test_build_context_empty_raw():
    ctx = week.build_context({}, TABLES, SETS, NOW)
    assert ctx["activities"] == [] and ctx["vendors"] == []
    assert ctx["reset"]["end"] == "2026-10-13T17:00:00Z"


def test_apply_overrides():
    ctx = week.build_context(RAW, TABLES, SETS, NOW)
    overrides = {
        "activities": [
            {"name": "last wish: standard", "boost": None, "note": "no bonus actually"},
            {"name": "Nightfall: Glassway", "boost": "bonus", "until": "2026-10-10T17:00:00Z"},
            {"name": "Expired", "boost": "focus", "until": "2026-10-01T17:00:00Z"},
            {"name": "Bad", "boost": "triple"},
            {"boost": "focus"},
        ],
        "notes": [{"text": "Double dungeon loot", "until": "2026-10-13T17:00:00Z"},
                  {"text": "Old", "until": "2026-10-01T00:00:00Z"}],
    }
    out = week.apply_overrides(ctx, overrides, NOW)
    lw = next(a for a in out["activities"] if a["hash"] == 1)
    assert lw["boosts"] == [] and "override" in lw["sources"] and lw["note"] == "no bonus actually"
    nf = next(a for a in out["activities"] if a["name"] == "Nightfall: Glassway")
    assert nf == {"hash": None, "name": "Nightfall: Glassway", "sources": ["override"], "boosts": ["bonus"],
                  "modifiers": [], "rewards": [], "until": "2026-10-10T17:00:00Z"}
    assert not any(a["name"] == "Expired" for a in out["activities"])
    assert out["notes"] == [{"text": "Double dungeon loot", "until": "2026-10-13T17:00:00Z"}]
    assert out["warnings"] == ["overrides.activities[3]: unknown boost 'triple' (focus, bonus or null)",
                               "overrides.activities[4]: missing name, skipped"]
    assert [a["name"] for a in out["activities"]][:2] == ["Grandmaster: The Glassway", "Nightfall: Glassway"]
    assert ctx["activities"][1]["boosts"] == ["bonus"]   # original context untouched


def test_expired_override_skipped():
    ctx = week.build_context(RAW, TABLES, SETS, NOW)
    overrides = {"activities": [{"name": "Yesterday", "boost": "focus", "until": "2026-10-06"},
                                {"name": "Today", "boost": "focus", "until": "2026-10-07"}],
                 "notes": [{"text": "gone", "until": "2026-10-06"}, {"text": "today", "until": "2026-10-07"}]}
    out = week.apply_overrides(ctx, overrides, NOW)
    names = [a["name"] for a in out["activities"]]
    assert "Yesterday" not in names and "Today" in names   # a date-only until lasts to 23:59:59 UTC that day
    assert out["notes"] == [{"text": "today", "until": "2026-10-07T23:59:59Z"}]
    assert out["warnings"] == []


def test_apply_overrides_by_name_hits_every_activity_with_that_name():
    raw = {**RAW, "activities": RAW["activities"] + [
        {"activityHash": 9, "focused": True, "modifierHashes": [], "rewardItemHashes": []}]}
    ctx = week.build_context(raw, TABLES, SETS, NOW)
    overrides = {"activities": [{"name": "GRANDMASTER: the glassway", "boost": "bonus"},
                                {"name": "Grandmaster: The Glassway", "note": "match 2"}]}
    out = week.apply_overrides(ctx, overrides, NOW)
    gms = [a for a in out["activities"] if a["name"] == "Grandmaster: The Glassway"]
    assert sorted(a["hash"] for a in gms) == [2, 9]
    for a in gms:
        assert a["boosts"] == ["bonus"] and a["note"] == "match 2"
        assert a["sources"] == ["portal", "override"]   # once despite two overrides


def test_apply_overrides_boost_key_absent_keeps_boosts_null_removes_them():
    ctx = week.build_context(RAW, TABLES, SETS, NOW)
    overrides = {"activities": [{"name": "Nightfall: The Glassway", "note": "to do"},
                                {"name": "Grandmaster: The Glassway", "boost": None}]}
    out = week.apply_overrides(ctx, overrides, NOW)
    by_name = {a["name"]: a for a in out["activities"]}
    assert by_name["Nightfall: The Glassway"]["boosts"] == ["bonus"]
    assert by_name["Nightfall: The Glassway"]["note"] == "to do"
    assert by_name["Grandmaster: The Glassway"]["boosts"] == []


def test_apply_overrides_dates():
    ctx = week.build_context(RAW, TABLES, SETS, NOW)
    overrides = {
        "activities": [{"name": "Nightfall: The Glassway", "boost": None, "until": "2026-10-07"},
                       {"name": "Patrol", "boost": "focus", "until": "soon"},
                       {"name": "Last Wish: Standard", "boost": "focus", "until": "2026-10-07T08:00:00"}],
        "notes": [{"text": "a", "until": "2026-10-08"}, {"text": "b", "until": "later"}],
    }
    out = week.apply_overrides(ctx, overrides, NOW)
    nf = next(a for a in out["activities"] if a["name"] == "Nightfall: The Glassway")
    assert nf["boosts"] == [] and nf["until"] == "2026-10-07T23:59:59Z"   # date only: to the end of the day
    assert not any(a["name"] == "Patrol" for a in out["activities"])
    assert next(a for a in out["activities"] if a["hash"] == 1)["boosts"] == []   # no time zone = UTC, past
    assert out["notes"] == [{"text": "a", "until": "2026-10-08T23:59:59Z"}]
    assert len(out["warnings"]) == 2
    assert out["warnings"][0].startswith("overrides.activities[1]: invalid date 'soon'")
    assert out["warnings"][1].startswith("overrides.notes[1]: invalid date 'later'")


def test_load_overrides(tmp_path):
    assert week.load_overrides(tmp_path / "absent.json") == {"activities": [], "notes": []}
    path = tmp_path / "o.json"
    path.write_text(json.dumps({"notes": [{"text": "x"}]}), encoding="utf-8")
    assert week.load_overrides(path) == {"activities": [], "notes": [{"text": "x"}]}
    path.write_text("[", encoding="utf-8")
    with pytest.raises(ValueError):
        week.load_overrides(path)


def test_load_overrides_default_path():
    path = week.state.folder() / "overrides.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"notes": [{"text": "x"}]}), encoding="utf-8")
    assert week.load_overrides() == {"activities": [], "notes": [{"text": "x"}]}


@pytest.mark.parametrize("data", [{"activities": {}}, {"notes": "x"}, {"activities": [1]},
                                  {"notes": [{"text": "ok"}, ["x"]]}])
def test_load_overrides_rejects_bad_types(tmp_path, data):
    path = tmp_path / "o.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="o.json"):
        week.load_overrides(path)


def test_run_writes_context(tmp_path):
    ctx = week.run(RAW, TABLES, SETS, {"activities": [], "notes": [{"text": "n"}]}, NOW, tmp_path)
    saved = json.loads((tmp_path / "2026-10-07.json").read_text(encoding="utf-8"))
    assert saved == ctx and saved["notes"] == [{"text": "n", "until": "2026-10-13T17:00:00Z"}]


def test_run_defaults_to_week_folder():
    week.run(RAW, TABLES, SETS, {}, NOW)
    assert (week.folder() / "2026-10-07.json").exists()


def test_summary_lines():
    lines = week.summary(week.build_context(RAW, TABLES, SETS, NOW))
    assert lines[0] == "Week until 2026-10-13 (reset 17:00 UTC)"
    assert "Focus: Grandmaster: The Glassway" in lines
    assert "Bonus: Nightfall: The Glassway" in lines
    assert "Vendors: 2 with gear (1 until the reset)" in lines
