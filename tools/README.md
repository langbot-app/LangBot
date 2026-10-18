# Mock LLM for regression tests

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
with [`regression_profiles/normal.json`](regression_profiles/normal.json), which
defines the chat/Box/RAG mix from the ten-minute trial.

Use a dedicated QA Workspace. First provision the instance with `lbctl install`
or your source deployment, enable Docker Box, start the mock and embedding
backends, and prepare a Workspace-bound `lbctl` config. Set the profile's CLI
config path, backend URLs, and three plugin archive paths. The sample embedding
endpoint must serve `all-MiniLM-L6-v2`; the mock serves generation only. Relative
paths resolve against the profile directory, so adjust them if you move it.

Run on the Linux test host:

```sh
python3 tools/regression_suite.py validate --profile tools/regression_profiles/normal.json
python3 tools/regression_suite.py run \
  --profile tools/regression_profiles/normal.json --output .qa/regression/run-001
```

`validate` checks profile syntax and references without contacting the instance.
The output directory for `run` must be new. CLI options `--duration`, `--rps`, and
`--workers` override those values in every phase. No additional Python dependency
is needed.

The profile controls:

- `plugins`: local archives or GitHub/marketplace request files, installed with
  `lbctl plugin install ... --wait`.
- `resources`: Providers, models, knowledge bases, document ingestion, and
  Pipelines, created in dependency order. `${resource_id}` refers to a UUID
  returned by an earlier creation; `${workspace_uuid}` is the current Workspace.
  Pipeline config patches merge with actual server defaults. Existing resources
  can instead be supplied through `vars`, leaving `resources` empty.
- `cases`: CLI argument arrays and expected business text. Integer `weight`
  values set the mix; `2/1/1/1` means `40/20/20/20`. An optional `body` object
  becomes the case's request file. All workers share the weighted sequence.
- `phases`: each phase has a name, duration, target RPS, worker limit, and optional
  cooldown. Multiple phases provide a step load. In-flight requests drain at the
  end; the concurrency limit can reduce achieved RPS.
- `observe`: health URLs, host PIDs, PID files, and Docker container names/IDs.
  Set PIDs for disjoint process trees to avoid counting descendants twice.
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
  --profile tools/regression_profiles/normal.json --output .qa/regression/run-001
```

Cleanup checks the Workspace against `owned.json` and records remaining items
after partial failures. Keep `owned.json` until cleanup completes. Each run also
contains `profile.json`, resolved `resources.json`, and one directory per phase
with the original request/resource records. The root `summary.json` includes
target/achieved RPS, phase results, threshold failures, and the final verdict.

The `regression_suite.py` entry reuses an existing instance and backend processes.
Use the complete lifecycle Job below to own deployment, credentials and backends.
Cases still use the existing text oracle and new-session CLI entry; continuous
conversations, IM adapter acceptance, and resource-leak verdicts need separate
scenarios. Test the suite plumbing on Linux with:

```sh
python3 -m unittest discover -s tools -p test_regression_suite.py -v
```

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
