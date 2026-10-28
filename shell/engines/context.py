"""Weekly context (milestones, available activities, vendor sales) in destiny-zen's export shape."""


def _activity(a: dict) -> dict:
    return {"activityHash": a["activityHash"], "modifierHashes": a.get("modifierHashes") or []}


def build_context(character: str, cid: str, milestones: dict, profile: dict, vendors: dict, generated: str) -> dict:
    available = profile.get("characterActivities", {}).get("data", {}).get(cid, {}).get("availableActivities") or []
    activities = []
    for a in available:
        if a.get("isVisible") is False:
            continue
        rewards = [r["itemQuantity"]["itemHash"] for v in a.get("visibleRewards") or []
                   for r in v.get("rewardItems") or [] if isinstance(r.get("itemQuantity", {}).get("itemHash"), int)]
        activities.append({**_activity(a), "focused": a.get("isFocusedActivity") is True,
                           "rewardItemHashes": list(dict.fromkeys(rewards))})
    sales = vendors.get("sales", {}).get("data", {})
    return {
        "generated": generated,
        "character": character.lower(),
        "characterId": cid,
        "milestones": [
            {"milestoneHash": m["milestoneHash"], "startDate": m.get("startDate"), "endDate": m.get("endDate"),
             "activities": [_activity(a) for a in (m.get("activities") or [])
                            + [q["activity"] for q in m.get("availableQuests") or [] if q.get("activity")]]}
            for m in milestones.values()
        ],
        "activities": activities,
        "vendors": [
            {"vendorHash": int(h), "nextRefreshDate": v.get("nextRefreshDate"),
             "sales": [{"itemHash": s["itemHash"], "costs": s.get("costs") or []}
                       for s in (sales.get(h, {}).get("saleItems") or {}).values()]}
            for h, v in (vendors.get("vendors", {}).get("data") or {}).items() if v.get("enabled") is not False
        ],
    }
