# S-039 — Activity history

**Epic:** E11 Ideas from DIM and co

## Why
Shell knows what the player owns, not what they play or what actually works for them. `recommend` could favour weapons
they really use, and the Ghost could talk about their clears. `mikechambers/dcli` syncs this history locally
(`GetActivityHistory`, `GetPostGameCarnageReport`).

## Acceptance criteria
- [ ] A tool syncs activity history into `profile/` incrementally: a second run only fetches what is new and respects rate
      limits
- [ ] A read tool returns clears, completion rate and best time per activity
- [ ] A read tool returns the weapons with the most kills, overall or for an activity
- [ ] `recommend_weapons` can mention how much the player has used a pick, without changing its ranking
- [ ] Another player's data in a carnage report is not stored
- [ ] `uv run pytest` passes
