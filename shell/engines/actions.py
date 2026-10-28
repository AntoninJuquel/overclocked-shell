"""Write calls to Bungie: membership type added, spacing between calls, readable error names."""
import time
from typing import Any, Callable

from shell.core.bungie import BungieApiError, BungieClient

ERROR_NAMES = {
    1620: "character not found", 1623: "item not found", 1634: "character not in orbit / social space",
    1641: "unique-equip exotic clash", 1642: "no room in destination", 1645: "transfer failed",
    1648: "uniqueness violation", 1655: "can only equip in game", 1656: "cannot act on an equipped item",
    1660: "not transferable", 1672: "throttled by the game server",
    1676: "plug insertion rules failed (energy, or fragment slots not unlocked)", 1677: "socket not found",
    1678: "socket action not allowed", 1679: "plug already in this or another socket", 1680: "plug not unlocked",
}


def describe(error: BungieApiError) -> str:
    name = ERROR_NAMES.get(error.error_code)
    return f"{name} ({error})" if name else str(error)


class Actions:
    def __init__(self, client: BungieClient, membership: dict, sleep: Callable[[float], None] = time.sleep):
        self.client, self.membership, self.sleep = client, membership, sleep

    def post(self, path: str, body: dict, gap: float = 0.25) -> Any:
        result = self.client.post(path, {**body, "membershipType": self.membership["membershipType"]})
        self.sleep(gap)
        return result
