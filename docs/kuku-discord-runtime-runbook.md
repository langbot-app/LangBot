# KUKU Discord Runtime — End-to-End Runbook

This runbook walks through **verifying the in-process KUKU runtime**: silence detection, LLM-generated openers, and `send_message` on Discord. It assumes you already have LangBot source from this repository.

For API keys, `.kuku-demo.env`, and database bootstrap only, see [kuku-bootstrap-runbook.md](./kuku-bootstrap-runbook.md).

For **short silence thresholds**, **tick cadence**, and **heartbeat logging** while debugging, see [kuku-silence-debug-handbook.md](./kuku-silence-debug-handbook.md).

---

## What you are validating

After configuration:

1. LangBot runs with a **Discord** bot that is **enabled** and connected.
2. That bot uses a pipeline whose `ai.runner.runner` is **`local-agent`** with a working **primary LLM**.
3. **KUKU group settings** exist for that Discord **text channel** (`group_id` = channel snowflake id).

Then LangBot will:

- Record **human** message timestamps per `(bot_uuid, discord, channel_id)`.
- About every **20 seconds**, scan enabled rows in `kuku_group_settings`.
- When **silence_minutes** have passed with no new human messages, and **quiet_hours** / **cooldown_minutes** allow it, call the pipeline’s **local-agent primary model** and post **one** proactive message in the channel.

No separate plugin package is required; the runtime lives in `src/langbot/pkg/kuku/`.

---

## Prerequisites

### Discord

- A Discord application, bot **token**, and the bot **invited** to a server with permission to **View Channel**, **Read Message History**, and **Send Messages** in a text channel.
- In the [Discord Developer Portal](https://discord.com/developers/applications), under **Bot**, enable **Message Content Intent** if you depend on content in adapters (the LangBot Discord adapter sets message content intent).
- Obtain the **text channel ID** (Discord: Settings → App Settings → Advanced → Developer Mode → right‑click the channel → Copy Channel ID). This value is the KUKU **`group_id`** for guild text channels.

### LangBot

- Python env: from the repo root, `uv sync --dev`.
- Default HTTP API in dev: `http://127.0.0.1:5300` (see project `AGENTS.md` / main config).

---

## Step 1 — Run the backend (and optional Web UI)

From the repository root:

```bash
uv run main.py
```

Optional: run the Next.js admin UI (separate terminal):

```bash
cd web
cp .env.example .env
pnpm install
pnpm dev
```

Open `http://127.0.0.1:3000` for bot and pipeline setup.

---

## Step 2 — Create or confirm a Discord bot and pipeline

In the Web UI (or equivalent API/config flows):

1. **Bots** → create or edit a bot with adapter **`discord`**, paste the **token**, set **enabled**, save.
2. Assign a **pipeline** that uses **`local-agent`** and a configured **`ai.local-agent.model`** primary UUID (or legacy string UUID for the model).
3. Confirm normal conversational use works in your test channel (optional but strongly recommended before testing silence).

Note the bot’s **`uuid`** (shown in the UI or read from the `bots` table).

---

## Step 3 — Authenticate KUKU API calls

KUKU routes expect `Authorization: Bearer …` with a **user token** or **API key** (`USER_TOKEN_OR_API_KEY`).

**Fast local path:** from the repo root:

```bash
./scripts/kuku-bootstrap.sh
source .kuku-demo.env
```

This sets variables such as `KUKU_API_BASE_URL`, `KUKU_API_KEY`, `KUKU_BOT_UUID`, and `KUKU_GROUP_ID` (see [kuku-bootstrap-runbook.md](./kuku-bootstrap-runbook.md)). **Override `KUKU_GROUP_ID`** if the script’s default channel id does not match your test channel.

Alternatively, use any valid LangBot API key or session token you already have.

---

## Step 4 — Enable KUKU for the Discord channel

### Endpoint

- **GET** / **PUT**  
  `{API_BASE}/api/v1/kuku/groups/{bot_uuid}/{platform}/{group_id}`

Use:

- `platform` = **`discord`**
- `group_id` = **Discord text channel id** (string)

### PUT body (JSON)

| Field | Purpose |
|--------|---------|
| `silence_minutes` | Minutes after the last **human** message before KUKU may speak when **`silence_seconds`** is not set (default in templates is often 30; use **`1`** for quick manual tests). |
| `silence_seconds` | Optional. When set to a positive integer, **seconds** of quiet after the last **human** message (overrides the minute-based threshold). See [kuku-silence-debug-handbook.md](./kuku-silence-debug-handbook.md). |
| `cooldown_minutes` | Minimum minutes between KUKU proactive sends for that scope (use **`1`** for quick tests). |
| `quiet_hours` | Optional. Object with `start`, `end` (`HH:MM`), and optional `timezone` (IANA name, e.g. `UTC`). Empty `{}` disables. |
| `persona_id` | Optional; default **`kuku-sunny`**. |
| `enabled` | **`true`** to activate. |

The route **always** overwrites `bot_uuid`, `platform`, and `group_id` from the URL, so do not rely on the body for scope.

### Example

```bash
curl -s -X PUT "${KUKU_API_BASE_URL}/api/v1/kuku/groups/${KUKU_BOT_UUID}/discord/${KUKU_GROUP_ID}" \
  -H "Authorization: Bearer ${KUKU_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"silence_minutes":1,"cooldown_minutes":1,"enabled":true,"quiet_hours":{}}'
```

### Verify

```bash
curl -s "${KUKU_API_BASE_URL}/api/v1/kuku/groups/${KUKU_BOT_UUID}/discord/${KUKU_GROUP_ID}" \
  -H "Authorization: Bearer ${KUKU_API_KEY}"
```

You should receive JSON with `data.group` including your settings.

---

## Step 5 — Exercise proactive behavior

1. Keep **`uv run main.py`** running so the **KUKU background loop** is active.
2. In Discord, in the **same text channel** as `group_id`, send a message as a **normal user** (not as another bot). This seeds “last human activity” for KUKU.
3. **Stop typing** in that channel; wait at least **`silence_minutes`**.
4. You should see **one** new message from the bot (the opener). Subsequent messages respect **`cooldown_minutes`** and a new **`silence_minutes`** window after human silence.

### Logs

Python logger name: **`langbot.kuku`**. LLM failures, `send_message` errors, or pipeline/model misconfiguration surface there.

---

## Troubleshooting

| Symptom | What to check |
|--------|----------------|
| Nothing happens | At least **one human** message in the channel **after** KUKU was enabled; **channel id** in the URL matches the channel you are testing. |
| Still nothing | Bot **enabled** in LangBot; Discord process connected; `enabled: true` on the KUKU row. |
| Errors about LLM / model | Pipeline must be **`local-agent`** with a resolvable **primary** model UUID. Fix normal chat first. |
| Very long wait | Lower **`silence_minutes`** in the PUT for testing (e.g. `1`). |
| Wrong channel | `group_id` must be the **text channel** snowflake, not the guild (server) id. |
| Token / security | If the bot token appeared in a screen recording or shared log, **rotate** it in the Discord portal. |

---

## API reference (quick)

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/v1/kuku/personas` | MVP persona catalog. |
| GET | `/api/v1/kuku/groups/{bot_uuid}/{platform}/{group_id}` | Read settings; 404 if missing. |
| PUT | `/api/v1/kuku/groups/{bot_uuid}/{platform}/{group_id}` | Upsert settings; body JSON. |

`platform` must be **`discord`** for the current MVP validation rules in `KukuService`.

---

## Related files

- Runtime implementation: `src/langbot/pkg/kuku/runtime.py`
- Group settings service: `src/langbot/pkg/api/http/service/kuku.py`
- HTTP routes: `src/langbot/pkg/api/http/controller/groups/kuku.py`
- Discord activity hook: `src/langbot/pkg/platform/botmgr.py` (group messages)
- Design context: `docs/kuku-design.md`
