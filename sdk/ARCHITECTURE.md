# Architecture

This document maps the plugin SDK in `sdk/` of the LangBot monorepo (formerly the `langbot-plugin-sdk` repository). It explains the durable structure and cross-process contracts. For working rules, commands, and pitfalls, see `AGENTS.md`.

## What This Package Is

The plugin SDK is the infrastructure package behind LangBot's plugin and sandbox systems. It is published to PyPI as `langbot-plugin` (tags `sdk/vX.Y.Z`) and pinned exactly by LangBot Core.

The package has four roles:

- **Plugin SDK**: public APIs and entities imported by plugin authors.
- **CLI**: `lbp`, used to scaffold, run, debug, build, publish, and launch runtimes.
- **Plugin Runtime**: `lbp rt`, the host process that manages plugin packages and plugin processes.
- **Box Runtime**: `lbp box`, the sandbox runtime used by LangBot's Box subsystem.

The runtime code under `src/langbot_plugin/runtime/` is AGPL; the rest of the package is Apache 2.0.

## Repository Boundary

The SDK shares the LangBot repository but is versioned and released separately.

- LangBot Core (`../src/langbot/`) owns product behavior, HTTP API, web UI, platform adapters, pipeline execution, model/tool orchestration, persistence, skills integration, and the LangBot-side runtime connectors.
- The SDK (`sdk/`) owns plugin author APIs, shared message/event/context entities, the action RPC protocol, the execution-independent filesystem Skill store, `lbp`, Plugin Runtime implementation, and Box Runtime implementation.
- Plugins import this package directly; LangBot also imports it for shared entities and runtime protocols.

If a change alters shared entities, component contracts, action names/payloads, runtime behavior, or Box models, change and test SDK and Core together in one PR, and release the SDK before the Core release that depends on it.

## Top-Level Layout

```text
sdk/
├── src/langbot_plugin/
│   ├── api/                  # Public plugin-author SDK
│   │   ├── definition/       # BasePlugin, components, manifests
│   │   ├── entities/         # Contexts, events, builtin platform/provider models
│   │   └── proxies/          # APIs exposed to plugin code
│   ├── cli/                  # `lbp` entrypoint and subcommands
│   ├── runtime/              # Plugin Runtime (`lbp rt`)
│   ├── box/                  # Box Runtime (`lbp box`)
│   ├── skill_store.py        # Execution-independent Skill package storage
│   ├── workspace.py          # Neutral Workspace namespace identity
│   ├── entities/io/          # Action RPC request/response/error/action models
│   ├── assets/               # Scaffolding templates and page SDK asset
│   └── utils/
├── docs/                     # Supplemental protocol/component docs
├── tests/                    # Unit and black-box tests
├── pyproject.toml
└── README.md
```

## Public Plugin SDK

Plugin-facing APIs live under `src/langbot_plugin/api/`.

- `definition/plugin.py` defines `BasePlugin`.
- `definition/components/` defines component base classes.
- `definition/components/manifest.py` defines component manifest models. Plugin
  manifests may set `execution.sharedRuntime: shared-runtime-v1` together with
  `execution.componentModel: stateless-v1`; omission keeps the legacy dedicated
  object model.
- `certification.py` defines optional ZIP-comment certification envelopes. It
  canonicalizes envelope JSON, normalizes the ZIP digest by removing the comment,
  and verifies the signed manifest identity and runtime profile without changing
  unsigned archive output. New certificates exist only for Cloud cross-tenant
  sharing of one Worker and one plugin/component singleton, not dedicated mode;
  older v1 claims without signed stateless component model cannot authorize sharing.
- `entities/` defines event/context/message/provider data models passed across LangBot, runtime, and plugin code.
- `proxies/` defines methods plugins can call back into LangBot, such as messaging, storage, model invocation, tools, RAG, parser, and query-scoped APIs.

Plugins extend LangBot through seven component types:

- `Command`
- `Tool`
- `EventListener`
- `KnowledgeEngine`
- `Parser`
- `Page`
- `Runner` (Agent execution and event processing)

The CLI scaffolds components via `lbp comp <Type>`. Component templates live under `src/langbot_plugin/assets/templates/`; generation logic lives under `src/langbot_plugin/cli/gen/`.

## CLI Architecture

`lbp` is declared in `pyproject.toml` and enters at `src/langbot_plugin/cli:main`, implemented by `src/langbot_plugin/cli/__init__.py`.

Subcommands:

- `init`: scaffold a plugin project.
- `comp`: generate a plugin component.
- `run`: run/remote-debug a plugin against a Runtime debug server.
- `build`: package a plugin zip.
- `publish`: publish a plugin to the marketplace.
- `login` / `logout`: marketplace authentication.
- `rt`: launch the Plugin Runtime.
- `box`: launch the Box Runtime.
- `ver`: print package version.

Subcommand implementations live under `cli/commands/`, `cli/run/`, and `cli/gen/`. CLI i18n lives under `cli/locales/`.

## Action RPC Protocol

Streaming callers may send `stream_flow_control: 1` in the request envelope.
Supporting senders number data responses with `stream_index` starting at 1 and
allow eight unacknowledged frames per stream. After processing four frames, the
caller sends `__stream_ack` with the original `seq_id` and cumulative `index`,
using the original immutable installation context. The sender validates the
context and index before returning credit. ACK admission has its own bounded
capacity, separate from business actions and cancellation/heartbeat capacity.
Only that stream's producer waits for credit; the connection router never waits
on a consumer queue. Forwarding hops negotiate independently.

Each streamed frame is limited to 1 MiB of serialized UTF-8 and each receiving
buffer to 128 frames / 8 MiB. Oversize or legacy overflow is a terminal error,
never a silently dropped delta. Older senders ignore the optional request field;
without `stream_index`, callers send no ACKs and retain bounded legacy routing.
Older callers omit the field, so new senders retain legacy push behavior.
This compatibility does not provide backpressure on legacy hops; all hops must
be upgraded for end-to-end flow control. Unfinished/failed/closed consumers send
best-effort scoped cancellation, and producers explicitly close their iterators.
The wire timeout bounds idle reads and ACK waits, not arbitrary time spent by
application code processing a yielded value.

The runtime protocol is a bidirectional action RPC protocol over stdio or WebSocket. It is implemented by `runtime/io/handler.py` and data models under `entities/io/`.

Request shape:

```json
{ "seq_id": 1, "action": "action_name", "data": {} }
```

Tenant-scoped control actions must carry a complete, trusted installation
binding without placing authority in the action payload:

```json
{
  "seq_id": 1,
  "action": "action_name",
  "data": {},
  "context": {
    "instance_uuid": "instance-id",
    "workspace_uuid": "workspace-id",
    "placement_generation": 1,
    "installation_uuid": "installation-id",
    "runtime_revision": 1,
    "artifact_digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  }
}
```

`SET_RUNTIME_CONFIG` is the instance-scoped handshake. It carries no Workspace
context and accepts this frozen payload:

```json
{
  "runtime_identity": {
    "instance_uuid": "instance-id",
    "runtime_id": "short-lived-runtime-id"
  },
  "worker_policy": {
    "max_cpus": 1.0,
    "max_memory_mb": 512,
    "max_pids": 128,
    "max_open_files": 256,
    "max_file_size_mb": 512,
    "max_concurrent_restarts": 1,
    "restart_failure_threshold": 8,
    "restart_failure_window_seconds": 30.0,
    "restart_circuit_open_seconds": 60.0,
    "require_hard_limits": true
  },
  "runtime_profile": "shared",
  "cloud_service_url": "https://space.langbot.app"
}
```

The Runtime identity and worker policy can be repeated exactly after a control
reconnect but cannot be changed for the life of the Runtime process. A new
authenticated control handler atomically supersedes the old handler; old
requests fail even if the old transport has not finished closing.

After the handshake, every tenant-scoped LangBot-to-Runtime action (including
file chunks) requires the complete immutable tuple
`(instance_uuid, workspace_uuid, placement_generation, installation_uuid,
runtime_revision, artifact_digest)`. Missing context, a different instance, or
an attempted generation/revision/artifact rebind fails closed. Instance-scoped
actions reject tenant context. Plugin payload fields are never authoritative
for these bindings.

In the `shared` profile, `PluginManager` indexes desired state by the complete
installation binding. Each desired-state entry has an additive
`execution_mode`: omission or `dedicated` preserves the historical one-process
per installation behavior, while `shared-runtime-v1` opts a certified
`shared-runtime-v1` installation into a digest-scoped worker pool. Core is
responsible for selecting `shared-runtime-v1` only after certification succeeds;
the Runtime never infers shared authority from tenant-controlled manifest data.
The instance-scoped `RECONCILE_PLUGIN_INSTALLATIONS`
action replays the authoritative set, while tenant-scoped
`APPLY_PLUGIN_INSTALLATION` and `REMOVE_PLUGIN_INSTALLATION` actions change one
installation. Newer placement generations or Runtime revisions fence the old
worker immediately; stale or cross-Workspace transitions fail closed.

Dedicated enabled installations remain owned by installation-scoped
Supervisors. A certified shared worker is keyed by the raw artifact digest and
currently has pool size one: the first slot attach starts it and the last slot
detach stops it. Installations sharing that process use one `BasePlugin` and one instance of each
component. Lightweight slots retain immutable config snapshots, Host authority,
revision and task ownership. Invocation-local context selects the slot; config
updates replace that snapshot without recreating components. Revision and
generation fencing remove the exact stale slot, cancel its in-flight actions,
and prevent background calls after detach.

Unexpected worker exit is recovered with bounded exponential backoff. Disable,
remove, placement generation changes, Runtime revision changes, and shutdown
fence the old Supervisor before it can relaunch, while reconcile and control
reconnect restore the authoritative desired set.

Restart attempts also pass through one Runtime-wide coordinator. Launches are
globally bounded until a worker completes initialization; repeated unexpected
exits in the configured window open a circuit. After cooldown, exactly one
half-open probe may launch, and it must remain stable before the circuit closes.
A child that does not become ready within 30 seconds is cancelled and reaped.
Aggregate coordinator counters are exposed through Runtime health without
installation or Workspace identity.

Plugin packages are verified against `artifact_digest` and extracted once into
a read-only `artifacts/sha256/<digest>/code` tree. Installations may share that
code tree. Dedicated mode gives each installation a separate process and private
`home`, `tmp`, and `data` directories. Certified shared workers mount no
installation or tenant-writable directory; their writable scratch belongs to
the digest process and tenant state must go through Host actions. A dedicated
worker capability is bound to one complete installation tuple. A shared worker
capability is additionally bound to its digest; after registration, every slot
RPC carries an exact current `InstallationBinding` and cannot select or rebind
tenant scope.

Before any desired-state artifact worker is launched, the Runtime prepares an
immutable dependency tree. The resulting `site-packages` tree is keyed by the
verified artifact, requirements bytes, Python ABI, Runtime version, installer
schema, and Runtime profile, then atomically published under
`environments/sha256/<environment-digest>`. Concurrent installations reuse the
same ready tree. Failed or partial preparations are removed and reported as the
stable `dependency_prepare_failed` desired-state failure. Pip control options in
an artifact's `requirements.txt` are rejected because only Runtime configuration
may select indexes or trusted hosts.

The dependency admission path has one bounded historical ABI exception: nine
explicit `langbot-team` archive identities with exact raw SHA-256 digests and
`langbot-plugin==0.6.1` may use the Runtime-owned SDK **0.7.6** in `dedicated`
mode only. Artifact bytes are verified before extraction; a changed archive,
identity, requirement, Runtime version, or shared execution mode fails normal
SDK pin validation. This does not issue a certificate or change Core placement
eligibility, and it does not install an older SDK into a worker. Cache schema is
bumped so pre-exception dependency environments are never silently reused.

Workers in the shared Runtime profile launch through nsjail with policy-owned
cgroup CPU, memory, and
PID limits plus file/process rlimits. If `require_hard_limits` is true, missing
nsjail or cgroup v2 delegation makes configuration fail closed. The Runtime
nests every worker cgroup under its own cgroup (`langbot-runtime/` for its own
processes, `langbot-plugin-workers/NSJAIL.*` for sandboxes, passed to nsjail as
`--cgroupv2_mount`) so the container memory limit and accounting cover all
sandboxes; the workers subtree is capped at the Runtime cgroup's `memory.max`
minus `LANGBOT_PLUGIN_RUNTIME_MEMORY_RESERVE_MB` (default 2048). Run the
Runtime container privileged in its private cgroup namespace and never
bind-mount the host `/sys/fs/cgroup`: delegation refuses the host root cgroup
because sandboxes there escape every container limit. Their dependency
tree is prepared in a separate nsjail and mounted read-only into the worker.
Artifact `.env` files are not loaded in the shared profile. The default
`oss_dev` profile prepares the same kind of persistent tree with direct pip and
adds it to the direct worker's import path, while keeping artifact `.env`
behavior for local open-source development. POSIX workers use stdio RPC. On
Windows, where asyncio cannot support the required subprocess and pipe behavior
together, the Runtime owns the worker process while the worker connects back to
the loopback WebSocket server with its one-use registration capability.
The Runtime waits for this immutable profile handshake before inspecting legacy
plugin state. A shared Runtime never scans, installs dependencies for, or
launches the global `data/plugins` tree; only apply/reconcile desired state may
start an installation worker.

Response shape:

```json
{ "seq_id": 1, "code": 0, "message": "success", "data": {}, "chunk_status": "continue" }
```

Core mechanics:

- `seq_id` correlates responses to requests.
- `context` carries trusted tenant/installation authority independently of
  plugin-controlled `data`; it is mandatory on tenant control actions.
- Messages with `action` are requests; messages with `code` are responses.
- Each peer may initiate requests on the same connection.
- `Handler.call_action()` waits for one response.
- `Handler.call_action_generator()` consumes streamed responses.
- Streaming emits `chunk_status: "continue"` chunks and ends with `"end"`.
- File transfer uses `CommonAction.FILE_CHUNK` with 16KB base64 chunks stored
  under `data/temp/lbp/`. New transfer keys are high-entropy opaque capabilities;
  the receiver durably binds each capability to its exact authority namespace so
  a later read can recover that namespace after the action or handler ends. An
  explicit current context must still match, and the receiver never scans other
  namespaces. Legacy opaque basenames remain supported. Absolute paths,
  separators, `..`, and unsafe extensions are rejected.
- The transfer root is created and bound to one exact directory inode by walking
  every component from `/` without following links, so a swapped component cannot
  redirect a transfer. Deployments that deny inspecting the ancestors while still
  reaching the root itself (fnOS applications inside `/vol2/@appshare/...`,
  sandboxed containers) keep working: ancestors are opened path-only when a
  read-only open is refused, and a root whose ancestors are entirely denied is
  bound `O_NOFOLLOW` at the deepest reachable directory. Every component below
  that point, the root descriptor, and all later operations keep the same
  no-link, relative-only guarantees; the per-transfer drift check re-identifies
  the configured path the same way.

Action enums are the protocol contract:

- `CommonAction`
- `PluginToRuntimeAction`
- `RuntimeToPluginAction`
- `LangBotToRuntimeAction`
- `RuntimeToLangBotAction`
- `LangBotToBoxAction`

Do not duplicate action strings outside these enums.

## Plugin Runtime

`lbp rt` enters `runtime/app.py::main()` and builds `RuntimeApplication`.

Runtime graph:

```text
LangBot PluginRuntimeConnector
  ↔ control connection
  ↔ RuntimeApplication
  → PluginManager
  → PluginContainer(s)
  ↔ PluginConnectionHandler(s)
  ↔ plugin process(es)
```

Important modules:

- `runtime/app.py`: selects stdio vs WebSocket control transport, starts control/debug servers, launches plugin manager tasks.
- `runtime/context.py`: shared runtime context object.
- `runtime/settings.py`: runtime settings, including marketplace/cloud URL.
- `runtime/plugin/mgr.py`: plugin discovery, installation, dependency checks, launch, shutdown, event/tool/command/RAG/page dispatch.
- `runtime/plugin/container.py`: loaded plugin package, manifest, component containers, status.
- `runtime/io/handlers/control.py`: actions LangBot calls on the Runtime.
- `runtime/io/handlers/plugin.py`: actions the Runtime calls on plugin processes.
- `runtime/io/controllers/`: stdio/WebSocket server and client controllers.
- `runtime/io/connections/`: transport-specific connection implementations.

The Runtime has two external channels:

- **control channel**: LangBot ↔ Runtime, stdio or `:5400/control/ws` by default.
- **debug channel**: plugin dev process ↔ Runtime, WebSocket `:5401/plugin/debug/ws` by default.

Installed plugin processes do not authenticate with the shared debug key. For
each child launch, the Runtime reads the installed `manifest.yaml`, issues a
short-lived one-use registration capability bound to that author/name, and
passes only that capability to the child. The capability is consumed before
Host settings are requested, cannot be replayed, and the plugin must preserve
the same manifest identity after initialization. On Windows the child receives
an explicit environment allowlist, so Runtime and Box control secrets are not
inherited.

WebSocket control may use the high-entropy
`LANGBOT_PLUGIN_RUNTIME_CONTROL_TOKEN` in the
`X-LangBot-Plugin-Runtime-Token` handshake header. OSS defaults to no control
token when both LangBot and Runtime leave it unset; if either side configures
one, both sides must use the same value. The debug server instead accepts only
Workspace-scoped random credentials issued through the authenticated control
channel. Each Workspace gets a different token, valid for two hours, and
`lbp run` sends it in the `X-LangBot-Plugin-Debug-Key` handshake header
sessions. Windows production children use their one-use registration
capability in `X-LangBot-Plugin-Registration-Capability` instead. The
instance-scoped `SET_RUNTIME_CONFIG` handshake and per-action installation
bindings are authorization fences after transport authentication; neither is a
substitute for authenticating the peer.

An OSS-only exception permits legacy knowledge `FILE_CHUNK` replies carrying
`ActionContext`: the active, configured control connection must target the local
instance and already-bound Workspace/generation, and its installation capability
must exactly match a live registered plugin connection. Payload scope is ignored.
Shared transfers still require a complete binding; candidate artifact pretransfer
validates that binding without activating desired state. Transfer ownership and
tenant-visible plugin containers/log routing remain installation scoped even
when several slots use one process.

Legacy OSS plugins are stored under `data/plugins/{author}__{name}`. Runtime
plugin processes normally run as separate Python processes and connect back via
stdio or debug WebSocket. Shared workers instead use the digest-addressed
artifact tree and installation-private paths described above. RPC transfer files
created inside a shared worker use its private writable tmp mount; files accepted
by the Supervisor are stored in an installation-private Runtime directory and
enforce the instance file-size policy.

## Box Runtime

Runner plugins own sandbox policy: enablement, reuse-key interpolation, acquisition,
binding, and explicit file import/export. The Host exposes authenticated resource
APIs (`get_box_status`, `list_boxes`, `acquire_box`) and run-bound operations
(`bind_box`, `import_box_attachments`, `export_box_files`, `reply_files`). Box Runtime
owns atomic capacity enforcement and container reuse/lifecycle. Reusing an existing
Box is allowed when no additional capacity remains.

Transfer payloads are assembled through private, inode-bound staging files and are
published with no-overwrite links only after the final chunk succeeds. Durable owner
records include the published payload device/inode identity, so reads and deletion
fail closed if a canonical name is replaced. The transfer root assumes no untrusted
process can mutate its directories with the same Unix UID: such a mutator can rename
an owned inode to an unknowable name, which cannot be recovered safely. The SDK
reports that condition as local filesystem corruption, retains owner authority, and
never treats it as successful cleanup or as cross-tenant access.

A run binds one Box before native sandbox tools or file transfer. The Host does not
choose a conversation scope or stage attachments before starting the Runner. Input
references retain the original attachment metadata; import yields paths specific to
the run. Output export requires an explicit list of normalized absolute sandbox file paths
and returns opaque handles scoped to the current run. File creation alone does
not deliver an attachment. Core validates the selected batch before accepting it,
then removes only the accepted files; unselected files remain. A cleanup warning
is carried on the returned BoxFile handles and does not mean export failed.
Core, LocalAgent and the SDK must upgrade together: older no-argument export
clients are incompatible with this selected-path contract.
`message.completed.file_ids` attaches explicitly exported files to Pipeline output;
Agents send them explicitly with `ctx.reply_files()`, subject to event reply permission.
The Pipeline wrapper never scans a Box. Binding ends with the run; the reusable Box
remains subject to Runtime idle expiry. Persistent workspace files survive expiry,
but processes and container-local state do not.

`lbp box` enters `box/server.py::main()` and serves `BoxRuntime` through action RPC.

Box graph:

```text
LangBot BoxService
  ↔ BoxRuntimeConnector
  ↔ BoxServerHandler
  → BoxRuntime
  → Backend session(s)
  → Docker/Podman, nsjail, E2B sandbox, or explicit unsafe host process
```

Important modules:

- `box/server.py`: CLI entrypoint, aiohttp WebSocket routes, `BoxServerHandler` action registration.
- `box/runtime.py`: session lifecycle, per-session locks, TTL cleanup, command execution, managed processes.
- `box/models.py`: generic `BoxSpec`/read-only mount contracts, execution results, managed-process specs.
- `box/client.py`: action-RPC client used by LangBot-side connector/service.
- `box/actions.py`: `LangBotToBoxAction` enum.
- `box/backend.py`: backend abstraction and local backend selection.
- `box/host_backend.py`: explicit non-sandboxed host-process backend for
  trusted local development.
- `box/nsjail_backend.py`: nsjail backend.
- `box/e2b_backend.py`: E2B backend.
- `skill_store.py`: generic Skill package CRUD, revision, and read-only resource helpers; it does not start or connect to Box.
- `box/security.py`: path/security helper logic.

Default Box WebSocket endpoints on port `5410`:

- `/rpc/ws`: action RPC control channel.
- `/v1/sessions/{session_id}/managed-process/ws`: legacy default process stdio relay.
- `/v1/sessions/{session_id}/managed-process/{process_id}/ws`: named process stdio relay.

The Skill store keeps an authoritative registry in an `(instance, workspace)`
namespace. Each successful publication validates a complete staging tree,
computes one `sha256-tree-v1` digest, atomically installs an immutable revision,
and only then advances the registry pointer. Updates require the current
`base_revision`; deletion removes the pointer while retaining revisions for
active or recoverable runs. Former mutable package directories are only a
one-time online-upgrade import source.

LangBot Core composes pinned revisions into generic read-only `BoxMountSpec`
values. Ordinary fixed mounts include `content_digest` and `manifest_path` in
the session signature; supported digest-addressed packages are excluded from it.
Digest-addressed packages use the reserved
`/opt/langbot-artifacts/<digest>` namespace. Docker/Podman pre-mount a read-only
cache and atomically populate verified revisions before execution. Caches live
under the configured `box.local.host_root`, outside the default writable Workspace,
and are removed with their session. Containerized Box must share this root at the
same absolute path as the host daemon. E2B seals and
verifies packages before publishing stable digest projections. These packages can
be added after a Box is acquired, without replacing the session. nsjail applies
all mounts independently per execution. Fixed ordinary host mounts still reject
incompatible reuse; a conflict never implicitly destroys the existing session.
The unsafe host development backend maps each execution's paths without claiming
filesystem isolation. Cached artifacts are shared within a Box, just like its
Workspace; version pinning is not isolation between commands sharing that Box. Box
has no Skill model, CRUD API, or `SKILL.md` knowledge in its normal path; it only
validates and mounts artifacts. Copy-based backends prepare a digest-specific
staging tree, verify the complete manifest, and publish it before projecting the
mount path, so partial transfers and removed-file residue cannot be executed.
Core and the Box Runtime SDK are upgraded in lockstep; Box deliberately rejects
retired Skill-aware payload fields instead of carrying a mixed-version bridge.
Sandbox sessions and managed processes use an
`(instance, workspace, placement_generation)` namespace. Authenticated tenant
RPCs advance a monotonic generation fence, cancel in-flight older RPCs, and
retire older sessions. Managed-process relay handshakes carry Workspace and
generation in authenticated headers; an attached relay closes as soon as that
generation becomes stale.

Run-bound tool calls propagate scoped cancellation through Plugin Runtime to Box
EXEC. Cancellation cleanup uses the original request scope and remains bounded
when cancellation repeats or the invocation is revoked.
Cancelling an active execution retires its sandbox, as a command timeout
does; persistent workspace files survive, but container-local files and managed
processes do not. Cancelling a queued execution leaves the active sandbox alone.
Failed cleanup keeps the session fenced until a later acquire/delete retries it.

There is no supported `python -m langbot_plugin.box` entrypoint; use `lbp box`.

Box ownership is stable across restarts. `box/identity.py` resolves a configured
or persisted instance ID and holds its local ownership lock. Startup cleanup
only removes resources owned by that ID; RPC initialization cannot change it.
See [Box instance identity](docs/box-instance-identity.md) for configuration,
deployment persistence, and shared-daemon upgrade requirements.

## Backend Selection

Box can execute through multiple sandbox backends:

- Docker/Podman through the local CLI backend path.
- nsjail for local Linux sandboxing.
- E2B for remote cloud sandboxes.
- Host processes for explicitly opted-in, trusted local development without
  sandbox isolation.

LangBot sends Box config during initialization. Backend selection is controlled by LangBot's `box.backend` config (`local`, `docker`, `nsjail`, `e2b`, `host`) and the Box runtime's backend availability probes. `host` is never auto-selected and does not participate in the `local` fallback.

A false “no backend” often means Docker exists but the user cannot access the Docker socket. nsjail inside containers requires host cgroup namespace for cgroup v2 limits if hard memory/pid/cpu enforcement is expected.

## Cross-Repo Development Flow

When changing shared contracts:

1. Change this SDK repo first or in the same branch set.
2. Install the local SDK into LangBot's virtualenv: `uv pip install .` from this repo while LangBot's `.venv` is active.
3. Run LangBot with `uv run --no-sync ...` so `uv` does not replace the local SDK with the pinned PyPI package.
4. Exercise the exact path changed: plugin stdio, plugin WebSocket, `lbp run`, `lbp rt`, `lbp box`, Box WebSocket, or Box stdio.

Workspace action-context support starts in SDK `0.4.15`. The instance-scoped
Runtime handshake and complete `InstallationBinding` extend that protocol on
the multi-tenant branch and require a coordinated LangBot Core change before
release. Until a matching SDK version is published, Core must pin the exact
pushed SDK commit; the already-published `0.4.14` artifact does not contain any
of these contracts and must not be used as a compatibility alias.

The SDK `AGENTS.md` keeps the short command checklist; this file keeps the structural map.

## Design Biases

- Keep plugin-author SDK APIs stable and explicit.
- Treat action enums and Pydantic models as cross-process API contracts.
- Keep runtime process management separate from LangBot product logic.
- Keep Box limited to generic sandbox/session/mount semantics; Skill policy and
  package orchestration belong to LangBot Core.
- Prefer tests around protocol shape and black-box CLI behavior when changing runtime boundaries.
