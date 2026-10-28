# S-004 — MCP server Claude can use

**Epic:** E1 Foundation · **Plan:** docs/plans/2026-10-28-foundation.md (Task 6)

## Why
Claude talks to Bungie through Shell's own tools when opened in this repo.

## Acceptance criteria
- [ ] Declared in the repo's `.mcp.json`, loaded when Claude Code opens the repo
- [ ] A new tool = a new module in `shell/mcp/tools/`, no other edit
- [ ] `auth_status` and `get_profile_summary` work end to end
