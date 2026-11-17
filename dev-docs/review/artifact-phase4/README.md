# Phase-four Skill Artifact acceptance handoff

Baseline: `83b6b0607b426db3a35f8dbe22e556dfe96d0938`.
Branch: `feat/3051-skill-artifact-resources`.
Candidate SHA and actual command results must be filled from the delivered commit
and logs, not copied from the baseline or earlier phase-three reports.

## Scope and design

See [Artifact contract](../../architecture/artifacts.md#skill-package-sources-phase-four)
for identity, authorization, lifecycle and storage decisions. PR #3026 remains an
independent open change: its bounded binary reads, frozen-revision checks and path
counterexamples informed this work; it was not wholesale cherry-picked. This
phase uses the shared reader, not its separate base64/attachment wire contract.

Filesystem-only Skill sources are explicitly unsupported by the new source API.
This is a capability limit, not an acceptance pass. Original text reading remains
available. Full KnowledgeEngine migration, a new storage backend, PDF page
rendering and SDK release/tagging are out of scope.

## Required evidence matrix

This matrix is a handoff checklist, not a test-run record. Replace statuses only
with the candidate SHA, exact command, exit status and accessible raw evidence.
A pytest skip, xfail or missing service is not a passing acceptance case.

| Boundary | Independent counterexample / criterion | Execute where available |
| --- | --- | --- |
| Identity and storage | v1/v2 exact digest and bytes; old reference after cache deletion, new Core and catalog change; no new copied ContentObject | SQLite, then PostgreSQL/MinIO and two Core processes |
| Source access | Other principal in same Workspace; other Workspace; revoked view scope; wrong installation, cross/finished run, forged revision and storage key are denied | Service, HTTP/MCP and installed Runtime |
| Archive safety | Traversal, absolute/encoded escape, non-regular file, malformed/oversized ZIP and wrong file/package digest are rejected | Independent behavior tests |
| Lifecycle | Two files/consumers on one package; one release cannot remove the other; read/delete/GC races; package survives reference collection | SQLite and real PostgreSQL/S3 |
| Recovery | Fault at registration/read/release/delete/cleanup; no readable partial reference; retry safe; cancel and process restart release transient protection | Injected failures and real process termination |
| Compatibility | Legacy text/unknown extension, PNG, text PDF, native visual PDF, unsupported model, structured provider request | Unit/SDK/LocalAgent, then authorized real model |
| Schema/catalog | Full and partial-schema upgrade/downgrade; tenant registry and restricted-role RLS; generated proxy/catalog drift | SQLite and PostgreSQL |
| Long-running lifecycle | Defined load, duration, fault cadence; stable reference/lease counts; eventual reclaim after cancellation/restart | Task-owned services; original reviewer may run on 186 |

## Commands and backend requirements

Use the checkout's editable SDK (`uv sync --dev --frozen --python 3.12`). Do not
change the lockfile or switch to a released SDK merely to satisfy dependencies.
Run focused phase-four behavior tests first, followed by affected existing tests:

```sh
uv run --no-sync pytest tests/unit_tests/storage/test_artifact_reader.py \
  tests/unit_tests/storage/test_skill_resource_cache.py \
  tests/unit_tests/storage/test_skill_resource_parallel.py -q -rs
uv run --no-sync pytest tests/integration/storage -q -rs
uv run --no-sync pytest tests/integration/plugin --required-suite sdk_core -q -rs
uv run --no-sync python scripts/generate_plugin_workspace_api.py --check
```

Use the exact `skill_persistence` and `skill_network` commands and opt-in settings
in [CROSS_COMPONENT_TESTING](../../CROSS_COMPONENT_TESTING.md). Provision only
fresh task-owned databases/buckets and loopback-bound services. Do not reuse
unverified old ports or modify another task's environment. No Docker/service
permission means these rows remain unexecuted; it does not block local work.

## Repeat-run harness

`tools/entrypoints/skill_artifact_soak.py` is Linux-only and records repeated
pytest scenarios with per-round logs, JUnit and a JSON-lines manifest. Each round
runs under its own subreaper supervisor. On timeout, SIGINT or SIGTERM, the
supervisor cleans up and reaps its descendants, including detached processes
that called `setsid()`, while preserving logs and the manifest. Leaked descendants
fail the round even if pytest exited zero. The harness also rejects empty
collections, skips, xfails, failures and missing reports. Supply exact phase-four
node IDs; there is deliberately no fallback to unrelated tests. For example:

```sh
uv run --no-sync python tools/entrypoints/skill_artifact_soak.py \
  --duration 3600 --interval 5 --output .qa/skill-artifact-soak \
  'tests/integration/storage/test_skill_artifacts.py::test_skill_artifact_fixed_version_no_copies_and_restart[sqlite-database]' \
  'tests/integration/storage/test_skill_artifacts.py::test_skill_artifact_gc_never_deletes_package_or_other_reference[sqlite-database]' \
  'tests/integration/storage/test_skill_artifacts.py::test_skill_artifact_read_lease_cancel_releases_pin[sqlite-database]'
```

Each selected scenario must assert its own lifecycle/resource invariants. The
wrapper records repeated fresh-process behavior, not long-lived Core memory
stability. It does not inject faults or restart services on its own. A complete
long-lived soak additionally needs an externally defined task-owned Core load
and fault schedule; record that schedule and resource samples alongside this
manifest. Never label this wrapper alone as full process/GC endurance acceptance.

For the real-process run, use a 60-minute workload with v1/v2 registration and
bounded text/PNG/PDF reads, two independent consumers and parallel release/GC.
Every tenth cycle cancel a read; every twentieth restart one Core and clear only
its task-owned cache. At each cycle assert pinned digest and authorization;
after the final reader stops, wait through the configured lease/expiry boundary
and assert transient lease and eligible Artifact counts return to baseline while
retained Skill versions and the other consumer's bytes remain intact. Preserve
failed cycles rather than weakening the predicate. This schedule remains **to be
implemented/executed** unless a concrete scenario and logs accompany delivery.

## Review delivery

Provide PR URL (or patch), exact head SHA, actual baseline, four design decisions,
commands, raw sanitized logs/JUnit, result totals, run duration/cycle count and
all missing rows. Do not attach auth/config/state/env/database files or model
credentials. Real-model understanding needs its own evidence; an upstream 429
or a successful byte transfer is not a semantic success. Do not merge or publish
a release before review and necessary acceptance are complete.

## Executable additional phase-four cases

The following new/strengthened cases are ready for the reviewer environment:

- `tests/integration/storage/test_skill_artifacts.py`: owner/Workspace isolation,
  fixed revisions, HTTP/MCP, no-copy, run pin/expiry, cancelled read, concurrent
  registration/version deletion (both winners), transactional GC failure and retry.
- `tests/integration/persistence/test_artifact_skill_migration.py`: partial-schema
  guards, downgrade refusal and full FK-connected model-schema roundtrip.
- `tests/integration/storage/test_skill_artifact_loader.py`: actual database-backed
  run loader with text/PNG/native PDF, SDK content shape and finished-run denial.
- `tests/e2e/test_skill_persistence_replicas.py::test_two_core_processes_share_skill_packages_and_uploaded_media`:
  real HTTP, v1/v2 references, two Core instances, cache deletion/restart and safe
  reference deletion. Requires the existing opt-in persistence process environment.
- `tests/e2e/test_skill_network_runtime.py`: existing installed Runtime probes now
  additionally require Skill Artifact identity, digest and frozen revision.

Local development validation used Linux/Python 3.12.14 and the editable SDK
0.7.25, with isolated LocalAgent environments for released SDK 0.7.23 and
candidate SDK 0.7.25. The latter both passed all 36 `test_agent_core.py` cases.
`tests/integration/plugin --required-suite sdk_core` passed 40 selected cases;
13 unrelated cases were deselected by that suite's own selector. Generated
Workspace proxy check and Ruff check/format passed. No lockfile was changed.

The initial implementation was independently reviewed. Fixed issues included
filesystem text fallback for live runs, active-run protection beyond TTL and
host-dependent MIME lookup on replacement Core. Initial test-harness failures
included expected permission exception type and MCP structured-result unpacking;
the denial and content predicates were retained while correcting those tests.

No PostgreSQL/MinIO service, Docker/Podman, authorized test model or private
reviewer environment was available here. Related skipped cases remain unverified,
as do the real installed Runtime/process-chain run, restricted-role RLS and
one-hour long-lived load/fault/restart endurance. Documentation site build was
not run. This is a review candidate, not merge-ready final acceptance.
