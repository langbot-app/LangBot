# Cloud v2 multi-tenant verification report

Date: 2026-07-24

Status: `FOUNDATION AND CONTROL PLANE VERIFIED — PRODUCTION ACTIVATION REMAINS GATED`

This report records the implementation and verification evidence for one
logical LangBot instance serving multiple Workspace tenants. It covers the
open-source Core, the shared Plugin/Box runtimes, the closed Space adapter, and
the Space Cloud v2 modular-monolith control plane. It does not claim that the
production Cloud deployment may enable `CLOUD_V2_ENABLED` yet.

## Repository refs and scope

- LangBot Core: branch `feat/multi-tenants`, commit
  `e8a09b7537ef285a967f24add05fdb9bb557b97e`
- langbot-plugin-sdk: branch `feat/multi-tenants`, head
  `ca545d079ca1657a5d4efb4e31bfeafe1a374a46`
- langbot-space: branch `feat/cloud-v2-control-plane`, head
  `ce41ff370e94a405f70e2fbb2f99b0946e0e0387`
- Closed Core adapter: `langbot-space/cloud-adapter`
- SDK protocol/package version: `0.4.18`

Core pins SDK commit `e7d946af4a6b1494fbe74627c1815ace19ac8991`;
the SDK branch head adds CI-only follow-up. Cloud v2 is a greenfield
multi-Workspace deployment and does not provision one Pod, database, queue, or
Runtime per tenant. Legacy Space Pods remain a compatibility surface only.

## Implemented product and security boundaries

### Workspace and identity

- SaaS has one stable `instance_uuid`; `workspace_uuid` is the tenant key.
- Registering an Account creates its personal Workspace and owner Membership in
  the same PostgreSQL transaction.
- A Workspace may contain multiple users with owner, admin, and member roles.
  Invitation acceptance is token-hash based, email-bound, single-use,
  concurrency-safe, and member-limit checked while locked.
- Community remains exactly one local Workspace while supporting multiple
  Accounts and fixed RBAC roles. Installing the closed adapter is required to
  inject the SaaS policy; configuration alone cannot activate it.
- Disabled or deleted Accounts cannot use password/code/OAuth login, sessions,
  refresh/access tokens, or personal access tokens.

### Closed Space control plane

- `CLOUD_V2_ENABLED` defaults to false. Invalid or incomplete configuration
  fails startup, and disabled endpoints return 503.
- Space owns Workspace/Membership/Invitation, versioned plans, subscriptions,
  entitlements, usage events, directory outbox, and signed instance manifests.
- Free and Pro are Workspace plans. Pro projects one managed global sandbox;
  Free projects none. Both force stdio MCP off in the first release.
- Subscription changes use Workspace advisory locking, expected entitlement
  revision, one-live-order uniqueness, idempotent usage ingestion, period-end
  downgrade, renewal, and lazy expiry settlement.
- Account provisioning and quota projection into New API use PostgreSQL
  transactional outboxes, replica-safe claims, retry/backoff, revision fencing,
  and database-enforced identity/user/token ownership. No additional service is
  introduced.
- EPay and Stripe callbacks are bound to the locked order's provider identity,
  amount, currency, channel/session, expiry, and provider transaction ID.
  Replays are idempotent, EPay is CNY-only, credential rotation is supported by
  encrypted per-order snapshots, and permanent fulfillment conflicts are
  retained for reconciliation.
- Directory snapshot and per-Workspace delta reads use repeatable-read,
  read-only transactions with a high-water cursor. Core stores a replica-local
  consumer cursor and shared PostgreSQL projection state, snapshot coverage,
  and inbox rows.
- The `/cloud` page selects a Workspace and shows its independent subscription,
  entitlement, limits, and usage. When Cloud v2 is disabled or the backend does
  not expose the feature field, the complete legacy Welcome/Pod UI is used.

### PostgreSQL and pgvector

- SaaS business data uses one PostgreSQL shared schema with application scope
  plus forced RLS. Cloud directory writes are separated from local tenant
  writes.
- Projected Account and Membership revisions are monotonic. Tombstones remove
  memberships, and stale revisions cannot resurrect them.
- pgvector shares the business PostgreSQL database and remains
  Workspace-scoped.
- Space runs versioned SQL migrations before application seeds. A fresh
  database, a partial pre-migration database, and an existing-baseline path
  converge without startup-time `AutoMigrate`.

### Shared Plugin Runtime

- One instance-scoped trusted Supervisor serves multiple Workspaces.
- Every enabled installation has its own nsjail process bound to
  `(instance, workspace, execution generation, installation, runtime revision,
  artifact digest)`.
- Verified same-digest code and dependency files are mounted read-only and may
  be shared; home, tmp, data, process namespace, registration capability, and
  cgroup are private.
- Instance configuration owns CPU, memory, PID, open-file, and file-size
  limits. Plugin manifests cannot increase them.
- Memory includes swap: nsjail receives `memory.max` and `swap.max=0`.
- Unexpected worker exit is recovered by a completion callback with bounded
  per-installation exponential backoff. Remove, reconcile, Runtime shutdown,
  and container SIGTERM perform a graceful-to-SIGKILL bounded reap.

### Shared Box Runtime and MCP

- One shared Box control plane serves Workspace-bound logical sessions.
- Cloud grants allow at most one persistent `global` session for an entitled
  Workspace and no managed processes in the first release.
- Cloud is fixed to nsjail and network-off. Core and Box prove the shared
  durable Workspace mount with an authenticated marker challenge.
- stdio MCP is independently gated and forced off for Cloud v2.
- The current nsjail Box backend does not provide hard byte/inode quotas, so
  Cloud readiness correctly fails closed instead of silently using a soft
  directory scan.

## Automated verification

### LangBot Core

```text
uv run --no-sync pytest -q
  2590 passed, 32 skipped, 177 warnings

real PostgreSQL migration, pgvector, and release-migrator suites
  21 passed, 11 warnings

uv run --no-sync ruff check .
uv lock --check
git diff --check
  passed
```

The full suite ran without the closed adapter installed, proving the open-source
single-Workspace/multi-user path remains standalone. Focused closed-adapter,
directory projection, runtime connector, Box cleanup, and configuration suites
also passed with the adapter installed.

### Plugin SDK and real Linux runtime

```text
SDK full suite
  1226 passed, 22 existing warnings

Ruff check and format check
git diff --check
  passed
```

A privileged Linux test container with host cgroup namespace ran one shared
Runtime and two Workspace installations:

- both workers referenced the same artifact inode;
- home, tmp, and data inodes were distinct;
- each plugin saw only PID 1 in its private PID namespace;
- a tampered binding and an unknown installation were rejected;
- the control token was absent from worker environments;
- cgroups were distinct with `memory.max=134217728`, `memory.swap.max=0`,
  `pids.max=32`, and `cpu.max=500000 1000000`;
- touching 256 MiB exited with code 137 without swap growth;
- the 32nd fork failed with `EAGAIN`;
- reconcile and container SIGTERM removed the worker cgroups.

The same run started the Runtime from a non-root working directory, covering
absolute nsjail mount-source normalization.

### Space backend, adapter, and frontend

```text
MIGRATIONS_TEST_DSN=... MIGRATIONS_TEST_DSN_FRESH=... \
  go test -count=1 ./...
go vet ./...
  passed against PostgreSQL 16

fresh PostgreSQL app startup, partial-baseline migration,
Cloud v2 migration rerun, and control-plane integration
  passed

closed adapter pytest and Ruff
  passed

pnpm exec tsc --noEmit
pnpm check:i18n
pnpm check:cloud-checkout-currency
  passed; 7 checkout/currency cases
```

The PostgreSQL checks started from an empty database and verified all 34
registered migrations in order, Cloud v2 Free/Pro seeds, legacy plan seeds,
Cloud columns/indexes, payment callback constraints, New API outbox/ownership
constraints, and repeatable reruns.

## Cross-service and browser E2E

### Signed Space-to-Core directory projection

Using an isolated Space PostgreSQL database and a migrated Core PostgreSQL
database:

1. Space issued a signed manifest for the fixed LangBot instance.
2. Space returned a directory snapshot at cursor 5 containing two Workspaces,
   two projected Accounts, and owner/admin memberships.
3. Core verified the signature, instance, release, validity window, and
   capability before injecting the Cloud Workspace policy.
4. Core stored both Workspaces, all active Memberships, both projected
   Accounts, snapshot coverage, inbox entries, and cursor 5.
5. Account-field-only projection revisions and Workspace directory revisions
   remained independent, and cross-Workspace Account conflicts failed closed.

### Real browser Cloud v2 flow

A real local browser operated the Space frontend and backend:

1. An existing legacy-Pod owner logged in and saw the automatically created
   personal Workspace on Free.
2. The page showed Free and Pro Workspace plans while retaining the legacy Pro
   instance card, its Online state, URL, version, billing period, and actions.
3. Annual Pro checkout through the configured EPay/Alipay rail was re-quoted
   from the displayed USD plan price to `¥490.00 CNY`.
4. The browser reached the EPay gateway with `money=490.00`; no USD amount was
   sent through the CNY-only rail.
5. A valid signed `TRADE_SUCCESS` callback returned `success`. An exact replay
   also returned `success`, leaving one successful order and one Pro Workspace
   subscription.
6. Refreshing payment state cleared the pending indicator. The page then showed
   the Pro annual period and managed-sandbox entitlement while the legacy Pod
   remained Online.

The browser run used the real Space UI and HTTP handlers. Its disposable local
development harness added a same-origin Next.js rewrite only in the temporary
worktree; that harness change was removed after the run.

The legacy feature-flag branch was then covered by API/static checks and the
production build: false or missing `cloud_v2_enabled` renders the original
Welcome/Pod client; a failed web-config request renders an explicit retry
instead of guessing a deployment mode.

### Deliberate Core startup failure

Core completed signed manifest verification and directory projection, then
stopped at the Box readiness gate because the current nsjail backend cannot
prove hard Workspace byte/inode quota enforcement. Connector shutdown and
reconnect tasks were cleanly reaped; no event-loop or never-awaited coroutine
warning remained.

This is a successful fail-closed acceptance result, not a passing production
Cloud boot.

## Remaining production activation gates

Cloud v2 must remain disabled until these gates are closed:

- Box provides and proves hard byte and inode quotas for Workspace, Skill,
  root, home, and tmp storage.
- Plugin installation writable data receives an operator-owned hard total
  disk quota.
- Plugin and future networked Box workloads have tenant-safe egress/SSRF
  policy.
- Plugin Runtime adds jitter, global restart concurrency limiting, and a
  Runtime-level circuit breaker, then passes systemic-failure injection.
- M0 rolls Core and Plugin Runtime together until authenticated Runtime takeover
  or an owner lease/fencing protocol exists.
- Payment operations add scheduled reconciliation and alerting for stale
  `processing` orders and persisted permanent fulfillment conflicts.
- Cloud v2 subscription service periods are stored immutably and included in
  recognized-revenue reporting.
- Production migration Job, backup/rollback, PostgreSQL credential/network
  boundaries, horizontal-replica fault injection, Workspace release/export,
  deletion, and restore semantics are completed.

These gates intentionally add no tenant-specific service. They are implemented
inside the existing Space, Core, Plugin Runtime, Box Runtime, and PostgreSQL
components to preserve the architecture goal: near-zero static cost for a new
Workspace.
