# MiniMax requester compatibility

Implementation reference: `https://platform.minimax.io/docs/api-reference/text-openai-api.md`
(checked 2026-10-30).

## Discovery and saved configurations

New MiniMax configurations use `https://api.minimax.io/v1`. Saved endpoints and
manually selected model identifiers are not migrated or rewritten.

Direct discovery recommends MiniMax-M3.1-Flash followed by MiniMax-M3, including
when the direct service has no model-list endpoint (404). Authentication,
rate-limit, and server errors still fail the scan. Documented capabilities and
the 1,000,000-token context are defaults for these direct recommendations;
advertised context lengths are retained.

OpenRouter discovery never invents routes or replaces advertised metadata.
All advertised Flash variants precede M3. Only known legacy MiniMax text
families (M1/M2, MiniMax-01, abab) are removed from discovery; non-text entries,
other vendors, custom identifiers, and future model families remain available.
This filtering does not prevent saved/manual legacy models from being invoked.

## Thinking and conversation history

- Flash supports provider defaults, adaptive thinking (`enabled`), and
  `low`, `medium`, `high`, `xhigh`, `max` effort; disabling is rejected locally.
- M3 supports provider defaults, adaptive thinking, and disabled thinking.
- The default policy sends no additional thinking, admission-tier, or
  output-format parameters. Gateway requests keep the existing gateway protocol.
- `remove_think` changes display text, not the assistant history sent back to
  MiniMax. Both `reasoning_content` and the original inline `<think>` content are
  retained, including when the next M3 request disables thinking.

`minimax_raw_content` is internal provider metadata. Non-streaming responses
store their original content before display filtering. Streaming responses
buffer raw content and emit one complete snapshot at the finish event, or at
normal iterator exhaustion when the finish event is absent. This matches Local
Agent's opaque-field replacement semantics: only `reasoning_content` is a
concatenated delta there. Sending raw-content deltas would silently retain only
the last fragment. The internal field is removed during request conversion and
is not replayed as content when the user switches to another provider.

## Regression coverage

`tests/unit_tests/provider/test_minimax_protocol.py` covers real locked SDK
serialization against mocked HTTP/SSE, saved endpoints and identifiers,
thinking validation, image input, discovery failures and metadata, streaming
termination, JSON history round trips, tool follow-ups, and provider switching.
It makes no paid inference calls. The provider suite remains the shared-provider
regression check; Python packaging is independent of frontend/runtime deployment.
