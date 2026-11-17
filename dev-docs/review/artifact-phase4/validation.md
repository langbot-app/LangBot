# Candidate validation record

Production/test candidate: `ae58f17e8a1b215df481d4a84d0ef97b7178b356`.
This evidence-only follow-up changes no production code or tests.
Baseline: `83b6b0607b426db3a35f8dbe22e556dfe96d0938`.
Environment: Linux, Python 3.12.14, root editable in-tree SDK 0.7.25.

| Run | Result | Evidence |
| --- | --- | --- |
| Changed-boundary unit/integration/migration and existing Artifact/Runner regression | 259 passed, 133 skipped, 0 failed; 97.72s | [console](evidence/candidate-regression.log), [JUnit](evidence/candidate-regression.xml) |
| Required `sdk_core` | 40 passed; 13 unrelated cases deselected by suite selector | [console](evidence/candidate-sdk-core.log), [JUnit](evidence/candidate-sdk-core.xml) |
| Two-Core / installed Runtime process acceptance | 3 skipped, not verified | [console](evidence/candidate-process.log), [JUnit](evidence/candidate-process.xml) |
| Clean-candidate SQLite repeat smoke | 60-second target, 7 rounds / 21 cases passed, 0 skipped/failed | [manifest](evidence/rounds.ndjson), round logs/XML in [evidence](evidence/) |
| LocalAgent `tests/test_agent_core.py`, isolated released SDK 0.7.23 | 36 passed | [console](evidence/localagent-released.log), [JUnit](evidence/localagent-released.xml) |
| Same LocalAgent suite, candidate SDK 0.7.25 | 36 passed | [console](evidence/localagent-candidate.log), [JUnit](evidence/localagent-candidate.xml) |
| Ruff check/format; generated Workspace proxy check | Passed | [lint](evidence/ruff-check.log), [format](evidence/ruff-format.log), [proxy](evidence/proxy-check.log) |

LocalAgent checks preceded the source commit; plugin/SDK code did not change
after those checks. The 259-case pass count does not include 133 skipped cases.
Those unavailable PostgreSQL/MinIO and migration backend cases remain unverified.
The 60-second test repetition is not a one-hour or long-lived Core memory/GC soak.
Raw console/JUnit/NDJSON files are sanitized: only private workspace paths and
hostnames were replaced, with no credentials/config/env/database files included.
Initial failing harness results are retained (permission exception class and MCP
structured-return unpacking), with corrected runs and unchanged denial/content
predicates. Independent review also found and fixed filesystem text fallback,
active-run expiry/GC protection, and cross-host MIME lookup assumptions.

## Reproduction

The main regression includes the following selected unit paths plus all changed
Skill Artifact tests and existing Artifact integration suites:

```sh
uv run --no-sync pytest \
  tests/unit_tests/api/test_operation_docs.py tests/unit_tests/api/test_skill_artifact_operations.py tests/unit_tests/api/test_mcp_server.py \
  tests/unit_tests/storage/test_artifact_reader.py tests/unit_tests/storage/test_skill_artifact_resources.py \
  tests/unit_tests/storage/test_skill_resource_cache.py tests/unit_tests/storage/test_skill_resource_parallel.py \
  tests/unit_tests/test_skill_repository.py tests/unit_tests/provider/test_skill_artifact_tools.py \
  tests/unit_tests/provider/test_skill_tools.py tests/unit_tests/provider/test_litellm_convert_messages.py \
  tests/unit_tests/box/test_runner_box.py \
  tests/integration/storage/test_skill_artifacts.py tests/integration/storage/test_skill_artifact_loader.py \
  tests/integration/storage/test_artifacts.py tests/integration/storage/test_artifact_mcp.py \
  tests/integration/storage/test_artifact_run_outputs.py tests/integration/storage/test_artifact_content.py \
  tests/integration/storage/test_artifact_management.py tests/integration/storage/test_artifact_publication_policy.py \
  tests/integration/storage/test_artifact_run_inputs.py tests/integration/storage/test_input_artifact_actions.py \
  tests/integration/persistence/test_artifact_skill_migration.py tests/integration/persistence/test_migrations.py \
  tests/integration/persistence/test_migration_branch_convergence.py tools/tests/test_skill_artifact_soak.py -q
uv run --no-sync pytest tests/integration/plugin --required-suite sdk_core -q
uv run --no-sync pytest tests/e2e/test_skill_persistence_replicas.py tests/e2e/test_skill_network_runtime.py -q
```

The actual repeat commands are recorded per round in the manifest. Workspace
path placeholders in sanitized commands refer to the fresh checkout's interpreter.

## Remaining acceptance / support limits

See the [handoff matrix](README.md). Missing: PostgreSQL/restricted-role RLS,
MinIO, real two-Core/Runtime execution, authorized actual-model image/PDF
understanding, full long-lived load/fault/restart soak, documentation site build.
New references require database-backed immutable Skill versions and support at
most 1 MiB per resource. Legacy filesystem and no-run text reads stay compatible.
Run tool limits remain 256 KiB/file and 1 MiB/run. No merge or SDK release is authorized.
