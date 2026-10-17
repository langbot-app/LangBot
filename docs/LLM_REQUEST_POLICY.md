# LLM request policy and diagnostics

The Core owns chat-call deadlines and retry decisions. The existing SDK
`Message`, `MessageChunk`, invoke-with-usage and stream-usage shapes are unchanged.
No SDK or Runner upgrade is required. This policy does not add automatic tool
replay, model fallback, key rotation, or embedding/rerank retries.

The public API remains compatible with existing plugins. Full-chain testing
identified a pre-existing SDK <=0.7.11 early-close defect: prompt remote
cancellation through public plugin/Runner wrappers requires SDK 0.7.12 or later,
which includes the [SDK fix](https://github.com/langbot-app/langbot-plugin-sdk/pull/177).
Core now pins 0.7.12; separately deployed Runtime and plugin development
environments must also install a version containing the fix.
See [E2E acceptance results](LLM_REQUEST_E2E.md) for tested versions and scope.

## Configuration

Instance defaults live in `data/config.yaml` under `llm_request_policy`; restart
Core after editing them. Persist model-specific overrides in the existing model
advanced parameters (`extra_args`). Runners can override them through their
existing call-level `extra_args` argument:

```json
{
  "request_policy": {
    "retries": 1,
    "total_timeout": 180,
    "first_event_timeout": 60,
    "stream_idle_timeout": 45,
    "connect_timeout": 10,
    "read_timeout": 120,
    "write_timeout": 30,
    "pool_timeout": 10,
    "backoff_base": 0.5,
    "backoff_max": 8,
    "attribution": true,
    "conversation_header": null
  }
}
```

Precedence is instance/requester defaults, model extra arguments, then call extra
arguments. Within each layer, `request_policy.retries` overrides legacy
`num_retries` / `max_retries`. Zero disables retries. Legacy numeric `timeout`
sets read, first-event and idle timeouts; it does not extend the total deadline.
Timeouts are positive finite seconds; retries must be an integer from 0 to 5.
Unknown policy keys are rejected. Policy keys are removed before calling upstream.

Default retries are **zero**, total timeout is 300 seconds, and first-event and
idle timeouts are 120 seconds. Retry backoff uses exponential full jitter;
`Retry-After` seconds or HTTP dates are respected only within the remaining total
budget. Quota, authentication and invalid-request failures are not retried.
Core disables both LiteLLM and provider-SDK retries for managed calls. A gateway
may still retry internally; configure its budget separately.

Retries stop after any raw upstream event (including reasoning/control/usage)
or, for legacy adapters without raw instrumentation, the first yielded chunk.
Cancellation is propagated and the owned stream is closed. Total deadlines also
include downstream consumption time, but Core does not cancel a consumer while
the generator is suspended at a yield; expiration is enforced on the next pull.
Transport connect/read/write/pool limits apply to LiteLLM and native Codex HTTP.
Legacy third-party requesters receive Host-level deadlines but remain responsible
for their internal transport configuration and internal retries.

## Diagnostics and usage

HTTP monitoring and `get_monitoring_records(kind="llm_calls")` return additive
`details` containing `timing`, complete provider `usage`, and structured `error`.
Older records have null details. Existing top-level token counters remain intact.
Migration `0038_llm_call_details` adds a nullable JSON column and preserves rows.

Timing offsets use a high-resolution monotonic clock, in milliseconds from invocation start:

| Field | Meaning |
| --- | --- |
| `request_prepared_ms` | First attempt finished building its request |
| `request_started_ms` | First adapter call into the network SDK; not a socket-level timestamp |
| `response_open_ms` | SDK returned a response/stream object |
| `first_event_ms` | First parsed upstream stream event, including reasoning/control |
| `first_reasoning_ms` | First upstream reasoning delta when supported |
| `first_content_ms` | First upstream content delta; inline think tags may still be content |
| `first_visible_chunk_ms` | First nonempty normalized chunk; may include displayed reasoning |
| `response_completed_ms` | Host finished consuming the response |
| `total_ms` | Invocation duration, excluding the subsequent monitoring write |
| `attempts`, `retry_wait_ms` | Host attempts and total backoff wait |
| `preparation_ms` | Cumulative LiteLLM request-building time across attempts |
| `transport_setup_ms` | Cumulative managed HTTP pool acquisition, including first-use TLS setup |
| `preparation_cache_hits` | Message preparation reused within a retrying invocation |

Missing fields mean not observed or not instrumented, not zero latency. The Core
does not label these measurements as network-only TTFT. Usage preserves nested
cache and reasoning counts, costs and provider-specific counters when supplied;
missing upstream accounting cannot be reconstructed. Partial usage received
before cancellation/failure is retained. No fabricated usage event is sent early.

`RequesterError` retains its legacy string representation and adds `code`,
`status_code`, `retryable`, `retry_after`, `request_id`, `phase`, and `as_dict()`.
Native Codex errors retain their existing ValueError/HTTP error contract.
Legacy SDK error transport remains unchanged; structured diagnostics are available
in Core monitoring. The metadata never copies upstream error bodies or headers
wholesale. Requester-specific raw error strings are not included by the LiteLLM
error translator.

## Application and conversation headers

Direct OpenRouter requests automatically receive:

```text
HTTP-Referer: https://langbot.app
X-OpenRouter-Title: LangBot
x-session-id: lb-<opaque scoped hash>
```

Existing headers in model/call `extra_headers` win, case-insensitively. Legacy
`X-Title` is respected. Set `attribution: false` to disable automatic application
attribution (explicit headers remain untouched). Detection uses the exact
`openrouter.ai` hostname, or an OpenRouter requester without an overridden base
URL; arbitrary gateway hosts do not inherit OpenRouter identity headers.

The conversation hash includes Workspace, bot, pipeline and session identity;
it is stable across turns and differs across those scopes. It is pseudonymous,
not a claim of cryptographic anonymization. Calls without conversation context
omit generated conversation headers. No prompt, raw user ID or group ID is sent.

`x-langbot-conversation-id` is a custom convention, **not a documented universal
provider standard**. OpenRouter documents `x-session-id` (or body `session_id`,
which takes precedence). LiteLLM Proxy documents `x-litellm-session-id` and
vendor session headers. Configure `conversation_header` explicitly for gateways:

```json
{
  "request_policy": {"conversation_header": "x-litellm-session-id"},
  "extra_headers": {
    "HTTP-Referer": "https://langbot.app",
    "X-OpenRouter-Title": "LangBot"
  }
}
```

Supported generated header names are `x-session-id`, `x-litellm-session-id` and
`x-langbot-conversation-id`. The latter is intended for a gateway configured to
consume that custom header; do not expect automatic routing or caching benefits.

New API may supply its own OpenRouter attribution and may filter/override client
headers. Configure explicit channel forwarding/override rules and verify the
outgoing request. Sending a header to New API is not proof OpenRouter received it.
The local `langbot-new-api` snapshot inspected during implementation overwrites
attribution with New API; upstream main uses defaults when its outgoing headers
are empty. This change does not modify or deploy either gateway.

Sources checked on 2026-10-15:

- https://openrouter.ai/docs/app-attribution
- https://openrouter.ai/docs/guides/best-practices/prompt-caching
- https://docs.litellm.ai/docs/proxy/request_headers
- https://docs.litellm.ai/docs/routing
- https://github.com/QuantumNous/new-api/blob/main/relay/channel/openai/adaptor.go
- https://github.com/QuantumNous/new-api/blob/main/relay/channel/api_request.go

## Connection and preparation reuse

Initialized OpenAI-compatible, OpenRouter and native Codex requesters own a lazy
HTTP pool per runtime Provider. Keys, headers and timeout budgets stay request-local.
The pool holds at most 100 connections, with 20 idle keepalive connections and a
30-second idle expiry. Provider retirement rejects new leases and closes its pool
after existing streams finish or are cancelled. Native LiteLLM providers retain
their own transport handling; custom LiteLLM transport/TLS settings, explicit caller clients and redirected model routes
are preserved. Bare OpenAI names on OpenRouter retain LiteLLM's alternate routing;
use OpenRouter's fully qualified names such as `openai/gpt-4o`.

Each pool loads its TLS context once in a worker thread, preserving HTTPX
certificate and proxy environment settings. Concurrent initialization is serialized;
cancellation or retirement during certificate loading creates no HTTP client.

OpenAI-compatible streams drain HTTP framing after the SSE `[DONE]` record
(at most 50 ms / 64 KiB) so the SDK can return healthy connections to the pool.
Early close and cancellation never trigger this drain; late usage preceding
`[DONE]` remains available. OpenRouter already consumes EOF in its generic adapter.
Codex briefly drains the HTTP tail after a completion event (at most 50 ms) to
release a healthy connection for reuse. Incomplete/cancelled streams are closed.
Capability lookups use a bounded requester-local cache (128 entries, five minutes).
Message/tool conversion is reused only within an invocation that permits retries,
with independent copies for each attempt. No conversation content is cached across
invocations. Token counting runs in the application's executor instead of blocking
the event loop. These reduce local overhead; they do not guarantee faster upstream
inference or a cache hit.

## Unified thinking budgets

Existing effort levels and Runner/SDK signatures remain unchanged. Model
`reasoning_config` accepts an optional positive integer `budget_tokens`:

```json
{"reasoning_config": {"level": "enabled", "budget_tokens": 2048}}
```

Old SDKs can send the same object inside their existing call `extra_args`.
Precedence is persisted model configuration, model `extra_args.reasoning_config`,
call `extra_args.reasoning_config`, then the existing Runner override. Each object
replaces the previous one; a Runner effort override clears a lower-priority budget.
Omitting `level` with a budget means `enabled`. Budgets cannot be combined with an
effort level, `disabled`, or native thinking arguments. Unsupported budgets fail
before the network call; they are never silently converted into an effort level.

Numeric budgets map to Anthropic `thinking.budget_tokens`, Gemini 2.5 thinking
configuration, supported Qwen `thinking_budget`, or OpenRouter
`reasoning.max_tokens`. Direct OpenAI/Codex and adaptive-only Claude models keep
effort-based control. Query `reasoning_capabilities.budget_tokens` for the Core's
accepted bounds; upstream models/gateways may impose additional limits. OpenRouter
may translate numeric budgets to effort for models without native numeric support.
Direct Anthropic calls require an explicit `max_tokens` greater than the budget;
Core never silently raises the output limit. Existing UI effort selectors are
unchanged; numeric budgets can be configured through the model API or extra args.

## Prompt caching

Default behavior remains provider-controlled. `extra_args.prompt_caching` is a
Core-only object and is stripped before sending the request. Call-level objects
replace model-level objects. There is no local generated-response cache.

```json
{"prompt_caching": {"mode": "openai", "retention": "in_memory"}}
```

OpenAI mode adds an opaque conversation-and-model-scoped `prompt_cache_key` when
conversation context exists. `retention` is optional (`in_memory` or `24h`) and
must be supported by the destination model/gateway. Native explicit
`prompt_cache_key`, `prompt_cache_retention`, and newer `prompt_cache_options`
take precedence. Routing keys are hints, not cache-hit guarantees; current models
may route caching automatically or use newer native options instead. This mode
supports OpenAI-compatible/OpenRouter OpenAI models; forwarding through gateways
must be verified separately.

```json
{"prompt_caching": {"mode": "anthropic", "ttl": "5m"}}
```

Anthropic mode supports native Claude and OpenRouter Claude. It adds one ephemeral
breakpoint to the last text block in the leading system/developer prefix, without
reordering tools/history or marking user messages. TTL is `5m` (default) or `1h`.
If any native cache-control marker exists, Core preserves it without adding more.
With no eligible prefix, no marker is inserted. Provider minimum prefix lengths,
TTL pricing and eligibility still apply. Explicit `provider_default` adds no fields.
Codex's restricted Responses body does not accept this caching object; its existing
server-managed caching behavior is preserved. Gemini explicit cache resource
creation/lifecycle and general Responses migration are outside this batch.

References checked on 2026-10-15:

- https://developers.openai.com/api/docs/guides/prompt-caching
- https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- https://platform.claude.com/docs/en/build-with-claude/extended-thinking
- https://ai.google.dev/gemini-api/docs/generate-content/thinking
- https://openrouter.ai/docs/guides/best-practices/reasoning-tokens

See [the latency benchmark](LLM_LATENCY_BENCHMARK.md) for measured results and limitations.
