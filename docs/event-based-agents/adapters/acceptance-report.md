# EBA Adapter Acceptance Report

Date: May 10, 2026

Scope:

- `telegram-eba`
- `discord-eba`
- `aiocqhttp-eba`

This report applies the architecture-level checklist in `acceptance-checklist.md`. It intentionally separates implementation support from acceptance evidence. A capability is complete only when it has `plugin-e2e` evidence or is explicitly `not-supported`.

## Summary

| Adapter | Current Acceptance Status | Reason |
|---------|---------------------------|--------|
| Telegram | Partial | The adapter has implementation and direct live-probe evidence, but the current record does not show full standalone-runtime plugin evidence for all declared events, APIs, and message components. |
| Discord | Partial | The record includes standalone-runtime plugin evidence for core event flow and some SDK APIs, plus direct adapter live evidence for platform APIs. It still lacks per-component plugin evidence and plugin evidence for all declared platform APIs/destructive APIs. |
| OneBot v11 / aiocqhttp | Partial | The adapter has unit coverage and Matcha direct live-probe evidence, but no standalone-runtime plugin evidence yet. |

None of the three adapters should be marked fully accepted under the new checklist until the missing `plugin-e2e` items below are completed.

## Evidence Legend

| Value | Meaning |
|-------|---------|
| `plugin-e2e` | Verified through real SDK plugin, standalone runtime, LangBot core, adapter, and platform/simulator endpoint. |
| `adapter-live` | Verified through a direct adapter probe connected to platform/simulator endpoint. Auxiliary only. |
| `unit` | Verified by unit/API-shape tests. Auxiliary only. |
| `implemented` | Code path exists, but current evidence is not enough for acceptance. |
| `not-supported` | Platform or protocol has no portable equivalent. |
| `blocked` | Intended test could not be completed with current fixture/simulator/permission. |

## Message Receive Components

| Component | Telegram | Discord | OneBot v11 / aiocqhttp |
|-----------|----------|---------|-------------------------|
| `Source` | blocked: event has `message_id`/timestamp, but converter does not emit `Source` in `message_chain`; needs implementation or explicit design exception. | unit: Discord converter emits `Source`; needs plugin-e2e evidence. | unit + adapter-live: converter emits `Source`; Matcha inbound text produced source data in JSONL; needs plugin-e2e evidence. |
| `Plain` | adapter-live: text receive verified in prior live probe; needs plugin-e2e evidence. | plugin-e2e for message receive; per-component assertion still needs JSONL checklist entry. | adapter-live: Matcha inbound text converted to `Plain`; needs plugin-e2e evidence. |
| `At` | implemented: bot username mention maps to `At`; needs plugin-e2e evidence and mention fixture. | unit: Discord mentions map to `At`; needs plugin-e2e evidence. | unit: OneBot `at` maps to `At`; needs plugin-e2e inbound mention evidence. |
| `AtAll` | not-supported/blocked: Telegram has no direct `AtAll` common equivalent in current converter. Needs explicit final classification. | unit: `@everyone`/`@here` map to `AtAll`; needs plugin-e2e evidence. | unit: OneBot `qq=all` maps to `AtAll`; needs plugin-e2e evidence. |
| `Image` | adapter-live: image receive covered by direct probe; needs plugin-e2e evidence. | unit: image attachment maps to `Image`; needs plugin-e2e evidence. | unit: OneBot image maps to `Image`; needs plugin-e2e image receive evidence. |
| `Voice` | implemented: Telegram voice maps to `Voice`; needs plugin-e2e evidence. | not-supported for native voice message; Discord audio files are files/attachments, not a voice-message component. | unit: OneBot `record` maps to `Voice`; needs plugin-e2e evidence. |
| `File` | adapter-live: file receive/send covered by direct probe; needs plugin-e2e evidence. | unit: non-image attachment maps to `File`; needs plugin-e2e evidence. | unit: OneBot file maps to `File`; Matcha file send failed, inbound file still needs plugin-e2e or blocked reason. |
| `Quote` | implemented through reply API, but inbound quote conversion is not shown in current record. Needs plugin-e2e or unsupported classification. | implemented by message reference for reply send; inbound quote component is not currently produced. Needs classification. | unit: OneBot `reply` maps to `Quote`; needs plugin-e2e evidence. |
| `Face` | not-supported: Telegram native emoji/stickers are not mapped to `Face` in current adapter. | not-supported: Discord emoji/reactions are events or text/attachments, not `Face` components in current adapter. | unit: OneBot `face`/`rps`/`dice` map to `Face`; needs plugin-e2e inbound evidence. |
| `Forward` | not-supported for inbound structured forward in current adapter. | not-supported for inbound structured forward; Discord has no common native forward object. | implemented for outgoing merged/flattened forward; inbound structured forward needs plugin-e2e or blocked classification. |
| `Unknown` | blocked: no current plugin evidence for unsupported native message segments. | blocked: no current plugin evidence for unsupported native message segments. | unit: unsupported segment maps to `Unknown`; needs plugin-e2e/simulator evidence. |
| Mixed chain | adapter-live for text/media send; receive mixed-chain plugin evidence missing. | adapter-live for mixed send; receive mixed-chain plugin evidence missing. | unit + adapter-live for mixed outgoing text/mentions/face/image; plugin evidence missing. |

## Message Send Components

| Component | Telegram | Discord | OneBot v11 / aiocqhttp |
|-----------|----------|---------|-------------------------|
| `Plain` | adapter-live; needs plugin-e2e. | plugin-e2e/direct live for send; needs per-component JSONL assertion. | adapter-live through Matcha; needs plugin-e2e. |
| `At` | not implemented in current Telegram send converter; should be unsupported or implemented before acceptance. | unit + direct live support through mention text; needs plugin-e2e. | unit + adapter-live rendered `@Rock`; needs plugin-e2e. |
| `AtAll` | not implemented in current Telegram send converter; should be unsupported or implemented before acceptance. | unit support for `@everyone`; needs plugin-e2e. | unit + adapter-live rendered `@全体成员`; needs plugin-e2e. |
| `Image` | adapter-live; needs plugin-e2e. | adapter-live/unit; needs plugin-e2e. | unit + adapter-live rendered base64 image in Matcha; needs plugin-e2e. |
| `Voice` | not implemented for Telegram send converter; current adapter only sends text/photo/document. Needs implementation or unsupported classification. | implemented as file attachment; needs plugin-e2e evidence or unsupported classification as native voice. | unit support; needs plugin-e2e; Matcha not yet verified for outgoing voice. |
| `File` | adapter-live; needs plugin-e2e. | adapter-live/unit; needs plugin-e2e. | implemented/unit, but Matcha returned `ActionFailed`; classify blocked for Matcha and test against capable endpoint. |
| `Quote` | supported by `reply_message`; needs plugin-e2e quoted-send assertion. | supported by `reply_message` references; needs plugin-e2e quoted-send assertion. | adapter-live quoted reply rendered in Matcha; needs plugin-e2e. |
| `Face` | not-supported/not implemented in current Telegram converter. | not-supported/not implemented as message component. | unit + adapter-live rendered face payload; needs plugin-e2e and final rendering assertion. |
| `Forward` | implemented by flattening nodes into send components; needs plugin-e2e or explicit fallback classification. | implemented by flattening node content; needs plugin-e2e or explicit fallback classification. | implemented; Matcha does not support merged-forward action, so blocked with Matcha; needs capable endpoint or fallback acceptance. |
| Mixed chain | adapter-live partial; needs plugin-e2e. | adapter-live partial; needs plugin-e2e. | adapter-live partial; needs plugin-e2e. |

## Declared Event Acceptance

### Telegram

| Event | Support Explanation | Current Evidence |
|-------|---------------------|------------------|
| `message.received` | Implemented for text/photo/voice/document updates. | adapter-live; plugin-e2e missing. |
| `message.edited` | Implemented from `edited_message`. | adapter-live record does not explicitly prove plugin-e2e. |
| `message.reaction` | Implemented from Telegram reaction update. | plugin-e2e missing. |
| `group.member_joined` | Implemented from chat member status transition. | plugin-e2e missing. |
| `group.member_left` | Implemented from chat member status transition. | adapter-live observed member-left/bot-removed path; plugin-e2e missing. |
| `group.member_banned` | Implemented for restricted/kicked style member update. | adapter-live observed ban/mute path; plugin-e2e missing. |
| `bot.invited_to_group` | Implemented from bot member status update. | plugin-e2e missing. |
| `bot.removed_from_group` | Implemented from bot member status update. | adapter-live observed; plugin-e2e missing. |
| `bot.muted` | Implemented from bot restricted status. | plugin-e2e missing. |
| `bot.unmuted` | Implemented from bot unrestricted status. | plugin-e2e missing. |
| `platform.specific` | Implemented for callback/unknown updates. | adapter-live record mentions Telegram-specific updates; plugin-e2e missing. |

### Discord

| Event | Support Explanation | Current Evidence |
|-------|---------------------|------------------|
| `message.received` | Implemented from Discord `on_message`. | plugin-e2e observed. |
| `message.edited` | Implemented from edit gateway event. | plugin-e2e observed. |
| `message.deleted` | Implemented from cached/raw delete gateway events. | plugin-e2e observed after probe subscribed to delete. |
| `message.reaction` | Implemented for add/remove and raw reactions. | plugin-e2e observed add/remove. |
| `group.member_joined` | Implemented from member join. | current record does not show plugin-e2e observed. |
| `group.member_left` | Implemented from member remove. | current record does not show plugin-e2e observed. |
| `bot.invited_to_group` | Implemented from guild/member join. | plugin-e2e observed bot invited/joined. |
| `bot.removed_from_group` | Implemented from guild remove. | adapter-live observed through destructive leave; plugin-e2e status unclear. |
| `platform.specific` | Declared for Discord-specific gateway payloads. | plugin-e2e evidence missing. |

### OneBot v11 / aiocqhttp

| Event | Support Explanation | Current Evidence |
|-------|---------------------|------------------|
| `message.received` | Implemented for private and group OneBot messages. | adapter-live with Matcha; plugin-e2e missing. |
| `message.deleted` | Implemented for group/friend recall notices. | unit only. |
| `group.member_joined` | Implemented from `group_increase`. | unit only. |
| `group.member_left` | Implemented from `group_decrease`. | unit only. |
| `group.member_banned` | Implemented from non-bot `group_ban`. | unit only. |
| `friend.request_received` | Implemented from friend request. | unit only. |
| `friend.added` | Implemented from `friend_add`. | unit only. |
| `bot.invited_to_group` | Implemented from group invite request or bot group increase. | unit only. |
| `bot.removed_from_group` | Implemented from bot group decrease. | unit only. |
| `bot.muted` | Implemented from bot group ban duration > 0. | unit only. |
| `bot.unmuted` | Implemented from bot group ban duration = 0. | unit only. |
| `platform.specific` | Implemented for meta/unmapped notice/request events. | adapter-live observed lifecycle; plugin-e2e missing. |

## Declared Common API Acceptance

### Telegram

| API | Support Explanation | Current Evidence |
|-----|---------------------|------------------|
| `send_message` | Supports text, image, file; does not currently send `At`, `AtAll`, `Voice`, or `Face` as common components. | adapter-live; plugin-e2e missing. |
| `reply_message` | Supports replies through original update and quoted mode. | adapter-live; plugin-e2e missing. |
| `edit_message` | Supports text edit. | adapter-live; plugin-e2e missing. |
| `delete_message` | Uses Telegram delete API. | adapter-live; plugin-e2e missing. |
| `forward_message` | Uses Telegram forward API. | adapter-live; plugin-e2e missing. |
| `get_group_info` | Uses Telegram chat metadata. | adapter-live; plugin-e2e missing. |
| `get_group_member_list` | Returns administrators only, due Telegram Bot API limitation. | adapter-live; needs explicit plugin-e2e/limitation evidence. |
| `get_group_member_info` | Uses `get_chat_member`. | adapter-live; plugin-e2e missing. |
| `get_user_info` | Uses `get_chat`. | adapter-live; plugin-e2e missing. |
| `get_file_url` | Uses Telegram file path. | adapter-live; plugin-e2e missing. |
| `mute_member` | Uses restrict permissions. | adapter-live for disposable target; plugin-e2e missing. |
| `unmute_member` | Restores permissions. | adapter-live for disposable target; plugin-e2e missing. |
| `kick_member` | Destructive kick. | adapter-live destructive; plugin-e2e missing and should remain opt-in. |
| `leave_group` | Destructive leave. | adapter-live destructive; plugin-e2e missing and should run last. |
| `call_platform_api` | Supports 10 Telegram-specific actions. | adapter-live; plugin-e2e per action missing. |

### Discord

| API | Support Explanation | Current Evidence |
|-----|---------------------|------------------|
| `send_message` | Supports text/media/file chains. | plugin-e2e for SDK send plus direct adapter message chain evidence; needs per-component plugin evidence. |
| `reply_message` | Uses Discord message references. | adapter-live; plugin-e2e missing. |
| `edit_message` | Edits bot messages; file edit sends replacement. | adapter-live; plugin-e2e missing. |
| `delete_message` | Deletes messages with permissions. | adapter-live; plugin-e2e event observed but API evidence unclear. |
| `forward_message` | Emulates by copying content/attachments. | adapter-live; plugin-e2e missing. |
| `get_group_info` | Maps guild metadata. | adapter-live; plugin-e2e missing. |
| `get_group_member_list` | Requires member intent/cache/fetch. | adapter-live; plugin-e2e missing. |
| `get_group_member_info` | Maps guild member role. | adapter-live; plugin-e2e missing. |
| `get_user_info` | Uses Discord fetch/cache. | adapter-live; plugin-e2e missing. |
| `get_file_url` | Returns Discord attachment URL. | unit/direct evidence; plugin-e2e missing. |
| `mute_member` | Uses timeout API. | blocked: no disposable target in shared server run. |
| `unmute_member` | Clears timeout. | blocked: no disposable target in shared server run. |
| `kick_member` | Destructive kick. | blocked: no disposable target in shared server run. |
| `leave_group` | Bot leaves guild. | adapter-live destructive observed; plugin-e2e status unclear. |
| `call_platform_api` | Supports 10 Discord-specific actions. | adapter-live per action; plugin-e2e per action missing. |

### OneBot v11 / aiocqhttp

| API | Support Explanation | Current Evidence |
|-----|---------------------|------------------|
| `send_message` | Supports group/private sending and common components implemented by converter. | adapter-live text/mention/face/image; plugin-e2e missing. |
| `reply_message` | Uses original OneBot event and reply segment. | adapter-live quoted reply; plugin-e2e missing. |
| `delete_message` | Uses `delete_msg`. | unit only; destructive/permission live test missing. |
| `forward_message` | Emulates by `get_msg` then send. | unit only. |
| `get_message` | Uses `get_msg` and converts to `MessageReceivedEvent`. | adapter-live with Matcha; plugin-e2e missing. |
| `get_group_info` | Uses `get_group_info`. | adapter-live with Matcha; plugin-e2e missing. |
| `get_group_list` | Uses `get_group_list`. | unit only; plugin-e2e missing. |
| `get_group_member_list` | Uses `get_group_member_list`. | adapter-live returned empty in Matcha; plugin-e2e missing. |
| `get_group_member_info` | Uses `get_group_member_info`. | unit only; Matcha member list empty. |
| `set_group_name` | Uses `set_group_name`. | unit only; live permission/destructive fixture missing. |
| `get_user_info` | Uses `get_stranger_info`. | unit only; plugin-e2e missing. |
| `get_friend_list` | Uses `get_friend_list`. | unit only; plugin-e2e missing. |
| `approve_friend_request` | Uses `set_friend_add_request`. | unit only; disposable request fixture missing. |
| `approve_group_invite` | Uses `set_group_add_request`. | unit only; disposable invite fixture missing. |
| `mute_member` | Uses `set_group_ban`. | unit only; destructive live fixture missing. |
| `unmute_member` | Uses `set_group_ban` duration 0. | unit only; destructive live fixture missing. |
| `kick_member` | Uses `set_group_kick`. | unit only; destructive live fixture missing. |
| `leave_group` | Uses `set_group_leave`. | unit only; destructive live fixture missing. |
| `call_platform_api` | Supports 14 OneBot-specific actions. | adapter-live for five safe actions; remaining actions need plugin-e2e or blocked reason. |

## Platform-Specific API Acceptance

| Adapter | Declared Actions | Current Evidence |
|---------|------------------|------------------|
| Telegram | `pin_message`, `unpin_message`, `unpin_all_messages`, `get_chat_administrators`, `set_chat_title`, `set_chat_description`, `get_chat_member_count`, `send_chat_action`, `create_chat_invite_link`, `answer_callback_query` | Direct live evidence exists for several supergroup actions in the Telegram record, but the report does not show plugin-e2e JSONL for every action. |
| Discord | `get_channel`, `get_guild`, `get_guild_channels`, `get_guild_roles`, `create_invite`, `pin_message`, `unpin_message`, `add_reaction`, `remove_reaction`, `typing` | Direct live probe verified all listed actions; plugin-e2e per-action evidence is still required by the new checklist. |
| OneBot v11 / aiocqhttp | `get_login_info`, `get_status`, `get_version_info`, `get_group_honor_info`, `set_group_card`, `set_group_special_title`, `set_group_admin`, `set_group_whole_ban`, `send_group_forward_msg`, `get_forward_msg`, `get_record`, `get_image`, `can_send_image`, `can_send_record` | Matcha adapter-live verified `get_login_info`, `get_status`, `get_version_info`, `can_send_image`, and `can_send_record`; the rest need plugin-e2e or endpoint-specific blocked reasons. |

## Required Work Before Final Acceptance

1. Create or reuse a real EBA adapter acceptance plugin that subscribes to all declared EBA events and calls every declared API through the SDK platform API surface.
2. Run the plugin through standalone runtime for Telegram, Discord, and aiocqhttp.
3. For each adapter, record JSONL evidence for receive components, send components, declared events, common APIs, and platform-specific APIs.
4. Reclassify every unsupported component/API as `not-supported` with the protocol/SDK reason.
5. Reclassify every simulator/permission limitation as `blocked`, not complete.
6. Update each adapter document with the tables required by `acceptance-checklist.md`.

## Current Conclusion

The three adapters are implemented and have meaningful auxiliary evidence, but they are not yet fully accepted under the architecture-level checklist. Discord is closest because it has existing standalone-runtime plugin evidence for the event path. Telegram and aiocqhttp need full plugin-driven E2E runs before they can be marked complete.
