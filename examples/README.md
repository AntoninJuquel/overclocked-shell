# Examples

Starting data for a fresh clone. Your own data lives in `profile/` (gitignored); copy what you want there:

- `builds/example-warlock-prismatic-grenades.json` → `profile/builds/`: a build sheet with only its intent (no
  `resolved` part yet). Ask Claude to "optimize my example build" to fit it to your inventory, or to create your own
  build from scratch.
- `todo/sources.json` and `todo/overrides.json` → `profile/todo/`: empty templates for item sources the manifest
  doesn't know and corrections to the week's context (the `todo` skill explains both). Shell creates the other TODO
  files itself.
