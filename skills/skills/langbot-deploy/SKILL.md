---
name: langbot-deploy
description: Deploy and configure a LangBot instance — Docker / Docker Compose, Kubernetes, the config.yaml model, the Box sandbox runtime, the plugin runtime, and the global API key. Use when installing, deploying, upgrading, or configuring LangBot in production or self-hosted environments. Triggers on "deploy langbot", "langbot docker", "langbot compose", "langbot kubernetes", "langbot config.yaml", "langbot box runtime", "langbot global api key".
---

# LangBot Deployment & Configuration

Covers running LangBot in production. For development see `langbot-dev`.

## Docker Compose (recommended)

```bash
git clone https://github.com/langbot-app/LangBot
cd LangBot/docker

# Full stack (sandbox/Box + stdio MCP hosting + skill add/edit enabled)
docker compose --profile all up

# Basic (no Box runtime)
docker compose up
```

The `all` / `box` profile starts three services:

- `langbot` — main app, serves API + UI on `:5300`.
- `langbot_plugin_runtime` — plugin runtime (control `:5400`, debug `:5401`).
- `langbot_box` — Box sandbox runtime (`:5410`). Uses the host Docker socket to
  spawn sandbox containers, so the **Box root host path and in-container path
  must be identical** (`BOX__LOCAL__HOST_ROOT=${LANGBOT_BOX_ROOT:-${PWD}/data/box}`).

With Box off, the dashboard/skills list stays visible (read-only) but sandbox
tools, skill add/edit, and stdio MCP are disabled. Set `box.enabled: false`
(or `BOX__ENABLED=false`) to match.

## Kubernetes

See `docker/kubernetes.yaml` and the deployment guide at
https://docs.langbot.app. `docker/deploy-k8s-test.sh` is a test helper.

## config.yaml (generated at `data/config.yaml` on first run)

Top-level sections: `api`, `system`, `command`, `concurrency`, `proxy`,
`database`, `vdb`, `storage`, `plugin`, `monitoring`, `box`, `space`.

Key settings:

| Key | Meaning |
| --- | --- |
| `api.port` | HTTP API + UI port (default 5300) |
| `api.global_api_key` | **Global API key** for the HTTP API + MCP server. Non-empty = accepted with no login/DB record; no `lbk_` prefix required. Empty = disabled. Plaintext — trusted/internal only, serve over HTTPS. |
| `plugin.runtime_ws_url` | Standalone plugin runtime WS URL (e.g. `ws://langbot_plugin_runtime:5400/control/ws`) |
| `box.enabled` | Master switch for the Box sandbox runtime |
| `box.backend` | `local` (Docker/nsjail autopick) / `docker` / `nsjail` / `e2b`; env override `BOX__BACKEND` |
| `box.runtime.endpoint` | External Box runtime URL (e.g. `ws://127.0.0.1:5410`); empty = local auto-managed |

Many keys have `ENV__SUBKEY` overrides (e.g. `BOX__BACKEND`, `BOX__ENABLED`).

## Runtimes & flags

- LangBot started directly spawns the plugin runtime over **stdio**.
- In containers it connects to a standalone runtime over **WebSocket**; start
  with `--standalone-runtime`.
- Box has a parallel `--standalone-box` flag; the Docker box host is
  `langbot_box:5410`.

## Global API key — enabling for agents/automation

```yaml
# data/config.yaml
api:
    port: 5300
    global_api_key: 'a-strong-secret'   # empty disables it
```

This key authenticates both the HTTP API and the MCP server (`/mcp`) without a
login session. See `langbot-mcp-ops` for using it, and `docs/API_KEY_AUTH.md`.

## Pitfalls

- "No supported sandbox backend (Docker / nsjail / E2B)" with Docker running
  usually means the user isn't in the `docker` group →
  `sudo usermod -aG docker <user>` and restart in a new shell.
- Box root host/container path mismatch breaks sandbox container creation.
- Don't commit a non-empty `api.global_api_key` to version control.
