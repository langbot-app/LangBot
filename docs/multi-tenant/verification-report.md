# Multi-tenant isolation kernel verification report

Date: 2026-07-20

Status: `CORE ISOLATION KERNEL VERIFIED — SAAS ACTIVATION REMAINS DISABLED`

This report records the final implementation and verification evidence for the
shared Workspace isolation kernel. It does not claim that the closed SaaS
Control Plane, billing system, or greenfield Cloud v2 deployment is
production-ready.

## Repository refs and scope

- LangBot branch: `feat/multi-tenants`
- LangBot implementation commit:
  `a47bfe8167e12d1853667b3d059cfb940ff0643e`
- LangBot base: `origin/master` at
  `6baeb032a7f76c65337b51c7b58593de4687a61c`
- Plugin SDK branch: `feat/multi-tenants`
- Plugin SDK commit and LangBot dependency pin:
  `044536f3720a2a8424d92f78934b9623da9f7f1d`
- Space remained on `main` at
  `5058b039c2629e3b01ebd7358369b50e7df62a1c`; this implementation made no
  tracked Space change and does not reuse the legacy Space deployment model.

The SDK protocol is versioned as 0.4.15 and is intentionally consumed from the
exact pushed Git commit on this feature branch. Publishing 0.4.15 and replacing
the Git pin with a registry pin remain merge-to-master release steps.

## Implemented boundaries

- OSS bootstraps exactly one Workspace per instance while allowing multiple
  Accounts, memberships, invitations, and role-based permissions inside it.
  Local configuration or an edition flag cannot activate SaaS multi-Workspace
  routing.
- The Cloud bootstrap remains a closed-policy injection point. The closed entry
  point owns Manifest signature verification; Core accepts only a verified
  deployment receipt and validates its instance, expiry, generation,
  capability, entitlement-adapter, and runtime-configuration invariants.
- PostgreSQL uses one shared business schema with application scope plus exact
  `ENABLE` and `FORCE ROW LEVEL SECURITY` policies. Tenant UoWs keep `SET LOCAL`
  and SQL on one transaction; transaction-free scopes avoid holding pool
  connections across model or network waits.
- The one-shot release migrator owns DDL and grants a distinct runtime role only
  business-table DML, `alembic_version` read access, required sequence access,
  database `CONNECT`, and schema `USAGE`. Runtime startup reruns the complete
  role, ACL, schema, session, extension, routine, parameter, and RLS audit.
- pgvector is stored in the same business database with Workspace-scoped keys,
  checked dimensions, release-created partial ANN indexes, and RLS. Legacy
  vector migration can temporarily suspend source-table RLS as a non-superuser,
  non-`BYPASSRLS` table owner and restores each source table's prior state.
- One shared Plugin Runtime supervisor serves the logical instance. Every
  enabled installation still owns one nsjail worker and one immutable
  Workspace/installation/generation/revision/digest binding. Verified
  same-digest code and dependency environments are read-only shared; processes
  and writable state are never merged.
- One shared Box control plane admits at most one persistent logical `global`
  sandbox for an entitled Workspace. Cloud admission is entitlement-gated,
  generation-fenced, shared-volume-challenged, quota-aware, and fixed to
  nsjail. Plain nsjail correctly fails Cloud readiness without a hard storage
  quota provider.
- stdio MCP has an independent policy gate and is forced off by the Cloud
  bootstrap even when Box is available.

## Automated verification

### LangBot backend and static checks

```text
uv run pytest tests/unit_tests tests/integration -q
  2374 passed, 30 skipped, 148 warnings in 26.76s

uv run ruff check .
  passed

changed and untracked Python format check
  112 files already formatted

git diff --check
  passed
```

The fresh SQLite journey test covers first-Account registration, automatic
singleton Workspace creation, authenticated current-Workspace bootstrap,
wizard-state persistence, and a 403 `edition_limit` response when an OSS owner
attempts to create a second Workspace.

### Real PostgreSQL 16 and pgvector

```text
test_migrations_postgres.py
test_pgvector_postgres.py
test_release_migration_postgres.py
test_plugin_identity_migration.py
  20 passed, 11 warnings in 13.51s
```

The real-database suite covers fresh and upgraded RLS schemas, two-Workspace
isolation, pgvector CRUD and ANN indexes, plugin installation identity,
operator/runtime credential separation, advisory locking, and actual Cloud
runtime initialization as the least-privilege role. Negative tests inject and
reject role membership, grant options, persistent GUCs, extra schemas and
relations, column ACLs, explicit routine and parameter ACLs, runtime-owned and
`SECURITY DEFINER` routines, extra/runtime-owned extensions, and foreign data
wrappers, servers, and user mappings.

Alembic has exactly one head: `0013_tenant_pgvector`.

### Plugin SDK and Box Runtime

```text
Plugin SDK full suite
  1154 passed, 18 warnings in 11.99s

Plugin SDK Ruff and action consistency checks
  passed

Docker-backed Box integration suite
  18 passed, 33 warnings in 13.89s
```

The installed LangBot environment resolves `langbot-plugin==0.4.15` from the
same exact SDK commit recorded above.

### Frontend

```text
pnpm lint
  0 errors, 34 warnings

VITE_API_BASE_URL=/ pnpm build
  passed; 3168 modules transformed

pnpm exec playwright test --project=chromium
  40 passed in 21.9s
```

### Packaging and deployment configuration

- `uv lock --check` resolved 277 packages and passed.
- The configuration template, migration workflow, and Docker Compose file
  passed YAML parsing.
- `docker compose -f docker/docker-compose.yaml config --quiet` passed with the
  existing warning that the top-level `version` field is obsolete.
- Migration CI now runs the PostgreSQL RLS, pgvector, release-role, and plugin
  identity suites against PostgreSQL 16 with pgvector.
- The staged high-signal credential scan found no private key or provider token.

## Real browser E2E

A production frontend and backend were run against an isolated temporary
SQLite data directory and operated in a real local Google Chrome Guest window:

1. The first Account registered and received the automatically created default
   singleton Workspace as owner.
2. Skipping the setup wizard reached `/home/monitoring`; reload preserved the
   dashboard and authenticated Workspace state.
3. Account Settings showed the OSS single-Workspace/multi-user model and owner
   membership. The owner created an invitation for another Account.
4. After refresh, the pending invitation remained while its one-time raw secret
   was no longer displayed.
5. The related Workspace, user, system, invitation, and monitoring requests
   returned successful responses in the backend log.

The server was stopped, port 15321 was verified free, and the two temporary
test directories were moved to the system Trash for recoverable cleanup. No
invitation secret is recorded in this report.

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
- durable object references survive execution-generation cutovers without
  stranding files, images, plugin artifacts, or knowledge-base content;
- Plugin Runtime deployment provides delegated cgroup v2 plus tenant-safe
  network isolation and egress policy. The current shared network namespace is
  not an acceptable public-SaaS isolation boundary;
- Box deployment supplies and proves hard byte and inode quotas for Workspace,
  Skill, root, home, and temporary storage; stock nsjail intentionally fails
  this readiness contract;
- production PostgreSQL uses a dedicated cluster/endpoint, or a tested
  HBA/proxy policy proves that the cluster-wide runtime credential can connect
  only to the target business database;
- the release migrator is deployed as a one-shot Job with credential issuance,
  backup, rollback, and orchestration retry procedures. A future direct
  migrator/pooler runtime endpoint split additionally requires an immutable
  database-backed cluster identity;
- OAuth exchange and directory projection state use an atomic shared store for
  horizontally scaled replicas;
- Workspace release, data export, deletion, and single-Workspace restore
  semantics are decided and implemented; and
- the greenfield Cloud v2 deployment is validated without inheriting the old
  Space deployment topology.

These are explicit release gates, not hidden fallbacks. The current branch is a
verified isolation foundation on which the closed SaaS system can be built; it
is not a production Cloud activation.
