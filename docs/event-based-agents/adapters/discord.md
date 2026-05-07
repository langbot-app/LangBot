# Discord EBA Adapter

## Status

Discord is currently being migrated from the legacy source adapter:

```text
src/langbot/pkg/platform/sources/discord.py
src/langbot/pkg/platform/sources/discord.yaml
```

Target EBA directory:

```text
src/langbot/pkg/platform/adapters/discord/
├── adapter.py
├── api_impl.py
├── event_converter.py
├── manifest.yaml
├── message_converter.py
├── platform_api.py
├── types.py
└── voice.py
```

## Configuration

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `client_id` | Yes | `""` | Discord application client ID. |
| `token` | Yes | `""` | Discord bot token. |

The bot needs gateway permissions and intents for the target test server. Message content intent is required for message-based EBA events.

## Planned Events

Initial EBA migration should support:

- `message.received`
- `message.edited`
- `message.deleted`
- `message.reaction`
- `group.member_joined`
- `group.member_left`
- `bot.invited_to_group`
- `bot.removed_from_group`
- `platform.specific`

Discord-specific events that do not map cleanly to common events should be surfaced as `platform.specific`.

## Planned Common APIs

| API | Expected Status | Notes |
|-----|-----------------|-------|
| `send_message` | Supported | Text plus attachment files. |
| `reply_message` | Supported | Uses Discord message references. |
| `edit_message` | Supported | Bot can edit its own messages. |
| `delete_message` | Supported | Requires message management permissions for non-bot messages. |
| `forward_message` | Emulated | Discord has no native forward API; copy content and attachments when possible. |
| `get_group_info` | Supported | Maps Discord guild/channel metadata into EBA group info depending on target ID. |
| `get_group_member_list` | Supported | Requires member cache or guild member fetch permissions. |
| `get_group_member_info` | Supported | Maps Discord roles/permissions into EBA member roles. |
| `get_user_info` | Supported | Uses Discord user fetch/cache. |
| `upload_file` | Not standalone | Discord uploads files as message attachments; standalone upload should raise `NotSupportedError` unless a storage-backed design is added. |
| `get_file_url` | Supported for attachment URLs | Discord attachment URLs are already downloadable URLs. |
| `mute_member` | Supported where possible | Prefer Discord timeout API for guild members. |
| `unmute_member` | Supported where possible | Clears timeout. |
| `kick_member` | Supported | Destructive; test only with a disposable account/bot. |
| `leave_group` | Supported | Bot leaves a guild; destructive and should run last. |
| `call_platform_api` | Supported | Discord-specific actions live here. |

## Planned Platform-Specific APIs

Initial actions to expose through `call_platform_api`:

- `get_channel`
- `get_guild`
- `get_guild_channels`
- `get_guild_roles`
- `create_invite`
- `pin_message`
- `unpin_message`
- `add_reaction`
- `remove_reaction`
- `typing`

Voice actions should stay Discord-specific:

- `join_voice_channel`
- `leave_voice_channel`
- `get_voice_connection_status`
- `list_active_voice_connections`
- `get_voice_channel_info`

## Live Test Plan

Use the LangBot Discord server debug channel for end-to-end verification:

1. Create or reuse a Discord bot application.
2. Invite it to the LangBot server with message, member, reaction, and moderation permissions needed by the test.
3. Run the Discord EBA adapter in standalone test mode.
4. Send a message in the debug channel and verify `message.received`.
5. Verify send/reply/edit/delete/forward message APIs.
6. Verify attachment/file URL behavior.
7. Verify guild/channel/member info APIs.
8. Verify platform-specific APIs such as typing, pin/unpin, invite, reaction.
9. Verify moderation APIs against a disposable target member if available.
10. Run destructive `leave_group` only at the very end or skip it when preserving the server membership matters.
