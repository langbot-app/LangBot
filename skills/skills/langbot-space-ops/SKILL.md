---
name: langbot-space-ops
description: Browse and search the LangBot Space marketplaces (plugins, MCP servers, skills) through the Space MCP server. Use when an AI agent needs to discover LangBot extensions on space.langbot.app over MCP. Covers the /mcp endpoint, Personal Access Token (PAT) auth, the tool surface, and client configuration. Triggers on "langbot space mcp", "search langbot plugins", "langbot marketplace mcp", "space.langbot.app mcp".
---

# LangBot Space MCP Operations

LangBot Space (space.langbot.app) exposes an **MCP server** so user-facing AI
agents can browse and search the marketplaces (plugins, MCP servers, skills).

## Endpoint

```
https://space.langbot.app/mcp
```

Transport: **streamable HTTP** (stateless, JSON responses). For a self-hosted
Space instance: `http://<host>:8383/mcp`.

## Authentication

Reuses the existing **Personal Access Token (PAT)** — the same token the `lbp`
CLI uses. Create one in your Space account (Profile → Personal Access Tokens),
then send it as a Bearer token:

```
Authorization: Bearer lbpat_...uests without a valid PAT get `401 Unauthorized`.

## Client configuration

```json
{
  "mcpServers": {
    "langbot-space": {
      "url": "https://space.langbot.app/mcp",
      "headers": { "Authorization": "Bearer <your-pat>" }
    }
  }
}
```

## Tool surface

| Tool | Purpose |
| --- | --- |
| `list_plugins` / `search_plugins` / `get_plugin` | Plugin marketplace |
| `list_mcp_servers` / `search_mcp_servers` / `get_mcp_server` | MCP-server marketplace |
| `list_skills` / `search_skills` / `get_skill` | Skill marketplace |

`list_*` and `search_*` are paged (`page`, `page_size`). `get_*` takes
`author` + `name`. The tool surface mirrors the REST endpoints under
`/api/v1/marketplace/*` and is read/browse only.

## How to use

1. Create a PAT in your Space account settings.
2. Point your MCP client at `https://space.langbot.app/mcp` with the Bearer PAT.
3. Use `search_plugins` / `search_mcp_servers` / `search_skills` to find items,
   then `get_*` for details (e.g. to obtain author/name for installation in
   LangBot itself).

## Implementation & maintenance (for Space developers)

- Server: `internal/controller/mcp/server.go` (official Go MCP SDK
  `github.com/modelcontextprotocol/go-sdk`). Tools call the service layer
  (`PluginService`, `MCPService`, `SkillService`) directly.
- Mount: `internal/controller/api.go` at `/mcp` and `/mcp/*any`.
- Auth: PAT via `AccountService.ValidatePersonalAccessToken`.
- Docs: `docs/MCP_SERVER.md`.

> When you add, remove, or change a marketplace API endpoint that should be
> agent-accessible, update the corresponding MCP tool **and** this skill. The
> MCP tool surface and the API must stay aligned (see `AGENTS.md`).

## Pitfalls

- The PAT prefix is `lbpat_` (Space), distinct from LangBot's `lbk_` API keys.
- This server is read/browse only; it does not publish or modify marketplace
  items. Use the web UI or REST API (with appropriate auth) for that.
