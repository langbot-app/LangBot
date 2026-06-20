# LangBot Skills

This directory is the **single source of truth** for LangBot's agent skills —
reusable, on-demand instruction packs for AI agents (Claude Code, Codex, Cursor,
and LangBot's own Local Agent) working with the LangBot ecosystem.

> These skills were consolidated here from the former `langbot-app/langbot-skills`
> repository (now archived). Documentation and the landing page link here; do not
> re-copy skill content elsewhere — link to this directory instead.

## Skill catalog

| Skill | What it covers |
| --- | --- |
| [`langbot-dev`](skills/langbot-dev) | Core backend + web frontend development (Quart, Vite, API, migrations, MCP server) |
| [`langbot-plugin-dev`](skills/langbot-plugin-dev) | Plugin SDK / component development, debugging, WebSocket testing |
| [`langbot-deploy`](skills/langbot-deploy) | Docker / Compose / Kubernetes deployment, config.yaml, Box runtime, global API key |
| [`langbot-testing`](skills/langbot-testing) | WebUI / e2e QA harness, cases, fixtures, troubleshooting (the `bin/lbs` CLI) |
| [`langbot-env-setup`](skills/langbot-env-setup) | Local dev/test environment, browser access, OAuth, proxy, startup |
| [`langbot-mcp-ops`](skills/langbot-mcp-ops) | Operating a LangBot instance through its MCP server (`/mcp`) |
| [`langbot-space-ops`](skills/langbot-space-ops) | Browsing the LangBot Space marketplaces through the Space MCP server |
| [`langbot-eba-adapter-dev`](skills/langbot-eba-adapter-dev) | Building platform adapters for the Event-Based Agents architecture |
| [`langbot-skills-maintenance`](skills/langbot-skills-maintenance) | Adding, deduplicating, and auditing skills in this directory |

`skills.index.json` is the machine-readable index (regenerate with `bin/lbs index`).

## Quick start (for an AI agent)

1. Read this README, `AGENTS.md`, and `qa-agent-docs/` to understand the layout.
2. Read `skills/.env` for shared local defaults. On a new machine, copy
   `skills/.env.example` to `skills/.env.local` (gitignored) and override
   machine-specific values there. Never commit secrets.
3. Pick the smallest relevant skill from the catalog above and follow its
   `SKILL.md`.

## The `lbs` CLI

The testing assets ship with a small CLI (`bin/lbs`, Node ≥ 22.6):

```bash
bin/lbs validate     # validate skills/cases/troubleshooting structure
bin/lbs index        # regenerate skills.index.json
bin/lbs env show     # inspect resolved env defaults (redacted)
bin/lbs env doctor   # diagnose local environment readiness
bin/lbs case list --ready
bin/lbs test plan <case-id>
```

## Maintenance rule

When the LangBot / LangBot Space **API or MCP server changes**, the
corresponding skill here MUST be updated in the same change. The MCP tool
surface, the API, and these skills are kept in lockstep — see each repo's
`AGENTS.md`.
