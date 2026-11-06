# OASlackBridge

[简体中文](readme/README_zh_Hans.md)

Forward WeChat Official Account messages containing configured keywords to a Slack channel. Staff reply in the resulting thread; the plugin sends the text back to the user through the Official Account customer-service API. AI replies are suppressed during takeover.

## Prerequisites

- A verified Official Account with customer-service messaging permission, configured as a LangBot bot with **Mode = auto**. Other modes cannot send asynchronous staff replies; core enforces this restriction.
- The minimum Host contract for 0.2.0 includes Unified API, plugin installation permissions, Runner `usages: [event]`, Bot Plugin processor subscriptions, Official Account `send_message`, and Slack thread support (`Quote.id` and `message_id`). Core must also include the standard Runner send authorization and MessageChain conversion shipped with this plugin update. Older Hosts without these capabilities cannot load or run this version.
- A Slack App connected through LangBot, invited to the target channel. Enable bot event subscriptions `app_mention` and `message.channels`; for a private channel also enable `message.groups`. Required bridge scopes are `chat:write`, `app_mentions:read`, `channels:history`, and `groups:history` for private channels. Retain the other scopes required by LangBot's Slack adapter. Reinstall the Slack App after changing scopes. Socket Mode also needs an App-Level Token with `connections:write`; webhook mode needs LangBot's reachable event endpoint.
- Restrict membership of the target channel to staff authorized to reply to customers; every human participant in that channel can reply through a mapped thread.

## Setup and upgrade to 0.3.0

1. Install or upgrade the plugin. A Workspace member must confirm `bot.message.send` and `storage.plugin` on the plugin detail page. Version 0.2.0 switches from compatibility mode to strict permissions; declaring permissions does not grant them. No Workspace operations are requested.
2. Fill in the plugin-level configuration below. Both components use this configuration; the processor has no separate settings.
3. Set the Official Account Bot's **main route to a Pipeline with this plugin enabled**, before other plugins that answer or consume messages. The EventListener only runs inside a Pipeline. An Agent main route cannot suppress AI replies during takeover.
4. Create a Plugin processor instance using **Slack reply processor**, then subscribe to it in the Slack Bot detail page's **Plugin processor** section. Installation alone does not subscribe it. The Slack Bot main route can be any target, including **discard**; it no longer needs this plugin in its Pipeline.
5. Staff must reply in the mapped thread **without @bot**. Processor subscriptions run in parallel with the main route and cannot prevent its replies. Mentioning the bot while the main route is AI can therefore also trigger an AI response.

Existing 0.1.0 sessions and thread mappings remain usable after upgrading the same installation; storage keys are unchanged. The EventListener no longer handles Slack group messages. Complete the processor subscription before resuming staff replies.

Receipts use the event-scoped standard `ctx.reply`, preserving the source Slack `thread_ts`. The Runner declares `tool_calling: true` and `permissions.tools: [call]` with `permissions.storage: [plugin]`; `event_reply` is automatically available for message events, so no extra platform tools or installation capabilities need enabling. `get_bot_uuid` is also event-scoped. Cross-bot sends use `bot.message.send`; session reads, writes, and deletes use `storage.plugin`. Permission denials are logged without raw diagnostics; the processor posts a missing-permission receipt when event replies remain available.

## Configuration

If plugin storage or sending to Slack is denied, the Official Account listener logs a warning and leaves the normal AI Pipeline enabled for that message, including keyword matches and messages during an existing takeover. It suppresses AI only after bridge handling succeeds. This keeps customers from receiving no response while permissions are unavailable; messages already forwarded to Slack remain visible there. The plugin does not clear suppression set by another Pipeline plugin.

| Key | Default | Meaning |
| --- | --- | --- |
| `oa_bot` | required | Official Account bot selector, auto mode |
| `slack_bot` | required | Slack bot selector |
| `slack_channel_id` | required | Channel ID, not channel name |
| `keywords` | `[]` | Substrings that start takeover; empty entries are ignored |
| `case_sensitive` | `false` | Case-sensitive keyword matching |
| `takeover_minutes` | `60` | Idle takeover duration after the latest user message; use a positive integer |
| `forward_followups` | `true` | Forward subsequent user messages into the same thread |
| `start_notice` | `已为您转接人工客服，请稍候，客服会在这里回复您。` | Sent to the user when a keyword starts takeover; empty disables it |
| `end_notice` | `人工客服已结束本次服务，后续将由 AI 助手继续为您解答。` | Sent to the user when staff send `!close` or takeover expiration is observed; empty disables it |

## Staff workflow

1. A user sends a keyword. The channel receives a root message containing a shortened openid, the keyword, UTC time, and original text.
2. Reply **inside that thread without @bot**. Only `Plain` text is sent to WeChat; the reply context and any leading @bot prefix are removed. Slack links, mentions, channel references, and escaped `&`, `<`, `>` are converted to readable plain text. The thread receives `✅` after a successful send, or a bilingual error category and WeChat `errcode` after rejection. Unmapped threads are logged and receive no reply.
3. Send **`!close`** in the thread to release takeover. The processor also accepts `/close` if delivered as message text, but Slack may interpret it as a native slash command instead.
4. Once closed or expired, ordinary user messages follow the normal AI pipeline. A new keyword starts a new thread. Expiration is checked on the next event, without a background timer. Staff replies do not extend takeover; user messages do.

User notices (0.3.0) go through the same customer-service API as staff replies. The start notice follows the Slack root message; the end notice follows `!close` / `/close` or an observed expiration (on the user's next message, or when staff reply after expiry, before the AI answer). No end notice is sent when the 48-hour window has passed, or when the user's message after expiry contains a keyword again, since that starts a new takeover. A notice that fails never undoes the takeover change; the thread shows `⚠️` with the readable `errcode`. Installations upgraded from 0.2.0 without saving the config use the default texts.

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

Storage reads enumerate the plugin's keys. Expired conversations that are never accessed again remain stored and increase that listing; there is no periodic cleanup.

The plugin supports `shared-runtime-v1` / `stateless-v1`; details are in [SHARED_RUNTIME.md](SHARED_RUNTIME.md). Both components share plugin storage and use standard `send_message` and event reply APIs, with no plugin-specific credentials.

## Validation and packaging

From the repository root, create an isolated environment with the Unified API SDK snapshot:

```sh
uv venv plugins/misc/OASlackBridge/.venv
uv pip install --python plugins/misc/OASlackBridge/.venv/bin/python -r plugins/misc/OASlackBridge/requirements-dev.txt
source plugins/misc/OASlackBridge/.venv/bin/activate
python -m pytest plugins/misc/OASlackBridge/tests -q
python plugins/scripts/check_catalog.py
python plugins/scripts/test_repository.py
ruff check plugins/misc/OASlackBridge
cd plugins/misc/OASlackBridge
lbp build -o dist
```

Tests use real SDK invocation bindings, RunnerContext dispatch, and a mock Host for messaging and storage; they never contact Slack or WeChat. A live acceptance check needs your own authorized test accounts: subscribe the processor, send a keyword, send a follow-up, reply from Slack without @bot, restart the plugin worker and reply again, then send `!close` and confirm normal AI replies resume. Test in a dedicated channel, not a production customer thread.

## Limitations

- Replies are text-only. A non-text-only staff message gets an explanatory thread response; a non-text-only user follow-up is represented by a placeholder.
- Slack/API or storage transport failures propagate to the runtime. Check runtime delivery status before retrying; a successful provider send followed by a failed confirmation does not mean the user did not receive it.
- No live-account end-to-end verification is included in the mocked test suite.
