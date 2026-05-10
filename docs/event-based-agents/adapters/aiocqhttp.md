# OneBot v11 / aiocqhttp EBA Adapter

## Status

OneBot v11 has been migrated to the EBA adapter directory:

```text
src/langbot/pkg/platform/adapters/aiocqhttp/
├── adapter.py
├── api_impl.py
├── event_converter.py
├── manifest.yaml
├── message_converter.py
├── platform_api.py
├── types.py
└── onebot.svg
```

The EBA adapter is registered as `aiocqhttp-eba`. The legacy adapter remains at `src/langbot/pkg/platform/sources/aiocqhttp.py`.

## Configuration

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `host` | Yes | `0.0.0.0` | Host for the reverse WebSocket server that the OneBot endpoint connects to. |
| `port` | Yes | `2280` | Reverse WebSocket listen port. |
| `access-token` | No | `""` | OneBot access token, if the endpoint is configured to use one. |

## Events

The adapter declares these EBA events:

- `message.received`
- `message.deleted`
- `group.member_joined`
- `group.member_left`
- `group.member_banned`
- `friend.request_received`
- `friend.added`
- `bot.invited_to_group`
- `bot.removed_from_group`
- `bot.muted`
- `bot.unmuted`
- `platform.specific`

`platform.specific` is used for OneBot notice/request/meta events that do not yet have a common EBA event type, such as group admin changes, group file uploads, pokes, honor changes, and group join requests from non-bot users.

## Common APIs

| API | Status | Notes |
|-----|--------|-------|
| `send_message` | Supported | Supports private and group text, mentions, images, voice, files, faces, and flattened forwards. Group merged forwards are sent through OneBot forward APIs when possible. |
| `reply_message` | Supported | Uses the original OneBot event and can prepend a reply segment. |
| `edit_message` | Not supported | OneBot v11 has no standard message edit action. |
| `delete_message` | Supported | Uses `delete_msg`; permission depends on endpoint and group role. |
| `forward_message` | Supported | Emulates forward by fetching the source message with `get_msg` and sending its content to the target chat. |
| `get_message` | Supported | Uses `get_msg` and converts the response into `MessageReceivedEvent`. |
| `get_group_info` | Supported | Uses `get_group_info`. |
| `get_group_list` | Supported | Uses `get_group_list`. |
| `get_group_member_list` | Supported | Uses `get_group_member_list`. |
| `get_group_member_info` | Supported | Uses `get_group_member_info`. |
| `set_group_name` | Supported | Uses `set_group_name`; may be unsupported by mock endpoints. |
| `get_user_info` | Supported | Uses `get_stranger_info`. |
| `get_friend_list` | Supported | Uses `get_friend_list`. |
| `approve_friend_request` | Supported | Uses `set_friend_add_request`. |
| `approve_group_invite` | Supported | Uses `set_group_add_request` with `sub_type=invite`. |
| `upload_file` | Not supported | OneBot v11 has endpoint-specific file upload extensions but no portable standalone upload action. |
| `get_file_url` | Not supported | OneBot v11 file URL resolution is endpoint-specific. Use `call_platform_api("get_image")`, `get_record`, or endpoint extensions when available. |
| `mute_member` | Supported | Uses `set_group_ban`. |
| `unmute_member` | Supported | Uses `set_group_ban` with duration `0`. |
| `kick_member` | Supported | Destructive; test only with disposable members. |
| `leave_group` | Supported | Destructive; should run last in live tests. |
| `call_platform_api` | Supported | See below. |

## Platform-Specific APIs

`call_platform_api(action, params)` supports:

- `get_login_info`
- `get_status`
- `get_version_info`
- `get_group_honor_info`
- `set_group_card`
- `set_group_special_title`
- `set_group_admin`
- `set_group_whole_ban`
- `send_group_forward_msg`
- `get_forward_msg`
- `get_record`
- `get_image`
- `can_send_image`
- `can_send_record`

## Message Conversion Notes

Incoming OneBot segments are converted into common `MessageChain` components before LangBot core/plugin dispatch:

- `text` -> `Plain`
- `at` -> `At` / `AtAll`
- `image` -> `Image` or `Face` for OneBot emoji-package images
- `record` -> `Voice`
- `file` -> `File`
- `reply` -> `Quote`
- `face`, `rps`, `dice` -> `Face`
- unsupported segments -> `Unknown`

Outgoing `MessageChain` components are converted back into `aiocqhttp.Message` segments. Base64 media strings are normalized to OneBot `base64://...` format.

## Live Test Record

The direct live probe is:

```bash
PYTHONPATH=/Users/qinjunyan/code/projects/langbot/langbot-plugin-sdk/src \
uv run python tests/e2e/live_aiocqhttp_eba_probe.py --host 127.0.0.1 --port 2280
```

It starts the reverse WebSocket adapter directly, records observed EBA events to `data/temp/aiocqhttp_eba_live_probe.jsonl`, waits for a real Matcha or OneBot message, then tries reply/send/get/delete/group/user/platform API calls as far as the endpoint supports them.

Verified on May 10, 2026 with local Matcha connected to `ws://127.0.0.1:2280/ws`:

- Real inbound group message converted to `MessageReceivedEvent`.
- Real lifecycle connection converted to `PlatformSpecificEvent`.
- Real reply API succeeded and rendered a quoted bot reply in Matcha.
- Real proactive send API succeeded and rendered a bot group message in Matcha.
- Real outgoing component sweep succeeded for text, `At`, `AtAll`, `Face`, and base64 `Image`.
- Real `get_message`, `get_group_info`, `get_login_info`, `get_status`, `get_version_info`, `can_send_image`, and `can_send_record` calls succeeded against Matcha.
- Unit conversion and API-shape tests passed for `Plain`, `At`, `AtAll`, `Image`, `Voice`, `File`, `Quote`, `Face`, `rps`, `dice`, `Forward`, `Unknown`, private/group message events, delete notices, group join/leave/ban notices, bot mute notices, friend requests, group invites, friend added notices, dispatch specificity, send, reply, delete, forward, get message, group APIs, user APIs, request approval APIs, moderation APIs, leave group, unsupported file APIs, and all declared `call_platform_api` actions.

Skipped or residual live-test items:

- `edit_message`: not implemented because OneBot v11 has no standard edit action.
- `upload_file` and `get_file_url`: not implemented as common APIs because portable OneBot v11 file upload/download URL semantics are endpoint-specific.
- `kick_member` and `leave_group`: destructive; run only with explicit `--destructive` and disposable Matcha/OneBot state.
- `group.info_updated`, message reactions, and message edits are not declared because OneBot v11 does not provide standard equivalents for them.
- Matcha returned `ActionFailed` for outgoing `File` segment rendering and did not support merged-forward actions in this run. The adapter keeps the conversion/API implementations because they are valid OneBot/NapCat-style capabilities, but the Matcha live probe records them as skipped.
- Matcha returned an empty `get_group_member_list` for the test group, so `get_group_member_info`, mute/unmute, kick, and leave were covered by unit/API-shape tests only in this run.

## Standalone Runtime Plugin E2E Record

Verified on May 10, 2026 with `EBAEventProbe`, SDK standalone runtime, LangBot `--standalone-runtime`, local Matcha, and group `测试群`.

Evidence:

- Plugin JSONL: `data/temp/aiocqhttp-plugin-e2e-20260510-multiformat.jsonl`

Observed and verified:

- A real Matcha group message reached the plugin as `MessageReceived` with `bot_uuid=eba-aiocqhttp-matcha`, `adapter_name=aiocqhttp`, common `Source`/`Plain` message components, common sender, and common group identifiers.
- A protocol-level OneBot reverse WebSocket event reached the plugin as `MessageReceived` with a mixed common chain: `Source`, `Plain`, `At`, `Face`, `Image`, `Voice`, `File`, `Quote`, and trailing `Plain`. This proves the real adapter + LangBot + standalone runtime + plugin path for mixed inbound OneBot payloads, but it was not sent through Matcha UI.
- SDK API calls succeeded: `get_langbot_version`, `get_bots`, `get_bot_info`, `send_message`, plugin storage, workspace storage, `list_plugins_manifest`, `list_commands`, `list_tools`, and `list_knowledge_bases`.
- Outbound component sweep succeeded for plain text plus `At`/`Face`, `AtAll`, base64 `Image`, and quoted reply.
- Common APIs succeeded through the plugin path: `get_message`, `get_user_info`, `get_friend_list`, `get_group_info`, `get_group_list`, `get_group_member_list`, and `get_group_member_info`.
- Safe OneBot platform APIs succeeded through `call_platform_api`: `get_login_info`, `get_status`, `get_version_info`, `can_send_image`, and `can_send_record`.

Documented Matcha limits in this E2E run:

- Matcha UI did not provide a completed image/file upload/send path for inbound media. The rich inbound media evidence is `plugin-e2e-protocol`, not UI-level media upload evidence.
- Outbound `File` failed in Matcha even after the adapter emitted an official `file` segment shape.
- Outbound `Forward` failed because Matcha returned unsupported action for merged-forward.
- `get_group_honor_info` failed because Matcha returned unsupported action.
- Destructive/admin APIs such as mute, unmute, kick, leave, group rename, card/title/admin/whole-ban changes, and request approvals were not run without disposable fixtures.
