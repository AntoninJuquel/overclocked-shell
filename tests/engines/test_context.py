from shell.engines.context import build_context

GENERATED = "2026-10-28T10:00:00.000Z"


def build(milestones=None, activities=None, vendors=None, sales=None):
    profile = {"characterActivities": {"data": {"w": {"availableActivities": activities or []}}}}
    vendor_response = {"vendors": {"data": vendors or {}}, "sales": {"data": sales or {}}}
    return build_context("Warlock", "w", milestones or {}, profile, vendor_response, GENERATED)


def test_header():
    c = build()
    assert (c["generated"], c["character"], c["characterId"]) == (GENERATED, "warlock", "w")
    assert c["milestones"] == c["activities"] == c["vendors"] == []


def test_milestones_include_quest_activities():
    c = build(milestones={"1": {"milestoneHash": 1, "startDate": "2026-10-27T17:00:00Z",
                                "activities": [{"activityHash": 10, "modifierHashes": [5], "challengeObjectiveHashes": []}],
                                "availableQuests": [{"activity": {"activityHash": 11}}, {"questItemHash": 3}]},
                          "2": {"milestoneHash": 2}})
    assert c["milestones"] == [
        {"milestoneHash": 1, "startDate": "2026-10-27T17:00:00Z", "endDate": None,
         "activities": [{"activityHash": 10, "modifierHashes": [5]}, {"activityHash": 11, "modifierHashes": []}]},
        {"milestoneHash": 2, "startDate": None, "endDate": None, "activities": []},
    ]


def test_invisible_activities_dropped_and_rewards_unique():
    reward = lambda h: {"itemQuantity": {"itemHash": h}}  # noqa: E731
    c = build(activities=[
        {"activityHash": 1, "isVisible": False},
        {"activityHash": 2, "isFocusedActivity": True, "modifierHashes": [7],
         "visibleRewards": [{"rewardItems": [reward(5), reward(6)]}, {"rewardItems": [reward(5)]}]},
        {"activityHash": 3},
    ])
    assert c["activities"] == [
        {"activityHash": 2, "modifierHashes": [7], "focused": True, "rewardItemHashes": [5, 6]},
        {"activityHash": 3, "modifierHashes": [], "focused": False, "rewardItemHashes": []},
    ]


def test_disabled_vendors_dropped_costs_raw():
    cost = {"itemHash": 9, "quantity": 50, "hasConditionalVisibility": False}
    c = build(vendors={"100": {"enabled": True, "nextRefreshDate": "2026-10-29T17:00:00Z"}, "200": {"enabled": False},
                       "300": {}},
              sales={"100": {"saleItems": {"0": {"itemHash": 1, "costs": [cost]}, "1": {"itemHash": 2}}}})
    assert c["vendors"] == [
        {"vendorHash": 100, "nextRefreshDate": "2026-10-29T17:00:00Z",
         "sales": [{"itemHash": 1, "costs": [cost]}, {"itemHash": 2, "costs": []}]},
        {"vendorHash": 300, "nextRefreshDate": None, "sales": []},
    ]
