# Multi-tenant implementation decisions

This log records implementation choices made while delivering the Workspace architecture. It is intended to make trade-offs auditable without interrupting implementation for routine decisions.

> Architecture decisions, activation gates, and still-open follow-ups are tracked in
> [pending-architecture-decisions.md](./pending-architecture-decisions.md). Sections marked as decided there are authoritative;
> this file records the concrete implementation choices and compatibility names used to realize them.

## 2026-07-18

### OSS remains a singleton Workspace with multiple Accounts

- Decision: Community builds create exactly one Workspace per LangBot instance and allow multiple Accounts through invitations.
- Reason: This preserves a simple self-hosted deployment while making authorization and ownership explicit. Creating a second Workspace is an edition error, not a hidden fallback.
- SaaS boundary: Multi-Workspace directory, execution ownership, entitlement, and billing are the responsibility of a separate closed SaaS Control Plane. Core consumes a validated projection and remains the final isolation and authorization enforcement point; it does not become the SaaS system of record or billing engine.
- Deployment boundary: Cloud v2 is a greenfield deployment design. The previous per-account instance/pod scheme is not migrated, preserved for compatibility, or extended by this implementation. Existing OAuth, marketplace, and payment concepts may be reused only through explicit adapters where they still fit; `langbot-space` itself is not changed.

### Workspace selection is trusted only after authentication

- Decision: Browser requests carry `X-Workspace-Id`, but the server resolves it against the authenticated Account membership. API keys, public Bot routes, webhooks, jobs, and plugin calls derive Workspace from their trusted owning resource or binding instead of trusting the header.
- Reason: A selector is routing input, not authorization evidence.
- Compatibility: Community builds may select the singleton Workspace when the header is omitted. A multi-Workspace-capable build must reject an omitted selector.

### Stable Account UUID is the token subject

- Decision: New JWTs use the stable Account UUID as `sub`; a bounded compatibility path accepts legacy email-subject tokens and rotates them when checked.
- Reason: Email can change and therefore cannot be a durable authorization identity.

### Fixed roles are authoritative in Core

- Decision: `owner`, `admin`, `developer`, `operator`, and `viewer` map to a fixed permission matrix in LangBot Core. The last owner cannot be removed or demoted, and invitations cannot create an owner directly.
- Reason: Core must remain the final authorization boundary in both OSS and SaaS deployments.

### Cross-Workspace access is indistinguishable from absence

- Decision: Resource lookups always include Workspace UUID. A guessed UUID belonging to another Workspace returns 404; a visible resource with insufficient same-Workspace permission returns 403.
- Reason: This avoids leaking resource existence across tenants while preserving actionable same-tenant errors.

### Plugin Runtime is shared; every plugin process is single-Workspace

- Decision: One instance-scoped Plugin Runtime control plane serves all Workspaces in the logical LangBot instance. Each running plugin installation has its own nsjail worker with an immutable binding containing `instance_uuid`, `workspace_uuid`, `execution_generation` (stored as the compatibility field `placement_generation` until the schema rename), `installation_uuid`, `runtime_revision`, and verified artifact digest; enabled-resident is the desired semantic. A worker never routes actions for another Workspace or installation, and plugin-supplied scope fields are stripped.
- Isolation: Plugin code is mounted read-only. Home, tmp, and data paths are installation-scoped; process, file-descriptor, file-size, CPU, memory, and PID limits come only from `data/config.yaml` (including native environment overrides), never from a plugin manifest. Cloud requires nsjail and delegated cgroup v2 hard limits or fails closed.
- Cost boundary: Identical verified package bytes share one digest-addressed code cache. A dependency environment is keyed by the artifact and requirements digests, Python ABI, Runtime version, and installer schema, then atomically published read-only for reuse. Installations and processes are not merged, even for the same plugin and version. Registration creates database desired state only; a worker is launched only for an enabled installation.
- Recovery: PostgreSQL installation desired state and durable binary storage are authoritative. Runtime reconnect performs an instance-wide full reconciliation, removes stale workers, and can replay a verified package after Runtime-local cache loss. Dependency preparation failure is recorded per installation with `dependency_prepare_failed`; it prevents that worker launch without blocking recovery of other desired installations, and the same revision can be retried. Enabled-resident is the desired semantic, but the current Supervisor restores an unexpectedly exited worker only on the next Core apply/reconcile; a completion callback, bounded backoff, and cross-tenant restart-storm isolation remain Cloud activation gates.
- Compatibility: Older SDK payloads and legacy `data/plugins` remain an OSS-only bridge. Shared mode requires complete bindings and rejects incomplete context.
- Reason: Sharing the supervisor and immutable code cache removes per-Workspace service cost without turning an untrusted plugin process into a cross-tenant router.

### Invitation delivery does not require SMTP

- Decision: Core returns an invitation secret once for copy-and-share, persists only its hash, and supports expiry, revocation, and one-time acceptance.
- Reason: Self-hosted OSS must support adding users without an email service while avoiding recoverable invitation secrets at rest.
- Browser handling: The copyable invitation URL carries the secret in its fragment, which browsers do not send in HTTP requests or Referer headers. The acceptance page immediately removes the fragment and keeps the secret only in `sessionStorage` until login or acceptance completes; it is never placed in a path, query string, analytics event, or persistent local storage.

### Schema rollout is additive before enforcement

- Decision: Add Account/Workspace directory tables first, then add non-null Workspace ownership to every tenant resource with a deterministic default-Workspace backfill. Runtime and service enforcement is enabled only with matching migration and isolation tests.
- Reason: A Workspace column alone is not isolation, and enforcing queries before data backfill would break upgraded installations.

### Login capability discovery is instance-scoped, not account-scoped

- Decision: The unauthenticated login bootstrap endpoint reports only which login mechanisms the instance supports. It does not inspect the first Account or expose whether that Account has a password. Both password and Space OAuth entry points are available on a multi-user instance; the submitted identity determines which mechanism is valid.
- Reason: This avoids projecting the original owner's authentication type onto invited users and removes a public Account-state disclosure.

### Space OAuth identity does not choose a SaaS Workspace

- Decision: Space OAuth tokens remain Account credentials. In OSS singleton mode, an OAuth refresh may update the singleton Workspace's Space provider only when that Account's role can manage provider secrets. In SaaS multi-Workspace mode an OAuth callback without an authenticated Workspace selector never guesses which Workspace to mutate; explicit Workspace configuration or the closed control plane owns that linkage.
- Reason: An Account may belong to several Workspaces, and authentication must not silently mutate a shared tenant secret.

### SaaS execution state is a validated Core projection

- Decision: Core can resolve both local and `cloud_projection` Workspaces, but only from an explicit Workspace UUID and an active, unfenced `WorkspaceExecutionState` for the current instance and matching source. OSS-only bootstrap paths additionally require `source=local`.
- Reason: The closed control plane owns execution ownership and generation decisions, while Core remains the enforcement point for instance binding, generation, and write fences.

### API-key secrets are one-time and Workspace-bound

- Decision: Database API keys persist only a globally unique SHA-256 hash, an opaque UUID, one Workspace UUID, explicit fixed-permission scopes, status, expiry, creator, and last-used time. The raw secret is returned once. Authentication derives Workspace and generation from the key record and ignores Workspace selectors. Legacy plaintext keys are hashed during migration and receive a compatibility `*` scope. The plaintext config key works only for the OSS singleton Workspace and is disabled in multi-Workspace mode.
- Reason: A bearer key is an identity and routing credential, not merely a password layered on top of caller-controlled tenant selection.

### MCP tools inherit the authenticated API-key context

- Decision: The MCP ASGI mount authenticates the API key once, binds an immutable per-request `RequestContext`, and every tool checks a fixed permission before calling tenant services with that same context.
- Reason: Authenticating the transport without propagating Workspace identity into tool calls would leave the direct service path globally scoped.

### Unreleased SDK protocol is pinned reproducibly without publishing

- Decision: The SDK tenancy protocol is versioned as 0.4.15. This task does not create a GitHub release or publish PyPI because the user authorized pushing code, not a package release. After the SDK feature branch is final, LangBot's feature branch temporarily pins the exact pushed SDK Git commit. Before merging to master, the release gate is to publish `langbot-plugin==0.4.15` and replace the Git pin with the registry pin.
- Reason: PyPI 0.4.14 does not contain `ActionContext`; pinning it makes clean installs fail, while pinning an unpublished 0.4.15 makes dependency sync impossible. An exact Git commit is reproducible and keeps the feature branch testable without expanding release authority.

### Cloud directory writes stay outside Core

- Decision: The open-source Core startup always installs `SingleWorkspacePolicy`, creates or repairs one local Workspace, and permits local membership/invitation workflows. Changing mutable configuration such as `system.edition` cannot activate multi-Workspace routing. The future closed Cloud bootstrap will install `CloudWorkspacePolicy` only after verifying a signed `InstanceManifest`; that policy requires an explicit projected Workspace selector, does not create Workspaces, and rejects invitation or membership mutations with `control_plane_required`; member reads use the versioned local projection.
- Ownership split: The closed Control Plane owns the global Account/Workspace/Membership/Invitation directory, execution ownership and generation, entitlements, subscription state, usage aggregation, and billing decisions. Core owns request authorization, resource scoping, execution-generation validation, and fail-closed enforcement. Provisioning and invoice computation do not belong in open-source Core.
- Reason: The closed control plane is authoritative for SaaS Account, Workspace, Membership, and Invitation state. Allowing Core to mutate the same directory would create split-brain ownership and would make an ownerless compatibility Workspace a dangerous fallback.
- Release gate: Multi-Workspace activation is deliberately unavailable in the open-source bootstrap. Production Cloud v2 must implement the signed `InstanceManifest` verifier and closed bootstrap described in the architecture document before it can inject `CloudWorkspacePolicy`; `edition=cloud`, an environment variable, or any unsigned local configuration is never a valid activation credential.

### Workspace bootstrap is reactive and ordered before browser resource calls

- Decision: The web application blocks Workspace-owned pages until Account and current Workspace bootstrap completes. A `useSyncExternalStore` Workspace store publishes permission changes to React consumers; direct mutation-only routes and controls are hidden or disabled when the fixed role lacks the required permission.
- Reason: Mutating a module-level variable after the initial React render did not reliably re-render permission controls, and mounting resource pages before the selector was established could issue tenant requests without `X-Workspace-Id`.

### JWTs are bound to one LangBot instance

- Decision: New Core JWTs require `iss=langbot-core`, an audience derived from the immutable instance UUID, and an expiry. Legacy community tokens are accepted only when they have the historical issuer, carry no audience, and the active policy is the OSS singleton policy.
- Reason: A token issued by one instance must not authenticate against another instance that happens to share a secret, and a compatibility decoder must not become an alternate path around the SaaS trust boundary.

### Runtime control transports authenticate before protocol dispatch

- Decision: External Plugin Runtime and Box WebSocket control channels require independent strong shared secrets in handshake headers. Locally managed child processes receive ephemeral secrets through their environment; secrets are not placed in URLs, process arguments, request payloads, or logs. Box additionally binds the first authenticated control channel to one trusted instance. Plugin Runtime debug and control credentials remain separate.
- Reason: Workspace context inside an RPC payload is not trustworthy until the transport peer itself is authenticated. Separating control and debug credentials also limits accidental privilege reuse.
- Deployment consequence: Docker Compose and Kubernetes wire one shared secret to each host/runtime pair. An empty external-runtime secret fails startup instead of silently exposing an unauthenticated socket.

### Dashboard WebSocket sessions are tenant runtime objects

- Decision: A dashboard WebSocket sends an authentication frame immediately after upgrade. The server validates Account, Membership, permission, Pipeline ownership, instance, Workspace, and execution generation before registering the connection. Connection indexes, sessions, broadcasts, attachments, and resets include the complete execution scope.
- Reason: Browser WebSocket APIs cannot attach the normal authorization headers, and a process-global `pipeline_uuid` or `session_type` index can collide across Workspaces.

### Read permissions never imply secret permissions

- Decision: `resource.view` responses recursively redact Bot, Plugin, MCP, and provider credentials. Provider secrets require `provider_secret.manage`; Bot and Plugin configuration writes require `resource.manage`. Masked Plugin values can be round-tripped by a manager without overwriting the stored secret. Plugin Runtime debug credentials require `resource.manage`, not the operator-only `runtime.operate` permission.
- Reason: A multi-user Workspace needs useful viewer access without turning every visible configuration endpoint into credential export. Plugin debug attachment can register executable code and is therefore a resource-management operation.

### Temporary credential exchanges are bound to their initiator

- Decision: Lark, Weixin, DingTalk, WeComBot, and QQOfficial one-click registration sessions require `resource.manage` and store the initiating instance, Workspace, execution generation, and principal. Status and cancellation by any other scope return the same 404 as an unknown session.
- Reason: Random session IDs reduce guessing probability but do not authorize access to credentials returned by a completed exchange.

### Uploaded images and documents use different storage capabilities

- Decision: Browser images use the scoped `upload_image` owner type and may be resolved only through the opaque public-image route. RAG documents use `upload_document` and can be read, sized, or deleted only by an exact instance, Workspace, generation, and owner-type match. Legacy `upload` objects are cleanup-only.
- Reason: Treating every upload as a public image made a leaked document key sufficient to bypass authenticated RAG access.

## 2026-07-19

### Space OAuth state is server-issued and single-use

- Decision: Core issues an opaque, cryptographically random OAuth state for each Space login or Account-binding attempt, stores only its digest, and consumes it exactly once within a short expiry. Login and binding states are different capabilities; a binding state is additionally bound to the authenticated Account. Caller-supplied state, including a LangBot JWT, is rejected.
- Redirect boundary: Callback redirects are accepted only for the known callback path and an origin declared by the server-side `api.webui_url` or `api.webhook_prefix`. Request `Host` and `Origin` headers never expand this allowlist.
- Current deployment: The OSS state store is bounded and process-local, so a Core restart safely invalidates outstanding attempts. A horizontally scaled SaaS deployment must move this exchange to an atomic, shared Control Plane store before enabling the closed Cloud bootstrap.
- Reason: OAuth state is a narrow, one-time CSRF and flow-binding capability. Reusing a bearer JWT or trusting caller-controlled Host or Origin data would turn an authorization redirect into an Account-token theft or open-redirect primitive.

### OAuth provider subjects, not email addresses, bind Accounts

- Decision: A known Space `account_uuid` may refresh the credentials of its already-bound local Account. An unknown provider subject that presents an email belonging to an existing Account is rejected, even when the normalized emails match. The Account owner must authenticate locally and use the one-time, account-bound binding flow.
- Reason: Email is contact and display data, not a stable federated identity key. Email-only auto-linking would let provider verification drift or identity reassignment become a local Account takeover.

### Workspace discovery is an account-only bootstrap capability

- Decision: `ACCOUNT_TOKEN` validates the active Account JWT but intentionally cannot resolve a Workspace, receive `RequestContext`, or declare Workspace permissions. Its narrow bootstrap endpoint returns only active Workspace memberships belonging to that Account and never chooses the first Workspace when several exist. All tenant resource routes still require the explicit selector in multi-Workspace mode.
- Reason: Requiring a Workspace header to discover the Account's Workspaces creates an authentication deadlock; allowing the bootstrap route to perform tenant actions would create an authorization bypass. Separating the two capabilities resolves the cycle without weakening tenant routes.

### SQLite tenancy migrations have a verified recovery boundary

- Decision: Before each destructive tenant-schema boundary, a file-backed SQLite installation creates an online-consistent backup with its source and target revisions, runs `PRAGMA quick_check`, writes a durable manifest, and fsyncs restrictive-permission files and directories. A failed boundary disposes the engine, removes stale journal sidecars, atomically restores the verified source revision, and verifies the restored database before startup continues.
- Compatibility: In-memory SQLite cannot provide this recovery guarantee and is rejected for destructive production migration boundaries; it remains usable in tests that create the final schema directly.
- Reason: SQLite batch table rebuilds can leave an installation between schemas if a process or migration fails. A verified pre-boundary image makes retry behavior recoverable instead of merely idempotent in the happy path.

### Execution generation is an execution revocation capability

- Decision: RuntimeBot, RuntimePipeline, background tasks, object storage, Plugin Runtime, MCP, RAG, and Box operations carry the complete instance, Workspace, and execution-generation scope. The current schema and wire compatibility field remains `placement_generation` until a coordinated rename. They revalidate the active execution binding before accessing a provider or transport; long-running calls validate again before accepting results. A stale generation is fenced before it can read, write, or reuse a cached object.
- Plugin boundary: Each locally launched plugin receives a short-lived, one-use registration capability bound to the expected manifest identity and execution scope. The production child environment does not inherit the reusable debug credential, and Host APIs derive scope from the trusted connection and action context.
- Box boundary: Persistent skill content remains Workspace-scoped, while session/process state and relay requests also include execution generation. A generation change retires matching live sessions and closes a stale relay before further stdin, stdout, or file operations.
- Transaction boundary: Request admission and runtime side effects are fenced in this branch, but ordinary tenant database mutations do not yet hold a generation-aware lock through commit. The closed Cloud bootstrap must remain disabled until Core provides the shared-write/exclusive-cutover transaction primitive and a generation-stamped outbox (or an equivalent atomic publish fence). The OSS singleton policy has a fixed local generation and cannot trigger an execution-owner cutover.
- Durable-object boundary: Current opaque storage keys include generation and therefore fail closed after a generation change. That is safe for OSS's fixed generation, but a Cloud cutover must not strand durable KB files, images, or plugin references. Cloud v2 must publish stable final object identities from generation-scoped staging, or perform an atomic object-and-reference migration before activating the new generation.
- Reason: Workspace UUID prevents cross-tenant collisions, but it cannot revoke work after execution ownership changes or is fenced. Execution generation is the monotonic revocation value that makes old runtimes unusable; it does not express membership in a product-level deployment entity.

### Long-lived WebSockets continuously revalidate authority

- Decision: Dashboard WebSockets re-authenticate the Account, Membership, permission, resource ownership, instance, Workspace, and execution generation for every inbound message, not only during the initial frame. A changed role, removed Membership, or fenced execution binding takes effect without waiting for reconnect.
- Public embed boundary: The embed connection re-resolves its Bot before every message and rejects a Bot that was disabled, deleted, moved, or rebound. The public connection may identify a Bot, but it cannot make the initial Bot object an indefinite authorization capability.
- Reason: Authorization and resource state can change while a socket remains open. Connection-time validation alone leaves a revocation gap.

### Legacy vector migration is an OSS-local compatibility path

- Decision: Status, backup, execute, dismiss, and background entry points for legacy global vector collections require an active local Workspace binding under `SingleWorkspacePolicy`. A `cloud_projection` Workspace cannot observe or migrate the old global collection, even when it carries a legacy marker.
- Reason: The legacy collection predates tenant ownership. Treating it as a SaaS fallback would expose one installation's historical vectors to an arbitrary projected Workspace.

### External errors and persisted URLs are redacted centrally

- Decision: Unhandled HTTP and webhook failures return a stable `internal_error` response and request ID, and expose that ID in `X-Request-Id`; the detailed exception is retained only in server logs correlated by the same ID. Explicit domain and validation errors keep their documented status and code.
- Secret boundary: Shared sanitization removes URL user information and masks sensitive query parameters before provider or MCP configuration is serialized, logged, or shown to a reader. Masked placeholders can be round-tripped by an authorized manager without replacing the stored secret.
- Reason: Tenant isolation is incomplete if framework exceptions, connection URLs, or configuration reads can export credentials across otherwise authorized interfaces.

### Box is one shared control plane with one admitted sandbox per Workspace

- Decision: The logical instance has one shared Box Runtime control plane, implemented by one Runtime replica in M0. A closed entitlement adapter projects generic `managed_sandbox` capability and `managed_sandbox_sessions` limit; Core and Runtime never branch on a plan name. An eligible Workspace receives at most one persistent logical `global` session, while each ordinary command remains a one-shot nsjail process. Managed processes and network are disabled in the first Cloud release.
- Storage boundary: Core and Runtime prove they see the same durable volume with an authenticated random-marker challenge. Attachments use opaque query UUID directories and link-free dirfd operations. Skill packages remain in the Runtime-owned Workspace store and enter a sandbox only as a read-only logical-name mount; Python environments and caches live in the tenant's writable Workspace.
- Resource boundary: Cloud readiness requires cgroup v2 plus hard byte and inode limits for Workspace files, Skill storage, root, tmp, and home. The existing directory scan is only a compatibility soft check. Plain nsjail reports these storage capabilities as unavailable, so Cloud Box intentionally cannot start until the greenfield deployment supplies and verifies a real quota provider.
- Archive boundary: Skill ZIP processing is bounded by compressed input, entry count, per-entry size, total uncompressed size, and compression ratio, and rejects links, non-regular entries, duplicates, and path escape before streaming extraction.
- Reason: A shared supervisor removes per-Workspace services and idle control-plane cost, but storage and process admission must still fail closed at the untrusted execution boundary.

### Cloud business data and vectors share one PostgreSQL schema

- Decision: SaaS uses one PostgreSQL business database and shared schema. Every tenant row has an explicit Workspace key; application scope is the first boundary and precise `ENABLE` plus `FORCE ROW LEVEL SECURITY` policies are the second. The Cloud runtime role must be non-owner and have neither superuser nor `BYPASSRLS`.
- Vector boundary: pgvector is the Cloud default in the same business database. Vectors use `(workspace_uuid, knowledge_base_uuid, vector_id)` identity, an untyped vector column with explicit checked dimension, and release-created partial expression indexes for the enabled dimensions. Cloud never falls back to Chroma or performs vector DDL at runtime.
- Transaction boundary: A tenant UoW binds `SET LOCAL` and SQL to one transaction. Long-running pipeline and streaming MCP execution carry a trusted transaction-free tenant scope; each database helper opens a short scoped transaction, avoiding a held pool connection during LLM or network waits. Detached tasks start only after commit and create their own short UoW; rollback cancels them.
- Schema boundary: The first release has exactly one business schema, `public`. Both migrator and runtime sessions must report `current_schema() = 'public'` and `current_schemas(false) = ARRAY['public']`; the runtime role and business database must not carry a `search_path` override. Runtime startup validates this before using the prepared schema and reruns the complete catalog and privilege validation on every process start; it never runs DDL.
- Session boundary: Both Cloud modes require `session_replication_role = 'origin'`, `row_security = 'on'`, and `lo_compat_privileges = 'off'`. Every persistent setting applicable to the runtime role or current business database in `pg_db_role_setting` is rejected, even if its present value appears safe; tenant context remains transaction-local application state rather than a persistent role/database override.
- Grant boundary: The migrator grants the runtime role direct `CONNECT` on the dedicated business database and `USAGE` on `public`; exact `SELECT, INSERT, UPDATE, DELETE` on every allowlisted business table; `SELECT` only on `alembic_version`; and exact `USAGE, SELECT` on business-owned sequences. It grants neither `CREATE`, `TRUNCATE`, `REFERENCES`, `TRIGGER`, sequence `UPDATE`, nor any privilege with `WITH GRANT OPTION`, and grants nothing on other relations or schemas.
- Role boundary: The runtime identity is a `LOGIN` role with no superuser, `BYPASSRLS`, `CREATEDB`, `CREATEROLE`, or replication attribute; no role membership in any direction, including acting as grantor; no ownership of the business database, `public` schema, relations, sequences, routines, or extensions; no column ACLs; and no use, create, or ownership in another non-system schema. Neither the runtime role nor `PUBLIC` may have an explicit routine or parameter ACL, and the runtime role may not effectively execute any `SECURITY DEFINER` routine, including an extension-owned one. PostgreSQL's default `TEMP` privilege inherited from `PUBLIC` is an explicit first-release compatibility decision for this dedicated business database, not a direct runtime-role grant.
- Catalog boundary: The business database must contain `vector` and may contain no extension other than `plpgsql` and `vector`; the runtime role owns neither. It contains no foreign data wrapper, foreign server, or user mapping. These checks remove catalog-level escape paths without forbidding the ordinary implicit execution of non-`SECURITY DEFINER` built-in routines.
- Migration boundary: In the first release, the migrator and runtime URLs must name the same normalized PostgreSQL host, port, and database while using different roles. The migrator owns the application schema, establishes the exact allowlist above, and validates both required access and every prohibited escalation path before releasing the advisory lock. An exact Alembic head, RLS checks, and pgvector table/index/constraint validation remain mandatory; concurrent Jobs fail explicitly and are retried by orchestration.
- Deployment boundary: PostgreSQL roles are cluster-wide, while the in-database audit proves only the target business database contract. SaaS production must therefore use a dedicated PostgreSQL cluster or endpoint that exposes only this business database to the runtime credential, or enforce and test an HBA/proxy policy proving that the credential cannot connect to any other database. This external connectivity proof is still an incomplete SaaS activation gate.
- Endpoint evolution: A future deployment may use a direct endpoint for migrations and a pooler endpoint for runtime traffic. That topology may relax literal host/port equality only after both endpoints are proven to reach the same database through a database-internal, migrator-owned cluster identity that the runtime role can read but cannot create, alter, or spoof.
- Legacy pgvector boundary: Revision 0013 records the exact `ENABLE` and `FORCE ROW LEVEL SECURITY` state of each RLS-protected source table, temporarily suspends those source policies as their table owner inside the migration transaction, and restores every table to its recorded state in `finally`. The migrator does not require superuser or `BYPASSRLS` for this data move.
- Activation gate: The shared schema, pgvector adapter, and database-local runtime audit are implemented, but the external cluster/endpoint or HBA/proxy connectivity proof remains deployment work. Ordinary business writes also do not yet hold a generation-aware fence through commit; a generation-stamped outbox (or equivalent atomic publish fence) and stable durable-object references across generation cutover remain required before SaaS activation.
- Reason: Sharing one database and pool keeps marginal Workspace cost low, while transaction-local context and RLS prevent that shared storage from becoming shared authority.

### stdio MCP has an independent deployment gate

- Decision: `mcp.stdio.enabled` is independent of Box availability and entitlement. OSS defaults it on for compatibility; Cloud requires it off at bootstrap and enforces the same gate on create, update, test, startup loading, and final runtime execution.
- Reason: Treating Box availability as stdio permission would silently create another persistent `mcp-shared` sandbox for each Workspace and bypass the one-sandbox subscription and cost boundary.

## 2026-07-20

### The tenant UoW owns its task, root transaction, bind, and scope

- Decision: A tenant UoW creates one task-owned `TenantScopedAsyncSession` and one root transaction. Public commit, rollback, close, connection, bind, nested-transaction, synchronous-Session, live-streaming, raw SQL, public execution options, and public `set_config` paths fail closed and mark the transaction rollback-only. ORM objects cannot expose a usable synchronous Session, captured methods cannot run in child tasks, an explicit foreign bind is rejected, and a captured Session is permanently retired when its UoW exits rather than being reset for reuse. Tenant scope is installed only through a private UoW capability; pgvector index-plan `SET LOCAL`/`EXPLAIN` diagnostics use a test/operator connection rather than the business Session API.
- SQL boundary: Public UoW calls accept only structured SQLAlchemy query and DML trees. `TextClause`, literal SQL columns, textual labels, prefixes/suffixes/hints, statement execution options, `VALUES` roots, `INSERT FROM SELECT`, `EXTRACT`, literal-execute parameters, unknown/custom AST nodes, forced-unquoted identifiers, named `ON CONFLICT` constraints, unknown dialect post-values clauses, and untrusted casts/types fail closed. PostgreSQL/SQLite `ON CONFLICT DO UPDATE` and batch-insert containers are traversed explicitly because SQLAlchemy's standard visitor omits their executable values. Function classes are exactly allowlisted as `count`, `coalesce`, `sum`, `now`, `length`, and `nullif`; the only custom operator/cast admitted is the validated pgvector cosine operator and `Vector` cast.
- Legacy migration boundary: The local-only RAG backup restore uses explicit table and column objects, never raw SQL, but deliberately leaves legacy values untyped. This preserves SQLite's string-valued `DATETIME` rows and both the historical PostgreSQL `TEXT` and fresh-schema `JSON` settings columns while keeping every value bound rather than interpolated.
- ORM boundary: SQLAlchemy `SessionEvents` are unsupported on a tenant-scoped Session. If a listener is registered before or during a UoW, the operation fails before the callback executes and cleanup proceeds against an empty dispatch surface. Public `get`, `get_one`, `refresh`, and `merge` reject caller-supplied loader, bind, lock, shard, and execution options. Flush, implicit autoflush, and commit reject a SQL expression assigned to a mapped attribute before it can reach the compiler. Tenant code uses the async Session directly; relationships use eager loading or explicit `await session.refresh(entity, [attribute])`. LangBot's persistence base does not expose `AsyncAttrs.awaitable_attrs` as a supported tenant API.
- Compiler trust boundary: This guard prevents accidental scope/transaction escape by trusted LangBot Core code; it is not an in-process Python sandbox. Registered SQLAlchemy compilers and mapped schema metadata are trusted boot-time code. The fail-closed traversal of dialect containers necessarily covers SQLAlchemy private fields, so dependency upgrades require the regression suite and remain pinned until verified. Untrusted plugins cannot import or call this Session because they remain isolated in Plugin Runtime child processes.
- Result boundary: A caught database or boundary failure rolls back the root transaction and cancels after-commit work. Buffered results contain only already-authorized rows and no live connection; live database results cannot escape the UoW operation.
- Reason: `SET LOCAL` plus RLS protects a tenant only while every statement stays on the same owned connection and callers cannot end the transaction, replace the GUC, recover the synchronous proxy, or route a statement through another bind.

### Parallel request work re-enters tenant scope explicitly

- Decision: Child coroutines created by request-level `asyncio.gather` open their own explicit transaction-free tenant scope before calling persistence-backed Plugin, MCP, or Skill operations. They never inherit the parent's active database Session.
- Reason: Python copies ContextVars into child tasks, but SQLAlchemy Sessions are not task-safe and task identity is part of the tenant UoW boundary.

### Ordinary monitoring is readable; audit and export remain privileged

- Decision: Workspace monitoring dashboards, Bot logs, sessions, messages, calls, errors, and feedback require `resource.view`. Monitoring export requires `data.export`; system/runtime audit logs keep `audit.view`. Frontend tabs and controls use the same split.
- Reason: A Viewer needs useful read-only product observability, while bulk data extraction and privileged runtime/system logs are separate capabilities.

### Invitation failures survive login without contradictory success state

- Decision: Invitation terminal codes map to stable browser states. A login-mediated email mismatch preserves the fragment-captured secret only in session storage, returns to the acceptance page with the stable error code, and suppresses the generic login-success toast. A transient acceptance failure retains the authenticated session and offers the same one-time invitation for retry. Invalid Bearer tokens on acceptance map to the normal authentication error instead of an internal failure.
- Reason: Invitation acceptance crosses signed-out and authenticated states; losing or masking the domain error makes recovery ambiguous and can present contradictory UI feedback.

### Shared Plugin Runtime starts only from verified desired state

- Decision: SDK shared mode waits for immutable runtime configuration before inspecting plugin state, never scans or launches legacy `data/plugins`, and rejects legacy install/restart/delete/upgrade control actions. Worker RPC files use installation-private directories with aggregate size enforcement, and resident nsjail workers explicitly disable the default 600-second wall-time limit.
- Remaining gate: Unexpected worker exit is still recovered only by the next Core apply/reconcile. Completion callbacks, bounded backoff, hard installation disk quota, and production Linux/cgroup/egress evidence remain Cloud activation requirements.
- Reason: A shared supervisor reduces per-Workspace services only if legacy global paths, writable transfer state, and lifecycle defaults cannot bypass installation isolation.
