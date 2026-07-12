# AGENTS.md

This file guides code agents working in the LangBot main repository. `CLAUDE.md` is a symlink to this file.

Read `ARCHITECTURE.md` before non-trivial backend, frontend, runtime, plugin, Box, MCP, persistence, or cross-repo SDK changes. This file is the working checklist; `ARCHITECTURE.md` is the system map.

## Quick Facts

- Python backend: `>=3.11,<4.0`, dependencies managed by `uv`.
- Frontend: `web/` is Vite + React Router 7 + shadcn/ui + Tailwind, managed by `pnpm`.
- Backend framework: Quart served by Hypercorn on `api.port`, default `5300`.
- Frontend dev server: `web/` on `3000`, with `VITE_API_BASE_URL` pointing at the backend.
- Plugin/Box/runtime contracts live in sibling repo `langbot-plugin-sdk`, pinned as `langbot-plugin` in `pyproject.toml`.

## Essential Commands

```bash
uv sync --dev
uv run main.py
uv run pre-commit install

cd web
pnpm install
pnpm dev
pnpm build
```

Useful focused tests:

```bash
uv run pytest tests/unit_tests -q
uv run pytest tests/integration -q
uv run pytest tests/integration/persistence -q
uv run pytest tests/manual/mcp_smoke.py

cd web
pnpm lint
pnpm test:e2e
```

Run the narrowest useful test first, then broader checks when confidence is needed.

## Where to Look

- Architecture map: `ARCHITECTURE.md`.
- Dev environment guide: https://docs.langbot.app/zh/develop/dev-config.
- Plugin runtime / CLI / SDK debugging: https://docs.langbot.app/zh/develop/plugin-runtime.
- API-key auth: `docs/API_KEY_AUTH.md`.
- Box deep-dive notes: `docs/review/box-architecture.md` and related files.
- In-repo skills: `skills/` is the single source of truth for LangBot agent skills.
- SDK repo: `../langbot-plugin-sdk/` when changing shared entities, plugin APIs, action protocol, `lbp rt`, or `lbp box`.

## Cross-Repo SDK Work

When changing SDK contracts used by LangBot:

```bash
# from langbot-plugin-sdk, with LangBot's .venv active
uv pip install .

# from LangBot, preserve the locally installed SDK
uv run --no-sync main.py
```

For standalone runtime debugging:

```bash
# in langbot-plugin-sdk
uv run --no-sync lbp rt
uv run --no-sync lbp box

# in LangBot
uv run --no-sync main.py --standalone-runtime
uv run --no-sync main.py --standalone-box
```

Config keys to verify in `data/config.yaml` / `src/langbot/templates/config.yaml`:

- Plugin runtime: `plugin.runtime_ws_url`, default Docker host `langbot_plugin_runtime:5400/control/ws`.
- Box runtime: `box.enabled`, `box.backend`, `box.runtime.endpoint`, Docker host `langbot_box:5410`.
- API/MCP auth: `api.global_api_key`.

## Change Rules

- HTTP API changes that should be agent-accessible must update the matching MCP tool in `src/langbot/pkg/api/mcp/server.py` and the relevant skill under `skills/` in the same pass.
- New schema changes use Alembic under `src/langbot/pkg/persistence/alembic/versions/`. LangBot 4.x does not support upgrading 3.x databases.
- New platform behavior belongs in platform adapters only for platform translation; pipeline/business logic belongs in `pkg/pipeline/` or services.
- User-facing strings must support i18n (`en_US`, `zh_Hans`; include `ja_JP` where the repo already does).
- Code comments and docstrings must be English.
- Keep compatibility and security in mind; LangBot is used in both self-hosted/community and toB deployments.
- Commit message format: `<type>(<scope>): <subject>`.

## Runtime Pitfalls

- Local stdio Plugin Runtime disconnects do not auto-reconnect; restart LangBot if that path breaks.
- Orphan runtime processes on `5400`/`5401` commonly break plugin debugging.
- Use `uv run --no-sync` after locally installing the SDK, or `uv` may restore the pinned package.
- A false Box “no backend” often means Docker is running but the current user lacks Docker socket permission.
- Do not confuse external MCP servers LangBot connects to (`pkg/provider/tools/loaders/mcp.py`) with LangBot's own `/mcp` server (`pkg/api/mcp/`).
- `CLAUDE.md` is a symlink to this file; edit `AGENTS.md`, not the symlink.

## Principles

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
