# Request-chain acceptance (2026-10-15)

The acceptance suite starts an isolated Core process, a real SDK Plugin Runtime
process, and a packaged Runner plugin. It installs the plugin and creates the
provider, model and Agent through the same authenticated HTTP APIs used by the
application. Agent Debug requests then traverse:

HTTP -> Core Agent orchestration -> Plugin Runtime -> plugin SDK -> Runtime ->
Core model manager/request policy -> LiteLLM/provider SDK -> HTTP/SSE provider.

Assertions cover plugin return values, captured provider requests, TCP disconnects
and persisted SQLite monitoring records. No requester, action transport, model
manager or monitoring implementation is replaced with a mock.

The remote provider is a deterministic local HTTP server. It injects failures and
delays reproducibly; these are real process/network integration tests, **not** a
claim that every external provider has been tested. See the separate
[latency benchmark](LLM_LATENCY_BENCHMARK.md) for the live NewAPI experiment.

## Matrix

Measured results on Windows / Python 3.12.7 / LiteLLM 1.88.1:

- Core with SDK companion commit `c25ff9b`: **31 passed**, strict stream closure,
  including all four historical API cases (106.30 seconds).
- Core with the existing SDK 0.7.11rc5 environment: **27 passed, 4 XFAIL** for
  the reproduced SDK cancellation defect (107.61 seconds).
- Published stable SDK 0.7.11 also reproduced the cancellation defect in the
  preceding 23-case run. The old and stable wrappers were verified identical.
- Focused Core regressions: **371 passed** on Python 3.13.7, ResourceWarnings fatal.
- SDK API and stream flow-control regressions: **507 passed**.
- Existing real Runner discovery/orchestration/event-processor E2E: **3 passed**.

| Area | Cases and evidence |
| --- | --- |
| Public APIs | Runner and invocation-bound plugin APIs: message, message with usage, chunk stream and event stream; unchanged SDK entities and nested usage |
| Historical plugin APIs | Verbatim SDK 0.5.8 proxy and provider-message entities, all four APIs, ordinary calls without `run_id` |
| Request configuration | Persisted defaults, call overrides, OpenAI cache key/retention, OpenRouter numeric reasoning budget and Anthropic cache marker |
| Headers | Explicit application attribution and scoped conversation ID reach the provider |
| Multimodal/tools | Image data URL and function schema survive plugin serialization and provider conversion |
| Retry/failure | 503 then success, `num_retries=0`, `max_retries=0`, 401 without retry, first-event timeout, total timeout, idle timeout and connection loss after content |
| Recovery | Each fault followed by a successful request through the same running processes |
| Cancellation | Early close of Runner and plugin APIs, both chunk and event streams; provider socket closes and the next invocation succeeds |
| Reasoning | Reasoning content shown/hidden with the existing `remove_think` option; unsupported numeric budget rejected before HTTP |
| Monitoring | Full cache/reasoning usage, transport timing and structured errors persisted |

Historical API files come from SDK tag `0.5.8`, commit
`41e320b68e899a7b5e74cb48c5246f6ccbf9d73f`.
They use their own message serializers and the current Runtime transport. This
checks old plugin call/response compatibility; it is not a test of running the
entire old Runtime against the current Core.

## Defects exposed by the full chain

- The plugin bridge flattened model and call policy layers, allowing persisted
  `request_policy.retries` to override a call's legacy zero-retry option. LLM
  policy layers are now resolved separately; unrelated argument merging remains.
- Ordinary plugin calls without a Runner/query returned content but lost usage.
  Core now creates a trusted, invocation-local query for accounting, using the
  existing plugin-action query builder. No public payload/signature changes.
- The shipped OpenRouter requester uses OpenAI metadata. Numeric budgets selected
  the wrong mapping, and LiteLLM's OpenAI chat adapter stripped cache markers.
  OpenRouter chat now uses its own protocol adapter. Embedding/rerank routing is
  unchanged, and a regression test reads the actual shipped requester YAML.
- Published SDK 0.7.11 leaves inner streaming generators unowned in several public
  proxy wrappers. Core's direct TCP close test passes, but the complete plugin
  chain does not promptly cancel its upstream request. The companion
  [SDK PR #177](https://github.com/langbot-app/langbot-plugin-sdk/pull/177) adds
  explicit generator ownership without changing signatures, permissions, action
  payloads or error translation.

**Immediate remote cancellation requires SDK 0.7.12 or later.** Core now pins
published SDK 0.7.12, which contains the companion fix. Separately deployed
Runtime and plugin development environments also need the fixed SDK. The E2E
suite reports the known close failure as XFAIL only for SDK <=0.7.11. Set
`LLM_E2E_REQUIRE_STREAM_CLOSE=1` to require strict passing with the patched SDK;
newer SDK versions must pass without this override. Historical API checks are
explicitly skipped unless their released source files are supplied.

## Reproduction

```sh
python -m pytest tests/e2e/test_llm_request_chain.py -q --tb=short
```

For the historical API matrix, export the two unmodified files below from SDK tag
`0.5.8` into a temporary directory, named `legacy_api.py` and `legacy_message.py`,
then set `LLM_E2E_LEGACY_API_DIR` to its absolute path:

- `src/langbot_plugin/api/proxies/langbot_api.py`
- `src/langbot_plugin/api/entities/builtin/provider/message.py`

For strict cancellation acceptance, install the companion SDK into an isolated
test environment and set `LLM_E2E_REQUIRE_STREAM_CLOSE=1` before running the suite.
The existing CI E2E job discovers this test module automatically. Tests use random
localhost ports, test-only credentials and pytest temporary data directories;
they leave application data and running user instances untouched.

## Limits

The suite does not exercise IM delivery, browser rendering, external provider
authentication/billing, native Anthropic/Gemini network services, Codex OAuth, or
complete third-party Runner business logic. It validates multimodal/tool request
transport rather than image understanding or actual tool execution. Native Codex,
retry, reasoning, transport and plugin regressions also run in the focused Core
test suite. A Python 3.13 Windows full-app attempt timed out during startup before
any LLM request; full process acceptance therefore uses Python 3.12.7, while the
focused Core regressions run on Python 3.13.7.
