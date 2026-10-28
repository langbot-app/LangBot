# LINE Native EBA Adapter

This module implements a **native Event-Based Agent (EBA) platform adapter for [LangBot](https://langbot.app)**,
making LINE one of LangBot's native sources. It wires the LINE Messaging API into LangBot's EBA
abstraction — the `MessageChain` model and the native platform-event dispatch — following the same
adapter shape used by the Telegram / Slack sources.

The design keeps the framework invisible to the platform and the platform pluggable to the framework,
so business logic ports across Telegram / Slack / LINE with minimal change.

## Module layout (`pkg/platform/adapters/line/`)

| File | Responsibility |
|------|----------------|
| `__init__.py` | Package init / plugin manifest |
| `adapter.py` | `LineAdapter` — native event handler, capability declaration, send/reply, `run_async` / `kill` |
| `event_converter.py` | LINE event → EBA payload; `_sdk_to_payload` staticmethod (single SDK normalization boundary) |
| `message_converter.py` | EBA `MessageChain` ↔ LINE payload, bidirectional |
| `send_api.py` | `LineSendApi` (reply / push / flex, expired reply falls back to push) + `RetryPolicy` + Flex card builders |
| `streaming.py` | `LineStreamClient` (WebSocket skeleton) + `LineStreamOutput` (typewriter) |
| `api_impl.py` | SDK call abstraction (`call_platform_api` passthrough) |
| `platform_api.py` | Empty capability mapping (declares only verified capabilities) |
| `errors.py` | `NotSupportedError` (SDK import optional, local fallback) |
| `line_types.py` | Event / payload type contracts |
| `selftest_message_loop.py` | Offline self-test harness |
| `test_*.py` | Domain boxed self-tests (no hard SDK dependency) |

## Inbound flow (LINE → EBA)

```
LINE webhook
  └─ _handle_native_event(raw)
       ├─ _sdk_to_payload(raw)          # single SDK access; needs real-device verification
       ├─ self-message filter (sender.id == bot_account_id)  # avoids reply echoes
       ├─ inject content provider
       └─ LineEventConverter.target2yiri(ev)
            ├─ _convert_message ─▶ MessageChain (LineMessageConverter.target2yiri)
            └─ MessageReceivedEvent ─▶ _dispatch_eba_event ─▶ listener ─▶ EventBus
```

Outbound (bot sends): `send_message` / `reply_message`
→ `LineMessageConverter.yiri2target` → LINE payload → `_sdk_push_message` / `_sdk_reply_message`.

## Capability-declaration boundary

An adapter must **not declare capabilities it has not verified** — a hard rule inherited from
LangBot's source discipline. Unverified events fall back to `platform.specific.*`.

```python
get_supported_events()   # verified events only
get_supported_apis()     # verified APIs only
```

## Self-test

Run offline (no live SDK needed for pure-logic checks), inside the repo environment:

```bash
python -m langbot.pkg.platform.adapters.line.selftest_message_loop
```

The harness exercises non-SDK-dependent pure logic only: `_sdk_to_payload` dict branches,
`target2yiri` bidirectional mapping, and the message converter. The full send/reply path needs the
`line-bot-sdk` present, so run it inside a repo checkout that has the SDK installed.

## Verification status (line-bot-sdk 3.26.0)

The following contract items are implemented against line-bot-sdk 3.26.0. Items marked ⚠️ still need
real-device verification and are annotated in-code as "pending verification" — they are never shipped
as declared capabilities.

1. ✅ `_sdk_to_payload` — staticmethod contract.
2. ✅ `reply_token` — read from the event object's `.reply_token` / `.message.reply_token`.
3. ✅ SDK object access via `.body.events/.destination/.webhookEventId/.sender`.
4. ✅ `_sdk_push_message` / `_sdk_reply_message` map to SDK `LineBotApi.push_message()` / `reply_message()`.
5. ✅ Attachment download via `MessagingApiBlobClient.download_b64(message_content_id)`.
6. ⚠️ SDK client / `WebhookContentProvider` construction — skeleton left in place, needs verification.
7. ⚠️ follow / unfollow / leave / join EBA event mapping — deferred, currently `platform.specific`.

## Notes

- Capabilities are declared only after verification; ⚠️ items stay annotated in-code as pending and
  are never published as declared.
- The offline self-tests carry no hard SDK dependency, so they run in CI without a live LINE connection.
