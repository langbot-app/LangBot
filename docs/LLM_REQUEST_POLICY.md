# LLM request policy and diagnostics

The Core owns chat-call deadlines and retry decisions. The existing SDK
`Message`, `MessageChunk`, invoke-with-usage and stream-usage shapes are unchanged.
No SDK or Runner upgrade is required. This policy does not add automatic tool
replay, model fallback, key rotation, or embedding/rerank retries.

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

Timing offsets use a monotonic clock, in milliseconds from invocation start:

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
