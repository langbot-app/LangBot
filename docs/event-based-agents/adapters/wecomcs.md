# WeCom Customer Service EBA Adapter

## Status

WeCom Customer Service now has an EBA adapter directory:

```text
src/langbot/pkg/platform/adapters/wecomcs/
├── adapter.py
├── api_impl.py
├── event_converter.py
├── manifest.yaml
├── message_converter.py
├── platform_api.py
└── types.py
```

The adapter is registered as `wecomcs-eba`. It is separate from regular WeCom application messages (`wecom-eba`) and WeCom AI Bot (`wecombot-eba`).

## Configuration

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `webhook_url` | No | `""` | Unified webhook URL copied into the WeCom Customer Service callback settings. |
| `corpid` | Yes | `""` | WeCom corporate ID. |
| `secret` | Yes | `""` | Customer Service secret used for access tokens. |
| `token` | Yes | `""` | Customer Service callback token. |
| `EncodingAESKey` | Yes | `""` | Customer Service callback encryption key. |
| `api_base_url` | No | `https://qyapi.weixin.qq.com/cgi-bin` | WeCom API base URL, overrideable for proxy/private-network deployments. |

## Events

| Event | Status | Notes |
|-------|--------|-------|
| `message.received` | Plugin E2E UI covered for text | Text, image, file, and voice payloads convert to common EBA message components in unit tests. Real WeChat customer-side UI text reached `EBAEventProbe` on May 27, 2026. |
| `platform.specific` | Unit covered | Non-message or unknown Customer Service payloads become structured `PlatformSpecificEvent` records. |

## Common APIs

| API | Status | Notes |
|-----|--------|-------|
| `send_message` | Plugin E2E outbound covered | Private/person target only. `target_id` must be `external_userid|open_kfid`. Text and image are implemented; voice/file are explicitly unsupported. |
| `reply_message` | Plugin E2E partial | Replies through Customer Service `kf/send_msg` using the original `source_platform_object`. The pipeline reply path reached the send API, but the dev account later hit WeCom `95001 send msg count limit`. |
| `get_message` | Plugin E2E covered from cache | Returns cached inbound `MessageReceivedEvent` by message ID. |
| `get_user_info` | Plugin E2E covered | Uses cached event users first, then Customer Service `customer/batchget`. |
| `get_friend_list` | Plugin E2E covered, partial | Returns customer users seen by this adapter instance. |
| `call_platform_api` | Unit covered | See platform-specific APIs below. |
| `edit_message` / `delete_message` | Not supported | WeCom Customer Service does not expose a general edit/delete endpoint for bot-sent messages in this adapter. |
| Group/member/moderation APIs | Not supported | Customer Service conversations handled here are private customer sessions, not group chats. |
| `upload_file` / `get_file_url` | Not supported | Media upload is used internally for outbound image; no portable file URL common API is exposed. |

## Platform-Specific APIs

| Action | Status | Notes |
|--------|--------|-------|
| `check_access_token` | Unit covered | Checks whether the current access token is present. |
| `refresh_access_token` | Unit covered | Refreshes the Customer Service access token. |
| `get_customer_info` | Unit covered | Calls Customer Service customer lookup by `external_userid`. |

## Message Components

Receive:

| Component | Status | Notes |
|-----------|--------|-------|
| `Source` | Unit covered | Uses Customer Service `msgid` and `send_time`. |
| `Plain` | Unit covered | Text payload content is preserved. |
| `Image` | Unit covered | Uses the base64 data URL produced by the existing SDK image download path. |
| `Voice` | Unit covered | Maps exposed voice media ID to common `Voice.voice_id`; live UI evidence pending. |
| `File` | Unit covered | Maps exposed file media ID/name/size to common `File`; live UI evidence pending. |
| `Quote`, `At`, `AtAll`, `Face`, `Forward` | Not supported inbound | The current Customer Service SDK event model does not expose these as structured inbound fields. |
| `Unknown` | Unit covered | Unsupported message types become `Unknown` in message conversion or `platform.specific` at event level. |

Send:

| Component | Status | Notes |
|-----------|--------|-------|
| `Plain` | Plugin E2E outbound covered | Sends through `kf/send_msg` text. |
| `Image` | Plugin E2E outbound covered | Uploads media as WeCom image media and sends through `kf/send_msg` image. |
| `Quote`, `At`, `AtAll`, `Forward` | Unit covered fallback, live partially blocked | Flattened to text where possible. In the May 27 sweep, later text sends hit WeCom `95001 send msg count limit` after the successful text/image sends. |
| `Voice`, `File`, `Face` | Not supported | The adapter raises `NotSupportedError`; no tested Customer Service send path is implemented. |

## Unit Verification

Covered by:

```bash
PYTHONPATH=/Users/wangqiang/code/python/langbot-plugin-sdk/src uv run pytest tests/unit_tests/platform/test_wecomcs_eba_adapter.py
```

Result on May 27, 2026: `10 passed`.

The local `PYTHONPATH` is required in this workspace because the installed SDK package in the LangBot venv does not contain the newer `langbot_plugin.api.entities.builtin.platform.errors` module; the existing EBA adapter tests need the same SDK override.

## Live Probe

Auxiliary direct adapter probe:

```bash
PYTHONPATH=/path/to/langbot-plugin-sdk/src uv run python -m py_compile tests/e2e/live_wecomcs_eba_probe.py

WECOMCS_CORPID=... \
WECOMCS_SECRET=... \
WECOMCS_TOKEN=... \
WECOMCS_ENCODING_AES_KEY=... \
PYTHONPATH=/path/to/langbot-plugin-sdk/src \
uv run python tests/e2e/live_wecomcs_eba_probe.py \
  --path /wecomcs/callback \
  --log data/temp/wecomcs_eba_live_probe.jsonl
```

This probe is diagnostic only. Final EBA acceptance still requires the standalone SDK runtime plus `EBAEventProbe` plugin path.

## Standalone Runtime Plugin E2E Record

Completed partial plugin E2E on May 27, 2026 against `dev.rockchin.top` and the WeChat customer-side UI entry `微信 -> 客服消息 -> 浪波智能客服`.

Evidence:

- Server JSONL: `/home/wgc/LangBotxg/LangBotEbaTest/data/temp/wecomcs_eba_plugin_probe.jsonl`
- Trigger text: `EBA wecomcs dedupe probe 2026-05-27`
- `bot_uuid`: `cc810d2c-91f3-4f92-8f27-e1bf9f7b6cb4`
- `adapter_name`: `wecomcs-eba`
- Observed common event: `MessageReceived`, `event.type=message.received`
- Observed message chain: `Source + Plain`
- Observed chat: `chat_type=private`, `chat_id=external_userid|open_kfid`
- Observed sender: customer `User` with nickname/avatar from Customer Service lookup
- Plugin API probe: `send_message`, `get_message`, `get_user_info`, `get_friend_list`, plugin/workspace storage, and manifest/list APIs succeeded
- Component sweep: outbound `Plain` and `Image` succeeded; `Face` and `File` returned explicit `NotSupportedError`; later quote/forward fallback sends were blocked by WeCom `95001 send msg count limit`

Command shape used:

```bash
cd langbot-plugin-sdk
uv run python -m langbot_plugin.cli.__init__ rt --debug-only --ws-control-port 5400 --ws-debug-port 5401 --skip-deps-check

cd LangBot
PYTHONPATH=/absolute/path/to/langbot-plugin-sdk/src uv run main.py --standalone-runtime

cd data/plugins/LangBot__EBAEventProbe
DEBUG_RUNTIME_WS_URL=ws://127.0.0.1:5401/plugin/ws \
EBA_PROBE_LOG=/absolute/path/to/LangBot/data/temp/wecomcs_eba_plugin_probe.jsonl \
EBA_PROBE_API=1 \
EBA_PROBE_COMPONENT_SWEEP=1 \
EBA_PROBE_PLATFORM_API=1 \
uv --project /absolute/path/to/langbot-plugin-sdk run python -m langbot_plugin.cli.__init__ run
```

Required real UI trigger: send a Customer Service message from the WeCom/WeChat customer-side UI to the configured `dev.rockchin.top` Customer Service account.

## Current Acceptance

Current status is **partial EBA acceptance**.

Blocked or pending items:

- Inbound UI media (`Image`, `Voice`, `File`) was not sent from the real WeChat customer UI during this run, so receive-side media remains unit-covered only.
- Pipeline auto-reply reached `kf/send_msg`, but the test account hit WeCom `95001 send msg count limit` after successful plugin outbound text/image sends. This is recorded as an account/platform rate-limit block, not a conversion or API-shape failure.
- The current `EBAEventProbe` run did not call the adapter-specific `call_platform_api` actions (`check_access_token`, `refresh_access_token`, `get_customer_info`); the platform API map remains unit-covered.
- Inbound voice/file depends on whether the real Customer Service callback plus `sync_msg` endpoint returns those fields in the shape the local SDK models.
- Group, member, edit, delete, moderation, and standalone file URL APIs are intentionally not declared because this Customer Service protocol path does not provide tested common equivalents.
