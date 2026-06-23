---
name: langbot-mcp-ops
description: Operate a LangBot instance through its built-in MCP (Model Context Protocol) server. Use when an AI agent needs to manage LangBot — list/create/update/delete bots, agents, pipelines, models, knowledge bases, MCP servers, and skills — over MCP instead of raw HTTP. Covers the /mcp endpoint, API-key auth (web-UI lbk_ keys and the config.yaml global key), the tool surface, and client configuration. Triggers on "langbot mcp", "manage langbot via mcp", "langbot /mcp", "langbot mcp server".
---

# LangBot MCP Operations

LangBot exposes an **MCP server** so AI agents can manage an instance
programmatically. It mirrors a curated subset of the HTTP service API.

## Endpoint

```
http://<langbot-host>:5300/mcp
```

Transport: **streamable HTTP** (stateless, JSON responses). Same host/port as
the web UI and HTTP API.

## Authentication

Reuses the same API keys as the HTTP API. Send either header:

```
X-API-Key: <api-key>
# or
Authorization: Bearer <api-key>
```

Two kinds of key are accepted:

1. **Web-UI key** — created in the web UI (sidebar → API Keys), prefixed `lbk_`,
   stored in the database.
2. **Global API key** — set in `data/config.yaml` under `api.global_api_key`.
   Requires no login session and no DB record; does not need the `lbk_` prefix.
   Leave empty to disable. See the `langbot-deploy` skill for config details.

Requests without a valid key get `401 Unauthorized`.

## Client configuration

```json
{
  "mcpServers": {
    "langbot": {
      "url": "http://<langbot-host>:5300/mcp",
      "headers": { "X-API-Key": "<api-key>" }
    }
  }
}
```

## Tool surface

The tools wrap the LangBot service layer. Current tools (v1):

| Tool | Purpose |
| --- | --- |
| `get_system_info` | Version, edition, instance id |
| `list_bots` / `get_bot` / `create_bot` / `update_bot` / `delete_bot` | Manage messaging-platform bots (secrets redacted on read) |
| `list_agents` / `get_agent` / `create_agent` / `update_agent` / `delete_agent` | Manage the Agent product surface, including Agent orchestrations and Pipelines |
| `list_pipelines` / `get_pipeline` / `create_pipeline` / `update_pipeline` / `delete_pipeline` | Manage pipelines |
| `list_llm_models` / `get_llm_model` / `list_embedding_models` / `list_model_providers` | Inspect models & providers |
| `list_knowledge_bases` / `get_knowledge_base` / `retrieve_knowledge_base` | RAG knowledge bases (incl. semantic search) |
| `list_mcp_servers` | External MCP servers LangBot connects to (as a client) |
| `list_skills` / `get_skill` | Installed skills |

Mutating tools (`create_*`, `update_*`) take a JSON object matching the same
shape as the corresponding HTTP API request body. Discover resources with the
`list_*` / `get_*` tools before mutating; identifiers are UUIDs.

## How to use

1. Get an API key (web UI key, or set `api.global_api_key` in config.yaml).
2. Point your MCP client at `http://<host>:5300/mcp` with the key header.
3. Call `get_system_info` to confirm connectivity.
4. Use `list_*` tools to discover, then `get_*` / `create_*` / `update_*` /
   `delete_*` as needed.

## Implementation & maintenance (for LangBot developers)

- Server: `src/langbot/pkg/api/mcp/server.py` (FastMCP). Tools call the service
  layer directly, so the MCP surface stays aligned with the API.
- Mount: `src/langbot/pkg/api/mcp/mount.py` — an ASGI dispatcher fronting Quart,
  authenticating `/mcp` requests, running the streamable-HTTP session manager.
- Smoke test: `tests/manual/mcp_smoke.py`.

> When you add, remove, or change an HTTP API endpoint that should be
> agent-accessible, update the corresponding MCP tool **and** this skill. The
> MCP tool surface and the API must stay aligned (see `AGENTS.md`).

## Pitfalls

- `/mcp` is the **server** LangBot exposes. The `/api/v1/mcp` routes are the
  **client** side (managing external MCP servers LangBot connects to). Don't
  confuse them.
- A `401` means the key is wrong, missing, or (for the global key)
  `api.global_api_key` is empty in config.yaml.
- The global key is plaintext in config.yaml — only enable it on trusted/internal
  deployments and serve over HTTPS.
