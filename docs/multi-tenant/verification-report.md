# Multi-tenant isolation kernel verification report

Date: 2026-07-20

Status: `CORE ISOLATION FOUNDATION VERIFIED — SAAS ACTIVATION REMAINS DISABLED`

This report records the final implementation and verification evidence for the
shared Workspace isolation foundation. It does not claim that the closed SaaS
Control Plane, billing system, or greenfield Cloud v2 deployment is
production-ready.

## Repository refs and scope

- LangBot branch: `feat/multi-tenants`
- LangBot implementation commit:
  `90a977488212d3f3f50fb92d94e3fcae60f27eab`
- LangBot base: `origin/master` at
  `6baeb032a7f76c65337b51c7b58593de4687a61c`
- Plugin SDK branch: `feat/multi-tenants`
- Plugin SDK commit and LangBot dependency pin:
  `95a1805af2038c745de2c018a00db1305089a32e`
- No tracked `langbot-space` change was made. Cloud v2 does not extend or
  preserve the legacy per-account instance/pod deployment topology.

The SDK protocol is versioned as 0.4.15 and is intentionally consumed from the
exact pushed Git commit above. Publishing the release and replacing the Git
pin with a registry pin remain merge-to-master release work; no registry
release was performed here.

## Implemented boundaries

### Workspace, identity, and authorization

- Community bootstraps exactly one local Workspace per LangBot instance while
  allowing multiple Accounts, memberships, invitations, and role-based
  permissions inside it. A mutable edition setting cannot activate SaaS
  multi-Workspace routing.
- Each Account registration resolves or creates its local singleton Workspace.
  Invitation acceptance is one-time, email-bound, and survives the signed-out
  login transition without exposing the invitation secret in URLs after the
  initial fragment capture.
- The Account-token Workspace discovery route is intentionally separate from
  Workspace-authorized routes. `X-Workspace-Id` becomes authority only after
  membership resolution; API keys and public resources derive Workspace from
  their trusted owner.
- Ordinary monitoring uses `resource.view`. Export remains `data.export`,
  privileged runtime/system audit remains `audit.view`, and frontend controls
  follow the same permission split.

### Persistence and PostgreSQL

- PostgreSQL uses one shared business schema with application scope plus exact
  `ENABLE` and `FORCE ROW LEVEL SECURITY` policies. Tenant UoWs keep `SET LOCAL`
  and business SQL on one owned root transaction and one task.
- The public tenant Session accepts only structured SQLAlchemy query/DML trees.
  Raw/textual SQL, textual modifiers, custom AST/compiler nodes, unapproved
  functions/operators/types/casts, hidden dialect values, foreign binds,
  loader/execution options, Session event callbacks, ORM SQL-expression
  attributes, transaction control, and live-result escape fail closed and make
  the root transaction rollback-only.
- The SQL guard is a trusted-Core misuse boundary, not an in-process Python
  sandbox. Mapped metadata and registered compilers are trusted boot-time code;
  plugins remain out of process. SQLAlchemy dialect-private container fields
  are pinned and covered by regression tests before dependency upgrades.
- Legacy local RAG restore remains structured and tenant-fenced while accepting
  SQLite string-valued timestamps and both historical PostgreSQL `TEXT` and
  fresh-schema `JSON` settings columns.
- The one-shot release migrator owns DDL and grants a distinct runtime role only
  the required business-table DML, `alembic_version` read access, sequence
  access, database `CONNECT`, and schema `USAGE`. Runtime startup reruns the
  role, ACL, schema, session, extension, routine, parameter, and RLS audit.
- pgvector is stored in the same business database with Workspace-scoped keys,
  checked dimensions, release-created partial ANN indexes, and RLS.

### Shared Plugin Runtime and Box

- One instance-scoped Plugin Runtime supervisor serves multiple Workspaces.
  Every enabled installation still owns one nsjail worker with an immutable
  instance/Workspace/generation/installation/revision/artifact binding.
- Verified same-digest code and dependency environments may be mounted
  read-only and reused. Plugin processes and writable installation state are
  never merged, including for the same plugin and version.
- Runtime limits come only from instance configuration with native environment
  overrides. Plugin manifests cannot raise limits. Shared mode rejects legacy
  global plugin directories and legacy lifecycle control paths.
- One shared Box control plane admits at most one persistent logical `global`
  sandbox for an entitled Workspace. Admission is entitlement-gated,
  generation-fenced, shared-volume-challenged, quota-aware, and fixed to
  nsjail. Plain nsjail correctly fails Cloud readiness without a hard quota
  provider.
- stdio MCP has an independent gate and is forced off by Cloud bootstrap even
  when Box is available.

## Automated verification

### LangBot backend and static checks

```text
uv run pytest -q --tb=short
  2527 passed, 32 skipped, 177 warnings in 73.37s

focused tenant UoW and legacy RAG compatibility suite
  120 passed, 10 warnings in 1.30s

uv run ruff check .
  passed

changed Python format check
  15 files already formatted

git diff --check
  passed
```

The full suite includes startup E2E, the fresh SQLite registration/Workspace
journey, API authorization, storage, RAG, Plugin, MCP, and 18 Docker-backed Box
integration cases.

### Real PostgreSQL 16 and pgvector

```text
test_migrations_postgres.py
test_pgvector_postgres.py
test_release_migration_postgres.py
  21 passed, 11 warnings in 11.61s
```

The real-database suite covers fresh and upgraded RLS schemas, two-Workspace
isolation, pgvector CRUD and ANN indexes, least-privilege runtime bootstrap,
release locking, historical/fresh RAG settings column compatibility, and
transaction-scope escape rejection. Negative tests inject and reject role
membership, grant options, persistent GUCs, extra schemas and relations,
column ACLs, explicit routine and parameter ACLs, runtime-owned and
`SECURITY DEFINER` routines, extra/runtime-owned extensions, and foreign data
wrappers, servers, and user mappings.

Alembic has exactly one head: `0013_tenant_pgvector`.

### Plugin SDK and Box Runtime

```text
Plugin SDK full suite
  1160 passed, 18 warnings

Plugin SDK Ruff and action consistency checks
  passed

Docker-backed Box integration suite
  18 passed, 33 warnings
```

The LangBot environment resolves `langbot-plugin==0.4.15` from the same exact
SDK commit recorded above. The SDK local ref and remote
`refs/heads/feat/multi-tenants` were independently verified equal.

### Frontend

```text
pnpm lint
  0 errors, 34 existing warnings

VITE_API_BASE_URL=/ pnpm build
  passed; 3168 modules transformed

pnpm exec playwright test --project=chromium
  43 passed in 22.2s
```

The frontend suite includes Viewer monitoring visibility, privileged control
hiding, stable terminal invitation states, email-mismatch login handoff, and a
temporary invitation-accept failure that retains the authenticated session and
succeeds on retry.

### Packaging and deployment configuration

- `uv lock --check` resolved 277 packages and passed.
- Changed TypeScript/TSX files passed Prettier verification.
- `docker compose -f docker/docker-compose.yaml config --quiet` passed with the
  existing warning that the top-level `version` field is obsolete.
- The staged high-signal credential scan found no private key or provider
  token.

## Real browser E2E

A production frontend and backend were run against an isolated temporary
SQLite data directory and operated through a real local Chrome session:

1. The first Account registered and automatically received the default
   singleton Workspace as owner.
2. Skipping the setup wizard reached `/home/monitoring`; reload and a new tab
   recovered the authenticated Account, membership, and Workspace selection.
3. The owner invited a Viewer. After signing out, the second Account registered
   through the invitation and joined the same Workspace.
4. Owner and Admin could read overview/export/audit/API-key surfaces and reach
   resource-write validation. Runtime debug mutation remained disabled.
5. Developer retained ordinary resource management and monitoring, while
   export, audit, and API-key management returned 403.
6. Operator and Viewer retained ordinary monitoring reads while resource
   writes, export, audit, API-key management, and runtime mutation returned 403.
7. The UI matched the server matrix: Add/API Key/Export controls appeared only
   with their permissions, while ordinary monitoring refresh remained visible
   to read-only members.
8. A second Workspace creation attempt returned 403 `edition_limit`, proving
   Community remains single-Workspace and multi-user.
9. Used, revoked, expired, and email-mismatched invitation paths produced
   stable visible states. The mismatch survived login without a contradictory
   generic success toast.

The server was stopped, port 15321 was verified free, and temporary artifacts
were moved to the system Trash for recoverable cleanup. No invitation secret,
password, token, or provider credential is recorded in this report.

## Deliberately incomplete SaaS activation gates

Multi-Workspace activation remains unavailable in the open-source bootstrap.
Cloud v2 must stay disabled until all of the following are implemented and
independently verified:

- the closed Control Plane owns the Account/Workspace directory, memberships,
  invitations, monotonic execution generations, entitlements, usage,
  subscriptions, and billing;
- ordinary tenant writes hold a generation-aware fence through commit, and a
  generation-stamped outbox or equivalent atomic publish fence protects
  external side effects;
- durable object references survive generation cutovers without stranding
  files, images, plugin artifacts, or knowledge-base content;
- every tenant-configurable outbound path has complete SSRF/egress policy, and
  Plugin Runtime has production Linux namespace, cgroup v2, and network
  isolation evidence;
- an unexpectedly exited enabled plugin worker is restored by a completion
  callback with bounded backoff and cross-tenant restart-storm isolation;
- plugin installation data has an operator-owned hard disk quota, not a
  directory-scan approximation;
- Box supplies and proves hard byte/inode quotas for Workspace, Skill, root,
  home, and temporary storage, and the production shared volume passes the
  authenticated marker challenge;
- production PostgreSQL uses a dedicated endpoint/cluster, or a tested
  HBA/proxy policy proves the runtime credential can connect only to the target
  business database;
- the release migrator is deployed as a one-shot Job with credential issuance,
  backup, rollback, failure/retry, and orchestration procedures;
- OAuth exchange, directory projection, leases, snapshots, event replay, and
  outbox state use durable shared stores suitable for horizontally scaled
  replicas;
- Workspace release, export, deletion, restore, and disaster-recovery semantics
  are decided and implemented; and
- production Runtime restart, crash, partition, revocation, and fault-injection
  acceptance is completed against the closed Control Plane and greenfield
  Cloud v2 deployment.

The following product work is also deliberately deferred: WebUI configuration
for tenant-provided remote E2B, multi-replica lease storage and sharding rules,
artifact signing/garbage collection, custom roles, SSO, and SCIM.

These are explicit release gates, not hidden fallbacks. The current branches
are a verified isolation foundation on which the closed SaaS system can be
built; they are not a production Cloud activation.
