# S-003 — Bungie API client and manifest

**Epic:** E1 Foundation · **Plan:** docs/plans/2026-10-28-foundation.md (Task 5)

## Why
Every feature needs reliable API calls and item definitions.

## Acceptance criteria
- [ ] Throttling and maintenance are retried, then reported with the Bungie error code
- [ ] Manifest tables download once per version into `cache/manifest/`, atomically
- [ ] Old manifest versions are cleaned up
