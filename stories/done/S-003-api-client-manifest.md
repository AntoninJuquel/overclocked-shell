# S-003 — Bungie API client and manifest

**Epic:** E1 Foundation · **Plan:** docs/plans/2026-10-28-foundation.md (Task 5)

## Why
Every feature needs reliable API calls and item definitions.

## Acceptance criteria
- [x] Throttling and maintenance are retried, then reported with the Bungie error code
- [x] Manifest tables download once per version into `cache/manifest/`, atomically
- [x] Old manifest versions are cleaned up
