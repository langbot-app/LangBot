# Human Handoff Bridge

Let your AI customer service hand users to real people when needed. When a user sends a keyword such as "转人工" (talk to a human), the conversation is posted to where your staff work, for example a Slack channel, a Lark group or a QQ group. Staff reply there and the replies reach the user. The AI stays quiet during the takeover and resumes when staff close it.

The **customer side** can be any platform LangBot supports (WeChat Official Account, WeCom customer service, Telegram, QQ, …). The **staff side** currently supports **Slack, Lark and QQ (OneBot v11)**.

## What it looks like

1. A user sends a message containing a keyword. The AI stops replying.
2. The user gets a notice: "已为您转接人工客服，请稍候，客服会在这里回复您。" (You are being connected to a human agent.)
3. The staff group/channel receives a "📩 Human handoff request" with the source bot, the (masked) user, the keyword and the original text.
4. Right after it comes a "👤 User details" reply: full user ID, message count, first contact time and the most recent conversation.
5. Further user messages during the takeover are forwarded as replies to the request.
6. Staff **reply to (quote)** any forwarded message and the user receives it; ✅ confirms delivery.
7. Staff reply `!close` to end the takeover. The user gets "人工客服已结束本次服务，后续将由 AI 助手继续为您解答。" (The human session has ended; the AI assistant will continue.) and the AI takes over again.

> In Slack, "reply" means posting in the message's thread; in Lark or QQ, use the message's Reply (quote) action.

## Before you start

| You need | Notes |
| --- | --- |
| **A customer-side bot that can send proactively** | Staff replies are pushed to the user by the bot. For a WeChat Official Account use **auto mode** (normally a verified service account); other platforms usually support it by default. |
| **A staff-side bot** | A Slack, Lark or QQ (OneBot v11) bot connected to LangBot and added to the staff group/channel. |
| **LangBot admin access** | To install the plugin, confirm permissions and configure bots. |

## Setup

### Step 1: Configure the customer-side bot

1. Make sure the customer-facing bot routes messages to a **Pipeline** (not an Agent) that can use this plugin. The plugin's event listener runs inside the Pipeline to hold back AI replies during a takeover.
2. WeChat Official Account: set **Mode** to **auto** and we recommend **clearing the LoadingMessage**. Otherwise, during a takeover the user sees "AI is thinking…" after every message.

### Step 2: Prepare the staff-side bot and group

- **Slack**: create a Slack app and connect it to LangBot (Quick Slack setup works). It needs at least `chat:write`, `app_mentions:read` and `channels:history` (plus `groups:history` for private channels), and the `app_mention` and `message.channels` events (plus `message.groups`). Reinstall the app after changing scopes. Run `/invite @YourApp` in the channel.
- **Lark**: create a custom app on the Lark developer platform, connect it to LangBot, enable the bot capability, subscribe to the message-received event, and add the bot to the staff group.
- **QQ (OneBot v11)**: connect a OneBot implementation as described in the LangBot docs and add the bot account to the staff group.

### Step 3: Find the staff group/channel ID

The plugin needs the **ID**, not the group name.

- **Works everywhere**: @mention the bot in the staff group with any message, then open the staff-side bot in LangBot and check its recent **event log**. The conversation ID of the message-received event (`chat_id`, or the part after `group_` in `group_xxx`) is the group ID.
- **Slack shortcut**: click the channel name; the **Channel ID** (like `C0123ABCD45`) is at the bottom of the dialog. Or right-click the channel → Copy link and take the part after `…/archives/`.
- **Lark**: group IDs look like `oc_xxxxxxxx`; the general method above is easiest.
- **QQ**: the QQ group number.

To send requests to **one staff member privately** instead, choose "Private chat" as the staff chat type and enter that person's user ID (found the same way).

### Step 4: Install the plugin and confirm permissions

After installing, **confirm the permissions** on the plugin detail page:

| Permission | Used for |
| --- | --- |
| `bot.message.send` | Sending messages to the user and to staff |
| `storage.plugin` | Storing takeover sessions |
| `bot.read` | Reading bot names and platforms (source label, Slack formatting) |
| `monitoring.messages` (read-only message history) | Message count, first contact time and recent conversation in user details |

The plugin does nothing without the first two; without the last two it still works, with less information.

### Step 5: Fill in the plugin configuration

| Setting | What to enter |
| --- | --- |
| Customer-facing bot | The bot from step 1 |
| Staff bot | The bot from step 2 |
| Staff chat type | Group/channel (default) or private chat |
| Staff group / channel / user ID | The ID from step 3 |
| Takeover keywords | Words that start a takeover, e.g. `转人工`. A message that **contains** any of them triggers it |
| Case-sensitive matching | Off by default |
| Takeover duration (minutes) | How long after the user's latest message the takeover ends; default 60, restarted by every user message |
| Platform reply window (hours) | Staff replies are refused this long after the user's last message. Default 0 (no limit). **Use 48 for WeChat Official Accounts and WeCom customer service** |
| Forward follow-up messages | On by default |
| Post user details for staff | On by default |
| Recent messages in user details | Default 10, max 50; 0 posts only the basic info |
| Notice to the user when takeover starts / ends | Default texts shown above; leave empty to disable |

### Step 6: Attach the "Staff reply processor" to the staff-side bot

Staff replies are sent back by the plugin's **Staff reply processor**, which **must be attached to the staff-side bot separately**:

1. In LangBot, create a plugin processor configuration with **Staff reply processor** (no settings) and save it.
2. Open the staff-side bot, go to **Plugin processors**, click **Add plugin processor** and pick that configuration.

> If you skip this, handoff requests arrive but staff replies and `!close` do nothing.

### Step 7: Test it

1. Send the keyword on the customer side → you get the start notice; staff get the request and user details.
2. Send another message → it is forwarded to staff.
3. Reply to (quote) any forwarded message (in Slack, reply in the thread **without @mentioning the bot**) → the user receives it and ✅ appears.
4. Reply `!close` → the user gets the end notice; the next message gets a normal AI reply.

## Day-to-day use for staff

- **Always reply to (quote) a forwarded message.** Plain messages in the group are not forwarded.
- **Do not @mention the bot.** If the staff-side bot also routes @mentions to the AI, a mention triggers an extra AI reply. You can turn that route off if the group is only for support.
- Only **text** is forwarded; images and files are not.
- Send `!close` to end the takeover; otherwise it ends after the takeover duration.
- Every reply gets a receipt: ✅ delivered, ❌ with the reason.

## Troubleshooting

**The user only sees "AI正在思考中，请发送任意内容获取回复。"**: that is the WeChat Official Account LoadingMessage; clear it as in step 1.

**Staff replied, the user got nothing and there is no ✅/❌**: the Staff reply processor is not attached (step 6), staff did not reply/quote, or the staff-side bot does not receive group messages (for Slack, check the events and that the app is in the channel).

**No request arrives in the staff group**: check that permissions are confirmed, the ID is right and the bot is in the group. Platforms outside the supported list cannot return message IDs, so handoff cannot start (the AI keeps replying).

**❌ with an errcode (WeChat Official Account)**: `45015` 48-hour window expired (wait for the user to write again); `45047` message limit reached; `43004` user does not follow the account; `48001` no customer-service API permission (check verification).

**After changing the staff bot or ID**: an ongoing takeover ends when the user next writes; the user must send a keyword again.

## Limits

- Staff side: Slack, Lark and QQ (OneBot v11). Other platforms first need message IDs from `send_message` and quoted replies.
- Only the customers' **private** messages are handled.
- No queueing or automatic retries; a ❌ receipt is the source of truth.
- The conversation in user details comes from LangBot's message records and is posted to the staff platform; make sure that fits your data policy, or turn it off / set the count to 0.
- The plugin stores only user ↔ staff message mappings, not chat history.

## Migrating from OASlackBridge

This plugin is the generic successor of OASlackBridge and has a different plugin ID, so install and configure it fresh:
- the Official Account bot becomes the customer-facing bot;
- the Slack bot becomes the staff bot;
- the channel ID becomes the staff group / channel ID;
- set the platform reply window to 48.

Then attach the Staff reply processor to the Slack bot in place of the old Slack reply processor. Ongoing takeovers of the old plugin are not migrated.

## For developers

The customer side is an EventListener (`components/event_listener/handoff.py`), which runs in the Pipeline. The staff side is a Runner declaring `usages: [event]` (`components/runner/staff_reply.py`), subscribed to the staff bot's `message.received` as a plugin processor. Routing uses only the standard `send_message` (returning `message_id`) and inbound `Quote`. Slack escaping is applied only when the staff bot is Slack.

```bash
uv venv
uv pip install -r requirements-dev.txt
uv run pytest -q
uv run ruff check .
```
