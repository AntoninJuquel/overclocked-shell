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

## Development

`uv run pytest`. Design in `docs/specs/`, plans in `docs/plans/`, work items in `stories/`.
