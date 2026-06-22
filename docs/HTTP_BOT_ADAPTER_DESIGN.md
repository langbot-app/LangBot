# HTTP Bot Adapter — Design Document

> Status: **Draft / RFC** · Target branch: `feat/http-bot-adapter` · Author: LangBot core
>
> A first-class, **standalone** message-platform adapter that lets any external
> system (e.g. LangBot Space ticketing, an internal back-office, a CRM, a custom
> web app) talk to a LangBot pipeline over plain HTTP — **inbound** by POSTing
> messages in, **outbound** by receiving replies on a callback URL — with full
> support for the pipeline's native N→1 aggregation and 1→M multi-reply
> semantics, and **without** holding a long-lived WebSocket connection.

---

## 1. Background & Motivation

### 1.1 The concrete need

LangBot Space wants to use a LangBot pipeline as the brain for **ticket
handling**. The integration is **server-to-server**: Space's backend pushes a
user's ticket messages into LangBot and renders LangBot's replies back into the
ticket thread.

This interaction is **not** request/response shaped:

- **N → 1**: a user may fire several messages in a row ("the app crashed" …
  "when I click export" … "here's a screenshot"). The pipeline's
  **message aggregation** feature should debounce and merge these into one turn.
- **1 → N**: a single turn may yield **multiple** outbound messages — a tool/
  function call narrating progress, a plugin emitting several cards, a streamed
  answer split into chunks.

### 1.2 Why the existing options don't fit

LangBot today exposes exactly one externally-reachable way to drive a pipeline
that is **not** tied to a specific IM vendor: the **WebSocket** path
(`/api/v1/pipelines/<uuid>/ws/connect` for dashboard debug, and
`/api/v1/embed/<bot_uuid>/ws/connect` for the embeddable web widget).

For a server-to-server integration the WebSocket path has real friction:

| Problem | Detail |
|---|---|
| Long-lived connection | Caller must maintain a socket, heartbeats, and reconnect logic for what is fundamentally a fire-and-collect workload. |
| Session identity | Inbound messages are keyed by the transient `connection_id` (`websocket_{connection_id}`); the caller **cannot supply a stable, business-meaningful session id** (e.g. a ticket number). Multi-ticket isolation is not expressible. |
| Auth mismatch | The debug socket is gated by the **dashboard JWT** (must not be handed to an external service); the embed socket is gated by **Cloudflare Turnstile** (a *browser* human-check that a backend cannot satisfy). Neither is a server-to-server credential. |
| In-memory, single-process state | Session history lives in process memory and is lost on restart. |

> **Key realisation.** The N→1 / 1→M behaviour the caller wants is **not**
> provided by WebSocket — it is provided by the **pipeline** (aggregation +
> the adapter being free to call `reply_message` any number of times). It is
> therefore **transport-independent**. We can deliver the exact same semantics
> over a far lighter HTTP transport.

### 1.3 Why a *new, standalone* adapter (not a refactor of an existing one)

The brief is explicit: **do not reuse / fork an existing vendor adapter.** The
vendor adapters (`lark`, `wecom`, `qqofficial`, `slack`, …) carry vendor-specific
signature schemes, payload shapes, and message-segment mappings. Bending one of
them into a "generic" mode would couple a public integration surface to one
vendor's quirks and make the developer experience worse for everyone.

Instead we ship `http_bot` as a clean, independent adapter whose **entire
contract is LangBot's own** — documented, versioned, and designed front-to-back
around *integrator* developer experience.

---

## 2. Goals & Non-Goals

### Goals

- **G1** A standalone `http_bot` adapter, selectable like any other platform
  adapter in the dashboard, with its own config schema and docs.
- **G2** **Inbound**: external systems POST messages to a stable LangBot URL,
  carrying a **caller-defined `session_id`** that maps 1:1 to a LangBot session.
- **G3** **Outbound**: LangBot delivers each reply by POSTing to a
  caller-configured **callback URL**; one turn may produce **many** callbacks.
- **G4** Preserve pipeline-native **N→1 aggregation** and **1→M multi-reply**.
- **G5** Server-to-server **auth**: shared-secret HMAC request signing both
  directions (no JWT, no Turnstile, no long-lived socket).
- **G6** **Great DX**: copy-pasteable curl, a tiny reference client, an OpenAPI
  fragment, idempotency, clear error envelope, and a local echo-server recipe.

### Non-Goals

- Not replacing or deprecating the WebSocket / embed widget path (that remains
  the right tool for *browser*, real-time, streaming chat UIs).
- Not a synchronous "one request → one response" RPC (explicitly rejected: it
  cannot express 1→M; see §9 for the optional sync convenience mode).
- No built-in message **persistence/replay** in v1 (callbacks are at-least-once
  best-effort; durability is the caller's responsibility — see §8).
- No multi-tenant API-key management UI in v1 (one secret per bot; see §11).

---

## 3. How LangBot routes a message (the parts we plug into)

Understanding the existing flow is what makes this adapter cheap. A message
flows through these stages (verified against current `master`):

```
                INBOUND                                         OUTBOUND
 external POST ─┐                                       ┌─ reply_message()
               ▼                                        │  reply_message_chunk()
  POST /bots/<bot_uuid>            (unified webhook router, AuthType.NONE)
               │  webhooks.py → adapter.handle_unified_webhook(bot_uuid, path, request)
               ▼                                        │
  HttpBotAdapter.handle_unified_webhook                 │  (called 0..N times
   • verify HMAC signature                              │   per turn by the
   • parse {session_id, message[]}                      │   pipeline / plugins)
   • build FriendMessage / GroupMessage                 │
   • fire registered listener  ───────────────┐        │
               │                               │        │
               ▼                               ▼        │
  botmgr.on_friend_message / on_group_message           │
   • (optional) webhook_pusher fan-out                  │
   • msg_aggregator.add_message(...) ── N→1 debounce ──►│
               │                                        │
               ▼                                        │
  query_pool → pipeline.run()  ─── invokes adapter ─────┘
                                    reply methods 1..M times
```

Two framework facts we rely on:

1. **N→1 aggregation is free.** `botmgr` hands every inbound event to
   `self.ap.msg_aggregator.add_message(...)`, which debounces per
   `session_id` and merges consecutive messages into one pipeline turn
   (`pkg/pipeline/aggregator.py`). The adapter does nothing special.

2. **1→M is free.** The pipeline (and any plugin in the chain) calls
   `adapter.reply_message()` / `reply_message_chunk()` **as many times as it
   wants** per turn. The adapter's only job is to deliver each call outward.
   For `http_bot` that means: **one outbound callback POST per call.**

3. **A unified inbound route already exists.** `WebhookRouterGroup`
   (`pkg/api/http/controller/groups/webhooks.py`) maps
   `POST /bots/<bot_uuid>[/<path>]` (auth `NONE`) to
   `adapter.handle_unified_webhook(bot_uuid, path, request)`. `http_bot`
   implements that method and is reachable **without registering any new
   route** — it does its own signature verification, exactly like the vendor
   webhook adapters do.

> Net new code is essentially: one `http_bot.py` adapter, one `http_bot.yaml`
> schema, signing helpers, and docs. No router, aggregator, or pipeline changes.

---

## 4. Architecture Overview

```
┌────────────────────┐         (1) inbound: POST signed message
│  External system   │  ──────────────────────────────────────────────►  ┌──────────────────────┐
│ (LangBot Space,    │         POST /bots/<bot_uuid>                      │      LangBot         │
│  CRM, web app …)   │         X-LB-Signature, X-LB-Timestamp             │                      │
│                    │         { session_id, message:[...] }              │  HttpBotAdapter      │
│  - callback server │  ◄──────────────────────────────────────────────  │   (platform/sources) │
│    (receives       │         (4) outbound: POST signed reply(s)         │                      │
│     replies)       │         POST <callback_url>                        │  pipeline + aggregator│
└────────────────────┘         X-LB-Signature, X-LB-Timestamp            └──────────────────────┘
                               { session_id, sequence, is_final,
                                 message:[...] }      (sent 1..M times)
```

- The adapter is **stateless across requests** at the HTTP layer; session
  continuity is carried by `session_id` and resolved by LangBot's normal
  session manager.
- **Inbound** and **outbound** are **independent HTTP exchanges**. LangBot does
  not answer the inbound POST with the pipeline result; it `202 Accepts` it and
  later POSTs the reply(s) to the callback URL. This is what makes 1→M natural.

---

## 5. Configuration Schema (`http_bot.yaml`)

Follows the existing `MessagePlatformAdapter` manifest convention (cf.
`slack.yaml`). Fields:

| field | type | required | purpose |
|---|---|---|---|
| `inbound_secret` | string (secret) | yes | HMAC key the **caller** uses to sign inbound POSTs; LangBot verifies. |
| `callback_url` | string (url) | no* | Where LangBot POSTs replies. *Optional if the caller supplies `callback_url` per-message (see §6.1); a static default lives here. |
| `outbound_secret` | string (secret) | no | HMAC key LangBot uses to sign outbound callbacks; caller verifies. Defaults to `inbound_secret` if empty. |
| `default_session_type` | enum `person`/`group` | no | Default when a message omits `session_type`. Default `person`. |
| `signature_required` | bool | no | If `false`, skip inbound signature check (dev only; logs a warning). Default `true`. |
| `callback_timeout` | int (seconds) | no | Per-callback HTTP timeout. Default `15`. |
| `callback_max_retries` | int | no | Retries on 5xx/timeout with backoff. Default `3`. |
| `webhook_url` | webhook-url (display) | — | Read-only field rendering the inbound URL `…/bots/<bot_uuid>` for copy-paste, like other webhook adapters. |

Manifest sketch (i18n labels elided for brevity):

```yaml
apiVersion: v1
kind: MessagePlatformAdapter
metadata:
  name: http_bot
  label: { en_US: "HTTP Bot", zh_Hans: "HTTP 通用接入" }
  description:
    en_US: "Integrate any backend over plain HTTP. Push messages in, receive replies on a callback URL. Server-to-server, no long-lived connection."
    zh_Hans: "通过 HTTP 接入任意后端系统。推入消息、在回调地址接收回复。面向服务间集成，无需长连接。"
  icon: http_bot.svg
spec:
  categories: [popular, global]
  help_links:
    zh: https://docs.langbot.app/zh/platforms/http-bot
    en: https://docs.langbot.app/en/platforms/http-bot
  config:
    - { name: inbound_secret,       type: string, required: true,  default: "" }
    - { name: callback_url,         type: string, required: false, default: "" }
    - { name: outbound_secret,      type: string, required: false, default: "" }
    - { name: default_session_type, type: select, required: false, default: "person",
        options: [person, group] }
    - { name: signature_required,   type: boolean, required: false, default: true }
    - { name: callback_timeout,     type: integer, required: false, default: 15 }
    - { name: callback_max_retries, type: integer, required: false, default: 3 }
    - { name: webhook_url,          type: webhook-url, required: false, default: "" }
execution:
  python:
    path: ./http_bot.py
    attr: HttpBotAdapter
```

---

## 6. The HTTP Contract (this is the DX surface)

### 6.1 Inbound — push a message into LangBot

```
POST /bots/{bot_uuid}
Content-Type: application/json
X-LB-Timestamp: 1718000000
X-LB-Signature: sha256=<hex hmac>
X-LB-Idempotency-Key: <uuid>        # optional, dedup window
```

Body:

```jsonc
{
  "session_id": "ticket-10293",        // REQUIRED. Caller-defined. Maps 1:1 to a LangBot session.
  "session_type": "person",            // optional, "person" | "group"; default from config
  "sender": {                          // optional metadata, surfaced to pipeline/plugins
    "id": "user-5567",
    "name": "Alice"
  },
  "callback_url": "https://space.langbot.app/api/lb/callback",  // optional; overrides config default
  "message": [                         // REQUIRED. A LangBot MessageChain (list of segments).
    { "type": "Text", "text": "Export keeps failing on the dashboard." },
    { "type": "Image", "url": "https://.../screenshot.png" }
  ]
}
```

Response (LangBot does **not** block on the pipeline):

```jsonc
// 202 Accepted
{
  "code": 0,
  "msg": "accepted",
  "data": {
    "session_id": "ticket-10293",
    "accepted_message_id": "in_01H....",   // server-assigned id for this inbound message
    "aggregating": true                    // true if buffered by the aggregator
  }
}
```

**N→1 in practice.** Fire three POSTs with the same `session_id` inside the
aggregation window → the pipeline runs **once** with the three messages merged.
No special flag needed; this is the aggregator's default behaviour when enabled
on the pipeline.

### 6.2 Outbound — LangBot delivers replies to your callback

For each `reply_message` / `reply_message_chunk` the pipeline emits, LangBot
POSTs to `callback_url`:

```
POST {callback_url}
Content-Type: application/json
X-LB-Timestamp: 1718000001
X-LB-Signature: sha256=<hex hmac over body>
```

Body:

```jsonc
{
  "session_id": "ticket-10293",         // echoes the inbound session
  "reply_to": "in_01H....",             // the inbound message id this answers
  "sequence": 1,                        // 1-based ordinal within this turn (for 1→M ordering)
  "is_final": false,                    // false for intermediate/streamed parts
  "stream": false,                      // true when this is a streamed chunk
  "message": [
    { "type": "Text", "text": "Looking into it — checking your export logs…" }
  ],
  "timestamp": "2026-06-22T09:00:01Z"
}
```

**1→M in practice.** A turn that fires a function call then a final answer
produces e.g.:

```
POST callback  → { sequence: 1, is_final: false, message: ["Checking logs…"] }
POST callback  → { sequence: 2, is_final: false, message: ["Found 2 failed exports."] }
POST callback  → { sequence: 3, is_final: true,  message: ["Fixed. Try again now."] }
```

The caller stitches by `session_id` + `sequence`, and knows the turn is complete
when `is_final: true` arrives.

Your callback endpoint should return `200` quickly. A non-2xx triggers retry
with backoff (`callback_max_retries`).

### 6.3 Error envelope (inbound)

Consistent, machine-readable; never leak internals:

```jsonc
{ "code": 40101, "msg": "invalid signature", "data": null }
```

| HTTP | code | meaning |
|---|---|---|
| 202 | 0 | accepted |
| 400 | 40001 | malformed body / missing `session_id` or `message` |
| 401 | 40101 | bad/expired signature |
| 403 | 40301 | bot disabled |
| 404 | 40401 | bot_uuid not found / not an `http_bot` adapter |
| 409 | 40901 | duplicate idempotency key (already accepted) |
| 413 | 41301 | message too large |
| 500 | 50001 | internal error |

---

## 7. Signing scheme (both directions)

Symmetric, dependency-free HMAC-SHA256 — trivial to implement in any language.

```
signing_string = "{timestamp}.{raw_request_body}"
signature      = "sha256=" + hex(HMAC_SHA256(secret, signing_string))
```

Verification rules:

- Reject if `|now - timestamp| > 300s` (replay window).
- Constant-time compare (`hmac.compare_digest`).
- Inbound verified with `inbound_secret`; outbound signed with
  `outbound_secret` (falls back to `inbound_secret`).
- `signature_required: false` bypasses verification **and logs a warning** —
  intended only for local development behind a trusted network.

Reference (Python, ~6 lines):

```python
import hmac, hashlib, time

def sign(secret: str, body: bytes, ts: int | None = None) -> tuple[str, str]:
    ts = ts or int(time.time())
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256)
    return str(ts), "sha256=" + mac.hexdigest()
```

---

## 8. Delivery semantics & reliability

- **Inbound**: `202 Accepted` means *queued*, not *processed*. Use
  `X-LB-Idempotency-Key` to make client retries safe (dedup window, e.g. 10 min).
- **Outbound**: **at-least-once**, best-effort. Retries on timeout/5xx with
  exponential backoff up to `callback_max_retries`. Callbacks for one
  `session_id` are delivered **in `sequence` order** (serialised per session);
  across sessions they may interleave.
- **No persistence in v1**: if LangBot restarts mid-turn, in-flight callbacks
  may be lost. Durable replay is deferred (see §13). Callers needing exactly-once
  should dedup on `(session_id, reply_to, sequence)`.
- **Backpressure**: the adapter must not block the pipeline on slow callbacks —
  outbound POSTs run on a per-session ordered queue with the configured timeout.

---

## 9. Optional: synchronous convenience mode (v1.1, behind a flag)

Some simple callers genuinely want "POST a message, get the reply in the HTTP
response" and don't care about streaming/multi-part. We can offer an **opt-in**
sync endpoint that internally waits for `is_final` and **collapses** all 1→M
parts into one array:

```
POST /bots/{bot_uuid}/sync     →    200 { session_id, message: [ ...all parts concatenated... ] }
```

Implemented by attaching a per-request future that resolves on the final reply,
with a hard timeout. This is a **convenience wrapper** over the same machinery,
explicitly documented as lossy for streaming/ordering. Not in v1 core.

---

## 10. Adapter implementation sketch (`platform/sources/http_bot.py`)

Implements `AbstractMessagePlatformAdapter`. Key methods:

```python
class HttpBotAdapter(AbstractMessagePlatformAdapter):
    listeners: dict = pydantic.Field(default_factory=dict, exclude=True)

    # --- inbound -------------------------------------------------------
    async def handle_unified_webhook(self, bot_uuid, path, request):
        body = await request.get_body()
        if self.config.get("signature_required", True):
            if not self._verify(request, body):
                return jsonify({"code": 40101, "msg": "invalid signature"}), 401
        data = json.loads(body)
        session_id    = data["session_id"]                 # caller-defined identity
        session_type  = data.get("session_type", self.config.get("default_session_type", "person"))
        chain         = MessageChain.model_validate(data["message"])
        event         = self._build_event(session_type, session_id, data.get("sender"), chain)
        # remember where to send replies for this session
        self._callback_for[session_id] = data.get("callback_url") or self.config.get("callback_url")
        # fire the registered listener → botmgr → msg_aggregator (N→1) → pipeline
        if type(event) in self.listeners:
            asyncio.create_task(self.listeners[type(event)](event, self))
        return jsonify({"code": 0, "msg": "accepted",
                        "data": {"session_id": session_id, "accepted_message_id": event.message_id}}), 202

    # --- outbound (called 1..M times per turn by the pipeline) ---------
    async def reply_message(self, message_source, message, quote_origin=False):
        return await self._post_callback(message_source, message, is_final=True, stream=False)

    async def reply_message_chunk(self, message_source, bot_message, message,
                                  quote_origin=False, is_final=False):
        return await self._post_callback(message_source, message, is_final=is_final, stream=True)

    async def is_stream_output_supported(self) -> bool:
        return True

    def register_listener(self, event_type, func):   self.listeners[event_type] = func
    def unregister_listener(self, event_type, func): self.listeners.pop(event_type, None)
    async def run_async(self): pass     # nothing to poll; purely webhook-driven
    async def kill(self): pass
```

`_post_callback` resolves the session's callback URL, assigns the next
`sequence`, signs the body, and enqueues an ordered, retrying POST.

Session→callback mapping is kept in a small in-memory dict keyed by
`session_id` (acceptable for v1; a turn's callback URL is captured at inbound
time so replies always have a destination even if config later changes).

---

## 11. Security considerations

- **Inbound route is `AuthType.NONE`** at the framework level (same as all
  webhook adapters) — the adapter **must** enforce HMAC itself. Default
  `signature_required: true`.
- **Timestamp window** (±300s) + idempotency key blunt replay.
- **SSRF on callback_url**: validate scheme (`https` in prod), and consider an
  allow-list / block of private CIDRs since LangBot initiates the POST. Document
  this; enforce in code where feasible.
- **Secret storage**: secrets live in the bot's `adapter_config` like every
  other adapter credential; surfaced as `type: string`/secret in the dashboard.
- **One secret per bot** in v1. Per-caller key rotation / multiple keys is a
  future enhancement (§13).

---

## 12. Developer Experience (explicit deliverables)

The whole point of a standalone adapter is that **integrating is pleasant**. v1
ships:

1. **`docs/platforms/http-bot.md`** — task-oriented integration guide:
   create the bot → copy inbound URL → set secret → stand up a callback
   endpoint → send first message → handle 1→M.
2. **Copy-paste curl** for the first message (with a working signing one-liner).
3. **Reference clients** (≤50 LOC each) in `examples/http-bot/`:
   `client.py` (push + a Flask/Quart callback receiver) and `client.ts`.
4. **OpenAPI fragment** `docs/http-bot-openapi.json` describing inbound +
   callback shapes, so integrators can codegen.
5. **Local echo recipe**: a one-command callback server that prints every
   reply, so a developer sees N→1 and 1→M working in under five minutes.
6. **Postman/Hoppscotch collection** (nice-to-have).

DX acceptance check: *a developer who has never seen LangBot can, from the docs
alone, push a message and observe a multi-part reply on their callback within
10 minutes.*

### Quickstart (curl)

```bash
BOT=https://your-langbot/bots/2f1c....
SECRET=supersecret
BODY='{"session_id":"ticket-10293","message":[{"type":"Text","text":"hello"}],"callback_url":"https://your-callback/recv"}'
TS=$(date +%s)
SIG="sha256=$(printf '%s.%s' "$TS" "$BODY" | openssl dgst -sha256 -hmac "$SECRET" -r | cut -d' ' -f1)"
curl -sS -X POST "$BOT" \
  -H "Content-Type: application/json" \
  -H "X-LB-Timestamp: $TS" \
  -H "X-LB-Signature: $SIG" \
  -d "$BODY"
```

---

## 13. Future work

- **Durable outbound queue** (persist + replay across restarts; exactly-once).
- **Per-caller API keys** with rotation and scopes (multi-tenant Space usage).
- **Sync convenience endpoint** (§9) once core is stable.
- **Server-Sent Events outbound option** for callers that *do* want a stream but
  not a full duplex socket — single GET, server pushes chunks.
- **Dashboard "test console"** for `http_bot` (send a message, watch callbacks)
  mirroring the existing WebSocket debug panel.

---

## 14. Rollout / task breakdown

| # | Task | Touches |
|---|---|---|
| 1 | `http_bot.yaml` manifest + icon | `platform/sources/` |
| 2 | `HttpBotAdapter` (inbound verify, event build, outbound queue) | `platform/sources/http_bot.py` |
| 3 | Signing helper module (shared) | `platform/sources/` or `utils/` |
| 4 | i18n strings (en/zh/ja) | adapter yaml + web locale |
| 5 | Integration docs `docs/platforms/http-bot.md` | `docs/` |
| 6 | OpenAPI fragment + reference clients | `docs/`, `examples/http-bot/` |
| 7 | Tests: signature verify, N→1 aggregation, 1→M ordering, retry | `tests/` |
| 8 | (opt) SSRF guard for callback_url | adapter |

No changes required to: the unified webhook router, the aggregator, the query
pool, or the pipeline. That is the design's main payoff.

---

## 15. Open questions

1. **Callback URL trust** — static (config-only) vs per-message override? Draft
   allows both; per-message is convenient but widens SSRF surface. Lock to
   config-only in prod?
2. **Session lifecycle** — when does a `session_id` "end"? Do we expose a
   `POST /bots/<uuid>/reset` keyed by `session_id` (mirrors the WS `reset`)?
3. **Group semantics** — for `session_type: group`, what is the `sender`
   identity model the Space ticket maps to?
4. **Backpressure policy** — drop, block, or buffer when a caller's callback is
   persistently down? (Draft: bounded per-session queue, then drop-oldest +
   log.)
