# Purchase Intent Lead Capture

Let your AI customer service notice customers who want to buy. After every AI reply, the plugin reads the conversation with a model you choose and against criteria you write, **scores the customer's purchase intent 0–100** and flags **compliance risk**. At medium intent or above (default ≥ 30) it appends a contact request to that reply, only once per customer. When the customer leaves a phone number, WeChat ID or email, the plugin **extracts lead fields** (company, use case, volume, budget, …) from the whole conversation and sends them with the **contact details, score and the entire conversation** to your inbox through [Resend](https://resend.com).

Works for private chats on any platform (WeChat Official Account, WeCom customer service, Telegram, QQ, …).

## What it looks like

1. A customer chats with the AI, e.g. "How much is the annual plan? Can you issue an invoice?"
2. After the AI replies, the plugin judges strong intent and appends: "为了更好地为您服务，方便留下您的手机号或微信号吗？我们的顾问会尽快与您联系。" (May we have your phone or WeChat so an advisor can contact you?)
3. The customer replies "138 0013 8000". The plugin recognizes the contact and immediately sends an email:
   - subject: `【购买意向】138 0013 8000 · <bot name>`;
   - body: contact, user ID, source bot, the reason for the intent judgment, capture time, first contact time, message count and the full conversation;
   - attachment: `conversation-<time>.txt` with the full transcript.
4. The next AI reply ends with a thank-you: "已收到您的联系方式，我们的顾问会尽快与您联系，感谢您的信任！"
5. That customer is never judged or asked again. A customer who does not leave contact details is not asked a second time either.

## Setup

### Step 1: Prepare Resend

1. Sign up at [resend.com](https://resend.com).
2. **Domains → Add Domain**: add your sending domain (e.g. `example.com`), add the DNS records it shows, and wait for **Verified**.
3. **API Keys → Create API Key** with **Sending access**, and copy the `re_…` key (it is shown once).

> Without a verified domain, Resend only lets `onboarding@resend.dev` send to your own Resend account address, which is useful only for testing.

### Step 2: Install the plugin and confirm permissions

| Permission | Used for |
| --- | --- |
| `models.invoke` | Judging intent and reading contact details |
| `storage.plugin` | Remembering each customer's asked / captured state |
| `monitoring.messages` (read-only message history) | Reading the conversation for judging and for the email |

### Step 3: Fill in the plugin configuration

| Setting | What to enter |
| --- | --- |
| Model for judging intent | A chat model. It is called once after every AI reply, so a fast, inexpensive model is best |
| Scoring criteria (prompt) | Which signals add or subtract points; you can paste a keyword/score list. The model scores the whole conversation 0–100 by meaning (including Traditional Chinese and synonyms). A general default is provided |
| High-intent score | Default 60 |
| Score to ask for contact | Default 30: medium (30–59) and high intent are asked once; set it equal to the high-intent score to ask only high intent |
| Compliance risk criteria | Matching conversations (default: fake orders, ticket scalping, cracking, scraping WeChat/banks, VPNs, …) are flagged: **no contact request and no sales email**, listed separately on the page for review |
| Lead fields to extract | Filled from the whole conversation once contact details arrive (default: company, industry, use case, target sites, monthly volume, budget, go-live date, contact name, title, work email, WeChat/phone, current vendor); shown at the top of the email and on the page |
| Messages used for judging | How many recent messages to read, default 20, max 100 |
| Contact request text | Fixed text appended to the AI reply once the ask score is reached |
| Thank-you text | Appended to the next AI reply after contact details arrive; leave empty to disable |
| Resend API key | The `re_…` key from step 1 |
| Sender address | An address on your verified domain, e.g. `leads@example.com` or `Leads <leads@example.com>` |
| Recipient addresses | One or more inboxes that receive leads |

### Step 4: Enable it in the Pipeline

The plugin works inside a Pipeline. Make sure the customer-facing bot routes messages to a **Pipeline** that can use this plugin.

### Step 5: Test it

Chat with the bot from your own account and ask about buying (price, contract, trial). Check that the AI reply ends with the contact request, reply with a phone number and check the inbox.

## Reviewing judgments (plugin page)

The plugin ships a **Lead judgments** page, opened from the plugin pages in the LangBot sidebar.

- **Totals**: conversations, judgments, asked for contact, contact captured, emailed.
- **Conversation list**: one row per private-chat user, with:
  - status (not yet / asked / captured);
  - the latest judgment and its reason;
  - how many judgments, and how many were strong;
  - contact and email result.

  Filter by status (including "with errors") or search by user ID or contact.
- **Details**: click a row to see the conversation's **timeline**:
  - every judgment, with the result, the reason, what the user said and the AI reply;
  - the contact request, the captured contact, email attempts and errors.

  The 30 most recent messages are shown below the timeline.

The latest 100 events are kept per conversation. The page is read-only.

## How contact details are recognized

- Patterns first: mainland China mobile numbers (with optional `+86`, spaces or dashes), landlines with an area code (e.g. `010-12345678`), email addresses, and WeChat IDs after "微信 / vx / wx".
- If no pattern matches, the model extracts it from that message (e.g. "add my QQ 123456789"). It is told never to invent one and to return empty when there is none.
- Every customer message is checked until contact details are found, and none after that.

## Troubleshooting

**No email arrives.** Look for `LeadCapture email failed (...)` in the plugin log:
- `not_configured`: the API key, sender or recipients are missing.
- `http_403:validation_error`: the sending domain is not verified in Resend, or the sender is not on it.
- `http_401` / `http_403`: wrong API key or insufficient permission.
- `network:...`: the server cannot reach `api.resend.com`.

A failed email is retried on later AI replies, **up to 3 attempts in total**.

**The contact request never appears.** Check that a model is selected and that the criteria are specific enough, and look for `intent evaluation failed` in the log. A customer who was already asked is not asked again.

**AI replies got slower.** Each AI reply triggers one extra model call (usually 1–3 s). Use a faster model or fewer messages. In WeChat Official Account auto mode replies are pushed asynchronously anyway, so the impact is small.

**Images in the AI reply.** When text is appended, that reply is sent as text; images in it become placeholders.

## Limits

- Private chats only.
- Each customer is asked once; state is kept per bot + user. Reinstalling the plugin clears the state of all customers.
- Emails contain customers' contact details and full conversations; make sure that fits your privacy and data policy.
- Transcripts come from LangBot's message records, up to 5,000 messages.

## For developers

One EventListener (`components/event_listener/lead.py`):

- `NormalMessageResponded` judges intent and appends the request or thank-you through `reply_message_chain`.
- `PersonMessageReceived` looks for contact details while the customer is in the asked state, and sends the email through Resend.

Conversations come from the read-only `monitoring.messages` Workspace operation. Every failure is only logged and never breaks the conversation.

```bash
uv venv
uv pip install -r requirements-dev.txt
uv run pytest -q
uv run ruff check .
```
