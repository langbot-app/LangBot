# Page Bot Adapter — Embed Demo

> English | [中文](./README.zh.md)

A single self-contained HTML page that demos the LangBot **Page Bot**
(`web_page_bot`) embeddable chat widget — the one you drop onto any website with
a single `<script>` tag.

Full guide: [docs.langbot.app — Page Bot](https://docs.langbot.app/en/usage/platforms/webpage).

## Files

| File | What it is |
|---|---|
| `index.html` | **Browser demo** — open it, point it at a running LangBot instance + a Page Bot you created, and it loads the live embed widget so you can chat with the bot exactly as a site visitor would. Zero deps, no build step. |

## How to use

1. In the LangBot WebUI, create a bot with the **Page Bot** (`页面机器人`)
   adapter and bind it to a working pipeline. Copy its **bot UUID** from the
   generated embed code.
2. Open `index.html` in a browser. Any of these work:
   - double-click the file, or
   - serve the folder: `python3 -m http.server 8930` then open
     `http://localhost:8930/examples/web-page-bot/`.
3. Fill in:
   - **LangBot base URL** — where your instance is reachable from the browser
     (e.g. `http://localhost:5300`, or your public address).
   - **Page Bot UUID** — from step 1.
   - **Widget title** — optional, sets the `data-title` attribute.
4. Click **Load widget**. A floating chat bubble appears in the bottom-right
   corner — click it and chat.

The page also renders the exact `<script>` snippet you'd paste into your own
site (before `</body>`), and updates it live as you edit the fields.

## What it demonstrates

- The embed contract: `<script data-title="…" src="<base>/api/v1/embed/<uuid>/widget.js"></script>`.
- `widget.js` is served by LangBot pre-configured for that bot UUID — title,
  bubble icon, language and optional Cloudflare Turnstile protection all come
  from the bot's config, no page changes needed.
- Messages travel over a WebSocket to the bot's bound pipeline; replies stream
  back into the bubble.

> The widget loads `widget.js` from your LangBot instance, so the **base URL
> must be reachable from the browser** you open this page in. If LangBot runs on
> a server, use its public address instead of `localhost`.
