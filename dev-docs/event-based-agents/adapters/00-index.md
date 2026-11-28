# EBA Adapter Migration Records

This directory records adapter-level migration details for the Event-Based Agents architecture. Each adapter document should be kept close to the implementation and must answer four questions:

1. What changed in the adapter structure.
2. Which configuration fields are required.
3. Which events and APIs are supported.
4. What has been verified end to end.

## Adapter Documents

General acceptance checklist: [EBA Adapter Acceptance Checklist](./acceptance-checklist.md)

Current acceptance report: [EBA Adapter Acceptance Report](./acceptance-report.md)

| Adapter | Status | Document |
|---------|--------|----------|
| Telegram | Migrated; partial plugin E2E, real UI inbound image/file verified | [Telegram](./telegram.md) |
| Discord | Migrated; partial plugin E2E, media-inbound gaps remain | [Discord](./discord.md) |
| OneBot v11 / aiocqhttp | Migrated; Matcha UI plus protocol-level multi-component coverage | [OneBot v11 / aiocqhttp](./aiocqhttp.md) |
| DingTalk | Migrated; partial plugin E2E, real UI inbound image/file verified; group gap remains | [DingTalk](./dingtalk.md) |
| Lark / Feishu | Migrated; partial live text E2E, media-inbound gap remains | [Lark / Feishu](./lark.md) |
| WeCom | Migrated; private text plugin E2E verified, media/group gaps remain | [WeCom](./wecom.md) |
| WeComBot | Migrated; private text and outbound/API plugin E2E verified, feedback/group gaps remain | [WeComBot](./wecombot.md) |
| Official Account | Migrated; private text plugin E2E verified, proactive outbound not supported | [Official Account](./officialaccount.md) |
| QQ Official API | Migrated; WebSocket inbound reached LangBot, model config blocked reply | [QQ Official API](./qqofficial.md) |
| Slack | Migrated; private text and outbound/API plugin E2E verified | [Slack](./slack.md) |
| WeCom Customer Service | Migrated; customer-side UI text plugin E2E verified, inbound media and platform-API live coverage pending | [WeCom Customer Service](./wecomcs.md) |
| Kook | Migrated; unit/mocked converter and API coverage only, live acceptance pending | [Kook](./kook.md) |

## Native streaming: first frame in group replies

Core passes the sender mention (`At`) and reply setting (`quote_origin`) to the adapter. It keeps the native stream open even when the adapter cannot render either option. The table describes adapter behavior, not a live client verification.

| Adapter | Mention sender | Reply to original message | Possible adapter improvement |
| --- | --- | --- | --- |
| Discord | No. The preview includes plain text only. | No. The first preview is sent without a message reference. | Render the mention and attach a reference when requested. |
| Lark / Feishu | No. The initial card has a placeholder, and text updates omit `At`. | A card for an incoming message is created as a reply regardless of `quote_origin`. The setting does not control this link. | Render the mention in the card and honor the reply setting when creating it. |

## Platform listener notifications

These notifications observe adapter events without consuming them. Availability depends on the upstream platform delivering the corresponding update to the bot.

| Listener | Adapter converters |
| --- | --- |
| MessageDeleted | OneBot v11, Discord, Lark, LINE, Slack, WeCom Customer Service |
| MessageEdited | Discord, Slack, Telegram |
| MessageReactionReceived | Discord, Lark, QQ Official, Slack, Telegram |
| GroupMemberJoined / GroupMemberLeft / BotInvitedToGroup / BotRemovedFromGroup | Discord, Lark, LINE, OneBot v11, QQ Official, Slack, Telegram |
| GroupMemberBanned | OneBot v11, Telegram |
| BotMuted / BotUnmuted | Telegram |
| FeedbackReceived | DingTalk, WeComBot |
| PlatformSpecificEventReceived | DingTalk, KOOK, Lark, LINE, Official Account, OneBot v11, QQ Official, Slack, Telegram, WeCom, WeComBot, WeCom Customer Service |

## Documentation Checklist

When migrating a new adapter, add one document here with:

- Configuration table matching the adapter manifest.
- Supported event list.
- Supported common API list.
- Supported `call_platform_api` action list.
- Known unsupported APIs and the reason.
- Live test notes, including platform, channel type, destructive operations, and residual risks.
- A clear distinction between real UI inbound media, protocol-level injected inbound media, and bot outbound media.
