# LangBot regression tools

Run the deterministic OpenAI Chat Completions endpoint with Python 3.11+, without
API credentials or third-party dependencies:

```sh
python3 tools/mock_llm.py --port 18080 --record /tmp/langbot-mock-requests.jsonl
```

In LangBot, create an `openai-chat-completions` Provider whose base URL is
`http://127.0.0.1:18080/v1` and whose API key is any test-only value. Use a model
from `GET /v1/models`. The loopback address works when Core and this tool run on
the same host; containers must use an address reachable from their own network.

| Model | Behavior |
| --- | --- |
| `mock-chat` | Returns `LANGBOT_CHAT_OK`, including SSE streaming |
| `mock-rag` | Requires the golden document sentinel in the model input, then returns `LANGBOT_RAG_OK` |
| `mock-embedding` | Returns deterministic normalized token-hash vectors from `/v1/embeddings` |
| `mock-box` | Calls `exec` twice to write/read `/workspace/mock-llm.txt`, then returns `LANGBOT_BOX_OK` |
| `mock-401`, `mock-429`, `mock-503` | Returns the selected HTTP failure |
| `mock-slow` | Delays the response by two seconds |
| `mock-slow-stream` | Delays each SSE chunk by 0.2 seconds |

`mock-rag` requires `aurora-parser-rag-9137` in the submitted messages. The
[golden HTML fixture](../skills/skills/langbot-testing/fixtures/rag/parser-golden.html)
contains this marker; retrieve it into the model context without including it
in the user's question.

For `mock-box`, enable Box in the Runner and expose the native `exec` tool. Each
tool result must contain `LANGBOT_BOX_SENTINEL` before the next step is returned.
Tool-call IDs and fragmented streaming arguments use the normal OpenAI protocol.
Scenario progress comes from each request's current conversation turn, so
concurrent sessions and retries do not consume a shared script counter.
Tagged group traffic additionally requires the previous user turn and assistant
acknowledgement in the model input, and rejects another group's history. Final
responses carry a per-turn acknowledgement checked by the traffic driver.

Add fixed response/tool sequences with `--scenarios path/to/scenarios.json`, using
`mock_llm_scenarios.json` as the example. `expect_tool_output` checks a substring
in the previous tool results; `expect_prompt` checks the submitted messages.
The server returns tool calls; it never executes
their commands. Request recordings contain prompts, tool results, responses,
status, and disconnects, but no HTTP headers. Use test data only.

Run the focused HTTP checks on the Linux test host:

```sh
python3 -m unittest discover -s tools -p test_mock_llm.py -v
```

These checks validate the mock server. A LangBot regression must additionally
verify real tool outputs and retrieved document IDs/content. Token usage is
synthetic, and this endpoint does not evaluate answer quality or embedding models.

`mock-embedding` accepts string/batch inputs, float/base64 encoding, and optional
dimensions (default 384). It tests the embedding protocol and RAG plumbing;
token hashes do not establish semantic retrieval quality.

## Normal traffic and resource collection

`regression_traffic.py` executes a JSON list of normal `lbctl` cases at a selected
rate. Each case has a name, CLI arguments, and an expected response substring:

```json
[{"name":"chat","args":["pipeline","run","PIPELINE_UUID","--message","Hello"],"expect":"LANGBOT_CHAT_OK"}]
```

Prepare a Workspace-bound CLI context and its API key environment variable, then
run on the Linux test host:

```sh
python3 tools/regression_traffic.py \
  --lbctl /path/to/lbctl --config /path/to/lbctl.yaml \
  --cases /path/to/cases.json --output /path/to/new-results-directory \
  --duration 600 --rps 2 --workers 4 --cooldown 30 \
  --pid core=CORE_PID --pid mock=MOCK_PID \
  --health core=http://127.0.0.1:5300/healthz \
  --health mock=http://127.0.0.1:18080/healthz
```

Add `--container CONTAINER_ID` for Docker CPU/memory/PID statistics. The executing
account must be able to inspect the selected process trees and Docker daemon.
Resource collection reuses `scripts/cloud_runtime_soak.py`; it does not require
cgroup v2. PID resource totals include descendants, so select disjoint trees.

The result directory contains `requests.jsonl`, `resources.jsonl`, `progress.json`,
and `summary.json`. The requested rate is a target: four workers bound concurrency,
and slow requests lower the achieved rate. Requests with unknown outcomes are
recorded without retry. A command fails its business check if it returns an error
or omits the expected response. Health/resource collection failures also make the
run fail. API key values are redacted from recorded CLI output.

Latency percentiles include the entire CLI invocation and use successful
requests only. Achieved request rate is `requests / load_elapsed_seconds`.
`health_samples` counts sampling rounds; `health_failures` counts rounds with
any failed health probe or process/container resource read.

## Configured regression suites

[`regression_suite.py`](regression_suite.py) turns a JSON profile into a repeatable
resource preparation, traffic, observation, verdict, and cleanup sequence. Start
with [`regression_profiles/groups.json`](regression_profiles/groups.json) for
continuous group conversations. The earlier
[`normal.json`](regression_profiles/normal.json) profile retains independent CLI
requests; parallel CLI workers alone do not simulate persistent groups.

Use a dedicated QA Workspace. First provision the instance with `lbctl install`
or your source deployment, enable Docker Box, start the mock and embedding
backends, and prepare a Workspace-bound `lbctl` config. Set the profile's CLI
config path, backend URLs, and three plugin archive paths. The sample embedding
endpoint must serve `all-MiniLM-L6-v2`; the mock serves generation only. Relative
paths resolve against the profile directory, so adjust them if you move it.

Run on the Linux test host:

```sh
python3 tools/regression_suite.py validate --profile tools/regression_profiles/groups.json
python3 tools/regression_suite.py run \
  --profile tools/regression_profiles/groups.json --output .qa/regression/run-001
```

`validate` checks profile syntax and references without contacting the instance.
The output directory for `run` must be new. CLI options `--duration`, `--rps`, and
`--workers` override those values in every phase. No additional Python dependency
is needed.

The profile controls:

- `plugins`: local archives or GitHub/marketplace request files, installed with
  `lbctl plugin install ... --wait`.
- `resources`: Providers, models, knowledge bases, document ingestion, Pipelines,
  and Bots, created in dependency order. `${resource_id}` refers to a UUID
  returned by an earlier creation; `${workspace_uuid}` is the current Workspace.
  Pipeline config patches merge with actual server defaults. Independent CLI
  cases can use existing resources supplied through `vars`; group mode creates
  its own signed HTTP Bots.
- `cases`: CLI argument arrays or `http_group` settings and expected business text. Integer `weight`
  values set the mix; `2/1/1/1` means `40/20/20/20`. An optional `body` object
  becomes the case's request file. All workers share the weighted sequence.
- `phases`: each phase has a name, duration, target RPS, worker limit, and optional
  cooldown. Multiple phases provide a step load. In-flight requests drain at the
  end; the concurrency limit can reduce achieved RPS.
- `observe`: health URLs, host PIDs, PID files, and Docker container names/IDs.
  Set PIDs for disjoint process trees to avoid counting descendants twice.
  `box_data_root` discovers Box containers mounted below that deployment's data
  directory on every sample, including sandboxes created as new groups speak.
  The complete Job sets it automatically; on an existing instance, set it to
  the instance's Box data directory when sampling dynamic Docker sandboxes.
- `thresholds`: minimum achieved/target RPS ratio and maximum P95 seconds per
  case, in addition to the existing business and health/resource checks. The
  sample limits are starting acceptance settings, not established product SLOs.
- `cleanup`: `on-success` (default), `always`, or `never`. Only recorded resources
  created by this run are deleted, in reverse order. Plugins and the existing
  instance remain installed. Failed/unknown creations are not automatically
  retried; inspect the instance if a creation outcome is unknown.

Failed runs retain resources by default. After inspection, clean them with the
same profile and credentials:

```sh
python3 tools/regression_suite.py cleanup \
  --profile tools/regression_profiles/groups.json --output .qa/regression/run-001
```

Cleanup checks the Workspace against `owned.json` and records remaining items
after partial failures. Keep `owned.json` until cleanup completes. Each run also
contains `profile.json`, resolved `resources.json`, and one directory per phase
with the original request/resource records. The root `summary.json` includes
target/achieved RPS, phase results, threshold failures, and the final verdict.

The `regression_suite.py` entry reuses an existing instance and backend processes.
Use the complete lifecycle Job below to own deployment, credentials and backends.
The independent `normal.json` cases use a new-session CLI entry. Group traffic
uses the signed HTTP Bot adapter instead, as described below. Real IM adapter
acceptance and resource-leak verdicts need separate scenarios. Test the suite
plumbing on Linux with:

```sh
python3 -m unittest discover -s tools -p test_regression_suite.py -v
```

### Persistent group traffic

The group profile creates three HTTP Bots routed to chat, Box, and RAG Pipelines.
Their signed `/bots/<uuid>/sync` ingress produces real `GroupMessage` events and
uses Core's session manager. Four groups follow a `2/1/1` case assignment;
members take turns within each group. The same member IDs appear in different
groups to exercise group isolation. Box session selection uses the group launcher ID.

In each group phase, `groups` selects the number of stable sessions and
`members_per_group` selects the rotating member identities. `rps` remains the
aggregate target, so a group's target speaking interval is `groups / rps`
seconds. `workers` bounds total in-flight requests independently of group count.
For example, 8 groups at 4 RPS target one message every 2 seconds per group.
Both the Suite and Job accept `--groups` and `--members-per-group` overrides.
The group count must cover the full weighted case sequence (4 in the sample).

Only one request is in flight per group. A failure or unknown outcome stops that
group without retry while other groups continue. Every selected group must
complete at least two turns in total for the phase to pass. The fake model checks
that the preceding user message and assistant acknowledgement survived in actual
model input, including when a different member speaks next. Cross-group markers
fail the oracle. The normal Box/tool-output and RAG-context checks still apply.

`group-state.json` carries group IDs, turn numbers and acknowledgements across
phases; existing groups keep their conversations when later phases add groups.
It refuses changed cases or a state left in progress by interruption. Do not
clear that marker to blindly resume: inspect the run and use a fresh output
directory when the last turn's outcome is unknown. Each phase summary includes
group-level turn counts and member IDs alongside case latency and health data.

The Suite generates the HTTP Bot signing secret and passes it through
`LANGBOT_QA_GROUP_SECRET`. Resource request bodies containing credentials are
stored under `.private/`; do not share that directory. Cases specify `http_group`
with `url`, `secret_env`, and `message` instead of CLI `args`. Core needs no code
changes. The `/sync` response collapses streaming parts: this tests multi-turn
group processing, not real IM delivery or callback streaming order.
Every selected group must also receive traffic in each phase. Group latency
measures the signed HTTP request through its completed reply; independent CLI
latency includes CLI startup. Compare results within the same traffic mode.

`lbctl` v0.3 may report Bot verification failure after a successful creation
because its safe projection omits event bindings. The Suite records the returned
Bot UUID before reading the full Core Bot API with the endpoint, Workspace and
environment credential confirmed by `lbctl whoami`. It then
checks the masked signing secret and effective route with a signed warmup turn
before load. The creation is not retried.

## Complete lifecycle Job

[`regression_job.py`](regression_job.py) owns the deployment as well as the suite.
Use [`regression_profiles/job.json`](regression_profiles/job.json) to pin the Core
Release and select the suite and plugin input directory. The job runs this chain:

1. `lbctl install --profile all` creates a fresh deployment inside the run directory.
2. A Compose override starts our mock backend on the deployment's private network
   and injects a generated test-only API key. The Job binds its own CLI context.
3. The suite installs plugins, creates resources and ingests documents. Each case
   runs once as warmup before measured traffic starts.
4. Configured load phases run with health, process-tree and container sampling.
5. Service-log tails and raw request/resource records are retained. Successful
   Jobs stop the deployment, remove only sandboxes mounted under their own data
   root, and use `lbctl uninstall --purge-data` to reclaim the deployment.

Both generation and embedding use our mock backend, with no external model
service or real model credentials. Plugin archives, the pinned Core image,
`lbctl`, Docker and Compose v2 are Job inputs/prerequisites. This wrapper uses
PyYAML, already included in LangBot's dependencies, to verify the CLI's deployment
record and recover ownership after an interrupted install.

Run on a Linux host with Docker access and permission to inspect the selected
container processes. Use an idle dedicated Docker daemon: current Box runtime
startup cleanup can remove sandboxes from another runtime. The Job refuses to
start when existing Box sandboxes are present. The current `lbctl` installer
also reserves host port 5401 and 2280–2285, independently of its HTTP port.

Set the plugin directory and the `lbctl` executable in `job.json`, then run:

```sh
uv run --no-sync python tools/regression_job.py validate --profile tools/regression_profiles/job.json
uv run --no-sync python tools/regression_job.py run \
  --profile tools/regression_profiles/job.json --output .qa/regression/job-001
```

`--duration`, `--rps` and `--workers` override every load phase. Each output
directory must be new. Job cleanup policy is `on-success`, `always`, or `never`;
it governs the whole deployment, whereas suite cleanup governs API resources
when a suite runs on an existing deployment. `purge_data: false` preserves the
deployment data after removing containers. Failed Jobs retain their environment
by default; after inspection use:

```sh
uv run --no-sync python tools/regression_job.py cleanup \
  --output .qa/regression/job-001
```

The root `summary.json` is the final Job verdict; `suite/` contains the measured
results, `mock/requests.jsonl` contains backend recordings, and `services.log`
contains up to 10,000 log lines per service. Generated credentials and deployment
inputs stay in `.private/`; share the result files, not that directory. A Job has
its own CLI locator/config and records its deployment identity before cleanup.
Changing that identity makes cleanup fail closed. Cleanup uses the saved Job
state and does not require the original profile or plugin input files.

The Job replaces the real embedding model with `mock-embedding`. This measures
LangBot/plugin/Box/RAG overhead, not real-model inference cost or retrieval
quality. Run the Job plumbing checks on Linux with:

```sh
uv run --no-sync python -m unittest discover -s tools -p 'test_*.py' -v
```

## Finite core smoke

Use [`regression_profiles/smoke.json`](regression_profiles/smoke.json) for a finite
functional check on an existing Core. It prepares 35 resources through `lbctl`,
ingests HTML and plain-text fixtures through GeneralParsers, then executes 28
cases / 43 requests. Reports group the verdicts by stage:

| Stage | Cases and independent checks |
| --- | --- |
| Configuration | Identity and plugins; provider, model, Pipeline and knowledge-base readback; document completed status and Workspace/KB ownership |
| Ingress | Missing and incorrect signatures return HTTP 401 / code 40101 without creating a group AgentRun; valid signatures are exercised by group conversations |
| Conversation | Ordinary and Unicode chat; chat, Box and RAG groups each use two interleaved groups with three turns and rotating members; model input must retain prior user/reply history without cross-group history |
| Model | Slow SSE reply; HTTP 401, 429 and 503 primary failures followed by successful fallback; recorded model/status/stream sequence must match |
| Tools | Docker write/read across rounds, two tool calls in one model response, and expected exit code 7 with separate stdout/stderr returned to the model |
| Delivery | ASCII and Unicode filenames/content delivered as one attachment with exact bytes |
| Retrieval | HTML and text parsing/ingestion, RAG model input, retrieval from two knowledge bases with distinct sentinels and KB ownership, and an empty knowledge base returning an empty list |

Cleanup is checked separately: delete journaled API resources and confirm their
UUIDs are absent from CLI list readback. Evidence goes to `cleanup-checks.json`;
cleanup failures affect the overall verdict.

Start a dedicated `mock_llm.py` with the bundled scenarios and `--record` as
shown above. Copy the smoke profile and configure the CLI executable/config,
service URLs, plugin archives, `vars.mock_records` to that mock recording file,
and `vars.core_db` to the target Core's existing SQLite `langbot.db`. The suite
must read both local files. Keep fixture paths valid relative to the copied
profile. Do not share the mock with other traffic during this run: fallback
checks compare requests appended during each case.

Set `plugins: []` to reuse installed plugins; LocalAgent, LangRAG and
GeneralParsers must still be enabled and initialized. The embedding endpoint
must serve the configured model (`all-MiniLM-L6-v2` by default). Generation is
deterministic mock traffic; Core, plugins, Box, document parsing and retrieval
execute normally.

```sh
uv run --no-sync python tools/regression_suite.py validate --profile /path/to/smoke.json
uv run --no-sync python tools/regression_suite.py run \
  --profile /path/to/smoke.json --output .qa/smoke-001
```

A correct reply alone does not pass. Each Pipeline/group request must match one
new AgentRun in the authenticated workspace with `completed` status and a persisted
`run.completed` event. The ledger is opened read-only. This version requires
local SQLite access; remote-only Core and PostgreSQL ledgers are not supported.
The observation timeout does not extend the Runner deadline or retry requests.
Unknown outcomes fail the suite; later turns of that group are skipped while
independent cases continue. An expected tool exit code of 7 passes only when
its output is correct and the agent handles the result and completes normally.

`summary.json` contains the overall and per-stage verdicts; exit code 0 means all
checks and required cleanup passed. `cases.json` records per-request evidence,
`environment.json` records identity/capabilities/plugins, and `owned.json` tracks
created resources. Successful runs delete those API resources. Failures retain
them by default; after inspection use:

```sh
uv run --no-sync python tools/regression_suite.py cleanup \
  --profile /path/to/smoke.json --output .qa/smoke-001
```

Box sessions and AgentRun records follow the reused service's normal retention
policy. Load override flags are rejected for smoke. `stage` labels cases;
`fields` compares exact response values by dotted path (including array indices),
`forbid` rejects response substrings, and `mock_requests` checks the actual
model/status/stream sequence. `box_exec` defaults to exit code 0; error-handling
cases can specify `exit_code` and `stderr` explicitly.

To use a fresh deployment, select this suite in `job.json`; the Job supplies its
SQLite/recording paths and uses mock embedding. Smoke skips load warmup and timed
phases. The dedicated Docker daemon requirement above still applies.

## PR smoke gate

`Core Smoke` runs regression-tool tests and a real Core smoke in parallel on
GitHub-hosted Linux runners. The smoke starts Core from the checked-out candidate,
uses the SDK from `uv.lock`, plugins built from the same checkout, `lbctl`
v0.3.0, a Docker Box and mock generation/embedding. It needs no model credentials
or access to a developer's running environment.
The SDK CLI builds LocalAgent, LangRAG and GeneralParsers into `.lbpkg` archives.
`plugins/manifest.json` records selection mode, plugin versions, archive hashes
and exact installation/readiness readback. Build logs are preserved alongside it.
The published route remains available when `--plugins` is omitted; see
[published plugin preparation and replay](published-plugins.md).

Dependency installation, service startup, sandbox image download and plugin
installation are preparation. After readiness, the gate allows **60 seconds total**
for API resource creation, 28 cases / 37 requests (two turns per group), verdict
checks and API cleanup. A missing verdict, failed check or timeout fails the gate.
The ordinary expanded profile keeps three turns / 43 requests. The entire cold
workflow takes longer than a minute; it has a separate 15-minute timeout.

On an existing prepared stack, use:

```sh
uv run --no-sync python tools/regression_gate.py \
  --profile /path/to/smoke.json --output .qa/gate-001
```

`gate.json` records the budget, measured duration, verdict and process resource
peaks. `resources.jsonl` samples configured process trees every second (RSS,
cumulative CPU time, threads and file descriptors); suite artifacts contain
per-case timings and business evidence. These are diagnostics, not calibrated
performance-regression thresholds. Docker sandbox resource sampling remains in
the longer load runner. A timeout kills the local Suite/CLI process group without
retrying requests; a reused remote service can still have an in-flight run, so
inspect its retained ownership journal before cleanup. CI tears down its own
service processes and owned sandboxes afterward.

The workflow always creates its two checks on PRs and cancels superseded runs.
The existing required check names remain `Regression tools` and `Core smoke (60s)`.
`Daily Endurance` is independent and is not required for merging. Longer load and
soak tests use the existing Suite and Job entry points with separately calibrated
latency, throughput and resource budgets; the one-minute smoke does not replace them.

## Daily regression

`Daily Endurance` runs independently of PR checks at 19:23 UTC (03:23
Asia/Shanghai) on the default branch. GitHub may delay scheduled starts. It also
supports **Run workflow** with a selected branch. The schedule becomes active
only after the workflow is merged into the default branch; it is not a required
merge check.

The workflow reuses the disposable smoke stack and builds plugins from this checkout.
`--suite daily` consumes 46 base cases plus the selected local groups, requires its first pass, then
repeats ordered cases within one **1800-second** window. The clock starts before
creating scenario resources and includes a 120-second reserve for drain/API
cleanup and a 60-second cooldown. Service and plugin preparation precede this
clock. A separate 1860-second process guard allows startup and final reporting;
it does not grant extra scenario time. The whole job retains its 45-minute limit.

The scheduled job enables all local groups (including `plugins`) and the optional one-time restart
checks. Manual dispatch exposes both switches. `--scenario-groups` accepts a
space-separated selection; supplying the flag with no values runs only base
cases. `scenarios` and `daily` enable all three groups when the flag is omitted.

| Group | Additional behavior |
|---|---|
| `faults` | Cancel/timeout cleanup, model retry side effects, partial stream failure, exhausted fallback, Box path rejection |
| `resources` | API-key revocation, direct Agent execution, document deletion with a surviving retrieval control |
| `plugins` | EssentialCommands version command without model/AgentRun execution; FAQManager Page API CRUD and search freshness |
| `lifecycle` | Signed HTTP callback 5xx retry identity and subsequent delivery |

For example, select resource and callback cases with
`--suite scenarios --scenario-groups resources lifecycle`. Add
`--restart-services` to check Core history after restart and a Runtime restart
during an active request. These checks run only against services owned by this
disposable runner, once before the fixed-PID resource sampler starts. Their
elapsed time is deducted from both scenario and outer process budgets; the
resource baseline never joins measurements from old and new PIDs. Failed restart
checks retain their own evidence and fail the run before repeated traffic starts.

Credential revocation and restart diagnostics use an ephemeral user created
through the normal initialization/login APIs in the runner's new private database.
Generic Suite callers must provide `LANGBOT_QA_USER_TOKEN` for credential tests;
missing prerequisites are skipped and produce an incomplete result. Disabled
groups remain unexecuted in coverage, and a saved profile cannot execute a case
whose group is disabled. Expected failed/cancelled/timeout Runs are recorded by
exact ID and status; extra, missing or nonterminal Runs still fail reconciliation.

Fault cases reuse one Box per case and suite, with unique files per invocation.
This bounds normal sandbox growth while preserving cancellation side-effect
checks. The callback receiver uses the standard library and loopback; Core and
the runner must share a network namespace. Document deletion and callback retry
identity have separate narrow contracts: they do not establish document update
semantics or exactly-once effects at an arbitrary callback receiver. Plugin
upgrade rollback and cases needing additional environments remain explicit gaps.

The daily profile uses the existing endurance resource allowances with a
180-second warmup before baseline sampling. Each pipeline that enables Box uses
one stable reuse key unique to this CI run, so conversations created by repeated
cycles reuse that pipeline's sandbox. This measures repeated tool use; it does not test
cross-group Box file isolation. The profile uses one Workspace and does not
establish isolation between tenants. Conversation history and AgentRuns still
accumulate and are reported. Resource excesses remain failures.

Throughput and full-step P95 are observations. Business assertions, unknown
results, health failures, incomplete evidence and resource limits determine the
verdict. Summaries include first-pass completion, cycles, plugin installation
readback, final ledger reconciliation and coverage. Manifests, case results,
coverage, cycles, execution stages, resource samples and service logs are retained
for 30 days, including failures. Hosted runners do not provide a controlled
performance baseline. No automatic comparison between runs is enabled.

To run the same entrypoint on a disposable Linux host with an idle Docker daemon:

```sh
uv run --no-sync python tools/regression_ci.py --suite daily --restart-services \
  --lbctl /path/to/lbctl --plugins plugins \
  --extra-plugins misc/EssentialCommands misc/FAQManager --output .qa/daily-001
```

`--suite smoke` retains the 60-second gate. `--suite scenarios` runs the shared
expanded profile once under a 300-second guard. `--suite endurance` retains the
separate ten-minute load profile under a 900-second guard; its CI entry point also
reports throughput/P95 without applying their thresholds. All four modes use
published plugins when `--plugins` is omitted. Both workflows explicitly select
`--plugins plugins` so source changes are tested in the same PR. Daily additionally
selects `misc/EssentialCommands misc/FAQManager`; manual dispatch can change the
space-separated `extra_plugins` list or leave it empty. `--extra-plugins` requires
source mode and accepts categorized plugin paths, without removing the three base
plugins. Missing or incompatible packages fail preparation, with no silent fallback.
Existing conversation Pipelines allow only the base plugins; plugin-specific cases
bind their own extensions to avoid changing unrelated prompts/tools. The suite attempts owned API cleanup
even after failures. The CI owner then stops its service processes and removes
its Box containers; a process guard timeout can interrupt API cleanup.

## Sustained regression and baseline comparison

[`regression_profiles/endurance.json`](regression_profiles/endurance.json) runs
nine minutes of mixed chat/Box/RAG traffic at 1 request/second across four stable
groups, followed by one minute without traffic to check recovery. Configure its
CLI context, plugin inputs, model endpoints, Core SQLite path and Core/Runtime/Box
PID files as for smoke. Set `plugins: []` to reuse initialized plugins. Configure
`observe.box_data_root` to the target deployment's Box mount root; the caller must
have Docker inspection access. Do not start another Box runtime on a shared daemon.

```sh
uv run --no-sync python tools/regression_suite.py validate \
  --profile /path/to/endurance.json
uv run --no-sync python tools/regression_suite.py run \
  --profile /path/to/endurance.json --output .qa/endurance-baseline
# For an hour including the one-minute cooldown, use --duration 3540.
```

This profile checks more than reply text:

- Each Runner request is reconciled to one completed AgentRun with a persisted
  completion event; Box additionally verifies two real Docker exec results.
  After drain and cooldown, the complete set of runs for the phase's conversations
  must match the verified set. Delayed extra, missing and nonterminal runs fail.
- At least 90% of target successful throughput must be delivered, with per-case
  P95 limits. Reports retain planned/actual counts, scheduling delay and request
  drain time. The load is bounded by workers and serial group sessions; it is
  not an open arrival-rate capacity benchmark.
- Process RSS, FD, thread and process-count medians from the final 30 seconds of cooldown are compared
  with a stable window after the first minute. Docker memory, PIDs and container
  counts are checked separately because sandbox processes are not children of
  the Box service. If a discovered container disappears before stats collection,
  the sampler refreshes the set and retries once, retaining the first error and
  membership change. Unchanged-set errors, failed recovery, missing samples and
  budget excesses fail.

The supplied limits are initial QA budgets, not product SLOs or proof of a leak.
Fixed groups prevent deliberate session growth from being mistaken for leakage;
Core and plugin caches can still retain memory legitimately. Inspect failures
before changing a budget. Process-tree CPU remains a raw diagnostic: child exits
can reduce the cumulative sum, so it is not used as a CPU regression verdict.

`requests.jsonl` separates dispatch/response latency from ledger setup and result
verification. Resource samples go to `resources.jsonl`; `summary.json` contains
throughput, latency, recovery and ledger closeout results. Failed runs retain
resources and evidence. The normal Suite cleanup command removes only owned API
resources after inspection.

To compare two successful runs from the same reserved test host:

```sh
uv run --no-sync python tools/regression_analysis.py \
  --baseline .qa/endurance-baseline --candidate .qa/endurance-candidate \
  --output .qa/comparison.json
```

The comparison rejects failed runs, missing dependency evidence, different enabled
plugin versions, fixtures, expanded case/resource inputs, phase geometry, budgets,
or observer-host identity. Both runs must use identical load/analysis/smoke oracle
files and mock scenarios; their hashes are recorded in the contract. Target URL
hosts, ports and credentials may differ; URL schemes and
paths, model names and actual stimulus variables remain part of the contract.
Both runs must use the same hardware allocation, model backend and background
load; the contract does not establish those external conditions automatically.
The default comparison allows at most 20% P95 growth and 10% successful-throughput
loss, requires 30 requests per case in both runs, and rejects invalid metrics or
incomplete ledger closeout. Set tolerances from repeated controls on your host.

Keep this longer test outside the one-minute merge gate while its budgets and
repeatability are being evaluated. The same profile can be selected by the
release-deployment Job, which supplies its ledger path and process IDs; that
fresh-deployment path still needs separate end-to-end validation.

## Business behavior coverage

`regression_contracts.json` declares behavior obligations independently of how
many requests a workload repeats. It includes explicit unimplemented risks
(cancellation, restart recovery, credential revocation, Workspace isolation,
PostgreSQL parity, real adapters and embeddings). This is coverage of the
registered scope, not a percentage of all product behavior or API endpoints.

Runners record named assertions as they execute. A green legacy request without
assertion evidence is **incomplete**. An evaluated failing assertion counts as
covered and failed; a timeout before an assertion does not count. A contract with
multiple required assertions passes only when all are observed. Repeated
observations cannot hide an incomplete or failed turn. History contracts require
a subsequent turn, not merely the initial reply. Database/Box-event inspections
are reported separately as gray-box evidence.

Reports distinguish `passed`, `failed`, `incomplete`, `skipped`, `not_run` (a test
exists but did not execute) and `missing_test`. Coverage and pass rate have separate
denominators. The catalog fingerprint identifies the registered denominator.
New case names with no contract appear as unclassified, and malformed evidence
is reported as an error instead of silently accepted.

The source route inventory discovers current static RouterGroup HTTP declarations
and flags routes without a linked behavior contract. Links describe test intent;
they are not observed HTTP hits or proof that every method behavior is tested.
Dynamic routes, WebSockets and platform-dispatched routes are outside this static
inventory. Full source locations and any unresolved declarations are retained
in `coverage.json`; new declarations appear without editing the case list.

```sh
python tools/regression_coverage.py --run .qa/smoke/suite \
  --run .qa/endurance/suite --output .qa/behavior-coverage
```

`coverage.json` and `coverage.md` are written by the Suite. CI consumers can
publish these files as artifacts. Uncovered contracts do not add a merge gate. A missing or corrupt evidence
file is a reporting failure; the report remains available for inspection.

Pass `--http-log /path/to/core.log` to include observed methods, declared route
templates and status counts from Hypercorn access records. Query strings and
resource identifiers are not retained in this report. Unmatched requests are
counted by method/status; webhook sub-paths are not separate declared routes.
Missing logs or logs without recognizable access records are evidence errors.
HTTP hits remain separate from assertion coverage.

`regression_scenarios.expanded_profile()` builds 46 finite cases from the smoke
fixtures (86 requests with two groups and three turns). It adds signed ingress
rejection, API authentication, group reset/history isolation, tool recovery and
empty retrieval cases. Save its returned profile alongside the existing fixture
paths, bind `cli.config` to the target Workspace, and run it through
`regression_suite.py`. Its three `mock-daily-*` models require the matching
expanded mock scenario fixtures. The profile exercises one authenticated
Workspace; OSS does not support creating a second Workspace. Multiple resources
or group IDs do not establish cross-Workspace isolation.

## Repeating finite scenarios within one budget

Add this to a finite smoke/scenario profile to run its ordered cases repeatedly:

```json
"execution": {
  "total_seconds": 1800,
  "drain_seconds": 120,
  "cooldown_seconds": 60
}
```

Run it with the existing `regression_suite.py run --profile ... --output ...`
entry point. Installation and plugin readiness precede the shared clock; the clock
starts immediately before creating scenario resources. It covers preparation,
case execution, owned-resource cleanup and final quiet sampling. The existing
cleanup policy still applies; use `cleanup: "always"` in disposable deployments
that must clean up after a failed run. Keep an outer process/environment supervisor
as the hard wall-clock backstop: socket timeouts bound individual I/O waits, and
local process termination cannot cancel work already accepted by the server.

Every configured case and group turn is required in the first pass. A shortfall
is `INCOMPLETE` and returns nonzero. Further cycles are optional: admission stops
before the drain/cleanup reserve, including between cases and turns. An unfinished
optional cycle does not fail the run by itself. Each attempted failure/unknown
remains recorded; unknown results stop subsequent cycles after independent cases
in the current cycle finish. Side-effecting requests are never retried. Known
conversation AgentRuns are reconciled again at closeout for unexpected/unfinished
runs. Outcomes without a session identity remain unknown.

`cases.json` retains every attempted row and its cycle number; `cycles.json`
records completion and status per cycle. `execution.json` records stage times.
`resources.jsonl` uses the existing load/cooldown format plus the specific stage;
existing `resource_limits` apply, including failure for missing recovery evidence.
The final summary distinguishes `FAIL` and `INCOMPLETE`; both return nonzero.
The CLI and deployment Job share the same resource cleanup, quiet sampling, final
ledger reconciliation, coverage report and verdict. The Job preserves this
sequence after partial resource preparation; its environment teardown follows
the suite result and its own cleanup policy.
Sampling starts before scenario resource creation, so choose the existing warmup
window to cover the measured preparation and initial case warmup.

Repeated cases create fresh group/conversation identities. The summary records
observed session/run counts and the owned API resource count. History, Box reuse
keys and idle expiry retain their product semantics, so repeated sessions can
intentionally grow stored test data and live sandboxes. Resource budget failures
remain failures; use an explicitly bounded profile when measuring steady reuse.
Cleanup uses only `owned.json` and checks the authenticated Workspace. It does not
delete arbitrary history, files, or containers; the deployment owner handles its
outer teardown. The final quiet period lasts the configured cooldown, bounded by the remaining
total budget. An early abort does not wait out the unused execution budget. Cleanup or drain exceeding its reserved endpoint is a failure.

Finite scenarios record successful request rate and full-step P95 as observations
(the step includes its verification). Load profiles can set
`performance_mode: "observe"` to record throughput and latency while disabling
only configured RPS/P95 thresholds. Business assertions, unresolved results,
health failures, and process/container resource limits still determine success.
The default load mode remains `gate` for existing benchmark users.
