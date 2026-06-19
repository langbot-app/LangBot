# AGENTS.md

This file guides code agents (Claude Code, GitHub Copilot, OpenAI Codex, etc.) working in the LangBot project. `CLAUDE.md` is a symlink to this file.

## Project Overview

LangBot is an open-source, LLM-native instant-messaging bot development platform. It aims to provide an out-of-the-box IM bot development experience with Agent, RAG, MCP and other LLM application capabilities, supporting mainstream global IM platforms and exposing rich APIs for custom development.

LangBot has a comprehensive web frontend — almost every operation can be performed through it.

- **Python**: `>=3.11,<4.0`, dependencies managed by `uv`. Package version is in `pyproject.toml`.
- **Frontend**: `web/` is a **Vite + React Router 7 + shadcn/ui + Tailwind CSS** SPA, managed by `pnpm`. (Note: this is NOT Next.js — the `dev` script is `vite`.)
- **Backend framework**: Quart (the async flavour of Flask). The HTTP API and the pre-built web UI are both served by the backend on `http://127.0.0.1:5300`.

## Repository Layout

```
LangBot/
├── main.py                     # Entrypoint shim -> langbot.__main__.main()
├── pyproject.toml              # Python project + deps (uv), pins langbot-plugin==<x.y.z>
├── src/langbot/
│   ├── __main__.py             # Real entrypoint, CLI args (--standalone-runtime, --standalone-box, --debug)
│   ├── pkg/                    # Core backend package
│   │   ├── api/                # HTTP API controllers + services (Quart)
│   │   ├── core/               # App bootstrap, stages, task manager
│   │   ├── platform/           # IM platform adapters, bot managers, session managers
│   │   ├── provider/           # LLM providers, requesters, tool providers
│   │   ├── pipeline/           # Pipelines, stages, query pool
│   │   ├── plugin/             # Bridge connecting LangBot to the plugin runtime (see below)
│   │   ├── box/                # Code-sandbox subsystem (Docker / nsjail / E2B backends)
│   │   ├── skill/              # Skill subsystem
│   │   ├── rag/ , vector/      # RAG + vector store
│   │   ├── command/            # Built-in commands
│   │   ├── persistence/        # ORM models + Alembic migrations (SQLite & PostgreSQL)
│   │   ├── storage/            # Object/file storage abstractions
│   │   ├── config/, entity/, discover/, utils/, telemetry/, survey/
│   ├── libs/                   # Vendored SDKs (qq_official_api, wecom_api, etc.)
│   └── templates/              # Config/component templates (e.g. templates/config.yaml)
├── web/                        # Frontend SPA (Vite + React Router 7 + shadcn + Tailwind)
└── docker/                     # docker-compose deployment files
```

## Development Environment Setup

Full guide lives in the wiki: **["开发配置" / Dev Config](https://docs.langbot.app/zh/develop/dev-config)**. Summary:

### Backend

```bash
pip install uv
uv sync --dev          # uv creates a .venv/ for you; point your editor's interpreter at it
uv run main.py         # serves API + web UI on http://127.0.0.1:5300
```

On first run the config file is generated at `data/config.yaml`. DB is SQLite by default (zero setup); PostgreSQL is supported. Migrations run automatically on startup.

### Frontend

Requires Node.js + [pnpm](https://pnpm.io/installation).

```bash
cd web
cp .env.example .env   # Windows: copy .env.example .env
pnpm install
pnpm dev               # http://127.0.0.1:3000  (npm install / npm run dev also work)
```

`pnpm dev` reads `VITE_API_BASE_URL` from `web/.env` so the dev frontend can reach the backend on port `5300`. In production the frontend is pre-built into static files served by the backend on the same origin.

### Code formatting

The repo runs lint + format checks in CI. Install the pre-commit hooks so the same checks run locally before each commit:

```bash
uv run pre-commit install
```

## Plugin System

LangBot's plugin system (Plugin SDK, CLI `lbp`, Plugin Runtime, and the shared entity/API definitions) lives in a **separate repository**: [`langbot-plugin-sdk`](https://github.com/langbot-app/langbot-plugin-sdk). LangBot depends on it via the pinned `langbot-plugin` package in `pyproject.toml`.

### Architecture (what to know inside this repo)

- Plugins run as independent processes managed by the **Plugin Runtime**. The Runtime supports two control transports: `stdio` and `websocket`.
- When LangBot is started directly by a user (not in a container), it spawns and connects to the Runtime over **stdio** (lightweight/personal use).
- When LangBot runs in a container, it connects to a standalone Runtime over **WebSocket** (production).
- The bridge code lives in `src/langbot/pkg/plugin/` (`connector.py`, `handler.py`).
- Relevant config (`data/config.yaml`): `plugin.runtime_ws_url` (e.g. `ws://langbot_plugin_runtime:5400/control/ws`). Start LangBot with `--standalone-runtime` to make it connect to an externally-launched Runtime over WebSocket instead of spawning one over stdio.

### Debugging the Plugin Runtime / CLI / SDK

This is documented in detail in the **SDK repo's `AGENTS.md`** and in the wiki page **["调试插件运行时、CLI、SDK" / Plugin Runtime](https://docs.langbot.app/zh/develop/plugin-runtime)**. The short version:

- Clone `LangBot` and `langbot-plugin-sdk` as siblings under one parent dir so the editor resolves shared entities.
- Start a standalone Runtime from the SDK repo: `uv run --no-sync lbp rt` (control port `5400`, debug port `5401`).
- To make LangBot use a locally-modified SDK: from the SDK dir, with LangBot's `.venv` active, run `uv pip install .`, then launch LangBot with `uv run --no-sync main.py --standalone-runtime` (keep `--no-sync` so your local SDK isn't overwritten).

### Debugging the Box (sandbox) runtime

The Box subsystem (`src/langbot/pkg/box/`) is the code sandbox. It picks the first available backend among **Docker / nsjail / E2B**. The standalone Box runtime is launched via the SDK CLI: `lbp box`. Backend selection details, the `lbp box` flags, and the SDK-side architecture are documented in the SDK repo's `AGENTS.md`.

Relevant config (`data/config.yaml`, `box:` section): `box.enabled` (master switch — disabling it also disables the native sandbox tools, skill add/edit, and stdio-mode MCP servers), `box.backend` (`'local'` = Docker/nsjail auto-pick, or `'docker'` / `'nsjail'` / `'e2b'`; also settable via `BOX__BACKEND`), and `box.runtime.endpoint` (external Box runtime base URL, e.g. `ws://127.0.0.1:5410`; empty = local auto-managed runtime). Like the plugin runtime, LangBot can connect to an externally-launched Box runtime by setting that endpoint and starting with `--standalone-box`.

> A common false "No supported sandbox backend (Docker / nsjail / E2B) is available" comes from Docker being installed and running but the current user not being in the `docker` group → `docker info` gets `permission denied` on the socket. Fix: `sudo usermod -aG docker <user>` and restart the backend in a shell that has the new group.

## Development Standards

- LangBot is a global project: **all code comments and docstrings must be in English**, and every user-facing string must support **i18n** (`en_US` + `zh_Hans` at minimum, plus `ja_JP` where the repo already has it).
- LangBot is adopted in both toC and toB scenarios — always consider compatibility and security.
- **Commit message format**: `<type>(<scope>): <subject>`
  - `type`: one of `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, etc.
  - `scope`: the affected package/module/file/class.
  - `subject`: concise description of the change.

### Database migrations (Alembic)

LangBot uses [Alembic](https://alembic.sqlalchemy.org/) for migrations, supporting both SQLite and PostgreSQL from a single set of scripts. Migration files live in `src/langbot/pkg/persistence/alembic/versions/`.

If you change ORM model definitions, generate a migration:

```bash
# Run from the project root (requires data/config.yaml to exist)
uv run python -m langbot.pkg.persistence.alembic_runner autogenerate "description of your change"
```

Review and edit the generated script before committing. Migrations execute automatically on startup. `autogenerate` detects schema changes (add/drop columns, tables, type changes) but **data migrations** (e.g. mutating JSON field contents) must be hand-written into the generated script. `env.py` sets `render_as_batch=True`, so SQLite's ALTER TABLE limits are handled automatically — no need to branch per database. More in the wiki ["开发配置"](https://docs.langbot.app/zh/develop/dev-config#数据库迁移).

When writing a migration, follow these rules:

- **Revision id ≤ 32 characters.** PostgreSQL stores `alembic_version.version_num` as `varchar(32)`; a longer id raises `StringDataRightTruncationError` at runtime. Prefer short, descriptive ids like `0005_add_llm_context_length`.
- **Guard every operation against missing tables/columns.** Fresh installs build the schema via `create_all()` and then stamp the Alembic baseline, so a migration may run against a table that already has the change — or, in tests, against an empty database. Check `inspector.get_table_names()` / `inspector.get_columns(...)` before `add_column` / `drop_column`, mirroring the existing migrations.
- **Keep a single linear head.** Chain `down_revision` to the current head; do not create branches. Run the migration tests after adding one: `uv run pytest tests/integration/persistence/ -q` (the PostgreSQL test needs a running PG via `TEST_POSTGRES_URL`).

> **Legacy migration system (deprecated — do not extend).** The old 3.x migration system under `src/langbot/pkg/persistence/migrations/` (`DBMigration` subclasses in `dbmXXX_*.py`, run from `pkg/persistence/mgr.py`) is **frozen**. Do **not** add new `dbmXXX_*.py` files. The chain is capped at `required_database_version = 25` (`pkg/utils/constants.py`); those files only exist to upgrade pre-existing 3.x databases up to the Alembic baseline and are kept read-only. All new schema changes go through Alembic.

## Some Principles

- Keep it simple, stupid.
- Entities should not be multiplied unnecessarily.
- 八荣八耻

    以瞎猜接口为耻，以认真查询为荣。
    以模糊执行为耻，以寻求确认为荣。
    以臆想业务为耻，以人类确认为荣。
    以创造接口为耻，以复用现有为荣。
    以跳过验证为耻，以主动测试为荣。
    以破坏架构为耻，以遵循规范为荣。
    以假装理解为耻，以诚实无知为荣。
    以盲目修改为耻，以谨慎重构为荣。
