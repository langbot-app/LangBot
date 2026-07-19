---
name: langbot-dev
description: Develop, build, and debug the LangBot core backend and web frontend. Use when working inside the LangBot repository — backend (Python/Quart, src/langbot/pkg), the Vite/React web UI, HTTP API controllers/services, Alembic migrations, or the MCP server. Covers the dev environment (uv, pnpm), repo layout, the API auth model (user token / API key / global key), adding API endpoints, and the rule that API changes must update the MCP server and skills. Triggers on "langbot backend", "langbot dev", "langbot api", "add langbot endpoint", "langbot migration".
---

# LangBot Core Development

This skill covers developing the LangBot core (the main repo), distinct from
plugin development (see `langbot-plugin-dev`) and deployment (`langbot-deploy`).

## Stack

- **Backend**: Python `>=3.11,<4.0`, deps via `uv`. Framework: **Quart** (async
  Flask). Serves the HTTP API + pre-built web UI on `http://127.0.0.1:5300`.
- **Frontend** (`web/`): **Vite + React Router 7 + shadcn/ui + Tailwind**,
  managed by `pnpm`. Dev server on `:3000`. (NOT Next.js — `dev` script is `vite`.)

## Dev environment

```bash
# Backend
pip install uv
uv sync --dev
uv run main.py            # API + UI on http://127.0.0.1:5300

# Frontend (separate terminal)
cd web
cp .env.example .env
pnpm install
pnpm dev                  # http://127.0.0.1:3000 (reads VITE_API_BASE_URL)

# Lint/format hooks (CI runs the same checks)
uv run pre-commit install
```

First run generates `data/config.yaml`; DB defaults to SQLite (PostgreSQL
supported). Migrations run automatically on startup.

## Repo layout (key paths)

```
src/langbot/
├── __main__.py             # entrypoint, CLI flags (--standalone-runtime/-box/--debug)
├── pkg/
│   ├── api/
│   │   ├── http/           # Quart controllers + services
│   │   │   ├── controller/groups/   # route groups (@group.group_class)
│   │   │   └── service/             # business logic (called by controllers AND MCP)
│   │   └── mcp/            # MCP server (server.py = tools, mount.py = ASGI dispatch)
│   ├── core/               # app bootstrap, stages, task manager
│   ├── platform/ provider/ pipeline/ plugin/ box/ skill/ rag/ vector/
│   ├── command/ persistence/ storage/ config/ entity/ telemetry/
│   └── templates/config.yaml        # config template (top-level: api, system, plugin, box, space...)
├── web/                    # Vite SPA
└── docker/                 # compose deployment
```

## HTTP API auth model

Route auth is declared per-route via `AuthType` in
`pkg/api/http/controller/group.py`:

- `NONE` — public.
- `USER_TOKEN` — web UI JWT (`Authorization: Bearer <jwt>`).
- `API_KEY` — `X-API-Key` or `Authorization: Bearer <key>`.
- `USER_TOKEN_OR_API_KEY` — either.

Authenticated routes receive an immutable `RequestContext` containing the
principal, authorized Workspace membership, fixed-role permissions, instance,
request id, and placement generation. A browser's `X-Workspace-Id` is only a
selector and is always checked against the Account membership. Tenant services
must accept this context (or an explicit trusted execution context) and fail
closed when it is absent.

API-key authentication accepts:

1. the **global key** from `config.yaml` `api.global_api_key` only for a
   community instance with exactly one local Workspace, then
2. **web-UI keys** whose one-time `lbk_` secret is stored only as a hash and is
   bound to one Workspace, explicit scopes, status, and optional expiry.

An API key derives its Workspace from the key record and ignores a caller's
Workspace selector. Public Bot/Webhook routes similarly derive Workspace from
the opaque owning resource rather than a header.

Route groups self-register via `@group.group_class(name, path)` and are
discovered by `importutil.import_modules_in_pkg`.

## Adding an API endpoint

1. Add/extend a controller in `pkg/api/http/controller/groups/` and the matching
   service method in `pkg/api/http/service/`.
2. Pick the right `AuthType`.
3. **If the endpoint should be agent-accessible, add/adjust the matching MCP tool
   in `pkg/api/mcp/server.py` and update the `langbot-mcp-ops` skill.** API and
   MCP surface must stay aligned (see `AGENTS.md`).
4. Update `docs/service-api-openapi.json` if you maintain the OpenAPI overview.

## Database migrations (Alembic)

Single migration set supports SQLite + PostgreSQL. Files in
`src/langbot/pkg/persistence/alembic/versions/`.

```bash
# From project root (needs data/config.yaml)
uv run python -m langbot.pkg.persistence.alembic_runner autogenerate "description"
```

## Standards

- All code comments/docstrings in **English**; user-facing strings need **i18n**
  (`en_US` + `zh_Hans` minimum, `ja_JP` where present).
- Consider toC and toB compatibility + security.
- Commit format: `<type>(<scope>): <subject>` (feat/fix/docs/refactor/...).

## Tests

```bash
uv run pytest tests/unit_tests -q          # unit tests
uv run pytest tests/unit_tests/api -q      # API service tests
uv run python tests/manual/mcp_smoke.py    # MCP server e2e smoke
```

## See also

- `langbot-plugin-dev` — plugin SDK / runtime development.
- `langbot-testing` — WebUI/e2e QA harness (`bin/lbs`).
- `langbot-deploy` — Docker/compose deployment + config.
- `langbot-mcp-ops` — operating the LangBot MCP server.
