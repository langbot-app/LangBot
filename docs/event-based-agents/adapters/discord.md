# Discord EBA Adapter

## Status

Discord has been migrated from the legacy source adapter:

```text
src/langbot/pkg/platform/sources/discord.py
src/langbot/pkg/platform/sources/discord.yaml
```

EBA adapter directory:

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

The adapter is registered as `discord-eba`.

## Configuration

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `client_id` | Yes | `""` | Discord application client ID. |
| `token` | Yes | `""` | Discord bot token. |

The bot needs gateway permissions and intents for the target test server. Message Content intent is required for message bodies, Server Members intent is required for member APIs/events, and reaction events require the Reactions intent and channel permissions.

## Events

Discord declares these EBA events:

- `message.received`
- `message.edited`
- `message.deleted`
- `message.reaction`
- `group.member_joined`
- `group.member_left`
- `group.member_banned`
- `bot.invited_to_group`
- `bot.removed_from_group`
- `platform.specific`

Discord-specific events that do not map cleanly to common events should be surfaced as `platform.specific`.

## Common APIs

| API | Status | Notes |
|-----|-----------------|-------|
| `send_message` | Supported | Supports text, image, file, and mixed message chains through Discord messages and attachments. |
| `reply_message` | Supported | Uses Discord message references when replying to a received EBA message event. |
| `edit_message` | Supported | Bot can edit its own messages. File edits are implemented by clearing old attachments and sending replacement files when needed. |
| `delete_message` | Supported | Requires message management permissions for non-bot messages. |
| `forward_message` | Emulated | Discord has no native forward API; the adapter copies content and attachments. |
| `get_group_info` | Supported | Maps Discord guild metadata to EBA group info. |
| `get_group_member_list` | Supported | Requires member cache or the Server Members intent/fetch permission. |
| `get_group_member_info` | Supported | Maps Discord roles/permissions into EBA member roles. |
| `get_user_info` | Supported | Uses Discord user fetch/cache. |
| `upload_file` | Not supported | Discord uploads files as message attachments; standalone upload raises `NotSupportedError`. |
| `get_file_url` | Supported | Discord attachment URLs are already downloadable URLs, so the adapter returns the input URL. |
| `mute_member` | Supported where possible | Uses Discord timeout API and requires guild moderation permission. |
| `unmute_member` | Supported where possible | Clears timeout and requires guild moderation permission. |
| `kick_member` | Supported | Destructive; test only with a disposable account/bot. |
| `leave_group` | Supported | Bot leaves a guild; destructive and should run last. |
| `call_platform_api` | Supported | Discord-specific actions live here. |

## Platform-Specific APIs

`call_platform_api(action, params)` supports:

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

Voice helpers are intentionally kept Discord-specific:

- `join_voice_channel`
- `leave_voice_channel`
- `get_voice_connection_status`
- `list_active_voice_connections`
- `get_voice_channel_info`

## Live Test Record

The live probe is:

```bash
uv run python tests/e2e/live_discord_eba_probe.py --help
```

Verified on May 7, 2026 with a newly created Discord application/bot named `LangBot EBA Test 0507`, the LangBot Discord server, and the `#🐞-debugging` channel:

- SDK standalone runtime started with WebSocket control/debug ports, and the `EBAEventProbe` plugin connected through `lbp run`.
- Plugin runtime received real Discord events through LangBot: `BotInvitedToGroup`, `MessageReceived`, `MessageReactionReceived` add/remove, `MessageEdited`, and `MessageDeleted`.
- Plugin runtime API calls succeeded through the standalone runtime: `get_langbot_version`, `get_bots`, `get_bot_info`, `send_message`, plugin storage APIs, workspace storage APIs, `list_plugins_manifest`, `list_commands`, `list_tools`, and `list_knowledge_bases`.
- Direct live adapter probe observed `message.received`, `message.edited`, `message.deleted`, and `bot.removed_from_group`.
- Message APIs verified: send, reply, edit, delete, forward, text/image/file mixed message chains.
- User and guild APIs verified: `get_user_info`, `get_group_info`, `get_group_member_list`, `get_group_member_info`.
- Platform-specific APIs verified: `get_channel`, `get_guild`, `get_guild_channels`, `get_guild_roles`, `create_invite`, `typing`, `pin_message`, `unpin_message`, `add_reaction`, `remove_reaction`.
- Unsupported API behavior verified: `upload_file` raises `NotSupportedError`.
- Destructive API verified at the end: `leave_group`, which emitted `bot.removed_from_group`.

Not verified in the shared LangBot server live run: `mute_member`, `unmute_member`, and `kick_member`, because the run did not use a disposable target member. They are implemented through Discord timeout/kick APIs and should only be exercised against a disposable account or bot.

The test fixed one real test-fixture issue: `EBAEventProbe` previously assumed `get_bots()` returned UUID strings. The current standalone runtime returns bot dictionaries, so the probe now selects an enabled bot dictionary and passes its `uuid` to `get_bot_info` and `send_message`. The probe also now subscribes to `MessageDeleted`.
