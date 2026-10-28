"""Sign-in state and who the player is."""
from mcp.server.mcpserver import MCPServer

from shell.context import Context
from shell.mcp import tool


def register(mcp: MCPServer, ctx: Context) -> None:
    @tool(mcp)
    def auth_status() -> dict:
        """Whether the player is signed in to Bungie, and until when."""
        return ctx.oauth.status()

    @tool(mcp)
    def get_profile_summary() -> dict:
        """The player's Destiny account: display name, platform membership and characters (class, light)."""
        memberships = ctx.client.get("/User/GetMembershipsForCurrentUser/", auth=True)
        accounts = memberships["destinyMemberships"]
        primary = memberships.get("primaryMembershipId")
        account = next((a for a in accounts if a["membershipId"] == primary), accounts[0])
        profile = ctx.client.get(f"/Destiny2/{account['membershipType']}/Profile/{account['membershipId']}/",
                                 params={"components": "200"}, auth=True)
        classes = ctx.manifest.table("DestinyClassDefinition")
        name = account.get("bungieGlobalDisplayName") or account.get("displayName", "")
        if account.get("bungieGlobalDisplayNameCode") is not None:
            name = f"{name}#{account['bungieGlobalDisplayNameCode']:04d}"
        return {
            "display_name": name,
            "membership_type": account["membershipType"],
            "membership_id": account["membershipId"],
            "characters": [
                {"character_id": c["characterId"],
                 "class": classes[str(c["classHash"])]["displayProperties"]["name"],
                 "light": c["light"]}
                for c in profile["characters"]["data"].values()
            ],
        }
