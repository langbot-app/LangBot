# OASlackBridge

Hand off WeChat Official Account conversations from the AI to human agents in Slack. When a user sends a keyword such as "转人工" (talk to a human), the conversation is posted to a Slack channel of your choice. Staff reply in Slack and the replies reach the user in WeChat. The AI stays quiet during the takeover and resumes when staff close it.

## What it looks like

1. A WeChat user sends a message containing a keyword (for example 转人工). The AI stops replying.
2. The user receives a notice: "已为您转接人工客服，请稍候，客服会在这里回复您。" (You are being connected to a human agent.)
3. A "📩 Official Account takeover" message appears in Slack with the (masked) user, the matched keyword and the original text.
4. Right below it, the thread gets a "👤 User details" reply: full OpenID, session ID, message count, first contact time and the most recent user/AI messages, so staff have the context.
5. Further messages from the user during the takeover are added to that message's thread.
6. Staff reply in the thread; the user receives the reply in WeChat and the thread shows ✅.
7. Staff send `!close` in the thread. The user receives "人工客服已结束本次服务，后续将由 AI 助手继续为您解答。" (The human session has ended; the AI assistant will continue.) and the AI takes over again.

Both user notices can be changed or turned off in the plugin configuration.

## Before you start

| You need | Notes |
| --- | --- |
| **A verified Official Account** | Replies are sent through WeChat's customer-service message API, which normally requires a verified service account. WeChat's actual permissions decide. |
| **The Official Account bot in auto mode** | Only auto mode lets the plugin send messages to the user on its own. |
| **A Slack workspace and a dedicated channel** | Use a separate support channel with only the staff who answer customers. |
| **LangBot admin access** | To install the plugin, confirm permissions and configure bots. |

## Setup

### Step 1: Configure the Official Account bot

1. In LangBot, open your Official Account bot under **Bots** (the new "WeChat Official Account" adapter).
2. Set **Mode** to **auto (Automatic reply with fallback)**.
3. We recommend **clearing the LoadingMessage**. In auto mode AI replies are pushed automatically, so the placeholder is not needed. Otherwise, during a takeover the user sees "AI is thinking…" after every message.
4. Make sure messages to this bot are handled by a **Pipeline** (not an Agent) that can use this plugin. The plugin's event listener runs inside the Pipeline to hold back AI replies during a takeover.

### Step 2: Create a Slack app and connect it to LangBot

1. In LangBot, create a bot with platform **Slack**. You can use **Quick Slack setup** to create the app automatically, or create one at [api.slack.com/apps](https://api.slack.com/apps) and enter its credentials.
2. If you create the app yourself, check in the Slack app settings:
   - **OAuth & Permissions → Bot Token Scopes**: at least `chat:write`, `app_mentions:read`, `channels:history`; add `groups:history` for private channels.
   - **Event Subscriptions → Subscribe to bot events**: at least `app_mention`, `message.channels`; add `message.groups` for private channels.
   - After changing scopes, click **Reinstall to Workspace**.
   - For **Socket Mode** (no public URL needed), generate an `xapp-` token with `connections:write` under **Basic Information → App-Level Tokens** and enter it as the App-Level Token in LangBot. For webhook mode, paste the callback URL shown in LangBot into Slack's Event Subscriptions.
3. Enter the bot token (`xoxb-…`) and other credentials in LangBot and enable the bot.

### Step 3: Prepare the Slack channel and find its ID

1. Create a channel in Slack (for example `#customer-service`) and invite the support staff.
2. Send `/invite @YourSlackApp` in the channel. **Without this, the app can neither post notifications nor receive replies.**
3. Find the **channel ID**. The plugin needs the ID, not `#channel-name`. Either:
   - click the **channel name** at the top of the channel; the **Channel ID** (like `C0123ABCD45`) is at the bottom of the dialog, with a copy button; or
   - right-click the channel in the sidebar → **Copy link**; the last part of `…/archives/C0123ABCD45` is the ID.

### Step 4: Install the plugin and confirm permissions

1. Install this plugin.
2. On the plugin detail page, **confirm the permissions**:
   - `bot.message.send`: send messages to the WeChat user and to Slack;
   - `storage.plugin`: store takeover sessions;
   - `monitoring.messages` (read-only message history): message count, first contact time and recent conversation in the user details.

   The plugin does nothing until the first two are confirmed. Without the third, user details contain only the OpenID and basic info, plus a hint to confirm the permission.

### Step 5: Fill in the plugin configuration

| Setting | What to enter |
| --- | --- |
| Official Account bot (auto mode) | The bot from step 1 |
| Slack bot | The bot from step 2 |
| Slack channel ID | The ID from step 3, e.g. `C0123ABCD45` |
| Takeover keywords | Words that start a takeover, e.g. `转人工`, `人工客服`. A message that **contains** any of them triggers it |
| Case-sensitive matching | Off by default |
| Takeover duration (minutes) | How long after the user's latest message the takeover ends on its own. Default 60; every user message restarts the timer |
| Forward follow-up messages | On by default. When off, the AI still stays quiet during the takeover, but follow-up messages are not posted to Slack |
| Post user details in the thread | On by default. Replies in the takeover thread with user details |
| Recent messages in user details | Default 10, up to 50; 0 posts only the basic info, without conversation |
| Notice to the user when takeover starts | Default "已为您转接人工客服，请稍候，客服会在这里回复您。"; leave empty to disable |
| Notice to the user when takeover ends | Default "人工客服已结束本次服务，后续将由 AI 助手继续为您解答。"; leave empty to disable |

### Step 6: Attach the "Slack reply processor" to the Slack bot

Staff replies are sent back by the plugin's **Slack reply processor**, which **must be attached to the Slack bot separately**. Installing the plugin is not enough:

1. In LangBot, create a plugin processor configuration with **Slack reply processor** (no settings needed) and save it.
2. Open the **Slack bot** from step 2, go to the **Plugin processors** section, click **Add plugin processor** and pick that configuration.

> If you skip this step, takeover and Slack notifications work, but staff replies and `!close` do nothing.

### Step 7: Test it

Use your own WeChat account and a test channel:

1. Send 转人工 to the Official Account → you get the start notice and Slack shows the takeover message.
2. Send another message → it appears in the thread.
3. Reply in the thread (**without @mentioning the app**) → WeChat receives it and the thread shows ✅.
4. Send `!close` in the thread → WeChat receives the end notice; your next message gets a normal AI reply.

## Day-to-day use for staff

- **Reply only inside the takeover thread.** Messages posted directly in the channel are not forwarded.
- **Do not @mention the app** when replying. If the Slack bot also routes "@mentions in groups" to the AI, a mention triggers an extra AI reply in Slack (forwarding still works). If the channel is only for support, you can turn that route off on the Slack bot.
- Only **text** is forwarded; images and files are not. Slack links, user mentions and channel references are turned into plain text.
- Send `!close` to end the takeover. Otherwise it ends after the takeover duration; the end notice is sent when the user next writes (or when staff reply after it expired).
- Every reply gets a receipt in the thread: ✅ delivered, ❌ with the reason.

## Troubleshooting

**The user only sees "AI正在思考中，请发送任意内容获取回复。" (AI is thinking…)**
That is the bot's LoadingMessage. In auto mode it is the instant answer to every message, and during a takeover the AI does not reply, so it is all the user sees. Clear it as in step 1.

**Staff replied but the user got nothing, and the thread shows no ✅/❌**
The Slack reply processor is not attached to the Slack bot (step 6), or the Slack app is missing the `message.channels` / `message.groups` events or is not in the channel (steps 2–3).

**The thread shows ❌ with an errcode**

| errcode | Meaning | What to do |
| --- | --- | --- |
| `45015` | 48-hour reply window expired | WeChat only allows replies within 48 hours of the user's last interaction; wait for the user to write again |
| `45047` | Customer-service message limit reached | WeChat limits these messages; it recovers after the user writes again |
| `43004` | User does not follow the account | The user must follow the Official Account |
| `48001` | API permission denied | The account lacks customer-service API permission; check verification |

**No Slack notification / the plugin does nothing**
Check that the plugin permissions are confirmed (step 4), the channel ID is correct and the app is in the channel.

**After changing the Slack channel or Slack bot**
An ongoing takeover ends when the user next writes; the user has to send a keyword again to start a takeover in the new channel.

## Limits

- WeChat only allows customer-service messages within **48 hours** of the user's last interaction and caps their number. A long takeover duration cannot get around this.
- The plugin does not queue or retry sends, so users never get duplicates; a ❌ receipt in the thread is the source of truth.
- Customer messages stay in Slack; set channel membership and retention to match your organization's policy.
- The plugin stores only the user ↔ Slack thread mapping, not chat history. Replies to an existing thread still work after a plugin restart.
- The conversation in "User details" comes from LangBot's message records and is posted to Slack; make sure that fits your data policy, or turn it off / set the count to 0.
- WeChat no longer gives Official Accounts the user's nickname or avatar, so users are identified by OpenID.

## For developers

The Official Account side is an EventListener (`components/event_listener/bridge.py`), which runs in the Pipeline, matches keywords, holds back the AI and posts to Slack. The Slack side is a Runner declaring `usages: [event]` (`components/runner/slack_reply.py`), which is subscribed to the Slack bot's `message.received` as a plugin processor. Slack threads are expressed only with the standard `send_message` + `Quote`.

Run the tests from the plugin directory:

```bash
uv venv
uv pip install -r requirements-dev.txt
uv run pytest -q
uv run ruff check .
```

Tests use real SDK invocation bindings, RunnerContext dispatch and a mock Host; they never contact WeChat or Slack.
