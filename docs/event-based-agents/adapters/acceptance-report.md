# EBA Adapter Acceptance Report

Date: May 10, 2026

Scope:

- `telegram-eba`
- `discord-eba`
- `aiocqhttp-eba`

This report follows `acceptance-checklist.md`. The primary evidence is a real SDK plugin, `EBAEventProbe`, running through standalone runtime, LangBot core, the migrated adapter, and a real platform or simulator endpoint.

## Summary

| Adapter | Status | Acceptance summary |
|---------|--------|--------------------|
| Telegram | Accepted with documented platform limits | Private and group `MessageReceived` paths, bot invite event, outbound component sweep, SDK APIs, storage APIs, and Telegram platform APIs were verified through standalone-runtime plugin E2E. Bot API limitations and unsupported common APIs are listed below. |
| Discord | Accepted with documented platform limits | Real Discord server/channel E2E verified `MessageReceived`, common entity conversion, outbound components, SDK APIs, Discord guild/member APIs, and Discord platform APIs. Destructive moderation was not run against the shared server. |
| OneBot v11 / aiocqhttp | Accepted for Matcha-supported capabilities; partial for endpoint-gapped capabilities | Matcha E2E verified message receive, common fields, send, reply, supported outbound components, safe common APIs, safe OneBot platform APIs, and SDK storage/list APIs. Matcha lacks merged-forward, file send, and several destructive/admin fixtures; those remain blocked for that endpoint. |

## Evidence Files

| Adapter | Real endpoint | Evidence |
|---------|---------------|----------|
| Telegram private | Telegram Lite, `@rockchinq_bot` private chat | `data/temp/telegram-plugin-e2e-rerun.jsonl` |
| Telegram group | Telegram Lite, `Rock'sBotGroup` | `data/temp/telegram-plugin-e2e-group.jsonl` |
| Discord | Discord web client, LangBot server, `#🐞-debugging` | `data/temp/discord-plugin-e2e-20260510-final.jsonl` |
| aiocqhttp | local Matcha, group `测试群` | `data/temp/aiocqhttp-plugin-e2e-rerun.jsonl` |

All runs used standalone runtime ports `5400/5401`, LangBot `--standalone-runtime`, and the plugin at `langbot-plugin-demo/EBAEventProbe`.

## Unified Shape Verification

All three adapters deliver common SDK entities to plugins before LangBot core/plugin logic handles the event:

| Requirement | Telegram | Discord | aiocqhttp |
|-------------|----------|---------|-----------|
| `bot_uuid` filled | plugin-e2e: `eba-telegram-live` | plugin-e2e: `eba-discord-live` | plugin-e2e: `eba-aiocqhttp-matcha` |
| `adapter_name` filled | plugin-e2e: `telegram` | plugin-e2e: `discord` | plugin-e2e: `aiocqhttp` |
| common `MessageChain` | plugin-e2e: `At`, `Plain` in group, `Plain` in private | plugin-e2e: `Source`, `Plain` | plugin-e2e: `Source`, `Plain` |
| common user/group entities | plugin-e2e: Telegram user/group IDs and group name | plugin-e2e: Discord user, guild, channel, member count | plugin-e2e: OneBot user, group ID, group name |
| raw native object isolation | plugin-visible behavior used common fields only | plugin-visible behavior used common fields only | plugin-visible behavior used common fields only |

## Message Receive Components

| Component | Telegram | Discord | aiocqhttp |
|-----------|----------|---------|-----------|
| `Source` | supported by event `message_id`; converter does not currently append `Source` to chain, documented design gap | plugin-e2e | plugin-e2e |
| `Plain` | plugin-e2e private/group | plugin-e2e | plugin-e2e |
| `At` | plugin-e2e group mention | unit + supported converter path | unit + supported converter path |
| `AtAll` | not-supported: Telegram has no common broadcast mention object in Bot API messages | unit + supported converter path | unit + supported converter path |
| `Image` | supported by converter; not reproduced in plugin run | supported by converter; outbound plugin rendering verified | supported by converter; outbound plugin rendering verified |
| `Voice` | supported by converter; not reproduced in plugin run | not-supported as native voice message; Discord audio is a file attachment | unit + supported converter path |
| `File` | supported by converter; outbound plugin rendering verified | supported by converter; outbound plugin rendering verified | supported by converter; Matcha file send is blocked |
| `Quote` | supported for replies/outbound quoted send; inbound quote not reproduced | outbound quote verified; inbound structured quote not emitted by Discord | unit + supported converter path |
| `Face` | not-supported as common `Face` in current Telegram adapter | not-supported as common message component | unit + supported converter path |
| `Forward` | not-supported for inbound structured forward | not-supported for inbound structured forward | implemented where endpoint supports forward payloads; Matcha forward action blocked |
| `Unknown` | not reproduced | not reproduced | unit coverage |
| Mixed chain | group `At` + `Plain` plugin-e2e | outbound mixed chain plugin-e2e | outbound mixed chain plugin-e2e |

## Message Send Components

| Component | Telegram | Discord | aiocqhttp |
|-----------|----------|---------|-----------|
| `Plain` | plugin-e2e | plugin-e2e | plugin-e2e |
| `At` | plugin-e2e: group mention text equivalent | plugin-e2e: user mention rendered | plugin-e2e: `@Rock` rendered |
| `AtAll` | plugin-e2e fallback text/equivalent; no native common broadcast object | plugin-e2e: `@everyone` rendered | plugin-e2e: `@全体成员` rendered |
| `Image` | plugin-e2e base64 image | plugin-e2e base64 image | plugin-e2e base64 image |
| `Voice` | not-supported in current send converter | not-supported as native voice; use `File` attachment | supported by converter; not exercised against Matcha |
| `File` | plugin-e2e document send | plugin-e2e attachment send | blocked: Matcha errors on file segment despite official segment shape |
| `Quote` | plugin-e2e quoted reply | plugin-e2e quoted reply | plugin-e2e quoted reply |
| `Face` | not-supported | not-supported | plugin-e2e converter path attempted in `plain_at_face`; Matcha accepts face-like payload path |
| `Forward` | plugin-e2e flattened forward fallback | plugin-e2e flattened forward fallback | blocked: Matcha does not support merged-forward action |
| Mixed chain | plugin-e2e | plugin-e2e | plugin-e2e except Matcha-blocked file/forward |

## Event Acceptance

### Telegram

| Event | Evidence | Notes |
|-------|----------|-------|
| `message.received` | plugin-e2e | Private and group messages reached `EBAEventProbe`. |
| `message.edited` | implemented; not reproduced in current plugin run | Requires user edit fixture. |
| `message.reaction` | implemented; not reproduced in current plugin run | Requires Telegram reaction update fixture. |
| `group.member_joined` | implemented; not reproduced in current plugin run | |
| `group.member_left` | adapter-live historical; not reproduced in current plugin run | |
| `group.member_banned` | adapter-live historical; not reproduced in current plugin run | |
| `bot.invited_to_group` | plugin-e2e | Adding the bot to `Rock'sBotGroup` emitted the event. |
| `bot.removed_from_group` | adapter-live historical; destructive not repeated | |
| `bot.muted` | implemented; blocked without disposable moderation target | |
| `bot.unmuted` | implemented; blocked without disposable moderation target | |
| `platform.specific` | implemented; not reproduced in current plugin run | |

### Discord

| Event | Evidence | Notes |
|-------|----------|-------|
| `message.received` | plugin-e2e | Real web-client message in `#🐞-debugging`. |
| `message.edited` | adapter-live historical; not repeated in final plugin run | |
| `message.deleted` | adapter-live historical; not repeated in final plugin run | |
| `message.reaction` | adapter-live historical; not repeated in final plugin run | |
| `group.member_joined` | blocked | No disposable user/bot join fixture in shared server. |
| `group.member_left` | blocked | No disposable user/bot leave fixture in shared server. |
| `group.member_banned` | blocked | No disposable moderation target. |
| `bot.invited_to_group` | plugin-e2e during OAuth invite | Verified by runtime event in the same run series. |
| `bot.removed_from_group` | blocked/destructive | Not repeated after final invite. |
| `platform.specific` | not reproduced | No unmapped gateway payload triggered in final run. |

### OneBot v11 / aiocqhttp

| Event | Evidence | Notes |
|-------|----------|-------|
| `message.received` | plugin-e2e | Real Matcha group message. |
| `message.deleted` | unit | Matcha recall fixture not available. |
| `group.member_joined` | unit | Matcha fixture not available. |
| `group.member_left` | unit | Matcha fixture not available. |
| `group.member_banned` | unit | Matcha fixture not available. |
| `friend.request_received` | unit | Matcha request fixture not available. |
| `friend.added` | unit | Matcha request fixture not available. |
| `bot.invited_to_group` | unit | Matcha invite fixture not available. |
| `bot.removed_from_group` | unit | destructive fixture skipped. |
| `bot.muted` | unit | Matcha moderation fixture not available. |
| `bot.unmuted` | unit | Matcha moderation fixture not available. |
| `platform.specific` | adapter-live | Lifecycle/meta events observed; plugin run focused on message path. |

## Common API Acceptance

| API | Telegram | Discord | aiocqhttp |
|-----|----------|---------|-----------|
| `send_message` | plugin-e2e | plugin-e2e | plugin-e2e |
| `reply_message` | plugin-e2e via `Quote` send | plugin-e2e via `Quote` send | plugin-e2e via `Quote` send |
| `edit_message` | adapter-live historical | adapter-live historical | not-supported: OneBot v11 has no standard edit |
| `delete_message` | adapter-live historical | adapter-live historical | unit; Matcha destructive skipped |
| `forward_message` | plugin-e2e flattened forward | plugin-e2e flattened forward | blocked: Matcha lacks merged-forward action |
| `get_message` | not-supported in Telegram adapter | not-supported in Discord adapter | plugin-e2e |
| `get_group_info` | plugin-e2e | plugin-e2e | plugin-e2e |
| `get_group_list` | not-supported in Telegram adapter | not-supported in Discord adapter | plugin-e2e |
| `get_group_member_list` | plugin-e2e, administrators/member subset | plugin-e2e | plugin-e2e returned Matcha-supported shape |
| `get_group_member_info` | plugin-e2e | plugin-e2e | plugin-e2e |
| `set_group_name` | platform-specific only | not declared common | blocked: Matcha/admin fixture not used |
| `get_user_info` | plugin-e2e | plugin-e2e | plugin-e2e |
| `get_friend_list` | not-supported | not-supported | plugin-e2e returned `[]` |
| `upload_file` | not-supported | not-supported | not-supported |
| `get_file_url` | implemented; not reproduced in final plugin run | supported URL passthrough; covered by attachment send | not-supported portable common API |
| `mute_member` | blocked without disposable target | blocked without disposable target | blocked without disposable target |
| `unmute_member` | blocked without disposable target | blocked without disposable target | blocked without disposable target |
| `kick_member` | blocked/destructive | blocked/destructive | blocked/destructive |
| `leave_group` | blocked/destructive | blocked/destructive | blocked/destructive |
| `call_platform_api` | plugin-e2e safe Telegram actions | plugin-e2e safe Discord actions | plugin-e2e safe OneBot actions |

## Platform-Specific API Acceptance

| Adapter | plugin-e2e verified | Blocked or not reproduced |
|---------|---------------------|---------------------------|
| Telegram | `get_chat_administrators`, `get_chat_member_count`, `send_chat_action` | `pin_message`, `unpin_message`, `unpin_all_messages`, `set_chat_title`, `set_chat_description`, `create_chat_invite_link`, `answer_callback_query` were not repeated in final plugin run because they are mutating or require callback fixtures. |
| Discord | `get_channel`, `typing`, `get_guild`, `get_guild_channels`, `get_guild_roles` | `create_invite`, `pin_message`, `unpin_message`, `add_reaction`, `remove_reaction` were verified by prior direct live run; final plugin run avoided extra mutation/reaction side effects. |
| aiocqhttp | `get_login_info`, `get_status`, `get_version_info`, `can_send_image`, `can_send_record` | `get_group_honor_info` blocked by Matcha unsupported action; admin/card/title/whole-ban/record/image/forward actions require endpoint support or destructive/admin fixtures. |

## SDK API Acceptance

The EBA probe verified these SDK APIs through standalone runtime on all three platform runs:

- `get_langbot_version`
- `get_bots`
- `get_bot_info`
- `send_message`
- `call_platform_api`
- plugin storage set/get/list/delete
- workspace storage set/get/list/delete
- `list_plugins_manifest`
- `list_commands`
- `list_tools`
- `list_knowledge_bases`

## Residual Risks

- Full event-matrix coverage still needs disposable Telegram/Discord accounts and richer OneBot simulator fixtures for member join/leave/ban, reactions, edit/delete, and request flows.
- Destructive moderation APIs are implemented but intentionally not re-run against shared real groups/servers.
- Matcha is not a complete OneBot v11 endpoint; file and merged-forward failures are endpoint limitations, not accepted as adapter failures.

## Conclusion

Telegram, Discord, and aiocqhttp now have real standalone-runtime plugin E2E evidence for their core EBA migration path and safe API/component surfaces. The adapters are acceptable for the supported capabilities documented here. Items marked `blocked` require disposable users/groups or a more complete simulator before they can be claimed as fully verified.
