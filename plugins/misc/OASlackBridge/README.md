# OASlackBridge

[简体中文](readme/README_zh_Hans.md)

Forward WeChat Official Account messages containing configured keywords to a Slack channel. Staff reply in the resulting thread; the plugin sends the text back to the user through the Official Account customer-service API. AI replies are suppressed during takeover.

## Prerequisites

- A verified Official Account with customer-service messaging permission, configured as a LangBot bot with **Mode = auto**. Other modes cannot send asynchronous staff replies; core enforces this restriction.
- A LangBot core containing **langbot-app/LangBot #2863 and #2864**: Official Account `send_message`, Slack `send_message` returning `message_id`, outbound `Quote` as a thread destination, and inbound bot-thread replies carrying `Quote.id`. Older cores cannot run this bridge.
- A Slack App connected through LangBot, invited to the target channel. Enable bot event subscriptions `app_mention` and `message.channels`; for a private channel also enable `message.groups`. Required bridge scopes are `chat:write`, `app_mentions:read`, `channels:history`, and `groups:history` for private channels. Retain the other scopes required by LangBot's Slack adapter. Reinstall the Slack App after changing scopes. Socket Mode also needs an App-Level Token with `connections:write`; webhook mode needs LangBot's reachable event endpoint.
- Enable this plugin for **both bots' message pipelines**. Place it before plugins that answer or consume messages. Restrict membership of the target channel to staff authorized to reply to customers; every human participant in that channel can reply through a mapped thread.

## Configuration

| Key | Default | Meaning |
| --- | --- | --- |
| `oa_bot` | required | Official Account bot selector, auto mode |
| `slack_bot` | required | Slack bot selector |
| `slack_channel_id` | required | Channel ID, not channel name |
| `keywords` | `[]` | Substrings that start takeover; empty entries are ignored |
| `case_sensitive` | `false` | Case-sensitive keyword matching |
| `takeover_minutes` | `60` | Idle takeover duration after the latest user message; use a positive integer |
| `forward_followups` | `true` | Forward subsequent user messages into the same thread |

## Staff workflow

1. A user sends a keyword. The channel receives a root message containing a shortened openid, the keyword, UTC time, and original text.
2. Reply **inside that thread**. An @mention is optional. Only `Plain` text is sent to WeChat; the reply context and @bot prefix are removed. The thread receives `✅` after a successful send, or a bilingual error category and WeChat `errcode` after rejection.
3. Send **`!close`** in the thread to release takeover. `@bot /close` is also supported. A bare `/close` may be interpreted by Slack as a native slash command instead of a message.
4. Once closed or expired, ordinary user messages follow the normal AI pipeline. A new keyword starts a new thread. Expiration is checked on the next event, without a background timer. Staff replies do not extend takeover; user messages do.

Turning `forward_followups` off still suppresses AI and refreshes both timestamps during takeover. Changing the configured Slack destination ends the old session when the next user message arrives; a new keyword is required to start a session in the new destination.

## Reply window and limits

WeChat's customer-service API permits replies only within **48 hours** of qualifying user interaction and imposes a message-count limit. This plugin refreshes its local window on each received user message; the platform remains authoritative about eligibility and remaining quota. Increasing `takeover_minutes` cannot bypass platform restrictions. There is no queue for delayed delivery and no automatic retry that might send a duplicate message.

| `errcode` | Staff-facing meaning |
| --- | --- |
| `45015` | 48-hour reply window expired |
| `45047` | Customer-service message-count limit reached |
| `43004` | User is not following the account |
| `48001` | API permission denied; check account verification |

Unknown error codes remain visible with a generic rejection reason. Raw exception text, tokens, and AppSecret are never included in plugin-generated Slack diagnostics or logs.

## Storage and runtime

Each session is stored separately by installation, Official Account bot UUID, and full openid, with a separate Slack bot/channel/root-ts lookup row. Worker restarts preserve routing. `/close`, `!close`, and observed expiration delete both rows; inactive expired rows are removed when that conversation is next accessed. Message history is not copied into plugin storage. Staff can still see customer text in Slack: apply your organization's channel retention and access policy.

The plugin supports `shared-runtime-v1` / `stateless-v1`; details are in [SHARED_RUNTIME.md](SHARED_RUNTIME.md). It uses only standard `send_message` calls for platform messaging and requires no plugin-specific credentials.

## Validation and packaging

From the repository root, with `langbot-plugin`, `pytest`, `pytest-asyncio`, and `PyYAML` installed:

```sh
python -m pytest plugins/misc/OASlackBridge/tests -q
python plugins/scripts/check_catalog.py
cd plugins/misc/OASlackBridge
lbp build -o dist
```

Tests use real SDK invocation bindings and a mock Host for messaging and storage; they never contact Slack or WeChat. A live acceptance check needs your own authorized test accounts: send a keyword, send a follow-up, reply from Slack both with and without @bot, restart the plugin worker and reply again, then send `!close` and confirm normal AI replies resume. Test in a dedicated channel, not a production customer thread.

## Limitations

- Replies are text-only. A non-text-only staff message gets an explanatory thread response; a non-text-only user follow-up is represented by a placeholder.
- Slack/API or storage transport failures propagate to the runtime. Check runtime delivery status before retrying; a successful provider send followed by a failed confirmation does not mean the user did not receive it.
- No live-account end-to-end verification is included in the mocked test suite.
