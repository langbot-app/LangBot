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
- `LangBot/plugins/` contains the official plugin catalog (`Runner/`, `KnowledgeEngine/`, `misc/`). Sources share this checkout; each plugin retains independent tests, dependencies, versioning, packaging and Marketplace publication. Core wheels, sdists, Docker contexts, release ZIPs and fnOS packages exclude this tree. See `plugins/RELEASING.md` and `plugins/MIGRATION.md`.
- `langbot-plugin-sdk/` is published as `langbot-plugin` and pinned in `LangBot/pyproject.toml`. It contains plugin developer APIs, shared entities, `lbp`, the Plugin Runtime (`lbp rt`), and the Box Runtime (`lbp box`).
- [`langbot-cli`](https://github.com/langbot-app/langbot-cli) is a separately released `lbctl` client for managing a running Workspace through the HTTP Service API; it is not part of the LangBot server or the SDK's `lbp` CLI.
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
│   │   ├── provider/               # Model providers and Host-owned tools
│   │   ├── agent/                  # Agent/Runner orchestration and run state
│   │   ├── plugin/                 # LangBot-side Plugin Runtime connector/handler
│   │   ├── box/                    # LangBot-side Box service/connector
│   │   ├── skill/                  # Skill metadata/activation integration
│   │   ├── rag/ , vector/          # Knowledge-base and vector DB integration
│   │   ├── persistence/            # SQLAlchemy/SQLModel and Alembic migrations
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
  → Runner orchestrator / ToolManager / PluginRuntimeConnector / BoxService
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
6. The chat stage emits plugin events and projects the current query into the Runner Host orchestrator. The selected plugin Runner returns streaming or final results while the Host owns authorization, tools, telemetry, and conversation history.
7. Output stages send text, cards, chunks, files, or error notices back through the original platform adapter.

Pipeline components are registered by decorators and package import side effects. When adding a new stage, loader, runner, or adapter, check the corresponding preregistration mechanism instead of inventing a second registry.

## Platform Layer

Platform code lives under `pkg/platform/`.

- `botmgr.py` owns runtime bots, routing rules, event logging, webhook pushing, and adapter lifecycle.
- Bots store exclusive Agent/Pipeline routes in `event_bindings` and independent plugin subscriptions in `plugin_processors` (`processor_uuid`, `enabled`). Subscriptions resolve event patterns from the installed Runner and fan out alongside the primary route. Configuration, state, debug and run logs belong to the reusable processor instance.
- `sources/` contains adapter implementations. Each adapter subclasses `langbot_plugin.api.definition.abstract.platform.adapter.AbstractMessagePlatformAdapter` from the SDK.
- Platform entities such as `MessageChain`, `Image`, `At`, `Voice`, and events come from `langbot-plugin-sdk`, not from this repo.
- `pkg/platform/image_urls.py` renews image references in authorized monitoring/history responses and before Host model attempts without downloading. The shared resource URL catalog persists renewed URLs behind stable references. OneBot connection-local state in `adapters/aiocqhttp/image_urls.py` identifies the implementation lazily and reuses NapCat credentials until their returned TTL expires. Other implementations use standard `get_msg` when the URL's creation or last successful check is at least 30 minutes old. URLs can be shared across Workspaces; bot ownership checks, credentials and original message identities remain scoped to their connection.

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

## Agents, Providers, RAG, and Tools

Agent orchestration lives under `pkg/agent/`; model providers and tools live under `pkg/provider/`.

- `modelmgr/` manages configured model providers and requesters.
- `pkg/agent/runner/` discovers plugin Runner components, resolves bindings, constructs run-scoped context/resources, and records execution state.
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
- [Certified plugin policy](dev-docs/architecture/certified-plugins.md) defines Core's archive-fact, admission, and tenant-log-visibility boundary; the SDK remains responsible for certificate verification.

In `langbot-plugin-sdk`:

- `src/langbot_plugin/api/` defines `BasePlugin`, component base classes, message/event entities, contexts, proxies, and manifests.
- `src/langbot_plugin/runtime/` implements `lbp rt`, plugin discovery, dependency installation, process launching, and control/debug connections.
- `src/langbot_plugin/entities/io/` defines the action protocol shared by LangBot, runtime, and plugin processes.

The Plugin Runtime supports stdio and WebSocket control transports. Direct local LangBot runs usually spawn the runtime over stdio. Containerized/standalone deployments connect over WebSocket using `plugin.runtime_ws_url` and `--standalone-runtime`.

## Box Runtime and Skills

Runner plugins own sandbox policy: enablement, reuse-key interpolation, acquisition,
binding, and explicit file import/export. The Host exposes authenticated resource
APIs (`get_box_status`, `list_boxes`, `acquire_box`) and run-bound operations
(`bind_box`, `import_box_attachments`, `export_box_files`, `reply_files`). Box Runtime
owns atomic capacity enforcement and container reuse/lifecycle. Reusing an existing
Box is allowed when no additional capacity remains.

A run binds one Box before native sandbox tools or file transfer. The Host does not
choose a conversation scope or stage attachments before starting the Runner. Input
references retain the original attachment metadata; import yields paths specific to
the run. Output export requires explicit normalized absolute sandbox file paths and returns
opaque handles scoped to that run. The selected files are validated as one batch
before registration; successful export removes only those files, and cleanup
failure is a warning with accepted handles retained. Writing an outbox file alone
does not deliver it. Core and Plugin Runtime must provide the selected-path API;
LocalAgent CI verifies this contract against the latest stable published SDK.
`message.completed.file_ids` attaches explicitly exported files to Pipeline output;
Agents send them explicitly with `ctx.reply_files()`, subject to event reply permission.
The Pipeline wrapper never scans a Box. Binding ends with the run; the reusable Box
remains subject to Runtime idle expiry. Persistent workspace files survive expiry,
but processes and container-local state do not.

Box is the optional sandbox subsystem used by native execution tools, stdio MCP servers, agent-side skill authoring, and managed processes. Skill storage and read-only access are Core responsibilities and remain available without Box.

In this repo:

- `pkg/box/service.py` is the application-facing facade for exec, sessions, managed processes, status, reconnects, quotas, generic mounts, and sandbox profiles.
- [Outbox export failures](dev-docs/BOX_OUTBOX_EXPORT.md) documents bounded reads, permission fallback, and cleanup after Runner acceptance.
- `pkg/box/connector.py` connects to the Box Runtime over stdio, Windows subprocess+WebSocket, or remote WebSocket.
- `pkg/provider/tools/loaders/native.py` is the Core orchestration seam: the
  Skill loader supplies generic read-only mounts to Box execution. `mcp_stdio.py`
  and execution-backed tools depend on Box availability.
- `pkg/skill/repository.py` is the thin async/Workspace adapter over the Plugin SDK's execution-independent `SkillStore`; `skills.root` owns its location independently of Box. Core's registry points to immutable content-addressed publications, and every update carries `base_revision` so concurrent writers fail instead of overwriting each other.
- `pkg/skill/manager.py` caches the Core repository catalog for progressive disclosure. Activation and read-only resource tools do not require Box; script execution and Workspace mutation still do.

Durable Box Workspace storage is shared across placement generations, but
sandbox sessions and managed processes are generation-scoped. LangBot validates
the current execution binding before an MCP stdio relay attach and sends the
Workspace/generation binding in authenticated headers, so a placement cutover
retires stale processes and closes already-attached relays.

In `langbot-plugin-sdk`:

- `src/langbot_plugin/box/server.py` implements `lbp box` and the WebSocket endpoints on `:5410`.
- `src/langbot_plugin/box/runtime.py` owns sandbox sessions, generic read-only mounts, and managed processes.
- `backend.py`, `nsjail_backend.py`, and `e2b_backend.py` implement sandbox backends.
- `src/langbot_plugin/skill_store.py` is consumed by Core, not Box. Activation
  pins the first revision for a run in Host-owned run ledger metadata; instructions,
  resource reads, execution mounts, and revision-scoped dependency state use that
  exact publication. A new run refreshes the Workspace catalog and resolves the
  current revision, ignoring old conversation activation state. Lost in-memory
  pins in an active authorized run are reloaded from its ledger. After a Core
  process restart, expired run sessions cannot call tools: the Host rejects them
  rather than silently resolving a new version. This does not add automatic run resumption. Core mounts only activated and authorized Skills. Published
  trees are never agent write targets: authoring happens in Workspace drafts and
  an explicit registration/update atomically publishes the next revision. Core
  turns those package roots and content digests into generic read-only mounts;
  Box does not understand Skill names, metadata, revisions, files, or CRUD.

Skill execution paths include the publication digest (`/opt/langbot-artifacts/<digest>`).
Docker/Podman mount a read-only cache when creating the Box and atomically add
verified packages before execution; E2B seals and verifies a private staging copy
before publishing a stable projection. nsjail applies the requested mounts in a
separate namespace for each execution. Activating a Skill after acquiring a Box
therefore does not recreate the session or stop its managed processes. Ordinary
host mount changes still fail explicitly on fixed-mount backends.

A shared Box remains a Workspace filesystem sharing boundary: its commands can
see previously materialized packages. Run pins prevent revision switching; they
are not access isolation between mutually untrusted programs in the same Box.
Use package-relative script paths or the path returned by activation. Core tools
translate legacy `/workspace/.skills/<name>` command paths to the run's digest
path, but do not rewrite paths embedded inside scripts. Published packages remain
read-only; use writable drafts and the existing per-run outbox for output.

Skill storage uses `skills.root`. Box execution config lives under `box:`:
`box.enabled`, `box.backend`, `box.runtime.endpoint`, and `box.local.*`. The old
`box.local.skills_root` key is read only as an online-upgrade fallback and is
marked for removal in the next major version. Start LangBot with
`--standalone-box` when connecting to an externally launched Box runtime.

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
- Every SQLite connection sets a 64 MiB `journal_size_limit`, including connections recreated after migration or pool disposal. SQLite's default automatic checkpoint policy and synchronous setting remain unchanged. The limit reduces retained WAL space when the WAL resets; it does not cap active transactions or WAL pinned by readers. Online maintenance does not periodically force checkpoints or truncate WAL files. Diagnose persistent excess growth by checking checkpoint progress and actual transaction lifetimes, then shorten the responsible transaction rather than forcing readers to finish.
- After schema initialization and migration, every SQLite startup completes `wal_checkpoint(TRUNCATE)` before runtime setup and producers start. Lock waits allow up to 60 seconds; checkpoint I/O may take longer. An incomplete checkpoint fails startup without undoing successful migrations, and the next startup retries even at schema head. The connection busy timeout is restored afterward. PostgreSQL is unaffected.
- SQLite files use incremental auto-vacuum. Migration `0042_sqlite_incremental_vacuum` converts existing files before producers start, with a verified backup and restoration on conversion failure when a full rebuild is required. Fresh files enable the format before creating tables. Monitoring cleanup reclaims free pages in independent adaptive batches (1–512 pages, starting at 8, targeting 25 ms), pausing 250 ms between batches and starting no new batches after a two-second round budget. Busy writers take priority. No full `VACUUM` or forced WAL checkpoint runs during online cleanup.
- Models live under `pkg/entity/persistence/`.
- `pkg/persistence/media.py::MediaReferenceText` validates bound conversation payloads on ORM/Core writes while preserving the existing TEXT schema and string API. It rejects recognized structured inline images: retained images go through `MediaCache.externalize_chain_dump()` before serialization, while metadata-only snapshots and transcripts use `redact_inline_images()`. Reads and comparisons preserve historical values for incremental cleanup. Runtime/adapter messages, arbitrary diagnostic text, and opaque strings are outside this contract.
- `pkg/persistence/resource_urls.py` interns structured resource URL fields in retained messages, history and monitoring at the typed SQL boundary, in the source transaction. `MediaReferenceJSON` preserves native JSON monitoring details. Payloads store opaque references to the global `resource_urls` catalog; typed SQL reads and comparisons expand them to current URLs, preserving API shapes and source-record authorization. Configuration URLs and URLs in free text are excluded. Catalog lookups use only the primary-key and URL-hash unique indexes. Successful refreshes overwrite the current URL and persist the check time even when standard `get_msg` returns the same URL. Converging URLs retain only ID redirects, with no old URL. PostgreSQL row locks and SQLite's immediate write transaction serialize concurrent refreshes; SQLite holds its write lock during the upstream call. Bounded in-memory aliases let reused Runner payloads resolve old URLs without retaining those URLs in the database. Migration `0041_resource_urls` normalizes existing payloads using their source creation timestamps before producers start; downgrade expands references before dropping the catalog.
- Timezone-less SQL `DateTime` columns store UTC-naive values on both backends. Normalize aware values with `pkg/persistence/datetime_utils.py::as_naive_utc` at the bind boundary, including deadlines, leases, event times, and query/retention cutoffs; do not merely strip an offset. Existing naive rows represent UTC. Restore UTC awareness for application comparisons and epoch serialization. Runner ledger/event/transcript stores follow this existing schema contract without a data migration or changes to journal/tenant authorization.
- Fresh schemas are created from current metadata, then Alembic migrations run to head. LangBot 4.x does not upgrade 3.x databases.
- New schema changes use Alembic under `pkg/persistence/alembic/versions/`; there is no legacy migration chain in 4.x.

Configuration starts from `src/langbot/templates/config.yaml` and is generated into `data/config.yaml` on first run. Most long-lived managers read from `ap.instance_config.data`.

Storage maintenance applies `storage.media_cache.retention_days` to both CAS files and historical inline images. Inline image expiry uses the owning record's creation time and preserves text, URLs, and record identity. It does not backfill CAS. `pkg/storage/inline_media_cleanup.py` processes one payload row at a time, with a per-table limit of 100 indexed candidates or 8 MiB of JSON characters per maintenance pass (one oversized row may exceed the latter limit). Run events lack a Workspace column, so their candidate cursor also advances past foreign or missing records; payloads are loaded only after checking Workspace ownership. Durable Workspace metadata cursors and timestamp/identity indexes keep completed history out of subsequent scans; newly written history must retain its actual creation timestamp. Updates and cursor advancement commit together. Invalid historical JSON is preserved. SQLite pages become reusable after payload removal; the database file is not automatically vacuumed by this task.

### Conversation summary boundary

`MonitoringService` delegates all interactive session lists to `SessionSummaryReader` in `pkg/persistence/`. The reader selects public columns from `monitoring_sessions` without history joins or repairs, keeping list cost independent of historical payload size. Sessions describe conversations, not executions; API filter semantics are documented in [LangBot MCP Operations](skills/skills/langbot-mcp-ops/SKILL.md#unified-execution-monitoring).

`SessionSummaryWriter` updates summaries in the source write's Workspace transaction. Each distinct message record counts once, including assistant and failure records. A platform `message.received` event contributes only while no non-assistant message matches its event ID or legacy message ID. Replays add no credit; late links retire ingress credit once, including across group/topic sessions. Observed start/activity timestamps never shrink the session's time range. Live writes and offline initialization share the same source mapping.

All display fields come from one source snapshot, including empty values. Missing names display the user ID instead of inheriting another record's name. Non-assistant sources outrank assistant sources, followed by timestamp and binary source-key order. Processor filters match the selected snapshot. Immutable message winners fold into `base_snapshot`; uncovered ingress retains a replaceable `candidate_snapshot` on its receipt. Covering or transferring ingress restores the remaining winner atomically, without reading history.

Receipts and event anchors are Workspace-scoped and expire in bounded batches under history retention. Expiry preserves counters and seals any uncovered ingress snapshot into the base in the same transaction. Summaries are deleted only after their receipts are gone. Deduplication and late linking are guaranteed within this retention window.

Migration `0040_session_summaries` marks historical Workspaces as pending. OSS startup automatically completes `SessionSummaryBackfill` before starting HTTP or message producers, then continues in the same process; no manual backfill or additional container restart is needed. Batches and progress commit together, so an interrupted startup resumes from its cursor. Initialization is bounded, never selects message bodies or variables, and preserves historical counts as a lower bound when source history has expired. Invalid or oversized required metadata stops startup for diagnosis. Fresh databases and completed initialization skip history scanning; pending source writes remain blocked. There is no request-time or background repair.

Cloud runtimes retain the initialization gate because other instances may write concurrently. For Cloud deployment or manual maintenance, stop **all** writers, back up the database, apply the migration, and run the command below for each pending Workspace before starting services. Set the named environment variable to a `sqlite+aiosqlite` or `postgresql+asyncpg` database URL; SQLite must point to an existing file. The connection must have access to the migrated schema and Workspace.

```bash
uv run python -m langbot.pkg.persistence.session_summary_backfill \
  --workspace WORKSPACE_UUID --writers-stopped \
  --database-url-env LANGBOT_SUMMARY_DATABASE_URL
```

## Frontend

The frontend lives in `web/` and is a Vite SPA using React Router 7, shadcn/ui, Tailwind CSS, and pnpm. It is not Next.js, despite some historical filenames.

In development, `pnpm dev` serves the UI on `:3000` and reads `VITE_API_BASE_URL` to call the backend on `:5300`. In production, the built frontend is packaged into the Python distribution and served by the backend.

Keep frontend API behavior aligned with `pkg/api/http/service/` and route groups. User-facing strings must go through the existing i18n setup.

## Agent-Facing Surfaces

LangBot is deliberately agent-friendly. The agent-facing surfaces are part of the architecture, not extra docs.

- `skills/` is the single source of truth for in-repo skills.
- `pkg/api/mcp/server.py` exposes the LangBot MCP server at `/mcp`.
- `lbctl` calls the authenticated HTTP Service API from a terminal; its source and releases live in `langbot-cli`.
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
- New database schema: add an Alembic migration.

## Design Biases

- Keep platform translation, pipeline orchestration, provider execution, and runtime protocols separate.
- Reuse existing registries and service layers instead of adding parallel paths.
- Prefer small, explicit agent surfaces over exposing every internal API.
- Treat cross-repo contracts with the SDK as public interfaces.
- Test behavior at the narrowest useful layer first, then add integration/e2e coverage for runtime or platform changes.

## Documentation repositories

The public documentation site lives in `docs/` and is built with Node.js 24 and Fumapress. Internal design and review notes live in `dev-docs/`. The landing site keeps its `docs` submodule path but tracks LangBot `master`, building from the nested `docs/` directory. The old `langbot-app/langbot-docs` repository can be archived; publication never writes to it. See `dev-docs/DOCS_MIGRATION.md` for publication and cutover details.
