"""Who the player is: Destiny membership, profile components, character by class."""
from shell.core.bungie import BungieApiError, BungieClient

CLASS_TYPE = {"titan": 0, "hunter": 1, "warlock": 2}


def primary_membership(client: BungieClient) -> dict:
    memberships = client.get("/User/GetMembershipsForCurrentUser/", auth=True)
    accounts = memberships.get("destinyMemberships") or []
    if not accounts:
        raise BungieApiError("No Destiny account on this Bungie.net profile.")
    primary = memberships.get("primaryMembershipId")
    return next((a for a in accounts if a["membershipId"] == primary), accounts[0])


def get_profile(client: BungieClient, membership: dict, components: list[int]) -> dict:
    return client.get(f"/Destiny2/{membership['membershipType']}/Profile/{membership['membershipId']}/",
                      params={"components": ",".join(map(str, components))}, auth=True)


def character_id(profile: dict, character: str) -> str:
    character = character.lower()
    wanted = CLASS_TYPE.get(character)
    for cid, c in profile["characters"]["data"].items():
        if c.get("classType") == wanted:
            return cid
    raise BungieApiError(f"No {character} on this account.")
