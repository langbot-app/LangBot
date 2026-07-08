# HTTP Bot Adapter — Integration Guide

Integrate **any backend system** with a LangBot pipeline over plain HTTP. Push
messages in via a signed webhook; receive replies on a callback URL. No
long-lived connection, full support for message **aggregation** (many inbound
messages merged into one turn) and **multi-part replies** (one turn → many
outbound messages).

This is the right adapter for **server-to-server** integrations — ticketing
systems, CRMs, internal tools, custom web backends. (For an in-browser,
real-time chat widget, use the embeddable Web Page Bot instead.)

> **5-minute goal:** stand up a callback receiver, send a message, and watch a
> multi-part reply arrive — using the reference client in
> [`examples/http-bot/`](../../examples/http-bot/).

---

## 1. Mental model

```
Your backend  ──(1) POST signed message──►  LangBot   /bots/<bot_uuid>
                                            (pipeline runs: aggregate → think → reply)
Your callback ◄─(2) POST signed reply(s)──  LangBot   one POST per reply part
```

- **(1) Inbound** is *fire-and-collect*: LangBot answers `202 Accepted`
  immediately and does **not** return the pipeline result on that response.
- **(2) Outbound** replies arrive later as separate signed POSTs to your
  `callback_url`. A single turn may produce **several** callbacks (e.g. a tool
  call narration followed by the final answer).
- Everything is keyed by a **`session_id` you choose** (e.g. a ticket number).
  Each `session_id` maps to one isolated LangBot conversation.

---

## 2. Create the bot

1. In the LangBot dashboard, add a bot and choose the **HTTP Bot** platform.
2. Fill in the config:

   | Field | Required | Notes |
   |---|---|---|
   | **Inbound Signing Secret** | yes | Your backend signs inbound requests with this. |
   | **Outbound Callback URL** | yes | Where LangBot POSTs replies. **Config-only** — cannot be overridden per message (SSRF protection). |
   | **Outbound Signing Secret** | no | LangBot signs callbacks with this; defaults to the inbound secret. |
   | **Default Session Type** | no | `person` (default) or `group`. |
   | **Require Inbound Signature** | no | Keep `true` in production. |
   | **Callback Timeout / Max Retries** | no | Defaults: 15s, 3 retries. |

3. Bind the bot to a **pipeline** and **enable** it.
4. Copy the **Inbound Webhook URL** shown in the config — it looks like
   `https://your-langbot/bots/<bot_uuid>`.

---

## 3. The signature scheme

Both directions use the same dependency-free HMAC-SHA256 scheme:

```
signing_string = "{timestamp}." + raw_body_bytes
signature      = "sha256=" + hex(HMAC_SHA256(secret, signing_string))
```

Sent as headers:

| Header | Meaning |
|---|---|
| `X-LB-Timestamp` | Unix seconds. Rejected if more than **±300s** from server time. |
| `X-LB-Signature` | `sha256=<hex>` over `"{timestamp}." + body`. |
| `X-LB-Idempotency-Key` | *(optional, inbound)* dedup key; retries with the same key return `409`. |

Verify outbound callbacks the same way, using the **outbound** secret (or the
inbound secret if you left it blank).

A six-line reference implementation is in `examples/http-bot/client.py`
(`sign()` / `verify()`); a Node/TS version is in `client.ts`.

---

## 4. Send your first message (curl)

```bash
BOT="https://your-langbot/bots/<bot_uuid>"
SECRET="your-inbound-secret"
BODY='{"session_id":"ticket-10293","message":[{"type":"Plain","text":"Export keeps failing on the dashboard."}]}'
TS=$(date +%s)
SIG="sha256=$(printf '%s.%s' "$TS" "$BODY" | openssl dgst -sha256 -hmac "$SECRET" -r | cut -d' ' -f1)"

curl -sS -X POST "$BOT" \
  -H "Content-Type: application/json" \
  -H "X-LB-Timestamp: $TS" \
  -H "X-LB-Signature: $SIG" \
  -d "$BODY"
# -> 202 {"code":0,"msg":"accepted","data":{"session_id":"ticket-10293","accepted_message_id":"in_...","aggregating":true}}
```

The reply(s) will be POSTed to your configured callback URL shortly after.

---

## 5. Inbound request format

`POST /bots/{bot_uuid}`

```jsonc
{
  "session_id": "ticket-10293",     // REQUIRED. Your stable id. Maps 1:1 to a LangBot session.
  "session_type": "person",         // optional: "person" | "group"; default from config
  "sender": {                       // optional metadata, surfaced to the pipeline/plugins
    "id": "user-5567",
    "name": "Alice"
  },
  "message": [                      // REQUIRED. A LangBot MessageChain (array of segments).
    { "type": "Plain", "text": "Export keeps failing on the dashboard." },
    { "type": "Image", "url": "https://example.com/screenshot.png" }
  ]
}
```

**Message segments.** Text uses `{"type":"Plain","text":"..."}`. Images use
`{"type":"Image","url":"..."}` (or `base64`). Other supported types: `Voice`,
`File`, `At`, `Quote`.

> Note: the callback URL is **not** accepted in the body — it is taken only from
> bot config. This is deliberate (prevents an attacker who obtains the inbound
> secret from redirecting replies to an arbitrary host).

### Aggregation (N → 1)

If your pipeline has **message aggregation** enabled, send several messages with
the **same `session_id`** within the aggregation window and they are merged into
**one** pipeline turn. No special flag — just reuse the `session_id`.

---

## 6. Outbound callback format

LangBot POSTs each reply part to your `callback_url`:

```jsonc
{
  "session_id": "ticket-10293",     // echoes the inbound session
  "reply_to": "in_01H...",          // the accepted_message_id this answers
  "sequence": 1,                    // 1-based ordinal within this turn
  "is_final": false,                // true on the last part of the turn
  "stream": false,                  // true for streamed chunks
  "message": [ { "type": "Plain", "text": "Looking into it…" } ],
  "timestamp": "2026-06-22T09:00:01Z"
}
```

Your endpoint should return `2xx` quickly. Non-2xx / timeout → LangBot retries
with exponential backoff (up to `callback_max_retries`).

### Multi-part replies (1 → M)

One turn may emit multiple callbacks, delivered **in `sequence` order** for a
given session:

```
seq=1 is_final=false  "Checking your export logs…"
seq=2 is_final=false  "Found 2 failed exports."
seq=3 is_final=true   "Fixed — please try again."
```

Stitch by `session_id` + `sequence`; the turn is complete when
`is_final: true` arrives.

---

## 7. Reset a session

Start a fresh conversation for a `session_id` (drops history):

```
POST /bots/{bot_uuid}/reset
{ "session_id": "ticket-10293", "session_type": "person" }
→ 200 { "code":0, "msg":"reset", "data": { "session_id":"ticket-10293", "removed": true } }
```

Signed exactly like an inbound message.

---

## 8. Synchronous convenience mode

If you don't need streaming/multi-part and just want one reply back on the same
HTTP call, POST to `/sync`. LangBot waits for the turn to finish and returns all
parts **collapsed** into one array:

```
POST /bots/{bot_uuid}/sync
{ "session_id": "ticket-10293", "message": [ { "type":"Plain", "text":"hi" } ] }
→ 200 { "code":0, "msg":"ok",
        "data": { "session_id":"ticket-10293", "reply_to":"in_...",
                  "message": [ {"type":"Plain","text":"..."}, ... ] } }
```

This is **lossy** (you lose `sequence` / streaming boundaries) and blocks up to
`callback_timeout × 4` seconds. Prefer the callback model for anything
real-time or multi-part. Only one in-flight `/sync` per `session_id`.

---

## 9. Error envelope

```jsonc
{ "code": 40101, "msg": "invalid signature: signature_mismatch", "data": null }
```

| HTTP | code | meaning |
|---|---|---|
| 202 | 0 | accepted |
| 400 | 40001 | malformed body / missing `session_id` or `message` |
| 401 | 40101 | bad/expired signature |
| 409 | 40901 | duplicate idempotency key |
| 413 | 41301 | message too large (>1 MiB) |
| 500 | 50001 | internal error |

---

## 10. Try it end-to-end in 5 minutes

```bash
cd examples/http-bot
pip install flask requests

# Terminal 1 — your callback receiver (point the bot's callback_url here, e.g. via a tunnel):
python client.py serve --port 8900 --secret SHARED_SECRET

# Terminal 2 — push a message:
python client.py push \
  --url https://your-langbot/bots/<bot_uuid> \
  --secret SHARED_SECRET \
  --session ticket-1 \
  --text "hello"
```

Watch Terminal 1 print each reply part (`[part ]` / `[FINAL]`) with its
sequence number — that's 1→M working, signatures verified.

A machine-readable contract is in
[`docs/http-bot-openapi.json`](../http-bot-openapi.json).

---

## 11. Security checklist

- Keep **Require Inbound Signature** on in production.
- Use **HTTPS** callback URLs; the URL is config-only (no per-message override).
- Treat the secrets like passwords; rotate via the dashboard.
- The inbound route is unauthenticated at the framework level **by design** —
  security comes entirely from the HMAC signature, so never disable it on a
  public deployment.
