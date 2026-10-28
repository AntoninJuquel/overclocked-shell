# Overclocked Shell

Your Ghost on steroids: a Destiny 2 companion for [Claude Code](https://claude.com/claude-code). You talk to Claude;
Shell gives it its own tools to read and act on your Destiny 2 account through the Bungie API.

## Install

Prerequisites: Git, [uv](https://docs.astral.sh/uv/), Claude Code.

1. Clone this repo and run `uv sync` inside it.
2. Create a Bungie application at <https://www.bungie.net/en/Application>:
   - OAuth Client Type: **Confidential**
   - Redirect URL: `https://localhost:7777/callback`
   - Scopes: read your Destiny 2 information, move or equip Destiny gear
3. Copy `.env.example` to `.env` and fill in the API key, client id and client secret.
4. Sign in once: `uv run shell auth login` (your browser warns about the localhost certificate: it was just made on
   your machine, continue). `uv run shell auth status` checks it.
5. Open Claude Code in this folder and approve the `overclocked-shell` server when asked. It is declared in
   `.mcp.json` (no secrets: the server reads `.env` itself), so Shell's tools are only loaded in this project.

Your data (`profile/`: tokens, builds, TODO) and downloaded data (`cache/`) stay local and are never committed.
To start with a sample build and the TODO templates, copy `examples/` into `profile/` (see `examples/README.md`).

## Use

Just talk to Claude in this folder, in English or French, for example:

- "sort my armor" / "sort my weapons" / "export the tags for DIM"
- "create a build around Getaway Artist", "re-optimize my build", "equip my build"
- "what should I farm tonight?", "I got the helmet", "ignore Exodus Down"
- "what does Facet of Courage do?", "what's the best rocket launcher?", "which endpoint equips items?"

Reference data (Destiny Data Compendium, Aegis's sheets, the Bungie API docs, DIM wishlists) is downloaded into
`cache/` on demand and stays there: it belongs to its authors.

## Switching from dim-agent

1. Import your builds and TODO data: `uv run shell import dim-agent <path to dim-agent>` (no trailing `\` in the
   path). dim-agent's version replaces Shell sheets with the same name and Shell's `needs.json`, `sources.json` and
   `overrides.json`; sheets that exist only in Shell are kept, old TODOs go to `profile/todo/history/`, and statuses
   are merged (a status you set by hand beats an automatic one). A sheet listed under `invalid` was copied as is
   (next to your Shell sheet as `<name>.dim-agent.json` if that one is valid): ask Claude to check it. dim-agent's
   folder is only read.
2. Remove the destiny-zen MCP server you registered at user level: `claude mcp remove destiny-zen -s user`.

## Development

`uv run pytest`. Design in `docs/specs/`, plans in `docs/plans/`, work items in `stories/`.
