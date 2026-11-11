# AGENTS.md

This file guides code agents working in the LangBot main repository. `CLAUDE.md` is a symlink to this file; edit `AGENTS.md`.

Read `ARCHITECTURE.md` before non-trivial backend, frontend, runtime, plugin, Box, MCP, persistence, or SDK (`sdk/`) changes. This file is the working checklist; `ARCHITECTURE.md` is the system map.

## Repository Layout

This is a monorepo: Core, WebUI, public docs, the plugin SDK, official plugins and agent skills share one checkout but not one release.

| Path | Contents | Notes |
| --- | --- | --- |
| `src/langbot/` | Core backend (Quart, `pkg/api`, `pkg/platform`, `pkg/pipeline`, `pkg/plugin`, ...) | Python `>=3.11,<4.0`, managed by `uv`. |
| `web/` | WebUI: Vite + React Router 7 + shadcn/ui + Tailwind | `pnpm`; dev server `3000`, backend `5300`. |
| `docs/` | **Public user/developer documentation**, published at https://langbot.app/docs/ | Fumapress, Node.js 24, `zh`/`en`/`ja` trees. Write for users and plugin authors; keep the three languages in step. |
| `dev-docs/` | **Internal design notes, contracts, reviews and test reports** for maintainers and agents | Not published. `architecture/` (Application API, i18n, ...), `event-based-agents/` (standard events/platform APIs and per-adapter records), `review/`, OpenAPI snapshots. |
| `sdk/` | Plugin SDK, `lbp` CLI, Plugin Runtime (`lbp rt`) and Box Runtime (`lbp box`), published to PyPI as `langbot-plugin` | Independent package (Python `>=3.10`, hatchling), own tests/CI (`sdk-*.yml`) and releases via `sdk/vX.Y.Z` tags. Core installs the PyPI pin, never `sdk/` directly. See `sdk/AGENTS.md` and `sdk/RELEASING.md`. |
| `plugins/` | Official plugins (`Runner/`, `KnowledgeEngine/`, `misc/`), indexed by `plugins/catalog.json` | Independent packages, CI and Marketplace releases; never bundled in Core artifacts. See `plugins/AGENTS.md`. |
| `skills/` | Agent skills (`skills/skills/<name>/SKILL.md`) and the `lbs` QA harness | Single source of truth for LangBot agent skills. See `skills/AGENTS.md`. |
| `tests/` | Core unit, integration, e2e and manual tests | |
| `tools/` | Regression harness, contracts, profiles and fixtures | See `tools/README.md`. |
| `scripts/` | Maintenance scripts, including catalog export and SDK code generation | |
| `docker/`, `packaging/`, `examples/`, `res/` | Deployment manifests, distro packages, integration examples, static resources | |

Choose `docs/` or `dev-docs/` by reader: anything a user or plugin author needs goes in `docs/`; design rationale, internal contracts and evidence go in `dev-docs/`. Do not duplicate content between them; link instead. The former `langbot-app/langbot-docs`, `langbot-app/langbot-plugins` and `langbot-app/langbot-plugin-sdk` repositories are archives: never edit or target them.

Related repository: [`langbot-cli`](https://github.com/langbot-app/langbot-cli) (`lbctl`, the Service API client).

Other references: dev environment `docs/zh/develop/dev-config.mdx`, Plugin Runtime debugging `docs/zh/develop/plugin-runtime.mdx`, API-key auth `dev-docs/API_KEY_AUTH.md`, Box internals `dev-docs/review/box-architecture.md`.

## Essential Commands

```bash
uv sync --dev
uv run main.py
uv run pre-commit install

cd web && pnpm install && pnpm dev   # pnpm build / pnpm lint / pnpm test:e2e
cd docs && npm ci && npm run dev
```

Focused tests (run the narrowest useful one first, in Linux to match CI; on Windows use Linux containers through `wslc` of WSL3):

```bash
uv run pytest tests/unit_tests -q
uv run pytest tests/integration -q
uv run pytest tests/integration/persistence -q
uv run pytest tests/manual/mcp_smoke.py
```

## SDK Work (`sdk/`)

Core depends on the exact PyPI pin `langbot-plugin==X` in `pyproject.toml`; `uv sync` never installs `sdk/`. When changing SDK contracts (shared entities, plugin APIs, action protocol, `lbp rt`, `lbp box`), change `sdk/` and the Core bridge in the same PR and test them together:

```bash
uv sync --dev
uv pip install ./sdk                           # overlay the in-tree SDK on Core's venv
uv run --no-sync main.py                       # add --standalone-runtime / --standalone-box
uv run --no-sync lbp rt                        # or: lbp box, for standalone debugging
cd sdk && uv run pytest -q                     # SDK's own environment (Python >=3.10)
```

CI mirrors this: `sdk-tests.yml` tests the SDK alone and the `Core with in-tree SDK` job in `run-tests.yml` runs Core tests over `sdk/`. Release order is always SDK first (`sdk/vX.Y.Z` tag → PyPI), then bump the Core pin, then release Core; `scripts/check_sdk_release_pin.py` blocks a Core release whose pin does not match the released `sdk/`. Never create a GitHub Release for the SDK. Details: `sdk/RELEASING.md`.

Config keys in `data/config.yaml` / `src/langbot/templates/config.yaml`: `plugin.runtime_ws_url` (Docker default `langbot_plugin_runtime:5400/control/ws`), `box.enabled` / `box.backend` / `box.runtime.endpoint` (Docker default `langbot_box:5410`), `api.global_api_key`.

## Change Rules

- New schema changes use Alembic under `src/langbot/pkg/persistence/alembic/versions/`. LangBot 4.x does not support upgrading 3.x databases.
- Platform adapters only translate platform protocols; pipeline and business logic belong in `pkg/pipeline/` or services.
- Conversation payload columns, including new ones, must use `MediaReferenceText` and persist image references only. See the [media persistence contract](ARCHITECTURE.md#persistence-and-configuration).
- Interactive session lists use `SessionSummaryReader` to read only `monitoring_sessions`; `SessionSummaryWriter` maintains summaries in the source transaction. Historical initialization completes before writers start, never in requests or application background tasks. Follow the [conversation summary contract](ARCHITECTURE.md#conversation-summary-boundary) and keep `uv run pytest --required-suite session_summary` passing.
- User-facing behavior changes update `docs/` (zh/en/ja) in the same pass; internal contract changes update the matching `dev-docs/` note.
- Code comments and docstrings must be English. Commit message format: `<type>(<scope>): <subject>`.
- Keep compatibility and security in mind; LangBot serves both self-hosted/community and toB deployments.

## Unified API (Workspace and Execution API)

`src/langbot/pkg/api/application/` is the transport-independent business boundary. Design: [Application API foundation](dev-docs/architecture/application-api.md).

- **Workspace operations** (`ap.application_api`): an explicit, versioned catalog of operation IDs such as `pipeline.list`, each with permission, principals, side effects, streaming mode and input/output schemas. Service operations are allowlisted in `service_operations.py`; label, summary, risk (read/write/high) and exposure (`none` / `assistant` / `all`) live in `operation_docs.py`. A public service method is not an operation until it is listed.
- **Execution operations** (`ExecutionAPI` in `execution.py`): the actions an installed plugin or a running Runner may call (models, RAG, tools, replies, `send_message`, `call_platform_api`, state, Box/files), bound to the trusted installation and run.

When adding or changing a Workspace capability:

1. Implement it once in the service layer and register it as an operation; do not write per-consumer business logic. Workspace identity comes only from the trusted `RequestContext`, never from arguments.
2. Decide and state in the PR how each consumer supports it:
   - **HTTP** route and response mapping (`pkg/api/http/`);
   - **MCP** tool in `pkg/api/mcp/server.py` plus the `langbot-mcp-ops` skill;
   - **Workspace assistant** and LocalAgent tools, including default tool sets for new Agents/Pipelines;
   - **Plugins**: exposure, principals, risk, wildcard eligibility, and the manifest permission a plugin must declare;
   - **`lbctl`** compatibility in `langbot-cli`.
   Existing HTTP/MCP entrypoints are still being migrated onto this boundary; do not add a second implementation beside it.
3. If the plugin-visible catalog changed, regenerate the SDK typed proxy with `uv run python scripts/generate_plugin_workspace_api.py` (writes `sdk/src/langbot_plugin/api/proxies/workspace_domains.py`; `--check` detects drift) and ship it in an SDK release.
4. Update `docs/*/plugin/dev/apis/workspace.mdx` and `permissions.mdx` when operations, risks or permissions change.
5. Verify through every adopted transport: denied access, missing resources, invalid input, cancellation and secret handling.

Plugin-/run-callable actions belong in the `ExecutionAPI` catalog; never add a side channel that bypasses installation grants, run binding or frozen run resources. Instance administration, login, public ingress, OAuth callbacks and Runtime handshakes stay outside the catalog.

## Platform Adapters: Standard Events and APIs

EBA adapters live in `src/langbot/pkg/platform/adapters/<platform>/` (legacy ones in `pkg/platform/sources/`). Standard definitions: `dev-docs/event-based-agents/01-event-system.md` (events) and `02-platform-api.md` (entities and APIs), implemented in the SDK under `langbot_plugin/api/entities/builtin/platform/`.

- Align with the standard definitions first. Map native events to a standard event (`message.received`, `message.edited`, `group.member_joined`, `bot.muted`, ...) and native operations to a standard API (`send_message`, `reply_message`, `get_group_info`, ...) whenever the semantics match, even if the platform names or shapes differ. Use `platform.specific` events and `call_platform_api` actions only for capabilities with no standard equivalent.
- Extend existing standard messages/APIs before inventing new ones (example: Slack threads ride on the standard message APIs).
- Propose a new standard event/API only for a capability common across platforms. Change it as one unit: SDK entity/event, the support matrix in `01`/`02`, every affected adapter, `docs/*/plugin/dev/apis/platform.mdx`, and the ExecutionAPI/Workspace consumers that expose it.
- `manifest.yaml` must match the implementation: `supported_events`, `supported_apis.required` / `optional`, and `platform_specific_apis`. Unimplemented optional APIs raise `NotSupportedError`; never silently no-op.
- Record each adapter in `dev-docs/event-based-agents/adapters/<platform>.md` against `acceptance-checklist.md`. Workflow: the `langbot-eba-adapter-dev` skill.

## Plugin Development

- SDK, `lbp` CLI and Plugin Runtime: `sdk/` (package `langbot-plugin`). Author docs: `docs/en/plugin/dev/` (`basic-info`, `permissions`, `components/*` for EventListener, Command, Tool, Runner, KnowledgeEngine, KnowledgeRetriever, Parser, Page, and `apis/*` for common, messages, platform, workspace, agent-run, llm-requests, pipeline-events).
- API catalogs: plugins call Workspace operations through `self.plugin.workspace.<domain>.<op>()` (runners: `ctx.api.workspace`), limited to operations declared in `spec.permissions` and granted by a member. `self.plugin.workspace.list()` returns the granted catalog at runtime; the full catalogs come from `ApplicationAPI.operation_catalog()` and `scripts/export_execution_catalog.py`. Runners expose only `ctx.resources.workspace_operations` to models.
- Reference implementations: `plugins/` (start from `plugins/catalog.json`; `misc/HelloPlugin` is the minimal example, `Runner/LocalAgent` the full Runner).
- Workflow and pitfalls: the `langbot-plugin-dev` skill. Release rules: `plugins/RELEASING.md`.

## Backend Message Language

- LangBot-owned errors, notices and default replies use the owning Workspace's `message_language` (default `en_US`), independent of WebUI language, resolved from a trusted Workspace/bot context and isolated per request/task/callback.
- Use `pkg/i18n` `t()` with stable English templates and named parameters; add the key and placeholders to all eight catalogs (`en_US`, `zh_Hans`, `zh_Hant`, `ja_JP`, `es_ES`, `ru_RU`, `th_TH`, `vi_VN`). Configurable Pipeline notices go through `pipeline_notice()`.
- Never translate raw provider/plugin diagnostics, protocol values or machine-readable codes, and never use substring replacement. China-only adapters and field validation diagnostics are exempt.
- Details and tests: [Backend message language](dev-docs/architecture/backend-i18n.md).

## Runtime Pitfalls

- Local stdio Plugin Runtime disconnects do not auto-reconnect; restart LangBot if that path breaks.
- Orphan runtime processes on `5400`/`5401` commonly break plugin debugging.
- Use `uv run --no-sync` after locally installing the SDK, or `uv` may restore the pinned package.
- A false Box "no backend" often means Docker is running but the current user lacks Docker socket permission.
- Do not confuse external MCP servers LangBot connects to (`pkg/provider/tools/loaders/mcp.py`) with LangBot's own `/mcp` server (`pkg/api/mcp/`).

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
