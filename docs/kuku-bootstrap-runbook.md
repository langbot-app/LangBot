# KUKU Bootstrap Runbook

This runbook is for bootstrapping a local LangBot environment when you need to demo the KUKU setup APIs currently implemented in this repository.

## Goal

Get the current repo code running locally on `http://127.0.0.1:5300`, with:

- the KUKU API routes from this repository
- a working local database
- a known bot UUID
- a temporary API key for demo requests

## When You Need This Runbook

Use this when:

- Docker LangBot is already running on port `5300`
- the browser UI works, but the locally checked-out KUKU API routes are missing
- you need to demo local repo code instead of an older container image

## Preconditions

- You are in the repo root
- `uv` dependencies are already installed, or you can run `uv sync --dev`
- Docker may already be running a LangBot container on ports `5300` and `5401`

## One-Time Commands Per Machine

If needed:

```bash
pip install uv
uv sync --dev
```

## Bootstrap Steps

### 1. Stop Docker LangBot if it is using the same ports

Check:

```bash
docker ps --format 'table {{.Names}}\t{{.Ports}}'
```

If you see `langbot` or `langbot_plugin_runtime`, stop them:

```bash
docker stop langbot langbot_plugin_runtime
```

Why:

- the Docker image may not include your local repo changes
- it occupies ports `5300` and `5401`

### 2. Reuse the Docker database state locally

Back up the local DB and copy the Docker DB over it:

```bash
cp data/langbot.db data/langbot.db.bak.$(date +%Y%m%d%H%M%S)
cp docker/data/langbot.db data/langbot.db
```

Why:

- this keeps your existing LangBot user and bot data
- it avoids having to recreate the Discord bot in a fresh local DB

### 3. Start LangBot from the local repo checkout

Run:

```bash
uv run main.py
```

Expected startup signals:

- database migration `25` completes or is already applied
- LangBot listens on `http://0.0.0.0:5300`
- plugin runtime listens on port `5401`

### 4. Optionally start the frontend

If you need the web UI:

**One-time:** create `web/.env` so the browser calls the Python API on `5300`, not the Next.js origin on `3000`:

```bash
cd web
cp .env.example .env
```

`web/.env.example` sets `NEXT_PUBLIC_API_BASE_URL=http://localhost:5300`. Without this (or if the variable is wrong), the login screen shows **Unable to connect to the LangBot backend** because API requests default to same-origin (`/`). After editing `.env`, restart `pnpm dev` so Next.js picks up `NEXT_PUBLIC_*` values.

Then:

```bash
pnpm install
pnpm dev
```

Open:

```text
http://127.0.0.1:3000
```

Why:

- the local backend may warn that built WebUI files are missing
- the Next.js dev server is the easiest way to get a UI while keeping the local backend on `5300`

Do **not** commit `web/.env`; it is gitignored. Only `web/.env.example` belongs in the repo.

## Demo Bootstrap Data

### 5. Get the bot UUID

Run:

```bash
sqlite3 data/langbot.db "select uuid,name,adapter from bots;"
```

Example:

```text
4b78ca5c-9801-4bf6-9ea3-4144d1d2247a|LangBotTest|discord
```

Use the UUID for your demo bot.

### 6. Create a temporary API key for demo calls

Run:

```bash
sqlite3 data/langbot.db "insert into api_keys (name,key,description) values ('demo-kuku','demo-kuku-key-YYYYMMDD','Temporary local API key for KUKU demo');"
```

Example:

```text
demo-kuku-key-20260328
```

## Demo Commands

Replace the bot UUID and group ID if needed.

### List personas

```bash
curl -s http://127.0.0.1:5300/api/v1/kuku/personas \
  -H 'X-API-Key: demo-kuku-key-20260328'
```

### Save KUKU group settings

```bash
curl -s -X PUT http://127.0.0.1:5300/api/v1/kuku/groups/4b78ca5c-9801-4bf6-9ea3-4144d1d2247a/discord/demo-group \
  -H 'X-API-Key: demo-kuku-key-20260328' \
  -H 'Content-Type: application/json' \
  -d '{"persona_id":"kuku-sunny","silence_minutes":30,"cooldown_minutes":10,"quiet_hours":{"start":"00:00","end":"08:00","timezone":"UTC"},"enabled":true}'
```

### Read KUKU group settings back

```bash
curl -s http://127.0.0.1:5300/api/v1/kuku/groups/4b78ca5c-9801-4bf6-9ea3-4144d1d2247a/discord/demo-group \
  -H 'X-API-Key: demo-kuku-key-20260328'
```

### Show a guardrail failure

```bash
curl -s -X PUT http://127.0.0.1:5300/api/v1/kuku/groups/4b78ca5c-9801-4bf6-9ea3-4144d1d2247a/slack/demo-group \
  -H 'X-API-Key: demo-kuku-key-20260328' \
  -H 'Content-Type: application/json' \
  -d '{"persona_id":"kuku-sunny","enabled":true}'
```

Expected result:

- `personas` returns `kuku-sunny`
- `PUT` returns the saved settings
- `GET` returns the same settings
- the `slack` request returns `KUKU MVP only supports discord`

## Recommended Demo Narrative

Use this sequence:

1. Show that LangBot is running from the local repo checkout.
2. Show that the Discord bot already exists.
3. Show the KUKU persona catalog.
4. Save KUKU settings for one Discord group.
5. Read them back to prove persistence.
6. Trigger one invalid request to show validation.
7. Close by explaining that runtime behavior is not implemented yet; the current KUKU slice is the persistence and setup foundation.

## Shutdown And Restore

When done:

### Stop the local backend

Use `Ctrl+C` in the terminal running `uv run main.py`.

### Restart the Docker version if you want the old setup back

```bash
docker start langbot langbot_plugin_runtime
```

## Notes

- If the Discord bot token was ever shown on screen or in screenshots, rotate it after the demo.
- The KUKU APIs are backend-only today. They do not make KUKU talk in Discord yet.
- If `5300` or `5401` are already in use, check Docker first before debugging the Python process.
