# S-025 — Cosmetics without a collectible

**Epic:** E6 Fashion · **Plan:** docs/plans/2026-10-29-plug-set-ownership.md

## Why
About 1,437 ornaments and 38 named shaders have no collectible, so `fashion_check` always says "unknown" for them.
The profile's plug sets (component 305) know most of them: checked live on 2026-10-29, they settle 531 of the
1,475 (61 owned, 470 not owned), against Collections they were never wrong on "owned" and 98% right on
"not owned".

## Acceptance criteria
- [x] A cosmetic with no collectible is owned when a profile or character plug set lists it as insertable
- [x] It is not owned when a plug set that can hold it is on the profile but doesn't list it
- [x] Otherwise (listed but not insertable, or no plug set for it) it stays unknown
- [x] Cosmetics with a collectible keep using Collections, unchanged
