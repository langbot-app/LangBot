# KOOK EBA Adapter

## Status

KOOK has been migrated to the EBA adapter directory:

```text
src/langbot/pkg/platform/adapters/kook/
├── adapter.py
├── api_impl.py
├── event_converter.py
├── manifest.yaml
├── message_converter.py
├── platform_api.py
└── types.py
```

The adapter is registered as `kook-eba`.

## Configuration

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `token` | Yes | `""` | KOOK bot token. |
| `enable-stream-reply` | Yes | `false` | Reserved for shared platform configuration compatibility. |

## Events

| Event | Evidence | Notes |
|-------|----------|-------|
| `message.received` | `plugin-e2e-ui` | Real KOOK UI channel message reached `EBAEventProbe` as `MessageReceivedEvent`. |
| `platform.specific` | `plugin-e2e-ui` | KOOK gateway event without a common EBA mapping reached `EBAEventProbe` as `PlatformSpecificEventReceived`. |

## Common APIs

| API | Evidence | Notes |
|-----|----------|-------|
| `send_message` | `plugin-e2e-outbound` | Probe plugin sent channel messages through SDK `send_message`; KOOK returned message IDs. |
| `reply_message` | `unit` | Supports `reply_msg_id` and optional quoted replies when the source message ID is available. |
| `get_message` | `plugin-e2e-outbound` | Probe plugin fetched the cached triggering message. |
| `get_group_info` | `plugin-e2e-outbound` | Probe plugin received cached KOOK channel info. |
| `get_group_list` | `plugin-e2e-outbound` | Probe plugin received cached channel/group entities observed by the adapter. |
| `get_group_member_info` | `plugin-e2e-outbound` | Probe plugin received cached sender info as a group member. |
| `get_user_info` | `plugin-e2e-outbound` | Probe plugin received cached sender user info. |
| `get_friend_list` | `plugin-e2e-outbound` | Probe plugin received cached users. |
| `upload_file` | `unit` | Uses KOOK `asset/create` and returns URL/ID. |
| `get_file_url` | `unit` | KOOK media IDs are URL-like in the adapter path; returns the ID unchanged. |
| `delete_message` | `unit` | Calls KOOK delete endpoints. Live permission verification is still required. |
| `forward_message` | `plugin-e2e-outbound` | Probe plugin sent flattened forward content through SDK `send_message`. |
| `call_platform_api` | `plugin-e2e-outbound` | Probe plugin called safe KOOK platform-specific APIs through SDK `call_platform_api`. |

## Platform-Specific APIs

| Action | Evidence | Notes |
|--------|----------|-------|
| `get_current_user` | `plugin-e2e-outbound` | Probe plugin called `user/me`. |
| `get_user` | `plugin-e2e-outbound` | Probe plugin called `user/view` for the triggering sender. |
| `get_channel` | `plugin-e2e-outbound` | Probe plugin called `channel/view` for the triggering channel. |
| `get_guild` | `plugin-e2e-outbound` | Probe plugin called `guild/view`; gateway URLs redact token query values. |
| `get_gateway` | `plugin-e2e-outbound` | Probe plugin called `gateway/index`; returned token query values are redacted. |
| `send_direct_message` | `unit` | Calls `direct-message/create`. |

## Components

| Component | Receive Evidence | Send Evidence | Notes |
|-----------|------------------|---------------|-------|
| `Source` | `plugin-e2e-ui` | N/A | KOOK message ID and timestamp are preserved. |
| `Plain` | `plugin-e2e-ui` | `plugin-e2e-outbound` | Text and KMarkdown are represented as plain common text. |
| `At` | `plugin-e2e-ui` | `plugin-e2e-outbound` | KOOK `(met)<id>(met)` mentions map to common `At`. |
| `AtAll` | `unit` | `plugin-e2e-outbound` | KOOK `(met)all(met)` maps to common `AtAll`; real inbound UI AtAll was not tested. |
| `Image` | `unit` | `unit` | URL/image ID based path only; live rendering still needs verification. |
| `Voice` | `unit` | `unit` | URL based path only; live rendering still needs verification. |
| `File` | `unit` | `unit` | URL based path only; upload API is exposed separately. |
| `Forward` | `unit` | `unit` | Outbound forwards are flattened; inbound structured forwards are not exposed by current legacy implementation. |
| `Unknown` | `unit` | N/A | Unsupported KOOK message types become `Unknown` or `PlatformSpecificEvent`. |

## Acceptance Record

Test date: June 4, 2026.

Plugin E2E verified on June 4, 2026 with `EBAEventProbe`, SDK standalone runtime, KOOK WebSocket adapter, and a real KOOK channel UI message.

Evidence:

- JSONL: `data/temp/kook_eba_plugin_probe.jsonl`
- Plugin log: `data/logs/eba-probe-kook.log`

Observed and verified:

- A real KOOK UI channel message reached the plugin as `MessageReceived` with `bot_uuid=7ab5b065-6e4e-4def-95f0-3c265366e26f`, `adapter_name=kook`, common sender/group/chat fields, and common `MessageChain` components.
- KOOK gateway-specific event reached the plugin as `PlatformSpecificEventReceived`.
- Probe plugin called SDK `send_message`; KOOK returned message IDs for text, At, AtAll, image URL/base64 fallback path, quote fallback, file fallback, and flattened forward cases.
- Probe plugin called common API methods through the SDK path: `get_message`, `get_user_info`, `get_friend_list`, `get_group_info`, `get_group_list`, and `get_group_member_info`.
- Probe plugin called safe KOOK platform-specific APIs through SDK `call_platform_api`: `get_current_user`, `get_user`, `get_channel`, `get_gateway`, and `get_guild`.

Run:

```bash
uv run pytest tests/unit_tests/platform/test_kook_eba_adapter.py
git diff --check
```

Blocked or partial items:

- `plugin-e2e-ui` inbound coverage for image, file, voice, AtAll, quote, and forward.
- `plugin-e2e-outbound` visual verification in KOOK UI for image/file/voice rendering. KOOK returned message IDs, but UI inspection was not performed in this run.
- `reply_message` and `delete_message` live permission verification.
- Destructive or permission-sensitive APIs were not declared beyond delete; KOOK mute/kick/leave remain explicit `NotSupportedError` paths until a safe fixture is available.
