# S-029 — Faster tools, and local data when Bungie is down

**Epic:** E1 Foundation

## Why
Most tools took 2 to 5 seconds, nearly all of it spent reading the same files again: the 214 MB item table parsed on
every call, the 23 MB wishlist, and a translator regex of 40,000 names. Tools that only need local data also failed
when Bungie was unreachable, because the manifest version always came from the network.

## Acceptance criteria
- [x] Huge manifest tables are shared between tool calls, parsed once by parallel calls, and freed after 10 minutes
      unused
- [x] When Bungie is unreachable and a manifest is on disk, its version is used after one short attempt, no retries;
      a table missing from disk still asks Bungie, and uses the version Bungie gives
- [x] `weapon_options` rereads the wishlist only when the file or the plug names changed
- [x] The translator gives the same text as the old regex, without compiling one
- [x] `uv run pytest` passes
