# Multi-tenant verification report

Date: 2026-07-19

This report records the implementation and verification evidence for the Core
Workspace isolation kernel. It does not claim that the closed SaaS Control
Plane or Cloud v2 deployment is production-ready.

## Repository refs and scope

- LangBot branch: `feat/multi-tenants`
- LangBot implementation commit: `c6f826fe2d2e12cc73479155e8f25566048c1c56`
- LangBot base: `origin/master` at
  `6baeb032a7f76c65337b51c7b58593de4687a61c`
- Plugin SDK branch: `feat/multi-tenants`
- Plugin SDK commit and LangBot dependency pin:
  `a1544b6b38a37ba72e3284f2836618144f0742c1`
- Space remained on `main` at
  `5058b039c2629e3b01ebd7358369b50e7df62a1c`, with no tracked changes made by
  this implementation.

The SDK protocol is versioned as 0.4.15 but is intentionally consumed from the
exact pushed Git commit on this feature branch. Publishing 0.4.15 and replacing
the Git pin with a registry pin remain merge-to-master release steps.

## Automated verification

### LangBot backend

```text
.venv/bin/ruff check .
  passed

changed and untracked Python format check
  220 files already formatted

.venv/bin/pytest tests/unit_tests -q
  2051 passed, 1 skipped, 110 warnings in 26.87s

.venv/bin/pytest tests/integration -q
  163 passed, 19 skipped, 28 warnings in 6.00s

uvx --from uv@latest uv lock --check
  resolved 277 packages; passed

git diff --check
  passed
```

### Database migrations

- Fresh and upgraded SQLite schemas passed, including verified pre-boundary
  backups, forced-failure restore, retry, and revision manifest checks.
- A disposable PostgreSQL 16 instance exercised fresh and upgraded tenancy
  migrations: `9 passed, 9 warnings in 8.57s`.
- Alembic has one head, `0010_scope_resources`, through the chain
  `0008_mcp_resource_prefs -> 0009_workspace_tenancy ->
  0010_scope_resources`.
- ORM-to-migration coverage found no missing tenant table.

### Plugin SDK and runtime

```text
SDK full test suite
  1029 passed, 18 warnings in 8.20s

SDK Ruff and action consistency checks
  passed

Docker-backed Box integration tests
  13 passed
```

The SDK remote branch and LangBot Git dependency were both resolved and
verified at the same commit recorded above.

### Frontend

```text
pnpm lint
  0 errors, 34 warnings

pnpm build
  passed; 3167 modules

pnpm exec playwright test --project=chromium
  40 passed in 19.9s

Bot form initialization race pressure test
  10 passed in 9.4s
```

The browser suite covers singleton bootstrap, explicit multi-Workspace
selection under the test policy, selector headers, account-state cleanup,
Workspace switching, and invitation terminal-state recovery.

### Packaging and deployment configuration

- Docker Compose with Plugin Runtime and Box control tokens passed
  `docker compose ... --profile all config --quiet`.
- Compose, Kubernetes, and the default configuration passed YAML parsing.
- Kubernetes selector, volume, and control-token reference checks passed.
- `skills/bin/lbs index --check` and `skills/bin/lbs validate` passed.
- The staged secret scan found no committed credential; test-token literals
  were confirmed to be non-secret fixtures.

## Real browser E2E

The bundled production web application and backend were started against a
clean, temporary SQLite data directory. The following flows were performed in
the in-app browser against the real API rather than mocks:

1. The first Account registered and became owner of the automatically created
   singleton Workspace.
2. The owner created a one-time invitation link.
3. A signed-out second Account inspected the fragment-based invitation,
   registered, accepted it, and entered the Workspace as viewer.
4. The same member was cycled through viewer, operator, developer, admin, and
   owner. Visible controls matched the backend permission matrix, including
   owner transfer only for an owner.
5. A viewer invitation mutation returned 403 `permission_denied`; an owner
   attempt to create a second OSS Workspace returned 403 `edition_limit`.
6. Owner/member account switching, refresh, and a newly opened browser tab
   recovered only the active Account and singleton Workspace state.
7. Used, revoked, expired, and email-mismatched invitation states rendered
   distinct errors. Terminal tokens were cleared, while the mismatch flow
   allowed switching to the intended Account.
8. With the plugin system disabled, `/api/v1/plugins` and
   `/api/v1/system/status/plugin-system` both returned 200 after a clean server
   restart. The only remaining browser console error was the expected failure
   to reach the optional external Space release feed.

The test server was stopped, port 15321 was verified free, and the temporary
test directory was moved to the system Trash. Multi-Workspace same-name and
same-identifier isolation is exercised by the automated test-only Cloud policy;
the OSS browser cannot create a second Workspace by design.

## Final audit

The final isolation audit found no remaining P0/P1 tenant isolation issue in
the OSS singleton-Workspace, multi-user scope. Focused checks also covered the
plugin-disabled Workspace fence, invitation fragment/account-switch behavior,
and the Bot form initialization sequence. Unrelated untracked workspace files
were excluded from both commits.

## Deliberately incomplete SaaS gates

Multi-Workspace activation remains unavailable in the open-source bootstrap.
Cloud v2 must remain disabled until the following closed-system gates are
implemented and independently verified:

- signed `InstanceManifest` verification and closed `CloudWorkspacePolicy`
  injection;
- authoritative Account, Workspace, Membership, Invitation, placement,
  entitlement, usage, subscription, and billing services;
- generation-aware database transaction and outbox fences through commit;
- stable durable object references across placement-generation cutovers;
- atomic shared OAuth-state and directory-projection stores;
- tenant-safe egress and SSRF enforcement for all configurable outbound URLs;
- a greenfield Cloud v2 deployment, without carrying forward the legacy Space
  deployment model.

These are release gates, not hidden fallbacks. Mutable Core configuration or an
edition flag cannot enable SaaS multi-tenancy.
