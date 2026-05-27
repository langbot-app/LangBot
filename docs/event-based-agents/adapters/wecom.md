# WeCom EBA Adapter

## Status

WeCom application messages now have an EBA adapter directory:

```text
src/langbot/pkg/platform/adapters/wecom/
├── adapter.py
├── api_impl.py
├── event_converter.py
├── manifest.yaml
├── message_converter.py
├── platform_api.py
└── types.py
```

The adapter is registered as `wecom-eba`.

This record covers the regular WeCom application-message adapter. WeCom AI Bot (`wecombot-eba`) uses a different protocol flow and is documented separately in `wecombot.md`. WeCom Customer Service (`wecomcs`) remains a separate follow-up migration.

## Configuration

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `webhook_url` | No | `""` | Unified webhook URL copied into the WeCom application callback settings. |
| `corpid` | Yes | `""` | WeCom corporate ID. |
| `secret` | Yes | `""` | WeCom application secret. |
| `token` | Yes | `""` | WeCom callback token. |
| `EncodingAESKey` | Yes | `""` | WeCom callback encryption key. |
| `contacts_secret` | No | `""` | Contacts secret for contact-list based helper APIs. |
| `api_base_url` | No | `https://qyapi.weixin.qq.com/cgi-bin` | WeCom API base URL, overrideable for proxy/private-network deployments. |

## Events

WeCom declares these EBA events:

- `message.received`
- `platform.specific`

`message.received` currently covers text and image application callbacks. Other WeCom callback types are surfaced as `platform.specific` so plugins can inspect the raw structured payload without crashing the common message path.

## Common APIs

| API | Status | Notes |
|-----|--------|-------|
| `send_message` | Supported | Private/person target only. `target_id` must be `user_id|agent_id`. Supports text, image, voice, file, flattened forward, and quote fallback. |
| `reply_message` | Supported | Replies to the original WeCom sender and application agent from `source_platform_object`. |
| `get_message` | Supported from cache | Returns cached inbound `MessageReceivedEvent` by message ID. |
| `get_user_info` | Supported | Uses cached event users first, then WeCom `user/get`. |
| `get_friend_list` | Partial | Returns users seen by this adapter instance. Full contacts listing is not declared as common coverage. |
| `call_platform_api` | Supported | See below. |
| `edit_message` | Not supported | WeCom application messages do not expose a general edit endpoint for sent messages. |
| `delete_message` | Not supported | WeCom application messages do not expose a general delete endpoint for sent messages. |
| `get_group_info` / member APIs | Not supported | Regular WeCom application callbacks handled here are private user messages, not group-chat bot messages. |
| `upload_file` / `get_file_url` | Not supported as common APIs | WeCom media upload is used internally while sending image/voice/file components; no portable standalone common file URL is exposed. |

## Platform-Specific APIs

`call_platform_api(action, params)` supports:

- `check_access_token`
- `refresh_access_token`
- `get_user_info`
- `send_to_all`

`send_to_all` requires a configured `contacts_secret` with suitable contact visibility and should be treated as a broad-send operation in live testing.

## Unit Verification

Covered by:

```bash
uv run pytest tests/unit_tests/platform/test_wecom_eba_adapter.py
```

The unit tests cover:

- Manifest events/APIs/platform actions match adapter declarations.
- Outbound component conversion for text, image, voice, file, quote fallback, and byte-safe text splitting.
- Text callback conversion to `MessageReceivedEvent`.
- Legacy `FriendMessage` compatibility.
- EBA listener dispatch and inbound message/user cache.
- `send_message`, `reply_message`, and safe platform API dispatch against a mocked WeCom client.

## Standalone Runtime Plugin E2E Record

Verified on May 27, 2026 with `EBAEventProbe`, SDK standalone runtime, LangBot core, and a real WeCom desktop client against the server test environment.

```bash
cd langbot-plugin-sdk
uv run python -m langbot_plugin.cli.__init__ rt --debug-only --ws-control-port 5400 --ws-debug-port 5401 --skip-deps-check

cd LangBot
uv run main.py --standalone-runtime

cd data/plugins/LangBot__EBAEventProbe
EBA_PROBE_API=1 EBA_PROBE_COMPONENT_SWEEP=1 EBA_PROBE_PLATFORM_API=1 \
uv --project /absolute/path/to/langbot-plugin-sdk run python -m langbot_plugin.cli.__init__ run
```

Evidence:

- JSONL: `data/temp/wecom_eba_plugin_probe.jsonl`
- Bot: `wecom-eba`
- Client: real WeCom desktop client
- Environment: `dev.rockchin.top` test server

Observed and verified:

- A real private WeCom user message reached the plugin as `MessageReceived` with `adapter_name=wecom-eba`, common sender/chat fields, and `Source + Plain`.
- SDK API calls succeeded through the standalone runtime, including `get_langbot_version`, `get_bots`, `get_bot_info`, `send_message`, plugin/workspace storage, and manifest/list APIs.
- Safe adapter API checks succeeded through the plugin path for cached message/user data and declared safe platform API actions.

Still required for stricter acceptance:

- Send a private image and confirm common `Image` reaches the plugin.
- Have the plugin call `send_message` and `reply_message` for text and one media component, then verify the WeCom client receives the bot output.
- Exercise `send_to_all` only with a disposable visible-contact scope.
- Trigger one non-text/image callback, if available, and confirm it becomes `PlatformSpecificEventReceived`.

## Current Acceptance

Current status is **partial EBA acceptance**.

Blocked items:

- Real inbound image/voice/file evidence was not completed in this run.
- Inbound voice/file callback parsing is not present in the legacy `WecomClient.get_message()` path, so the EBA adapter does not claim those receive components yet.
- Group/member/moderation APIs do not apply to this regular WeCom application-message adapter.
