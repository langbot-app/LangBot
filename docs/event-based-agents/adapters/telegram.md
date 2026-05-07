# Telegram EBA Adapter

## Status

Telegram has been migrated to the EBA adapter directory:

```text
src/langbot/pkg/platform/adapters/telegram/
├── adapter.py
├── api_impl.py
├── event_converter.py
├── manifest.yaml
├── message_converter.py
├── platform_api.py
└── types.py
```

The adapter is registered as `telegram-eba`.

## Configuration

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `token` | Yes | `""` | Telegram Bot API token from BotFather. |
| `markdown_card` | No | `true` | Whether to render Markdown card style replies. |
| `enable-stream-reply` | Yes | `false` | Whether to use Telegram streaming reply mode. |

## Events

Telegram declares these EBA events:

- `message.received`
- `message.edited`
- `message.reaction`
- `group.member_joined`
- `group.member_left`
- `group.member_banned`
- `bot.invited_to_group`
- `bot.removed_from_group`
- `bot.muted`
- `bot.unmuted`
- `platform.specific`

`platform.specific` is currently used for Telegram-only callback and chat-member update payloads that do not yet have a more specific common event type.

## Common APIs

| API | Status | Notes |
|-----|--------|-------|
| `send_message` | Supported | Supports text, image, file, and mixed message chains. |
| `reply_message` | Supported | Supports quoted replies through the original message event. |
| `edit_message` | Supported | Uses Telegram message editing APIs. |
| `delete_message` | Supported | Deletes messages where bot permissions allow it. |
| `forward_message` | Supported | Forwards a message between Telegram chats. |
| `get_group_info` | Supported | Uses Telegram chat metadata. |
| `get_group_member_list` | Supported | Telegram only exposes administrators through the Bot API; this returns the available member set. |
| `get_group_member_info` | Supported | Maps Telegram member status to EBA member roles. |
| `get_user_info` | Supported | Uses Telegram `get_chat` for user chat metadata. |
| `upload_file` | Not supported | Telegram has no standalone upload endpoint; files are uploaded as part of messages. The adapter raises `NotSupportedError`. |
| `get_file_url` | Supported | Returns the Bot API file URL. Test output redacts the bot token. |
| `mute_member` | Supported | Requires a supergroup and bot moderation permission. |
| `unmute_member` | Supported | Uses current `telegram.ChatPermissions` fields. |
| `kick_member` | Supported | Destructive; should only be run against disposable users/bots in tests. |
| `leave_group` | Supported | Destructive; should run at the end of a live test. |
| `call_platform_api` | Supported | See below. |

## Platform-Specific APIs

`call_platform_api(action, params)` supports:

- `pin_message`
- `unpin_message`
- `unpin_all_messages`
- `get_chat_administrators`
- `set_chat_title`
- `set_chat_description`
- `get_chat_member_count`
- `send_chat_action`
- `create_chat_invite_link`
- `answer_callback_query`

## Live Test Record

The live probe is:

```bash
uv run python tests/e2e/live_telegram_eba_probe.py --help
```

It supports private chat tests, group/supergroup tests, moderation tests, destructive tests, and a callback-only mode.

Verified on May 7, 2026:

- Private chat message APIs: send, reply, edit, delete, forward.
- Private chat media APIs: image/file sending and `get_file_url`.
- User API: `get_user_info`.
- Supergroup APIs: group info, member list, member info, administrators, member count, invite link.
- Supergroup mutation APIs: pin, unpin, unpin all, set title, restore title, set description, restore description.
- Moderation APIs: mute and unmute against a non-owner target bot.
- Destructive APIs: kick a disposable target bot, then make the test bot leave the test group.
- Event conversion observed for `message.received`, `group.member_banned`, `group.member_left`, `bot.removed_from_group`, and Telegram-specific chat-member updates.

The test fixed one real compatibility issue: `unmute_member` previously used Telegram's removed `can_send_media_messages` permission field. It now uses the split media permission fields required by current `python-telegram-bot`.

## Notes for Future Adapters

Telegram is the reference implementation for:

- Keeping platform-specific actions behind `call_platform_api`.
- Treating unsupported common APIs as explicit `NotSupportedError`.
- Marking destructive live test operations behind CLI flags.
- Redacting access tokens from live probe output.
