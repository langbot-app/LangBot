# Architecture

This document is a map of LangBot's moving parts. It is intentionally more stable than a feature guide and more concrete than the README: when you need to change behavior, start here, then follow the file references into the code.

For agent-specific working rules, see `AGENTS.md`. For plugin-runtime and Box-runtime implementation details, also read the sibling SDK repo: [`langbot-plugin-sdk`](https://github.com/langbot-app/langbot-plugin-sdk).

## What LangBot Is

LangBot is an open-source platform for building production IM bots backed by LLMs, agents, RAG, plugins, MCP tools, and a web management panel.

At runtime, one LangBot process owns:

- a Quart/Hypercorn HTTP service and the built web UI on `:5300`;
- messaging-platform adapters such as Discord, Telegram, Slack, WeChat, QQ, WeCom, Lark, DingTalk, KOOK, LINE, Satori, Matrix, and HTTP/WebSocket bots;
- a pipeline engine that turns inbound platform messages into LLM/tool/plugin work and replies;
- persistence, storage, vector database, telemetry, monitoring, and configuration managers;
- bridges to the Plugin Runtime and Box Runtime provided by `langbot-plugin-sdk`;
- an MCP server at `/mcp` exposing a curated agent-facing subset of the service layer.

## Repository Boundary

LangBot is not a single-repo system.

- `LangBot/` is the main product: backend, web UI, platform adapters, pipeline engine, HTTP API, MCP server, RAG, persistence, skills integration, and the bridge code that talks to runtimes.
- `langbot-plugin-sdk/` is published as `langbot-plugin` and pinned in `LangBot/pyproject.toml`. It contains plugin developer APIs, shared entities, `lbp`, the Plugin Runtime (`lbp rt`), and the Box Runtime (`lbp box`).
- Plugins import SDK APIs from `langbot_plugin.*`; the LangBot main process imports the same package for shared entities and runtime protocols.

This split matters. If a change modifies SDK entities, component APIs, action protocols, `lbp rt`, or `lbp box`, verify the sibling SDK repo and install the local SDK into LangBot's virtualenv when testing cross-repo behavior.

## Startup Path

The process entrypoint is small and layered:

1. `main.py` delegates to `langbot.__main__.main()`.
2. `src/langbot/__main__.py` parses `--standalone-runtime`, `--standalone-box`, and `--debug`, checks dependencies, generates missing config/data files, and calls `pkg.core.boot.main()`.
3. `pkg/core/boot.py` executes startup stages in order: `LoadConfigStage`, `GenKeysStage`, `SetupLoggerStage`, `BuildAppStage`, `ShowNotesStage`.
4. `BuildAppStage` constructs the `Application` object by wiring managers, services, runtime connectors, and controllers.
5. `Application.run()` starts the platform manager, query controller, HTTP controller, telemetry/cleanup loops, and plugin initialization.

The central runtime object is `pkg/core/app.py::Application`. It is a service locator for long-lived managers. That is not elegant, but it is the current architectural center; most subsystems receive `ap: Application` and collaborate through it.

## Top-Level Layout

```text
LangBot/
├── main.py                         # Entrypoint shim
├── pyproject.toml                  # Python package, deps, pinned langbot-plugin
├── src/langbot/
│   ├── __main__.py                 # CLI entrypoint and boot handoff
│   ├── pkg/
│   │   ├── core/                   # Application, boot stages, task manager
│   │   ├── api/                    # HTTP API + MCP server mount
│   │   ├── platform/               # IM adapters and runtime bot manager
│   │   ├── pipeline/               # Message routing and pipeline stages
│   │   ├── provider/               # LLM runners, model manager, tools
│   │   ├── plugin/                 # LangBot-side Plugin Runtime connector/handler
│   │   ├── box/                    # LangBot-side Box service/connector
│   │   ├── skill/                  # Skill metadata/activation integration
│   │   ├── rag/ , vector/          # Knowledge-base and vector DB integration
│   │   ├── persistence/            # SQLAlchemy/SQLModel, Alembic, legacy migrations
│   │   ├── storage/                # Local/S3 file storage abstraction
│   │   └── config/, entity/, utils/, telemetry/, survey/
│   ├── libs/                       # Vendored third-party platform SDKs
│   └── templates/                  # Default config and component metadata
├── web/                            # Vite + React Router + shadcn/ui + Tailwind SPA
├── docker/                         # Deployment manifests
├── skills/                         # In-repo agent skills, single source of truth
└── tests/                          # Unit/integration/e2e/manual tests
```

## The Runtime Graph

The most useful mental model is this graph:

```text
Platform adapter
  → RuntimeBot
  → MessageAggregator
  → QueryPool
  → Controller
  → RuntimePipeline
  → PipelineStage chain
  → RequestRunner / ToolManager / PluginRuntimeConnector / BoxService
  → response via adapter
```

The HTTP and MCP surfaces are parallel entrypoints into the same service layer:

```text
HTTP client / Web UI
  → Quart route group
  → api/http/service/*
  → Application managers / persistence / runtime connectors

MCP client
  → /mcp mount
  → api/mcp/server.py tools
  → the same service layer directly
```

## Message Flow

Inbound platform messages enter through adapter-specific SDK callbacks. The common path is:

1. A platform adapter under `pkg/platform/sources/` converts platform-specific events into SDK message/event entities.
2. `RuntimeBot` in `pkg/platform/botmgr.py` applies pipeline routing rules and either discards the message, pushes it to webhooks, or sends it to the message aggregator.
3. `MessageAggregator` batches/normalizes messages before adding a `Query` to `QueryPool`.
4. `Controller` in `pkg/pipeline/controller.py` selects queries subject to global pipeline concurrency and per-session concurrency.
5. `RuntimePipeline` in `pkg/pipeline/pipelinemgr.py` runs configured pipeline stages using a responsibility-chain style executor that supports generator stages.
6. The chat stage emits plugin events, calls a configured `RequestRunner`, handles streaming/non-streaming responses, records telemetry, and appends conversation history.
7. Output stages send text, cards, chunks, files, or error notices back through the original platform adapter.

Pipeline components are registered by decorators and package import side effects. When adding a new stage, loader, runner, or adapter, check the corresponding preregistration mechanism instead of inventing a second registry.

## Platform Layer

Platform code lives under `pkg/platform/`.

- `botmgr.py` owns runtime bots, routing rules, event logging, webhook pushing, and adapter lifecycle.
- `sources/` contains adapter implementations. Each adapter subclasses `langbot_plugin.api.definition.abstract.platform.adapter.AbstractMessagePlatformAdapter` from the SDK.
- Platform entities such as `MessageChain`, `Image`, `At`, `Voice`, and events come from `langbot-plugin-sdk`, not from this repo.

The platform layer should translate between external platform APIs and LangBot's shared message/event model. It should not contain LLM-provider logic or pipeline business logic.

## Pipeline Layer

Pipeline code lives under `pkg/pipeline/`.

Important pieces:

- `pool.py::QueryPool` stores pending queries and cached in-flight queries for plugin backward-compatible calls.
- `controller.py::Controller` schedules query processing and enforces concurrency.
- `pipelinemgr.py::RuntimePipeline` materializes database pipeline config into a runtime stage chain.
- `process/handlers/chat.py::ChatMessageHandler` is the main LLM conversation handler.
- Stage families include response rules, banned sessions, content filters, preprocessors, rate limits, message truncation, long text handling, response-back, command handling, and wrappers.

Pipelines are configuration-driven. Prefer adding a stage or extending an existing stage family over hard-coding behavior in platform adapters.

## Provider, RAG, and Tools

Provider code lives under `pkg/provider/`.

- `modelmgr/` manages configured model providers and requesters.
- `runners/` implements request runners such as the local agent runner and external workflow integrations.
- `tools/toolmgr.py` aggregates tools from native tools, plugin tools, external MCP servers, and skill-authoring tools.
- `tools/loaders/mcp.py` is the MCP client side: external MCP servers that LangBot connects to for agent tools.
- RAG lives across `pkg/rag/`, `pkg/vector/`, model services, and plugin KnowledgeEngine actions.

Do not confuse LangBot's MCP client side with LangBot's own MCP server at `/mcp`; they are different surfaces.

## Plugin System

The plugin system crosses the repo boundary.

In this repo:

- `pkg/plugin/connector.py` connects LangBot to the Plugin Runtime over stdio or WebSocket.
- `pkg/plugin/handler.py` exposes LangBot actions to the runtime and calls runtime actions for plugin operations.
- `pkg/provider/tools/loaders/plugin.py` exposes plugin Tool components to LLM runners.
- Pipeline handlers emit SDK events such as normal-message events and prompt-processing events.

In `langbot-plugin-sdk`:

- `src/langbot_plugin/api/` defines `BasePlugin`, component base classes, message/event entities, contexts, proxies, and manifests.
- `src/langbot_plugin/runtime/` implements `lbp rt`, plugin discovery, dependency installation, process launching, and control/debug connections.
- `src/langbot_plugin/entities/io/` defines the action protocol shared by LangBot, runtime, and plugin processes.

The Plugin Runtime supports stdio and WebSocket control transports. Direct local LangBot runs usually spawn the runtime over stdio. Containerized/standalone deployments connect over WebSocket using `plugin.runtime_ws_url` and `--standalone-runtime`.

## Box Runtime and Skills

Box is the sandbox subsystem used by native agent tools, stdio MCP servers, skill authoring, and managed processes.

In this repo:

- `pkg/box/service.py` is the application-facing facade for exec, sessions, managed processes, skill CRUD, status, reconnects, quotas, mounts, and sandbox profiles.
- `pkg/box/connector.py` connects to the Box Runtime over stdio, Windows subprocess+WebSocket, or remote WebSocket.
- `pkg/provider/tools/loaders/native.py`, `mcp_stdio.py`, and skill loaders depend on Box availability.
- `pkg/skill/manager.py` loads skills from the Box runtime, falling back to local `data/skills` when needed.

In `langbot-plugin-sdk`:

- `src/langbot_plugin/box/server.py` implements `lbp box` and the WebSocket endpoints on `:5410`.
- `src/langbot_plugin/box/runtime.py` owns sandbox sessions and managed processes.
- `backend.py`, `nsjail_backend.py`, and `e2b_backend.py` implement sandbox backends.
- `skill_store.py` manages skill packages from the Box side.

Important config keys live under `box:` in `src/langbot/templates/config.yaml`: `box.enabled`, `box.backend`, `box.runtime.endpoint`, and `box.local.*`. Start LangBot with `--standalone-box` when connecting to an externally launched Box runtime.

## HTTP API, Web UI, and MCP Server

`pkg/api/http/controller/main.py` builds a Quart app, registers route groups, serves the built SPA, and wraps the ASGI app with the MCP dispatcher.

- HTTP route groups live under `pkg/api/http/controller/groups/`.
- Service-layer logic lives under `pkg/api/http/service/`.
- The built web UI is served from the frontend build path with SPA fallback.
- The MCP server lives under `pkg/api/mcp/` and is mounted at `/mcp`.

The MCP server intentionally exposes a curated subset of the API. Tools call service classes directly rather than making HTTP requests back into LangBot.

Maintenance rule: when adding, removing, or changing an HTTP endpoint that should be agent-accessible, update the matching MCP tool and the relevant in-repo skill under `skills/` in the same pass.

## Persistence and Configuration

Persistence is centered on `pkg/persistence/mgr.py`.

- SQLite is the default database; PostgreSQL is supported.
- Models live under `pkg/entity/persistence/`.
- Fresh schemas are created from metadata, then legacy migrations run up to the frozen 3.x baseline, then Alembic migrations run to head.
- New schema changes should use Alembic under `pkg/persistence/alembic/versions/`; do not extend the frozen legacy migration chain.

Configuration starts from `src/langbot/templates/config.yaml` and is generated into `data/config.yaml` on first run. Most long-lived managers read from `ap.instance_config.data`.

## Frontend

The frontend lives in `web/` and is a Vite SPA using React Router 7, shadcn/ui, Tailwind CSS, and pnpm. It is not Next.js, despite some historical filenames.

In development, `pnpm dev` serves the UI on `:3000` and reads `VITE_API_BASE_URL` to call the backend on `:5300`. In production, the built frontend is packaged into the Python distribution and served by the backend.

Keep frontend API behavior aligned with `pkg/api/http/service/` and route groups. User-facing strings must go through the existing i18n setup.

## Agent-Facing Surfaces

LangBot is deliberately agent-friendly. The agent-facing surfaces are part of the architecture, not extra docs.

- `skills/` is the single source of truth for in-repo skills.
- `pkg/api/mcp/server.py` exposes the LangBot MCP server at `/mcp`.
- `api.global_api_key` authenticates API/MCP access without a browser login.
- `AGENTS.md` and `ARCHITECTURE.md` tell coding agents how the repo works.

When one of these changes, update the others if the behavior or contract changed. API, MCP tools, and skills are one system; drift is a bug.

## Where to Change Things

- New HTTP API: add/adjust a service in `pkg/api/http/service/`, a route group in `pkg/api/http/controller/groups/`, tests, and MCP/skills if agent-accessible.
- New platform adapter: add a `pkg/platform/sources/*` adapter, component metadata/templates as needed, i18n, docs, and tests/smoke coverage.
- New pipeline behavior: add or extend a pipeline stage family under `pkg/pipeline/`; avoid putting pipeline rules in adapters.
- New LLM provider/requester: work under `pkg/provider/modelmgr/` and related service/UI surfaces.
- New LLM tool source: extend `pkg/provider/tools/loaders/` and `ToolManager` intentionally.
- New plugin component/API/protocol: change `langbot-plugin-sdk` first or in lockstep, then update LangBot bridge code.
- New Box capability: change both `pkg/box/` and `langbot-plugin-sdk/src/langbot_plugin/box/`, plus config and tests.
- New database schema: add an Alembic migration, not a legacy `dbmXXX` migration.

## Design Biases

- Keep platform translation, pipeline orchestration, provider execution, and runtime protocols separate.
- Reuse existing registries and service layers instead of adding parallel paths.
- Prefer small, explicit agent surfaces over exposing every internal API.
- Treat cross-repo contracts with the SDK as public interfaces.
- Test behavior at the narrowest useful layer first, then add integration/e2e coverage for runtime or platform changes.
