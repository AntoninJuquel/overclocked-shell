---
name: bungie-api
description: Bungie.net API reference (Destiny2 endpoints, manifest definition schemas, profile components, enums such as DamageType, TierType, ItemState, DestinyComponentType) converted to Markdown from the official OpenAPI spec. Use to interpret a manifest or inventory field, decode an enum or bitmask value, or write / change Shell code that calls the API.
---

# Bungie.net API

Voice: speak as the player's Ghost — see [ghost-voice.md](../../ghost-voice.md) (French when the player writes French).

The official OpenAPI spec (the one behind https://bungie-net.github.io/) is converted to Markdown in
`cache/bungie-api/` (not versioned, regenerable).

1. If `cache/bungie-api/index.md` is missing, or to follow an API update:
   `refresh_references(source="bungie-api", force=true)`. Without `force`, the cached
   `cache/bungie-api/raw/openapi.json` is reused. The API version heads every file.
2. Read `cache/bungie-api/index.md`: basics (response envelope, auth, hashes, components), type notation and the
   file list.
3. Search without loading a whole file (some are 100-250 KB):
   - schema or enum: `grep -n "^### .*DestinyInventoryItemDefinition" cache/bungie-api/*.md`, then read the
     section up to the next `###`;
   - endpoint: `grep -n "^### Destiny2.InsertSocketPlugFree" cache/bungie-api/endpoints-*.md`;
   - keyword: `grep -n -i "<word>" cache/bungie-api/*.md`.
4. Follow types down: a `uint32 → X` type is a hash to resolve in manifest table X; a named type
   (`Destiny.Entities.Items.DestinyItemComponent`) is itself searched with `^### `.

Limits: the spec describes the shape of the data, not game values (for those: the `compendium` skill or the
manifest). Descriptions come from Bungie and some are dated; a documented field can be empty in practice.
