# EBA Adapter Acceptance Checklist

This checklist is the architecture-level acceptance standard for every Event-Based Agents platform adapter. It is not platform-specific. Adapter migration is not complete until the adapter has a written result against this checklist.

## Evidence Levels

Use these evidence levels consistently in adapter records:

| Level | Meaning | Can Mark Complete |
|-------|---------|-------------------|
| `plugin-e2e-ui` | Real SDK plugin running through standalone runtime, LangBot core, the migrated adapter, and a real platform/simulator UI action. | Yes |
| `plugin-e2e-protocol` | Real SDK plugin running through standalone runtime, LangBot core, and the migrated adapter from a protocol-boundary event injection, such as a OneBot reverse WebSocket event. | Partial; must not be claimed as UI coverage |
| `plugin-e2e-outbound` | Real SDK plugin calls an API and the bot output is visible in the real platform/simulator UI. | Yes for send/API coverage only |
| `adapter-live` | Direct adapter probe connected to a real or simulator platform endpoint, bypassing plugin runtime. | No, auxiliary only |
| `unit` | Unit/API-shape tests with mocked platform SDK objects or mocked APIs. | No, auxiliary only |
| `not-supported` | Platform protocol or SDK has no equivalent capability. Must include reason and source. | Yes, as explicitly unsupported |
| `blocked` | Intended capability could not be verified because of credentials, permissions, endpoint gaps, or simulator gaps. | No |

The primary acceptance path must be `plugin-e2e-ui` for inbound UI-triggered behavior and `plugin-e2e-outbound` for bot send/API behavior. `adapter-live`, `plugin-e2e-protocol`, and `unit` tests are useful, but they must be labelled precisely.

## Required Architecture Path

Every adapter must prove this full path:

```text
Real platform / simulator UI
  -> platform SDK native event
  -> adapter event converter
  -> unified EBA event/entity/message types
  -> LangBot core event dispatch
  -> standalone SDK runtime
  -> real test plugin listener
  -> plugin calls platform APIs through SDK
  -> LangBot core API dispatch
  -> adapter API implementation
  -> real platform / simulator UI
```

The test plugin must record JSONL evidence containing:

- event class and `event.type`
- `bot_uuid` and `adapter_name` as received by the plugin
- adapter name
- chat type and chat ID
- sender/user/group IDs with secrets redacted
- message component list for received messages
- API action name, input summary, result or error
- raw unsupported/blocked reason when an item is skipped

## Required Message Receive Tests

For every adapter, inbound message conversion must be tested through `plugin-e2e-ui` for each component the platform can receive. If a protocol-level injection is used, label it `plugin-e2e-protocol`; it proves the adapter/core/plugin path, but it does not prove that the user-facing platform UI can send that component. If the platform UI/simulator cannot create a component, record it as `blocked` with the endpoint limitation.

| Component | Required Receive Assertion |
|-----------|----------------------------|
| `Source` | Message ID and timestamp are present and stable enough for reply/get/delete APIs. |
| `Plain` | Text is preserved exactly, including spaces and multi-line content. |
| `At` | Mentioned user ID is converted to common `At.target`. |
| `AtAll` | Broadcast mention is converted to common `AtAll`, if platform supports it. |
| `Image` | Image ID, URL, path, or base64 is represented without leaking platform-native segment shape. |
| `Voice` | Voice/audio component is represented as `Voice` when the platform exposes it. |
| `File` | File name, ID/URL, and size are represented as `File` when available. |
| `Quote` | Reply/quote source ID and origin content are represented when the platform exposes it. |
| `Face` | Native emoji/sticker/dice/rps-like components are represented as `Face` or documented as platform-specific. |
| `Forward` | Merged/forwarded messages are represented as `Forward` when the platform exposes structured content. |
| `Unknown` | Unsupported native segments become `Unknown` or `PlatformSpecificEvent` data, not crashes. |
| Mixed chain | A message containing multiple component types preserves order. |

The plugin must subscribe to `MessageReceivedEvent` and assert that `message_chain` contains common `langbot_plugin.api.entities.builtin.platform.message` components, not platform-native SDK objects.

## Required Message Send Tests

For every adapter, outbound message conversion must be tested through `plugin-e2e-outbound` by having the plugin call SDK platform APIs and verifying the platform UI/simulator receives the expected message.

| Component | Required Send Assertion |
|-----------|-------------------------|
| `Plain` | Text appears exactly on the platform. |
| `At` | User mention renders as a mention or platform equivalent. |
| `AtAll` | Broadcast mention renders or is explicitly unsupported. |
| `Image` | URL, path, or base64 image sends and renders/downloads correctly. |
| `Voice` | Voice/audio sends when supported. |
| `File` | File sends with name and content/link when supported. |
| `Quote` | Quoted reply points to the original message when supported. |
| `Face` | Native emoji/sticker/dice/rps sends or is explicitly unsupported. |
| `Forward` | Forward/merged-forward sends when supported; otherwise fallback behavior is documented. |
| Mixed chain | A mixed chain preserves component order as closely as the platform allows. |

If a platform supports a component only in one direction, the adapter record must say so explicitly.

## Required Event Tests

The plugin must subscribe to every event declared in `manifest.yaml -> spec.supported_events` and record one of `plugin-e2e-ui`, `plugin-e2e-protocol`, `not-supported`, or `blocked`.

| Event | Required Assertion |
|-------|--------------------|
| `message.received` | Real message reaches plugin as `MessageReceivedEvent`. |
| `message.edited` | Edited message reaches plugin with message ID and new content, if declared. |
| `message.deleted` | Deleted/recalled message reaches plugin with message ID and operator when available, if declared. |
| `message.reaction` | Reaction add/remove reaches plugin with message ID, user, reaction, and direction, if declared. |
| `feedback.received` | Feedback payload reaches plugin with feedback type and message/session IDs, if declared. |
| `group.member_joined` | Join event reaches plugin with group and member. |
| `group.member_left` | Leave/kick event reaches plugin with group, member, and kick flag. |
| `group.member_banned` | Mute/ban event reaches plugin with group, member, operator, and duration. |
| `group.info_updated` | Group metadata update reaches plugin with changed fields, if declared. |
| `friend.request_received` | Friend request reaches plugin with request ID and message. |
| `friend.added` | Friend-added event reaches plugin. |
| `friend.removed` | Friend-removed event reaches plugin, if declared. |
| `bot.invited_to_group` | Bot invite/join request reaches plugin with group and inviter/request ID. |
| `bot.removed_from_group` | Bot removal reaches plugin with group and operator when available. |
| `bot.muted` | Bot mute reaches plugin with duration. |
| `bot.unmuted` | Bot unmute reaches plugin. |
| `platform.specific` | At least one unmapped native event is delivered as structured platform-specific data, if declared. |

Do not declare an event in the manifest unless there is an implementation path and an acceptance entry.

## Required Common API Tests

The plugin must call every common API declared in `manifest.yaml -> spec.supported_apis.required` and `optional`. Each call must be recorded with input summary and result.

| API | Required Assertion |
|-----|--------------------|
| `send_message` | Plugin sends to private and group/channel targets where supported. |
| `reply_message` | Plugin replies to the triggering message, with quoted mode tested when supported. |
| `edit_message` | Plugin edits a bot-sent message, if declared. |
| `delete_message` | Plugin deletes/recalls a bot-sent message, if declared and permissions allow. |
| `forward_message` | Plugin forwards or emulates forwarding a real message, if declared. |
| `get_message` | Plugin retrieves a real message and receives common `MessageReceivedEvent` shape. |
| `get_group_info` | Plugin receives `UserGroup` with ID/name/count where available. |
| `get_group_list` | Plugin receives joined groups/channels list where supported. |
| `get_group_member_list` | Plugin receives list of `UserGroupMember` where supported. |
| `get_group_member_info` | Plugin receives one member with role/display name where available. |
| `set_group_name` | Plugin changes and restores a disposable group name, if declared. |
| `mute_member` | Plugin mutes a disposable target, if declared. |
| `unmute_member` | Plugin unmutes the same target, if declared. |
| `kick_member` | Plugin kicks a disposable target only in destructive test mode, if declared. |
| `leave_group` | Plugin leaves only in destructive test mode and only at the end, if declared. |
| `get_user_info` | Plugin receives common `User` shape. |
| `get_friend_list` | Plugin receives friend/contact list where supported. |
| `approve_friend_request` | Plugin accepts/rejects a disposable friend request, if declared. |
| `approve_group_invite` | Plugin accepts/rejects a disposable group invite, if declared. |
| `upload_file` | Plugin uploads a real small file, if declared. |
| `get_file_url` | Plugin resolves a real file ID to a URL, if declared. |
| `call_platform_api` | Plugin calls every declared platform-specific action with safe parameters. |

Destructive APIs must be opt-in and documented with the exact target used.

The SDK must expose a plugin-side platform API escape hatch for adapter-specific actions. The acceptance plugin should call it from the same EBA event handler that received the real platform event, so the evidence proves both directions of the path:

```text
plugin -> SDK call_platform_api -> LangBot core -> adapter call_platform_api -> platform SDK/API
```

The result must be serialized into JSON-safe values before it is returned to the plugin runtime.

## Platform-Specific API Tests

Every action listed in `manifest.yaml -> spec.platform_specific_apis` must have one acceptance entry:

- `plugin-e2e-ui` or `plugin-e2e-outbound`: called by the plugin against the live/simulator endpoint.
- `plugin-e2e-protocol`: called by the plugin after a protocol-boundary injected event; useful for endpoint-specific simulators but must be labelled.
- `not-supported`: removed from manifest or explained if the platform SDK exposes it but this adapter intentionally does not.
- `blocked`: endpoint did not implement it, permissions missing, or safe fixture unavailable.

Do not leave a platform-specific API in the manifest without a corresponding test record.

## Required Compatibility Tests

Each migrated adapter must also prove:

- Manifest supported events match `adapter.get_supported_events()`.
- Manifest supported APIs match `adapter.get_supported_apis()`.
- Manifest platform-specific actions match `PLATFORM_API_MAP`.
- Legacy `FriendMessage` / `GroupMessage` listeners still work when the core registers them.
- EBA listener dispatch prefers the most specific event class, then `EBAEvent`, then base `Event`.
- Self-message filtering prevents bot echo loops without dropping edit/delete/moderation events needed for API tests.
- `source_platform_object` is present for reply/debug but not required by plugins for common behavior.

## Required Documentation Per Adapter

Each adapter document must include:

- adapter directory and manifest name
- config table
- supported event table with evidence level per event
- supported common API table with evidence level per API
- platform-specific API table with evidence level per action
- receive component table with evidence level per component
- send component table with evidence level per component
- exact test date
- exact platform endpoint or simulator used
- standalone runtime command
- plugin path/name used for testing
- evidence JSONL path
- destructive operations performed or explicitly skipped
- blocked items and reasons

## Acceptance Rule

An adapter can be marked migrated only when:

1. All declared events have `plugin-e2e-ui`, justified `plugin-e2e-protocol`, or `not-supported` evidence.
2. All declared APIs have `plugin-e2e-outbound` or `not-supported` evidence.
3. All platform-supported receive components have `plugin-e2e-ui` evidence; protocol-only receive coverage keeps the status partial.
4. All platform-supported send components have `plugin-e2e-outbound` evidence.
5. Unit tests cover conversion and API-shape boundaries.
6. The adapter document lists every blocked or skipped item honestly.

If any declared capability is only covered by `adapter-live` or `unit`, the adapter status must remain partial.
