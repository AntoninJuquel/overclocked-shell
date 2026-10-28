"""Where every item is right now (vault, character inventory, postmaster, equipped), for write actions."""
from shell.engines.inventory import POSTMASTER_BUCKET
from shell.engines.loadout import item_name

LOCATION_COMPONENTS = [102, 200, 201, 205]
VAULT_BUCKET = 138197802


def read_locations(profile: dict, defs: dict) -> tuple[dict[str, dict], dict[str, int]]:
    locations: dict[str, dict] = {}

    def add(item: dict, item_id: str, where: str, cid: str | None, bucket: int | None = None) -> None:
        locations[item_id] = {
            "itemId": item_id, "itemHash": item["itemHash"],
            "bucketHash": item.get("bucketHash", bucket), "where": where, "characterId": cid,
            "quantity": item.get("quantity", 1), "locked": bool(item.get("state", 0) & 1),
            "name": item_name(defs, item["itemHash"]),
        }

    for item in profile["profileInventory"]["data"]["items"]:
        if item.get("itemInstanceId"):
            add(item, item["itemInstanceId"], "vault", None, VAULT_BUCKET)
    for cid, inv in profile.get("characterInventories", {}).get("data", {}).items():
        for n, item in enumerate(inv["items"]):
            postmaster = item.get("bucketHash") == POSTMASTER_BUCKET
            if item.get("itemInstanceId"):
                add(item, item["itemInstanceId"], "postmaster" if postmaster else "inventory", cid)
            elif postmaster:  # uninstanced stacks can still be pulled from the postmaster
                add({**item, "state": 0}, f"pm:{cid}:{item['itemHash']}:{n}", "postmaster", cid)
    for cid, eq in profile.get("characterEquipment", {}).get("data", {}).items():
        for item in eq["items"]:
            if item.get("itemInstanceId"):
                add(item, item["itemInstanceId"], "equipped", cid)
    class_of = {cid: c.get("classType") for cid, c in profile["characters"]["data"].items()}
    return locations, class_of


def load_locations(client, defs: dict) -> tuple[dict, dict[str, dict], dict[str, int]]:
    """(membership, locations, class_of), read fresh: write tools never act on a stale snapshot."""
    from shell.engines.account import get_profile, primary_membership

    membership = primary_membership(client)
    return (membership, *read_locations(get_profile(client, membership, LOCATION_COMPONENTS), defs))


def bucket_of(defs: dict) -> callable:
    def bucket(h: int) -> int:
        weapon = defs["weapons"].get(str(h))
        return weapon["b"] if weapon else (defs["gear"].get(str(h)) or [0, 0, 0, 0])[3]
    return bucket
