# S-001 — Project skeleton

**Epic:** E1 Foundation · **Plan:** docs/plans/2026-10-28-foundation.md (Tasks 1–2)

## Why
A clone-and-go project: no build step, personal data never committed, paths that work from any folder.

## Acceptance criteria
- [x] `uv sync` installs everything; `uv run pytest` passes
- [x] `.env`, `profile/`, `cache/` gitignored; `.env.example` documents the three Bungie values
- [x] `.env`, `profile/`, `cache/` resolve from the install root, not the launch folder
- [x] Missing `.env` values are named in the error
