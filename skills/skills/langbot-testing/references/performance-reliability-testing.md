# Performance And Reliability Testing

Use this reference when a QA request asks whether LangBot is fast enough,
stable under load, or resilient to controlled faults.

## Scope

Treat `skills/` as the QA control plane:

- Cases define intent, readiness, thresholds, and required evidence.
- Probe scripts collect metrics, traces, resource logs, and artifacts.
- Reports classify the same run as `pass`, `fail`, `blocked`,
  `env_issue`, or `flaky`.

Do not turn `skills/` into a load generator or chaos engine. Call a focused
tool from a `mode: probe` case when the test needs one, for example k6,
Locust, pytest-benchmark, Playwright trace collection, Toxiproxy, Docker, or a
Kubernetes disruption tool.

## LangBot Performance Model

For LangBot, performance is the cost LangBot adds around external systems:

```text
LangBot overhead = end-to-end latency - provider latency - external tool latency - network/fault injection latency
```

Measure user experience and internal composition separately:

- WebUI load and interaction latency.
- Debug Chat send-to-first-visible-token and send-to-completion latency.
- Pipeline, RAG, plugin runtime, MCP, AgentRunner, and persistence segment
  latency.
- Queue wait time, concurrency, throughput, timeout rate, and p95/p99 latency.
- Startup, plugin install, knowledge-base ingestion, migration, and recovery
  time.

Do not report a single message round-trip time as "LangBot performance" unless
the report also explains external provider/tool/network time.

## Evidence Contract

Performance and reliability cases should declare the evidence they need:

- `metrics`: machine-readable latency, throughput, error-rate, or recovery
  metrics, usually `metrics.json`.
- `resource_log`: CPU, memory, process, connection, queue, or file descriptor
  samples.
- `trace`: browser, HTTP, database, or runtime trace artifacts.
- `profile`: CPU, memory, or flamegraph profile artifacts.
- `backend_log`, `network`, `api_diagnostic`, and `filesystem` as supporting
  evidence when relevant.

Automation should write `automation-result.json` with these fields when
available:

```json
{
  "status": "pass",
  "reason": "Probe passed all thresholds.",
  "metrics_summary": {
    "langbot_overhead_p95_ms": 12.4,
    "error_rate": 0
  },
  "thresholds_summary": {
    "langbot_overhead_p95_ms": { "actual": 12.4, "max": 50, "pass": true }
  },
  "artifacts": {
    "metrics_json": "/path/to/metrics.json"
  },
  "evidence_collected": ["metrics", "filesystem"]
}
```

Synthetic contract probes are useful for checking the QA harness, but they are
not live product performance results. Label them as contract probes in the case
title, checks, and report.

## Chaos And Reliability Rules

Chaos tests must be narrow and reversible:

- Declare the fault model in `fault_model_json`.
- Record blast radius, target component, injection method, duration, and abort
  conditions.
- Capture recovery checks and cleanup steps in the case.
- Classify unavailable dependencies as `env_issue` unless the target behavior
  is LangBot's handling of that dependency failure.
- Do not run destructive fault injection against a shared or production-like
  instance without explicit operator approval.

Recommended first fault models:

- Provider timeout or HTTP 429 from a fake provider endpoint.
- Plugin runtime disconnect/reconnect in a local instance.
- MCP stdio server exits mid-call.
- RAG parser fixture fails once and recovers on retry.
- Backend API endpoint returns 5xx from a controlled local proxy.

## Starter Live Probes

The starter gate separates QA-harness contracts from live product checks:

- `langbot-overhead-accounting-contract` verifies that reports can carry
  overhead accounting metrics. It uses deterministic synthetic samples and is
  not live product performance.
- `langbot-fault-taxonomy-contract` verifies that fault scenarios declare
  expected status, recovery, and cleanup before destructive chaos tests are
  added.
- `langbot-live-backend-latency` checks the unauthenticated `/healthz`
  endpoint for basic backend responsiveness.
- `langbot-live-control-plane-api` checks `/healthz` and
  `/api/v1/system/info` for HTTP 200, JSON `code: 0`, response shape, and
  per-endpoint p95 latency.
- `langbot-live-backend-log-health` scans the recent backend log window for
  fail-severity runtime findings. It is the reliability guard that should fail
  the gate when HTTP probes pass but backend logs contain Traceback, ImportError,
  ERROR, unclosed sessions, or unawaited coroutine signals.

Do not treat these starter live probes as Debug Chat or model-provider
performance. They are control-plane readiness checks; user-facing performance
needs browser/WebSocket/message-path measurements.

## Debug Chat Load And Fake Provider Baseline

Use `langbot-fake-provider-debug-chat-load` before real-provider load checks.
The setup automation starts a local OpenAI-compatible fake provider, registers
it as a normal LangBot provider/model, configures a local-agent pipeline, resets
Debug Chat, and then drives concurrent WebSocket messages through the live
backend.

This is not a mocked backend test. It still exercises:

- provider/model persistence and runtime reload;
- LiteLLM OpenAI-compatible requester path;
- local-agent runner selection and pipeline execution;
- Debug Chat WebSocket adapter and broadcast behavior;
- backend concurrency, timeout, and error-rate accounting.

The fake provider is deterministic and can inject controlled latency or faults
with `LANGBOT_FAKE_PROVIDER_*` variables, so it is the baseline for LangBot
message-path overhead. The probe uses unique expected response tokens per
request because Debug Chat broadcasts messages to every connection in the same
session; unique tokens prevent one connection from counting another
connection's response as its own.

After the baseline passes, run `langbot-fake-provider-debug-chat-slow-load` to
keep the same live backend path while injecting deterministic streaming latency.
Run `langbot-fake-provider-debug-chat-fault-recovery` to inject bounded HTTP
provider failures and require both observed failures and later successful
requests. The fault-recovery case is deliberately sequential because failed
Debug Chat responses do not carry a unique success token that can be attributed
to one concurrent connection.

Use `langbot-space-debug-chat-concurrency-smoke` after the fake-provider
baseline. It runs a deliberately small real Space-provider batch and reports
user-visible latency, not pure LangBot overhead. Space/model/network failures
are dependency findings until the fake baseline shows the same symptom.
If a Space smoke passes but log guard finds telemetry posting Tracebacks,
classify that separately as `telemetry-proxy-noise` instead of clearing the
proxy or treating the Debug Chat path as failed.

Useful commands:

```bash
rtk bin/lbs test run langbot-fake-provider-debug-chat-load --run-id langbot-fake-load-local
rtk bin/lbs test run langbot-fake-provider-debug-chat-slow-load --run-id langbot-fake-slow-local
rtk bin/lbs test run langbot-fake-provider-debug-chat-fault-recovery --run-id langbot-fake-fault-local
rtk bin/lbs test run langbot-space-debug-chat-concurrency-smoke --run-id langbot-space-smoke-local
rtk bin/lbs suite run langbot-debug-chat-load-gate --run-id langbot-debug-chat-load-local --include-manual-check
```

## Gate Layers

Use the smallest gate that answers the quality question:

- `langbot-performance-contract-gate`: fast synthetic checks for report shape,
  threshold accounting, and fault taxonomy. Good for PR feedback when no live
  service is running.
- `langbot-live-backend-gate`: live backend `/healthz`,
  `/api/v1/system/info`, and backend log health. Good after starting a local
  LangBot backend.
- `langbot-user-path-performance-gate`: browser-visible user path performance,
  starting with Pipeline Debug Chat send-to-visible-completion latency. Run it
  only when the browser profile and target pipeline are ready.
- `langbot-debug-chat-load-gate`: WebSocket Debug Chat load checks, starting
  with controlled fake-provider baseline, slow-provider, and fault-recovery
  profiles, plus an optional low-volume real Space-provider smoke.
- `langbot-performance-reliability-gate`: combined starter gate for synthetic
  contracts plus live backend checks.

Keep environment diagnostics separate from product regressions. For example, a
SOCKS proxy without Python `socksio` support should be fixed or clearly
classified by `bin/lbs env doctor`; do not hide the resulting backend
Traceback in reports.

## Debug Chat Performance

`pipeline-debug-chat-performance` reuses the browser Debug Chat automation and
adds `metrics.json`, `metrics_summary`, and `thresholds_summary` to
`automation-result.json`.

Current metric:

```text
response_duration_ms = prompt send -> expected assistant response visible and stable
```

This is a user-path metric, not pure LangBot overhead. If it regresses, inspect
provider latency, model route health, plugin/runtime logs, WebSocket behavior,
and browser console/network evidence before attributing the whole duration to
LangBot.

### User-Path Gate Runbook

1. Start the backend and frontend. The frontend must be launched with
   `VITE_API_BASE_URL="$LANGBOT_BACKEND_URL"` so browser API calls reach the
   backend.
2. Run `node scripts/e2e/ensure-local-agent-pipeline.mjs --write-env`. The
   setup refreshes the local QA login, skips the wizard, prepares a Debug Chat
   pipeline, scans Space models, tests candidates, writes tested fallback
   models, and writes the selected pipeline/model env values to
   `skills/.env.local`.
3. If setup returns `env_issue`, read `model_tests` and provider errors first.
   A missing Space key, failed Space scan, or unavailable model route is not a
   LangBot performance regression.
4. Run
   `bin/lbs suite run langbot-user-path-performance-gate --include-manual-check`.
5. Interpret `response_p95_ms` as browser-visible send-to-completion time. It
   includes provider latency; use backend logs and model test evidence to
   separate LangBot overhead from the external model route.

The setup keeps a `max-round` value in the generated pipeline config only
because the current backend truncator still reads that field directly. Do not
use it as a quality requirement for future local-agent behavior.

## Running The First Gate

Start with the reusable suite:

```bash
rtk bin/lbs suite plan langbot-performance-reliability-gate
rtk bin/lbs suite start langbot-performance-reliability-gate --run-id langbot-perf-rel-local
```

Run synthetic contract probes first. Run live probes only after the selected
backend/frontend instance is reachable and the run owner accepts any fault
scope.
