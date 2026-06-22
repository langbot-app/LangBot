# HTTP Bot Adapter — Reference Clients

Minimal, dependency-light clients for the LangBot **HTTP Bot** platform adapter.
They show the whole loop: signing a request, pushing a message, and receiving
multi-part replies on a callback endpoint.

Full guide: [`docs/platforms/http-bot.md`](../../docs/platforms/http-bot.md).
Machine-readable contract: [`docs/http-bot-openapi.json`](../../docs/http-bot-openapi.json).

## Files

| File | What it is |
|---|---|
| `playground.py` | **Interactive browser debug console** — a single-file web app you open in a browser to chat with a running `http_bot` bot and watch signing / 202 / callbacks live. Zero extra deps. |
| `client.py` | Python client + Flask callback receiver (`pip install flask requests`). |
| `client.ts` | TypeScript/Node 18+ client + callback receiver, **zero deps** (`npx tsx client.ts`). |

All three implement the identical HMAC-SHA256 scheme
(`sha256=hex(HMAC(secret, "{timestamp}." + body))`) — verified byte-for-byte
against the adapter.

## Interactive playground (recommended first run)

A self-contained web console: type a message in your browser, it is signed and
POSTed to a **running** `http_bot` bot, and the bot's replies stream back into
the page — with a debug panel showing the signature, the `202` ack, and each
callback's `sequence` / signature-verification.

```bash
# From the LangBot repo root, with the backend already running:
PUBLIC_IP=<your-host-ip> ./.venv/bin/python examples/http-bot/playground.py
# then open  http://<your-host-ip>:8920/
```

On startup it reads the LangBot API key + the `http_bot` bot from
`data/langbot.db`, and configures that bot (inbound/outbound secret +
`callback_url`) to point back at itself via the LangBot API — the bot reloads
live, no restart needed. Requirements: an enabled `http_bot` bot bound to a
working pipeline, and port `8920` reachable from your browser.

Env knobs: `PUBLIC_IP` (default `127.0.0.1`), `PLAYGROUND_PORT` (default `8920`).

## Headless clients

```bash
# Python — Terminal 1: callback receiver (your callback_url target)
python client.py serve --port 8900 --secret SHARED_SECRET

# Python — Terminal 2: push a message
python client.py push --url https://your-langbot/bots/<BOT_UUID> \
    --secret SHARED_SECRET --session ticket-1 --text "hello"

# blocking sync mode
python client.py sync  --url https://your-langbot/bots/<BOT_UUID> \
    --secret SHARED_SECRET --session ticket-1 --text "hello"

# reset a session
python client.py reset --url https://your-langbot/bots/<BOT_UUID> \
    --secret SHARED_SECRET --session ticket-1
```

```bash
# TypeScript (Node 18+)
npx tsx client.ts serve 8900 SHARED_SECRET
npx tsx client.ts push  https://your-langbot/bots/<BOT_UUID> SHARED_SECRET ticket-1 "hello"
```

When the bot replies, the receiver prints each part with its `sequence` and an
`[FINAL]` marker on the last one — that's the 1→M multi-reply model in action.

> The bot's `callback_url` must be reachable from LangBot. For local testing,
> expose your receiver with a tunnel (cloudflared / ngrok) and set that URL in
> the bot config.
