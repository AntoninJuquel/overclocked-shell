# S-041 — Verity solver for the raid companion

**Epic:** E10 Raid companion · **Follows:** S-024

## Why
Verity, the last encounter of Salvation's Edge, comes down to working out shape swaps under pressure: a good fit for a tool
that gives the same answer every time, and the raid companion only starts with Deep Stone Crypt.
`ChiriVulpes/verity` already solves it. Its license must be checked before reusing anything; only the idea is a given.

## Acceptance criteria
- [ ] The license of `ChiriVulpes/verity` is checked and its outcome noted here before any code is written
- [ ] The rules used by the solver come from a cached community guide and are checked against the current game
- [ ] Given what the player calls out, a tool returns the swaps to make, in order
- [ ] Invalid or impossible input is refused, saying which part is wrong
- [ ] The `raid-companion` skill uses it for Verity and can show the result on its live page
- [ ] Tests cover the known configurations
- [ ] `uv run pytest` passes
- [ ] Tried in the raid
