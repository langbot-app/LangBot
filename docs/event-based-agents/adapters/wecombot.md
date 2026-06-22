# WeComBot EBA Adapter

## Status

WeCom AI Bot now has an EBA adapter directory:

```text
src/langbot/pkg/platform/adapters/wecombot/
├── adapter.py
├── api_impl.py
├── event_converter.py
├── manifest.yaml
├── message_converter.py
├── platform_api.py
└── types.py
```

The adapter is registered as `wecombot-eba`.

This is separate from regular WeCom internal applications (`wecom-eba`). WeComBot supports WebSocket long connection mode, which does not require a webhook URL. Webhook mode remains available when `enable-webhook=true`.

## Configuration

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `BotId` | Yes for WebSocket mode | `""` | WeCom AI Bot ID. |
| `robot_name` | Yes | `""` | Bot display name used to strip bot mentions from incoming group text. |
| `enable-webhook` | Yes | `false` | `false` uses WebSocket long connection mode; `true` uses webhook callback mode. |
| `webhook_url` | No | `""` | Unified webhook URL, only needed when webhook mode is enabled. |
| `Secret` | Yes for WebSocket mode | `""` | WeCom AI Bot secret for long connection mode. |
| `Corpid` | Yes for webhook mode | `""` | WeCom corporate ID for webhook callback mode. |
| `Token` | Yes for webhook mode | `""` | WeCom callback token. |
| `EncodingAESKey` | Yes for webhook mode; optional for WebSocket media decrypt | `""` | Message encryption/decryption key. |
| `enable-stream-reply` | No | `true` | Enables WeComBot streaming replies. |

## Events

WeComBot declares these EBA events:

- `message.received`
- `feedback.received`
- `platform.specific`

`message.received` covers private and group messages from the WeComBot SDK. `feedback.received` covers WeComBot like/dislike feedback callbacks. Native SDK events without a common EBA equivalent are emitted as `platform.specific`.

## Common APIs

| API | Status | Notes |
|-----|--------|-------|
| `send_message` | Supported in WebSocket mode | Sends proactive markdown/text to a person or group chat ID. Webhook mode raises `NotSupportedError` because the platform callback flow has no proactive send path here. |
| `reply_message` | Supported | Replies through native `req_id` in WebSocket mode or stream finalization/cache in webhook mode. |
| `get_message` | Supported from cache | Returns cached inbound `MessageReceivedEvent` by message ID. |
| `get_user_info` | Supported from cache | WeComBot events carry user info; no full user lookup endpoint is declared. |
| `get_friend_list` | Partial | Returns users observed by this adapter instance. |
| `get_group_info` | Supported from cache | Returns groups observed from inbound group messages. |
| `get_group_member_info` | Supported from cache | Returns observed sender/group-member pairs. |
| `get_group_member_list` | Partial | Returns observed members for the cached group only. |
| `call_platform_api` | Supported | See below. |
| `edit_message` / `delete_message` / `forward_message` | Not supported | WeComBot does not expose portable common APIs for these operations in the current SDK wrapper. |
| `upload_file` / `get_file_url` | Not supported as common APIs | Media is represented inside messages; no portable standalone file upload/URL API is declared. |
| moderation / leave APIs | Not supported | WeComBot does not expose equivalent common moderation operations through this adapter. |

## Platform-Specific APIs

`call_platform_api(action, params)` supports:

- `is_websocket_mode`
- `get_stream_session_status`
- `send_markdown`

`send_markdown` is only available in WebSocket mode.

## Unit Verification

Covered by:

```bash
PYTHONPATH=/Users/wangqiang/code/python/langbot-plugin-sdk/src uv run pytest tests/unit_tests/platform/test_wecombot_eba_adapter.py
```

The unit tests cover:

- Manifest events/APIs/platform actions match adapter declarations.
- Outbound common components flatten to WeComBot markdown/text.
- Private and group native events become `MessageReceivedEvent`.
- Inbound image, file, voice, and quote components map to common `MessageChain`.
- Legacy `FriendMessage`/`GroupMessage` compatibility.
- EBA listener dispatch, message/user/group/member cache, reply, send, streaming chunk, feedback, and platform API calls.

## Live Probe

The direct adapter probe is:

```bash
PYTHONPATH=/absolute/path/to/langbot-plugin-sdk/src uv run python tests/e2e/live_wecombot_eba_probe.py --help
```

Default mode is WebSocket long connection and requires:

- `WECOMBOT_BOT_ID`
- `WECOMBOT_SECRET`
- `WECOMBOT_ROBOT_NAME`
- optional `WECOMBOT_ENCODING_AES_KEY`

Webhook mode uses `--webhook` and requires:

- `WECOMBOT_TOKEN`
- `WECOMBOT_ENCODING_AES_KEY`
- `WECOMBOT_CORPID`

The probe writes JSONL evidence to `data/temp/wecombot_eba_live_probe.jsonl`, waits for a real WeComBot message, records common EBA event fields and message components, then runs safe cached/common/platform API checks.

## Standalone Runtime Plugin E2E Record

Verified on May 27, 2026 with `EBAEventProbe`, SDK standalone runtime, LangBot core, and the real WeCom desktop client in a WeCom AI Bot private chat.

Evidence:

- JSONL: `data/temp/wecombot_eba_plugin_probe.jsonl`
- Bot UUID: `9f5d4125-7b6d-4c98-8ca2-111111111111`
- Adapter: `wecombot-eba`
- Client: real WeCom desktop client, private `LangBot` BOT chat
- Mode: WebSocket long connection (`enable-webhook=false`)

Observed and verified:

- A real user-side message reached the plugin as `MessageReceived` with `adapter_name=wecombot-eba`, common sender/chat fields, and `Source + Plain`.
- SDK API calls succeeded through the standalone runtime: `get_langbot_version`, `get_bots`, `get_bot_info`, `send_message`, plugin/workspace storage, manifest/list APIs, and safe cached common platform APIs.
- Outbound component sweep was visible in the WeCom client and returned `errcode=0`: plain/mention/face fallback, base64 image marker, quote fallback, file marker, and flattened forward fallback.
- Declared WeComBot platform APIs succeeded through `plugin.call_platform_api`: `is_websocket_mode`, `get_stream_session_status`, and `send_markdown`.
- The `send_markdown` platform API produced visible bot output in the WeCom client.

Not completed:

- Clicking the visible WeCom AI feedback button did not produce a `FeedbackReceived` JSONL entry in this run, so `feedback.received` remains unverified at plugin E2E level.
- Group chat inbound and group cache/member coverage still need a real group-side trigger.
- Real inbound image/file/voice from the WeCom client was not exercised.

## Current Acceptance

Current status is **partial EBA acceptance**.

Blocked or limited items:

- `feedback.received` is implemented and unit-covered, but real plugin E2E feedback evidence was not observed from the desktop client click.
- Outbound image/voice/file are flattened as textual markers because the WeComBot SDK reply/proactive path used here is markdown/text oriented.
- Group member APIs are cache-backed and only know members observed in received messages.
- Destructive or moderation APIs are not declared because the current WeComBot protocol surface does not provide safe common equivalents.
