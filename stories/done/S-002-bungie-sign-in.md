# S-002 — Bungie sign-in

**Epic:** E1 Foundation · **Plan:** docs/plans/2026-10-28-foundation.md (Tasks 3–4)

## Why
Sign in once with my own Bungie app, then forget about it for 90 days.

## Acceptance criteria
- [x] `uv run shell auth login` completes the browser flow and stores tokens in `profile/auth/`
- [x] Access tokens refresh automatically
- [x] Expired or missing sign-in gives one line telling me what to run
