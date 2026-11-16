# Cross-component acceptance

Run the paths affected by the change before recommending merge. A passing PR check covers only its selected contracts. Daily coverage is additional evidence; it does not replace acceptance of a changed backend. All commands below start at the repository root on the approved Linux development host. Follow the execution-host restrictions in the active workspace instructions; when local macOS execution is restricted, use the designated remote host and report unavailable verification instead of falling back to Mac.

## CI tiers and evidence

[Core Smoke](../.github/workflows/core-smoke.yml) still runs on every PR and on
protected-branch pushes. Its `Regression tools` and `Core smoke (60s)` check
names are unchanged, as is `CLAAssistant`. The smoke uses real Core, the
installed Runtime and plugins, Runner and the configured Docker Box/file
delivery path. A green selector or coverage summary is not a substitute.

| Previous check | PR lane after #3055 | Full daily / manual lane |
| --- | --- | --- |
| Core 3.11 / 3.12 / 3.13 unit and smoke | Affected 3.12 suites plus existing root-level unit regressions for source changes; full 3.12 with coverage for Core-wide or unmapped changes; all versions for affected SDK/compatibility inputs | All three versions, real 3.12 line-coverage gate |
| Core with in-tree SDK | Retire the duplicate unit and smoke pass; assert the local SDK import in the main Core job; run SDK protocol and Runtime Artifact contracts on affected changes | Same explicit SDK provenance and both contracts |
| Fast integration, SQLAlchemy, Core Browser and Box | Scoped integration in the main Python job; keep independent broad integration, DB, browser, security, Runner and Box lanes when selected | Full integration, SQLAlchemy variants, PostgreSQL, browser startup and LocalAgent/Box |
| Dependency Contracts | Route compiled CLI/HTTP, released plugin identity and SeekDB independently by affected boundary | All three; separate environments and mandatory results |
| SQLite and PostgreSQL migrations | Select storage/schema/Core-shared or CI/dependency changes; run the original migration paths with strict JUnit evidence | Both database engines, no skipped mandatory cases |
| SDK matrix and independent checks | Select SDK and shared compatibility inputs; combine lint/format/type/protocol/package preparation without dropping diagnostics | SDK 3.10 / 3.11 / 3.12, package and Docker Box acceptance |
| Frontend lint, i18n and browser | One install for lint, key parity, type checks, units and dev-browser scenarios; actual Core/Chromium wiring is a separate Core boundary test | Adds the production bundle; raw dev-only test fixtures cannot use that bundle |
| Official plugins | Route by consumer; Runner and KnowledgeEngine preserve separate released/candidate environments, including LocalAgent/LangRAG; keep standalone repro entries | Released/candidate checks for both groups plus misc and catalog |
| Core packaging | Tar/wheel/source/Docker exclusions on packaging changes; production-image builds on image dependency, SDK, deployment and build-configuration changes. Plugin/tool changes keep lightweight exclusions | Full production-image build, SHA, image, checksum and installed SDK metadata |
| Daily workload/recovery | Not a replacement for PR smoke | Preserve mixed load / weekly recovery, API cycles, real managed n8n and persistence/Runtime; scheduled Dify is required; explicitly opt in on manual runs |

Optional PR jobs may be deliberately unselected; selected jobs must succeed.
The Git-based selector checks the full base-to-tested-merge diff and both ends
of moves. Diff errors select all boundaries. Non-required docs, frontend, SDK and
plugin workflows also use native Actions path filters; GitHub evaluates at
most 300 paths for these filters. Shared workflows/dependencies get broader
checks; for a very large change explicitly run the full matrix. Do not change
branch protection to compensate for skipped optional jobs.

Run [Daily Endurance](../.github/workflows/daily-endurance.yml) with
`validation_scope=full` on the actual branch/tag to reproduce the daily
compatibility and migration matrix before release. The PR key contexts, not
the daily run, govern ordinary merges. Confirm the tested SHA and final
`Daily regression verdict` before treating the matrix as complete. The
`workload_only` option intentionally omits the matrix; without
`require_live_dify`, a manual run is not Dify acceptance. Existing release
packaging/pin checks still apply; the full verification entry does not publish.
Download pytest JUnit, browser results, SDK provenance, image metadata and
workload verdicts from the individual jobs. A failed prerequisite, zero
migration cases, skip or xfail in a required suite is incomplete acceptance.

To compare changes, use the same event type and the same change scope, record
each workflow/job link and SHA, exclude skipped jobs from executed job count,
and report cancellations separately. Measure job queue as job creation to start,
execution as start to completion, job minutes as their summed execution, and
overall wall time as first workflow creation to last workflow completion. Do
not count PR-target housekeeping or push runs as PR runs; list those separately.
The [#3054 baseline](https://github.com/langbot-app/LangBot/actions/runs/43878251084)
was 12 PR workflows, 32 executed jobs, 69.78 job-min and 22m28s end-to-end;
a duplicate same-SHA Unit Tests push consumed another 42.95 job-min. Do not
infer the new wall time by subtracting job minutes: parallelism, serial setup
and runner queues change the critical path.

## Shared SDK, API and Runtime changes

Standard Core `uv sync` installs the SDK from this checkout's `sdk/` through the root local source declaration. No overlay or SDK publication is needed to test coordinated changes:

```sh
uv sync --dev --frozen
uv run --no-sync pytest tests/integration/plugin --required-suite sdk_core -q -rs
```

This executes Core/SDK action routing, file envelopes and cancellation contracts. It uses real SDK handlers with local transports and explicit service doubles; it does not establish full-process file delivery. Run the affected SDK tests under `sdk/` as well.

Runner and KnowledgeEngine workflows trigger on affected Core and SDK changes; LocalAgent and LangRAG also retain standalone manual entries. They retain their released-SDK paths and then test the candidate SDK against existing official plugin consumers. Runner RPC tests check each plugin's declared requirements in its actual interpreter. Do not rewrite all plugin pins to satisfy a candidate. A plugin outside the candidate's declared support range needs an explicit compatibility decision, not a forced upgrade. Follow each workflow's isolated dependency setup when reproducing these tests.

## Choose the real acceptance path

| Changed behavior | Required developer acceptance | Environment |
| --- | --- | --- |
| File import/export, Runtime envelopes, persistent grants, reply delivery | `network_plugin` below | Full Core + Plugin Runtime + installed test Runner + Box on loopback; host is the account-free baseline |
| Skill publication, content aliases, media, cache or database schema | `skill_persistence` below | Disposable PostgreSQL + MinIO and two real Core processes; includes SQLite, PostgreSQL and named-S3 replicas, CAS, retained versions, migration/RLS, restart and deleted-cache recovery |
| Network Skill execution, resource reads or draft registration | `skill_network` below | Two real Core processes with independent Plugin/Box Runtimes and no shared Skill/workspace roots; run pins across publication, registration, grants, restart and cancellation |
| Box backend execution, mounts, sessions or file transfer | Relevant `sdk/tests/box` and Core Box tests; repeat network delivery on the changed supported backend | Docker/Podman, nsjail or E2B as applicable; host success does not establish another backend's behavior |

```sh
LANGBOT_NETWORK_PLUGIN_E2E=1 LANGBOT_CORE_NETWORK_BACKEND=host \
  uv run --no-sync pytest tests/e2e/test_network_file_plugin_runtime.py \
  --required-suite network_plugin -q -rs --junitxml=network-plugin.xml

# Both PostgreSQL URLs must point to task-owned disposable databases.
# The two-Core database must be fresh; the integration database needs schema/role creation.
export LANGBOT_PERSISTENCE_POSTGRES_URL='postgresql+asyncpg://postgres@127.0.0.1:5432/langbot_test'
export LANGBOT_PERSISTENCE_CORE_POSTGRES_URL='postgresql+asyncpg://postgres@127.0.0.1:5432/langbot_core'
export LANGBOT_PERSISTENCE_MINIO_ENDPOINT='http://127.0.0.1:9000'
# Supply ACCESS_KEY/SECRET_KEY through the environment for the disposable MinIO.
export LANGBOT_PERSISTENCE_CORE_E2E=1
uv run --no-sync pytest tests/integration/skill/test_persistent_skill_replicas.py \
  tests/integration/skill/test_legacy_skill_migration.py tests/integration/storage/test_legacy_storage_migration.py \
  tests/integration/persistence/test_skill_content_postgres.py tests/e2e/test_skill_persistence_replicas.py \
  --required-suite skill_persistence -q -rs --junitxml=skill-persistence.xml

# Use another fresh task-owned database for this independent pair of Core processes.
export LANGBOT_PERSISTENCE_CORE_POSTGRES_URL='postgresql+asyncpg://postgres@127.0.0.1:5432/langbot_skill_network'
LANGBOT_SKILL_NETWORK_E2E=1 uv run --no-sync pytest tests/e2e/test_skill_network_runtime.py \
  --required-suite skill_network -q -rs --junitxml=skill-network.xml
```

`tests/utils/required_suites.py` enforces the selected behavior obligations and rejects missing cases, skips, xfails and xpasses. Do not use `-k`, `-m` or `--deselect` to turn partial execution into acceptance. The explicit paths above keep collection narrow; the suite still fails if a required contract is missing.

For an actual legacy-Core upgrade, also run `tests/e2e/test_skill_legacy_upgrade.py`
with `LANGBOT_UPGRADE_OLD_SOURCE`, `LANGBOT_UPGRADE_OLD_PYTHON` (using its own old
SDK), and `LANGBOT_UPGRADE_POSTGRES_URL`. Supply a second fresh database through
`LANGBOT_FRESH_POSTGRES_URL` to check generated-template defaults. This path runs
old Core HTTP writes, migration, source-volume removal, restart and a second
Core. Box is disabled here; Runtime acceptance remains the separate network suite.
The normal daily suite does not provision historical Core interpreters.

The existing `daily-endurance.yml` runs both account-free suites on GitHub-hosted Linux, installs Core with its local SDK, and creates temporary loopback PostgreSQL/MinIO services. The other endurance/API/provider jobs retain their existing scope. It neither adds a PR required check nor runs the heavyweight recovery suite on every PR.

For nsjail, use an already prepared host and its delegated `LANGBOT_NSJAIL_CGROUP_V1_PARENT`. For E2B, use explicitly authorized `E2B_API_KEY`, `E2B_API_URL`, `E2B_SANDBOX_URL` and optional `E2B_TEMPLATE`. Set `LANGBOT_CORE_NETWORK_BACKEND=nsjail` or `e2b` for the same network suite. Do not add credentials, change machine configuration, or expose private development machines as runners for public PR code. These backend runs remain developer acceptance until suitable dedicated infrastructure exists.

Record candidate SHA, SDK source/version, actual service/backend configuration without secrets, command and exit status, JUnit/log evidence, and unverified scope. Report environment failure separately from a product failure. Missing environment or skipped cases leave the relevant acceptance incomplete.
