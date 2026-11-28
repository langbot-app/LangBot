# Artifact QA: deterministic checks and mixed-attachment soak

Scope: Artifact service, Agent attachment reads and Runner outputs ([#3063](https://github.com/langbot-app/LangBot/issues/3063), phases 1–3 of [#3051](https://github.com/langbot-app/LangBot/issues/3051)). Skill, knowledge-base and other phase 4+ consumers are not covered by this runbook. A matrix entry is a test obligation, not a claim that it has passed. Record candidate-specific evidence before calling it verified.

## Gates and scenario matrix

| Scenario | What must prove it | Lane |
| --- | --- | --- |
| Mixed PNG/JPEG, text and image-only PDF; several files per message; concurrent sessions; later reads in the same session | Valid decodable fixtures; exact digest and bytes; text extraction with the expected body marker; marker appears neither in the prompt nor metadata; no cross-session marker | Deterministic attachment contracts and TCP acceptance |
| Same filename, different bytes; same bytes from different principals | Exact per-file digest and denial of borrowed references, both between users in a Workspace and across Workspaces; reference and authorization checked before accepting cache/dedup hits | Deterministic TCP acceptance and storage isolation contracts |
| Upload, read, Runner output, retain, post-run read/download, release and reclamation | Verify transferred bytes and SHA-256—not just a success code—and separately check persistent, inaccessible and physically reclaimed state | TCP acceptance and accelerated soak |
| History compression, reconnect and Core replacement | Verify old authorized references, exact content after replacement and no complete media or large base64 in ordinary retained history/logs; a new HTTP client alone is not a WebSocket reconnect | LocalAgent compaction and TCP Core replacement; WebSocket reconnection must be proved separately |
| Read/commit/release/expiry/GC race; cancellation vs another session’s active reference | Barrier or observed overlap; A’s cancellation does not alter B’s legal reference; expired or revoked access cannot be satisfied through prior cache state | Deterministic lifecycle plus repeated soak; no inference from sequential calls |
| Bad/truncated PDFs, MIME spoofing, page/size bounds, timeout, cancel and backend failure | Identify the expected specific error, verify no leak of a live or partially committed reference, and prove healthy neighbors still work | Reader limits, fault/lifecycle checks and disposable object-store retry |
| PDF native, text extraction or unsupported | Check representation sent downstream, semantic content separately, and an explicit unsupported result instead of blank or fabricated output | Deterministic checks and separate real-provider sample |
| Accelerated TTL and cleanup under pressure | Age test-owned rows, prove autonomous cleanup on several rotations during concurrent activity, preserve guards, and drain the backlog after load | Separate four-hour accelerated lane |

Keep deterministic and real-provider evidence separate:

* The GitHub `Artifact QA` workflow checks scoped PRs without model credentials. It uses a locked Core checkout and verifies the imported SDK is the in-tree copy. It runs reader/HTTP/MCP checks for the SQLite/database case and the TCP suite against separately started Core and Runtime with the host Box fixture. The installed LocalAgent compaction test uses a deterministic provider and checks a later bounded read of old PDF text after an actual compaction checkpoint. The CI gate rejects missing JUnit output, skipped cases, expected failures and test failures. It does not prove Docker/nsjail/E2B compatibility, multi-host deployment, real model interpretation or long-term behavior.
* For a local run on Linux, run `uv sync --dev --frozen` and the same three pytest commands as the workflow. Mirror the workflow environment for all three runs. In particular, disable the startup release check, Space Models and telemetry, and use loopback Space URLs so deterministic tests never contact Space. Set `LANGBOT_ARTIFACT_MIXED_E2E=1`, `LANGBOT_NETWORK_PLUGIN_E2E=1` and `LANGBOT_CORE_NETWORK_BACKEND=host` for the TCP run. This lane uses owned services and fixtures, not production resources.
* For object-storage acceptance use the repository's [cross-component testing guide](CROSS_COMPONENT_TESTING.md) to provision disposable PostgreSQL/MinIO. Execute the same relevant byte/ownership/lifecycle assertions with DB content and named S3 content identified separately. Report these results separately from SQLite. Never reuse a production database, bucket or account. If a process-level scenario cannot be run against both stores, record that gap rather than counting an integration-client test as the same boundary.
* Real provider validation is a separate opt-in, bounded sample with a documented model, requester, capabilities and approved test credentials. Use synthetic PNG, JPEG, text PDF and a visually encoded scan; first verify the bytes reached the provider request, then compare the response to the body-only marker. A text-only provider rejecting a scan explicitly is a valid unsupported outcome, not a visual-understanding pass. Count throttling (e.g. 429), outbound timeout and provider outages separately from product results. Never expose secret values or upload raw provider requests.

### Optional live-provider sample

After approval for the model, endpoint and bounded sample cost, inject
`LANGBOT_ARTIFACT_LIVE_API_KEY`, `LANGBOT_ARTIFACT_LIVE_MODEL`,
`LANGBOT_ARTIFACT_LIVE_PROVIDER` and `LANGBOT_ARTIFACT_LIVE_BASE_URL` into the
test process environment through an approved secret mechanism. The base URL
must be an approved HTTPS endpoint without embedded credentials or query
parameters. Do not echo these values, put the key in shell history, or store
it in CI. From the same locked checkout, run:

```sh
SPACE__DISABLE_RELEASE_CHECK=true SPACE__DISABLE_MODELS_SERVICE=true \
SPACE__DISABLE_TELEMETRY=true SPACE__URL=http://127.0.0.1:9 CLOUD_SERVICE_URL=http://127.0.0.1:9 \
  uv run --no-sync pytest tests/manual/artifact_live_model.py -q -s --tb=short -rs
```

This checks four serial independent LocalAgent conversations using the live
LiteLLM requester: native PNG, native JPEG, text extraction for a text PDF,
and native input for an image-only scan. The harness requires a completed
attachment tool call and the exact body marker to declare semantic
verification; it labels recognized unsupported modes and upstream failures
separately. Merely submitting the payload is not proof of understanding.

## Long-run operating rules

Run long-lived jobs on disposable Linux hosts with sufficient storage and capacity. Use a different output directory for each run and let teardown finish before archiving evidence. Start with short and staircase runs to check correctness and sustainable throughput, then use the four-hour accelerated profile for repeated expiry and autonomous cleanup under load. Production TTL settings remain unchanged.

Set an explicit cap on offered files/bytes and actual stored objects/bytes, and a minimum disk-free floor. Include many short sessions, some long sessions with old references, and upload bursts. Stop on correctness or authorization failures, resource-budget exhaustion, or inability to keep collecting required evidence. After load stops, verify GC catches up and still-referenced objects remain usable. Record steady-state resource samples across equivalent load and data age. SQLite file size (or PostgreSQL allocated size) alone does not indicate a leak: look at active data, remaining/free pages or reuse and backlog as well.

### Four-hour accelerated regression

The `Artifact accelerated soak` workflow runs the fixed SQLite/database and
host Box configuration. It is not a PR job or a required status check. Once
the workflow is on the default branch, a maintainer may manually dispatch it
there. The daily trigger at 03:43 UTC runs its job only when maintainers set
the repository Actions variable `ARTIFACT_ACCELERATED_SOAK_ENABLED=true`; a
disabled schedule is not an executed test. There are no provider credentials
or new self-hosted runners.

This mode keeps the production TTL unchanged but shortens the TTL of
test-owned rows to two minutes on the disposable database. Core's real cleanup
scheduler runs every 20 seconds with four turns offered every five seconds
for four hours of active load, plus a drain of up to six minutes. Live
references must stay correct during multiple expiry rotations, not just
after requests stop. Keep the journal
and the summary alongside the mandatory passing JUnit case. Neither a
shortened smoke profile nor an accelerated pass establishes the 24-hour
native TTL. Failed/missing/short evidence must not be called a pass.

### Reproduce the run

Run from an exact, clean candidate checkout. Set `SOAK_HOME` to a fresh directory
on a persistent filesystem that can retain evidence for the entire run. The
fixture starts and tears down its own services; run from a persistent job
supervisor on the approved host so the shell closing does not kill the job.
Use the same host, checkout, backend and profile for short, staircase and accelerated runs.

```bash
set -euo pipefail
umask 077
: "${SOAK_HOME:?set SOAK_HOME to a new persistent output directory}"
mkdir -p "$SOAK_HOME"
export SPACE__DISABLE_RELEASE_CHECK=true SPACE__DISABLE_MODELS_SERVICE=true
export SPACE__DISABLE_TELEMETRY=true LITELLM_LOCAL_MODEL_COST_MAP=True
export SPACE__URL=http://127.0.0.1:9 CLOUD_SERVICE_URL=http://127.0.0.1:9
export LANGBOT_ARTIFACT_SOAK=1 LANGBOT_NETWORK_PLUGIN_E2E=1
export LANGBOT_KEEP_RUNNER_E2E=1  # Keep owned process logs locally; review before sharing.
export LANGBOT_CORE_NETWORK_BACKEND=host LANGBOT_SOAK_LANE=sqlite-database
export LANGBOT_SOAK_PROFILE="$PWD/tools/profiles/artifact-soak.json"
case_node=tests/e2e/test_artifact_lifecycle_soak.py::test_artifact_mixed_soak
uv sync --dev --frozen

for mode in short staircase; do
    export LANGBOT_SOAK_MIXED_MODE="$mode"
    export LANGBOT_SOAK_EVIDENCE="$SOAK_HOME/$mode"
    mkdir -p "$LANGBOT_SOAK_EVIDENCE"
    uv run --no-sync pytest -s -q -rs -o xfail_strict=true "$case_node" \
        --junitxml="$LANGBOT_SOAK_EVIDENCE/results.xml" 2>&1 |
        tee "$LANGBOT_SOAK_EVIDENCE/pytest.log"
    test -s "$LANGBOT_SOAK_EVIDENCE/$LANGBOT_SOAK_LANE.mixed-$mode.summary.json"
done

# Review the staircase measurements before starting the four-hour run.
export LANGBOT_SOAK_MIXED_MODE=accelerated
export LANGBOT_SOAK_EVIDENCE="$SOAK_HOME/accelerated"
mkdir -p "$LANGBOT_SOAK_EVIDENCE"
uv run --no-sync pytest -q -rs -o xfail_strict=true "$case_node" \
    --junitxml="$LANGBOT_SOAK_EVIDENCE/results.xml" 2>&1 |
    tee "$LANGBOT_SOAK_EVIDENCE/pytest.log"
test -s "$LANGBOT_SOAK_EVIDENCE/$LANGBOT_SOAK_LANE.mixed-accelerated.summary.json"
```

The checked-in [profile](../tools/profiles/artifact-soak.json) holds the fixed seed,
attachment weights, short/long session mix controls, stepped parallelism and
periods, accelerated TTL/cleanup timing, and file/object/space ceilings.
Review staircase measurements before starting the accelerated run. Keep the
stage journals, summary JSON and JUnit output together. An accelerated run
without its full-duration PASS summary and observed scheduler cleanup is
incomplete. The mixed lane reports fixture-source HTTP requests; this
counter is not S3 API request volume. Collect request totals separately from
the disposable object store when testing that lane. If made available, keep
PostgreSQL wait/active-size and separate Box telemetry distinct from SQLite
free-page and embedded host process measurements.

To repeat on PostgreSQL, use `LANGBOT_SOAK_LANE=postgres-database` and
`LANGBOT_PERSISTENCE_POSTGRES_URL` pointing to a **disposable** service whose
test role may create/drop test databases. For `postgres-minio`, also set
`LANGBOT_PERSISTENCE_MINIO_ENDPOINT`, `LANGBOT_PERSISTENCE_MINIO_ACCESS_KEY` and
`LANGBOT_PERSISTENCE_MINIO_SECRET_KEY` for a disposable service where the
fixture can create/drop a run-owned bucket. Do not pass credential values in
commands or evidence. Use a new output directory per backend.

## Evidence to attach to the review

* Candidate checkout SHA (not merely branch name); Core, in-tree or published SDK, LocalAgent/other Runner version or digest; OS, CPU/memory and storage type; Runtime and Box backend; separation of Core and Runtime local roots; database and object-store versions. Record observed TTL/maintenance settings.
* Command/config, seed, predeclared thresholds, actual wall time, warmup/load/drain phases, session/request/file counts and byte totals; attempted and completed outcomes by media and scenario, including p50/p95/p99, errors and timeouts. Identify which interaction counts include retries.
* Core/Runtime/Box CPU, RSS, FD and process/task samples; database active/allocated bytes and observable waits; object count/bytes and storage request totals; GC rounds, eligible backlog, oldest age and collection rate. Include evidence that the post-load drain did what the run expected. Document counters that cannot be collected rather than substituting guesses.
* Link the CI attempt and scoped fixtures/results, then list tests passed, failed, unsupported, skipped and unrun separately. Retain sanitized failure logs from owned services and journals. Do not attach database files, real messages, auth headers, credentials or complete Base64 payloads.
