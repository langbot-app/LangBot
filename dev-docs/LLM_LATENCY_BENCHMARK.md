# LLM request-layer benchmark (2026-10-15)

This controlled test did not reproduce a large LangBot slowdown. Warm request
preparation was sub-millisecond; most measured latency occurred upstream.
It did identify two local transport problems, now fixed in this PR.

## Method

One Windows host, Python 3.12.7, LiteLLM 1.88.1 and OpenCode 2.0.16 used the
same user-provided NewAPI gateway and requested `claude-haiku-4.5`. Each client
made one warmup and six measured streaming calls, alternating all six client
orders. The synthetic system prefix was about 6,000 tokens. Parameters were
`temperature=0`, `max_tokens=256`, `stream=true`, `include_usage=true`, with an
ephemeral cache marker on the system text. No reasoning budget was requested.

The measurement relay deliberately forwards identical serialized requests and
headers for all three clients. It replaces OpenCode's added agent/environment
instructions and normalizes SDK request differences. The canonical SHA-256 is
`7834a66a188e70b4eb1b6234b3a14be4c66b8c72dd8a2c06395fe2505c1c371b`.
OpenCode runs as an isolated resident server, using its
[versioned session API](https://github.com/anomalyco/opencode/blob/v2.0.16/packages/protocol/openapi.json).
Process startup and session creation are outside the warm dispatch measurement.

All clients share the relay's upstream connection pool. Therefore this experiment
isolates local request dispatch and upstream response timing; it does **not**
compare their independent direct-to-provider TLS/proxy behavior. It also excludes
the complete bot pipeline, Runner/plugin RPC and OpenCode UI rendering. It cannot
establish which application is faster in every production deployment.

## Results

Medians, milliseconds; six measured samples per client:

| Client | Dispatch to relay | First content | Complete upstream response |
| --- | ---: | ---: | ---: |
| Direct HTTPX | 3.952 | 1119.541 | 2199.413 |
| LangBot Core requester | 6.802 | 1089.092 | 2135.935 |
| OpenCode | 41.158 | 1104.020 | 2148.265 |

Dispatch includes client preparation and local HTTP dispatch. First content and
completion use the same relay boundary for all clients, measured from dispatch;
they are not UI latency. LangBot's separately instrumented preparation median
was **0.316 ms**, maximum **0.497 ms**. These small samples and upstream variation
do not justify interpreting the small TTFT differences as a speed ranking.

Every measured response reported 5,990 input tokens, 5,987 cache-read tokens and
109 output tokens. This demonstrates equal warm cache accounting under the
normalized upstream request, not native cache-marker forwarding by all clients.
No cache-miss latency comparison or independent provider-route verification was
performed. Missing cache accounting is represented as null, never assumed zero.
The gateway may perform its own routing, retries and cache translation.

Sanitized individual samples and summaries are in
[llm-latency-2026-10-15.json](llm-latency-2026-10-15.json).

## Bottlenecks fixed

1. The OpenAI SDK stops consuming SSE at `[DONE]` before HTTP framing reaches
   EOF. The healthy connection was then discarded. In the baseline relay run,
   LangBot reused zero of six measured client connections; after bounded terminal
   draining it reused six of six. A real TCP regression test also reproduces this
   with split terminal markers and late usage. OpenRouter's generic adapter
   already consumed EOF. Early close and cancellation still close immediately.
2. On this host, constructing default HTTPX clients took 1,761 / 1,443 / 1,435 ms.
   Loading one TLS context per requester pool and sharing it across that client's
   proxy mounts reduced measured pool setup to 666 / 430 / 431 ms. Certificate
   loading now runs off the event loop. These are local setup measurements, not
   a claim of equivalent percentage improvement in LLM latency. Runtime lazy
   initialization and process startup remain separate cold costs.
3. High-resolution monotonic timing replaces the low-resolution clock used on
   Python 3.12 Windows. Preparation no longer misleadingly rounds to zero.
   `transport_setup_ms` exposes pool initialization separately.

The relay socket observations concern client-to-relay connections. HTTPX and
OpenCode have different keepalive policies, so those counts alone are not a
cross-client pooling ranking. The shared relay also prevents quantifying the
provider-side handshake savings from the SSE fix in this run.

## Reproduce

From a development environment with LangBot dependencies installed, set
`LLM_BENCHMARK_API_KEY` securely in the environment, then run:

```sh
python scripts/llm_latency_probe.py --opencode /path/to/opencode \
  --opencode-version 2.0.16 --base-url https://gateway.example/v1 \
  --model claude-haiku-4.5 --long-prefix --cache-control --rounds 6 \
  --output /path/outside/repository/latency.json
```

This makes 21 billable requests by default. `--mock` uses synthetic local SSE
instead; it still needs OpenCode. `--baseline-no-drain` disables terminal draining
for a transport regression comparison. The harness records only hashes and
message sizes, not prompt bodies or credentials, and terminates its own isolated
OpenCode process. Keep raw results outside the repository because they include
the configured gateway URL. Other OpenCode versions may need API adjustments.

The next diagnostic for a reported slow production session should capture the
actual pipeline/Runner timing, streaming mode, prompt size, reasoning settings,
cache usage and gateway routing alongside these requester-level measurements.
