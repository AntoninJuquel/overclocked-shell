# S-004 — MCP server Claude can use

**Epic:** E1 Foundation · **Plan:** docs/plans/2026-10-28-foundation.md (Task 6)

## Why
Claude talks to Bungie through Shell's own tools, in any project.

## Acceptance criteria
- [ ] Registered at user scope with one documented command
- [ ] A new tool = a new module in `shell/mcp/tools/`, no other edit
- [ ] `auth_status` and `get_profile_summary` work end to end
