# Multi-tenant implementation checklist

This checklist turns the Workspace architecture into implementation and
verification gates. Exact commands and observed results are recorded in the
[verification report](./verification-report.md).

## Scope guard

- [x] LangBot uses branch feat/multi-tenants.
- [x] langbot-plugin-sdk uses branch feat/multi-tenants.
- [x] langbot-space has no changes made by this implementation; Cloud v2 does not extend the legacy Space deployment scheme.
- [x] Unrelated untracked files in either repository remain untouched.
- [x] Open-source startup cannot enable SaaS multi-workspace through edition flags or unsigned configuration.

## SaaS activation gates

These items intentionally remain incomplete. Some require additional Core
transaction/cutover primitives and others require the closed Control Plane or
deployment. The feature branch delivers the Core isolation kernel, not the
closed SaaS product or a production Cloud v2 deployment. Checked implementation
items later in this document do not supersede these gates.

- [ ] The closed Control Plane owns the global Account, Workspace, Membership, and Invitation directory.
- [ ] The closed placement service issues monotonic generations and leases for projected Workspaces.
- [ ] Core verifies a signed `InstanceManifest` before the closed bootstrap can inject `CloudWorkspacePolicy`.
- [ ] Tenant database writes hold a generation-aware shared transaction fence through commit, while placement cutovers take the exclusive fence.
- [ ] Business writes and non-transactional side effects use a generation-stamped outbox or equivalent publish fence.
- [ ] Durable object references survive a placement-generation change through stable published keys or an explicitly atomic key/reference migration.
- [ ] The SaaS runtime pools enforce tenant-safe egress and SSRF controls for Webhooks, providers, MCP servers, and every tenant-configurable outbound URL.
- [ ] Entitlement checks, usage aggregation, subscription lifecycle, and billing are implemented in the closed Control Plane.
- [ ] OAuth state and directory projection use an atomic shared store suitable for horizontally scaled SaaS services.
- [ ] A greenfield Cloud v2 deployment is designed and validated independently of the legacy Space deployment scheme.
- [ ] The Plugin Runtime deployment provides delegated cgroup v2 and tenant-safe egress; the shared profile refuses to run without hard CPU, memory, and PID limits.
- [ ] The Box deployment provides an operator-owned quota provider that proves hard byte and inode limits for Workspace, Skill, root, tmp, and home storage.
- [ ] Core and Box Runtime mount the same durable volume and pass the authenticated marker challenge during startup and reconnect.
- [ ] Production provisions distinct migrator/runtime credentials and runs the implemented same-host/port/database release command as a one-shot Job, with tested orchestration retry, backup, and rollback procedures.
- [ ] Production PostgreSQL uses a dedicated cluster/endpoint, or a tested HBA/proxy policy proves the cluster-wide runtime credential can connect only to the target business database.
- [ ] Any future direct-migrator/pooler-runtime endpoint split is admitted only by a migrator-owned, runtime-read-only database cluster identity that the runtime role cannot spoof.
- [ ] Legacy pgvector migration failure and retry integration paths prove exact source-table RLS/FORCE restoration; the non-superuser, non-`BYPASSRLS` success path is already covered below.
- [ ] Multi-workspace is enabled in SaaS only after all closed Control Plane, deployment, and security gates pass.

## 1. Persistence foundation

### Account and directory

- [x] User has a stable, unique account UUID and explicit status.
- [x] Existing email and password behavior remains compatible during migration.
- [x] Workspace table represents the instance-local tenant.
- [x] WorkspaceMembership has a unique Workspace and Account pair.
- [x] WorkspaceInvitation stores only a token hash and supports expiry, revoke, and one-time accept.
- [x] WorkspaceExecutionState stores generation, state, source, and write fence.
- [x] OSS initialization creates exactly one Workspace and one owner membership atomically.
- [x] OSS refuses a second Workspace while allowing multiple members.

### Migration

- [x] Alembic migration upgrades SQLite.
- [x] Alembic migration upgrades PostgreSQL.
- [x] Existing first user becomes owner of the default Workspace.
- [x] Existing tenant resources are backfilled with the default Workspace UUID.
- [x] SQLite destructive boundaries create verified, revision-aware backups and atomically restore after failure.
- [x] Migration can resume safely after interruption.
- [x] New installs and upgraded installs produce the same tenancy-kernel schema.
- [x] The first Cloud release pins migrator and runtime sessions to `public` with `current_schemas(false)` containing only that business schema; runtime-role/database `search_path` overrides are rejected.
- [x] Cloud sessions require `session_replication_role=origin`, `row_security=on`, and `lo_compat_privileges=off`; every persistent `pg_db_role_setting` applicable to the runtime role or current business database is rejected.
- [x] The release migrator grants the runtime role exact business-table DML, `alembic_version` read-only access, and business-sequence `USAGE/SELECT`, with no `WITH GRANT OPTION` or non-business object grants.
- [x] Every Cloud runtime startup revalidates the login role, current user, schema, effective/direct ACLs, ownership, memberships in all directions, column ACLs, routines, extensions, foreign objects, parameter ACLs, and other-schema access before serving traffic.
- [x] The business database requires `vector`, permits only `plpgsql`/`vector` extensions, forbids runtime extension ownership, and contains no foreign data wrapper, foreign server, or user mapping.
- [x] The runtime role and `PUBLIC` have no explicit routine or parameter ACL; the runtime owns no routine and cannot effectively execute any `SECURITY DEFINER` routine, including extension-owned routines.
- [x] PostgreSQL's default `PUBLIC TEMP` is documented and tested as a dedicated-business-database v1 compatibility exception; the migrator never grants `TEMP` directly to the runtime role.
- [x] Legacy pgvector migration succeeds as a non-superuser, non-`BYPASSRLS` source-table owner and restores mixed source-table RLS/FORCE states exactly.
- [ ] Legacy pgvector migration still needs explicit failure-and-retry integration coverage before SaaS activation.

## 2. Authentication and authorization

### Identity

- [x] JWT sub uses account UUID, with a bounded compatibility path for legacy email tokens.
- [x] Disabled or deleted accounts cannot authenticate.
- [x] Local password and Space-linked account flows support more than one local Account.
- [x] Public registration closes after initialization by default.
- [x] Invitation registration works without requiring SMTP.
- [x] An unknown Space OAuth subject cannot claim an existing Account by email; explicit account-bound binding is required.

### Request context

- [x] PrincipalContext identifies Account, API Key, or trusted runtime principal.
- [x] WorkspaceContext contains Workspace, Membership, role, permissions, and revision.
- [x] RequestContext contains instance UUID, Workspace context, auth type, request ID, and generation.
- [x] ExecutionContext propagates Workspace and generation to runtime work.
- [x] SaaS-style requests never fall back to the first or most recent Workspace.
- [x] OSS may resolve the single Workspace when the selector is omitted.
- [x] Account-token bootstrap can list only the authenticated Account's active memberships before a Workspace selector exists.

### Fixed RBAC

- [x] owner, admin, developer, operator, and viewer permissions match the architecture matrix.
- [x] Invitation cannot grant owner.
- [x] The last owner cannot be removed or demoted.
- [x] Cross-Workspace resources return 404.
- [x] Same-Workspace permission failures return 403.

## 3. Workspace and member APIs

- [x] GET /api/v1/workspaces returns the OSS singleton Workspace.
- [x] POST /api/v1/workspaces returns edition_limit in OSS.
- [x] Current Workspace endpoint returns the authenticated Membership.
- [x] Member list is permission scoped.
- [x] Invitation create, revoke, inspect, and accept are atomic.
- [x] Member role update and removal enforce owner rules.
- [x] Invitation tokens travel in a request body and are redacted from logs.
- [x] Relevant MCP tools and in-repo skills are updated with the same contract.

## 4. Tenant-scoped persistence and services

Each row type must have a non-null Workspace UUID, scoped indexes, scoped uniqueness, and scoped CRUD tests.

- [x] Bots and bot admins.
- [x] Legacy pipelines and pipeline run records.
- [x] Model providers.
- [x] LLM models.
- [x] Embedding models.
- [x] Rerank models.
- [x] Plugin installations, settings, and configuration.
- [x] MCP servers and resource preferences.
- [x] Knowledge bases, files, and chunks.
- [x] Vector collections and handles.
- [x] Monitoring messages, calls, sessions, errors, embeddings, and feedback.
- [x] API keys and scopes.
- [x] Webhooks and public route resolution.
- [x] Binary storage and Workspace storage.
- [x] Workspace metadata, separated from system metadata.

### Service and API rules

- [x] Every tenant Service receives RequestContext or an explicit Workspace UUID.
- [x] No tenant Service treats context None as global access.
- [x] Every applicable get, list, create, update, delete, copy, export, and bulk operation is scoped.
- [x] Parent-child references use the same Workspace.
- [x] API Key authentication derives Workspace from the key, not a header.
- [x] Webhook and Bot public routes derive Workspace from a trusted resource.
- [x] Background jobs carry Workspace and generation explicitly.

## 5. Runtime isolation

### Core runtime

- [x] RuntimeBot carries Workspace UUID and placement generation.
- [x] RuntimePipeline carries Workspace UUID and placement generation.
- [x] Query and Event carry Workspace UUID without making it an authorization source.
- [x] Session key includes Workspace UUID, Bot UUID, launcher type, and launcher ID.
- [x] QueryPool and manager indexes cannot collide across Workspaces.
- [x] Query and aggregation cache keys and locks include Workspace UUID.
- [x] Runtime transports, cached results, object operations, and long-lived tasks revalidate WorkspaceExecutionState generation at side-effect boundaries.
- [ ] Ordinary tenant database writes hold the generation fence in the same transaction until commit; this remains a SaaS activation gate.

### Plugin

- [x] Plugin installation and configuration are Workspace scoped.
- [x] Runtime control actions carry trusted Workspace binding and placement generation.
- [x] The Plugin Runtime supervisor is instance-scoped and intentionally serves multiple Workspaces.
- [x] Every plugin process is bound to exactly one Workspace, installation, generation, revision, and verified artifact digest.
- [x] Same-digest plugin code may be cached once, while worker processes and writable data remain isolated.
- [x] Same-digest plugin dependencies are prepared once in a Runtime-owned immutable environment and mounted read-only into each isolated worker; dependency failure is surfaced before launch and recorded per installation without blocking other desired-state recovery.
- [x] Host API derives Workspace from the connection, installation, and trusted action context, not plugin input.
- [x] Plugin get_bots, models, tools, vector, RAG, configuration, and messaging calls are scoped.
- [x] Plugin Workspace storage no longer uses owner default.
- [x] Plugin page APIs check Membership and installation ownership.
- [x] Local plugin launches use short-lived, one-use registration capabilities bound to manifest identity.

### MCP, RAG, and Box

- [x] MCP runtime key contains instance UUID, Workspace UUID, placement generation, and server UUID.
- [x] Same-named MCP servers in two Workspaces do not share sessions.
- [x] Pipeline cannot reference another Workspace's MCP resource.
- [x] RAG collection names and handles are server-derived and Workspace scoped.
- [x] Legacy global vector migration is available only to the local OSS singleton Workspace.
- [x] Object storage paths include instance, Workspace, and placement generation for the fixed-generation OSS runtime.
- [x] Object storage revalidates generation before touching a provider or resolving an opaque key.
- [ ] Cloud cutover uses generation-scoped staging plus stable published object references, rather than making the staging generation the durable identity.
- [x] Box persistent and ephemeral namespaces include the required instance, Workspace, and generation scope.
- [x] Same-named Box sessions and processes cannot collide across Workspaces or placement generations.
- [x] Box relay and process I/O reject or retire stale generations.
- [x] External paths and privileged mounts cannot be supplied by an untrusted plugin.
- [x] Cloud attachment host I/O uses query UUIDs and link-free dirfd operations with bounded inode traversal.
- [x] Cloud Skill package paths are Runtime-owned, Workspace-scoped, read-only mounts; Python env/cache stays tenant-writable.
- [x] Skill ZIP preview/install rejects path escape, links, non-regular files, duplicate entries, excessive compression ratio, entry count, per-file size, and total size.
- [x] Cloud Box startup proves Core and Runtime see the same durable volume.
- [x] Cloud Box readiness fails until hard Workspace, Skill, ephemeral-storage, and inode quota capabilities are available.

## 6. SDK and protocol

- [x] Public Query, Event, Session, and context entities carry backward-compatible Workspace data.
- [x] Action RPC request models carry trusted Workspace binding where required.
- [x] Action enums and callers remain consistent.
- [x] Old plugins continue to deserialize compatible events.
- [x] Plugins cannot select an arbitrary Workspace through a Host API argument.
- [x] Runtime storage uses the bound Workspace UUID.
- [x] SDK API tests pass.
- [x] Runtime tests pass.
- [x] Action consistency script passes.

## 7. Frontend

- [x] Every browser tenant API request carries the current Workspace selector after bootstrap.
- [x] OSS automatically selects the singleton Workspace.
- [x] OSS does not show Create Workspace or a misleading switcher.
- [x] Workspace settings show current Workspace information.
- [x] Members page lists roles and permissions.
- [x] Invitation creation shows a one-time link when SMTP is unavailable.
- [x] Invitation acceptance supports a signed-out user flow.
- [x] Role controls are hidden or disabled consistently with backend permissions.
- [x] Switching accounts clears stale Workspace query cache and local state.
- [x] User-facing strings support en_US, zh_Hans, and ja_JP.

## 8. Automated verification

### Persistence and authorization

- [x] SQLite fresh install.
- [x] SQLite upgrade from pre-tenant schema, including verified failure recovery.
- [x] PostgreSQL fresh install.
- [x] PostgreSQL upgrade from pre-tenant schema.
- [x] All fixed roles have positive and negative permission-matrix tests.
- [x] Concurrent invitation acceptance creates one Membership.
- [x] Concurrent owner changes never leave zero owners.

### Cross-tenant isolation

- [x] Two Workspaces are created through a test-only policy.
- [x] Applicable resource operations and parent-child references have cross-Workspace negative coverage.
- [x] Resource UUID guessing cannot cross Workspace.
- [x] API Key cannot cross Workspace.
- [x] Plugin cannot enumerate or invoke another Workspace's resources.
- [x] Sessions, caches, locks, MCP, RAG, Box, storage, and monitoring do not collide.
- [x] Background jobs cannot execute without an explicit Workspace and placement generation.

### Security and revocation

- [x] Space login and binding use purpose-bound, one-time opaque OAuth state; caller-supplied state is rejected.
- [x] OAuth redirects trust only server-configured WebUI or webhook origins, never request `Host` or `Origin` headers.
- [x] Dashboard WebSockets revalidate authentication, Membership, resource, permission, and generation per message.
- [x] Public embed WebSockets re-resolve Bot availability and execution binding per message.
- [x] Runtime, storage, Plugin Runtime, MCP, RAG, and Box reject a stale placement generation.
- [x] Unhandled API and webhook failures return a generic error plus request ID without exception text.
- [x] URL user information and sensitive query parameters are redacted before configuration is serialized or logged.

### Regression

- [x] LangBot unit tests pass.
- [x] LangBot integration tests pass.
- [x] Frontend lint completes without errors and the production build passes.
- [x] SDK focused and full relevant tests pass.
- [x] LangBot is pinned to the exact pushed SDK commit and cross-repo tests pass against that revision.

## 9. Real browser E2E

- [x] Start from a clean local data directory.
- [x] First user initializes the singleton Workspace as owner.
- [x] Owner creates an invitation link.
- [x] A second signed-out browser identity accepts the invitation and registers.
- [x] owner, admin, developer, operator, and viewer UI permissions match backend enforcement.
- [x] Direct API calls cannot bypass hidden controls.
- [x] Account switch does not expose prior account or Workspace data.
- [x] Refresh and a new browser tab recover the correct Workspace safely.
- [x] OSS rejects a second Workspace with `edition_limit`; same-name and same-identifier isolation is covered by the test-only multi-Workspace policy because OSS deliberately has no multi-Workspace browser surface.
- [x] Explicit error states are visible for expired, revoked, reused, and email-mismatched invitations.

## 10. Completion evidence

- [x] LangBot and SDK branch refs are recorded in the verification report.
- [x] Space git diff is empty relative to the pre-work snapshot.
- [x] Migration output is captured for SQLite and PostgreSQL.
- [x] Test commands and results are recorded.
- [x] Browser E2E actions and observed results are recorded.
- [x] No remaining tenant table, global Service query, owner default, or unscoped runtime key is found by the final audit.
