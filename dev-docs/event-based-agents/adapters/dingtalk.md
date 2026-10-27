# DingTalk EBA Adapter Migration Record

Status: migrated with partial plugin E2E evidence.

Adapter directory: `src/langbot/pkg/platform/adapters/dingtalk/`

## What Changed

The DingTalk adapter now has an Event-Based Agents adapter package with:

- `manifest.yaml` for adapter metadata, configuration, events, common APIs, and platform-specific APIs.
- `adapter.py` for DingTalk client startup, native callback handling, legacy compatibility, and EBA dispatch.
- `event_converter.py` for native DingTalk events and card callbacks to common EBA events.
- `message_converter.py` for DingTalk message payloads to/from common `MessageChain` components.
- `api_impl.py` for common EBA API implementations.
- `platform_api.py` for DingTalk-specific `call_platform_api` actions.

The legacy DingTalk HTTP client now returns successful JSON response bodies from proactive send methods and raises with response details on non-200 responses.

## Configuration

| Field | Required | Notes |
|-------|----------|-------|
| `client-id` | yes | DingTalk robot/client identifier. |
| `client-secret` | yes | DingTalk client secret. |
| `robot-code` | yes | Robot code used for send APIs. |
| `robot-name` | no | Used for bot mention/self filtering and display. |
| `encrypt-key` | no | DingTalk callback encryption key when configured. |
| `verification-token` | no | DingTalk callback verification token when configured. |

## Supported Events

| Event | Support | Evidence |
|-------|---------|----------|
| `message.received` | implemented | `plugin-e2e-ui` private text and emoji-as-text. |
| `feedback.received` | unit covered | DingTalk card callback actions with feedback-like values (`like`, `dislike`, `cancel`, or `1`/`2`/`3`) map to `FeedbackReceivedEvent`. Other card actions remain `platform.specific`. |
| `platform.specific` | implemented | Non-feedback card callbacks and unmapped callback/message shapes are emitted as structured platform-specific events. |

## Receive Components

| Component | Support | Evidence |
|-----------|---------|----------|
| `Source` | supported | `plugin-e2e-ui` private message. |
| `Plain` | supported | `plugin-e2e-ui` private text. DingTalk emoji currently arrives as plain text such as `[smile]`. |
| `At` | converter path | Group trigger was not completed in the latest run. |
| `AtAll` | fallback/send-side only | Not completed inbound. |
| `Image` | supported | Real DingTalk Mac private-chat image upload reached the plugin as common `Image`. |
| `Voice` | converter path | Real UI inbound voice was not completed. |
| `File` | supported | Real DingTalk Mac private-chat file upload reached the plugin as common `File`. |
| `Quote` | converter path | Real UI inbound quote was not completed. |
| `Face` | not native common mapping | DingTalk emoji was observed as `Plain`, not `Face`. |
| `Forward` | not-supported inbound | DingTalk does not expose a portable structured forward event in this adapter. |

## Send Components

| Component | Support | Evidence |
|-----------|---------|----------|
| `Plain` | supported | `plugin-e2e-outbound`. |
| `At` | supported or text fallback | `plugin-e2e-outbound`. |
| `AtAll` | fallback | `plugin-e2e-outbound`. |
| `Image` | supported | `plugin-e2e-outbound`. |
| `File` | supported | `plugin-e2e-outbound`. |
| `Quote` | fallback | `plugin-e2e-outbound`. |
| `Face` | fallback | `plugin-e2e-outbound` as text fallback. |
| `Forward` | flattened fallback | `plugin-e2e-outbound`. |
| `Voice` | fallback/endpoint-dependent | Not separately verified as a native DingTalk voice send. |

## Common APIs

| API | Support | Notes |
|-----|---------|-------|
| `send_message` | supported | Verified through `EBAEventProbe`. |
| `reply_message` | supported | Verified through quoted/fallback send path. |
| `get_message` | cache-backed | Requires the message to have been observed by this adapter process. |
| `get_group_info` | cache-backed/API-backed where available | Group path not completed in latest UI run. |
| `get_group_list` | supported where DingTalk API allows | Limited live coverage. |
| `get_group_member_info` | supported where DingTalk API allows | Limited live coverage. |
| `get_user_info` | supported | Private sender path verified. |
| `get_friend_list` | limited | DingTalk does not expose a portable friend-list equivalent. |
| `get_file_url` | supported with media/file identifiers | Real inbound file yielded a platform file URL in the converted `File` component. |
| `call_platform_api` | supported | Safe action `check_access_token` verified. |

## Platform-Specific APIs

| Action | Support | Evidence |
|--------|---------|----------|
| `check_access_token` | supported | `plugin-e2e`. |
| `refresh_access_token` | supported | Implemented; not separately reproduced in the latest plugin run. |
| `get_file_url` | supported | Real inbound file yielded a platform file URL in the converted `File` component. |
| `get_audio_base64` | supported | Needs real inbound audio/media ID. |
| `download_image_base64` | supported | Real inbound image reached the plugin as `Image`; separate image-download API replay was not completed. |

## End-to-End Evidence

Evidence files:

- Text/API/component JSONL: `data/temp/dingtalk-plugin-e2e-20260510-rerun.jsonl`
- Real UI inbound media JSONL: `data/temp/dingtalk-plugin-e2e-media-ui.jsonl`

Verified:

- DingTalk Mac private chat in the `LangBot Team` organization produced `MessageReceived` through LangBot standalone runtime and `EBAEventProbe`.
- The common chain was `Source + Plain` for normal text.
- DingTalk emoji was received as `Source + Plain`, not common `Face`.
- Real DingTalk Mac private-chat image upload was received as `Source + Image`.
- Real DingTalk Mac private-chat file upload was received as `Source + File`.
- The plugin sent outbound text, mention/fallback, image, quote/fallback, file, and forward/fallback messages visible in DingTalk.
- The plugin called safe SDK and DingTalk platform APIs.

Not completed:

- Real UI inbound voice.
- Real UI inbound quote.
- Group trigger with a real robot mention.
- Destructive or organization-mutating APIs.
