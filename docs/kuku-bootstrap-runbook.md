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

- you want to run the locally checked-out KUKU API routes
- you want a repeatable local demo flow with one bot UUID and one API key

## What `kuku-bootstrap.sh` does

`./scripts/kuku-bootstrap.sh` is a **prep script**. It does **not** start the LangBot backend.

It does these things:

- makes sure there is a demo API key in `data/langbot.db`
- reads one bot UUID from the `bots` table
- writes `.kuku-demo.env` with `KUKU_API_KEY`, `KUKU_BOT_UUID`, `KUKU_GROUP_ID`, and `KUKU_API_BASE_URL`
- optionally creates `web/.env` from `web/.env.example`

It does **not** do these things:

- it does **not** run `uv run main.py`
- it does **not** run `pnpm dev`
- it does **not** create a bot for you

The script always (re)writes **`.kuku-demo.env`** at the repo root so demo `curl` commands stay consistent. That file is gitignored.

## Which path should I use?

| Situation | Use this |
|------|-----|
| You already have `data/langbot.db` with at least one bot and just want to re-run the KUKU demo flow | **Returning user** |
| You have no local DB yet, or you have a fresh empty DB with no bot rows | **Brand-new setup** |

---

## Quick start

### Returning user

Use this if `data/langbot.db` already exists and already has at least one bot.

From the **repository root**:

```bash
./scripts/kuku-bootstrap.sh
source .kuku-demo.env
```

Then start the backend in another terminal:

```bash
uv run main.py
```

Optional web UI:

```bash
./scripts/kuku-bootstrap.sh --setup-web-env
cd web && pnpm install && pnpm dev
```

### Brand-new setup

Use this if `data/langbot.db` does not exist yet, or it exists but the `bots` table is empty.

1. Start LangBot once:

```bash
uv run main.py
```

2. Finish the normal first-time setup in the UI and create at least one bot.
3. Stop LangBot.
4. Run:

```bash
./scripts/kuku-bootstrap.sh --setup-web-env
source .kuku-demo.env
```

5. Start LangBot again:

```bash
uv run main.py
```

Script help: `./scripts/kuku-bootstrap.sh --help`

If you specifically need to import an existing Docker DB, the script still supports `--first-time-from-docker`, but that is an optional migration path and not the normal local workflow.

### API key behavior

- If a row `api_keys.name = 'demo-kuku'` already exists, the script **reuses** its `key` (good for returning users).
- If not, it inserts `demo-kuku-key`.
- To recreate the key row (e.g. after manual DB edits): `./scripts/kuku-bootstrap.sh --force-new-api-key`
- If you still have an older value in the DB (e.g. `demo-kuku-key-YYYYMMDD`), the script keeps using it until you run `--force-new-api-key`, which resets the secret to `demo-kuku-key`.

---

## One-time commands per machine

If needed:

```bash
pip install uv
uv sync --dev
```

---

## Manual bootstrap (if you prefer not to use the script)

### 1. Start LangBot from the local repo checkout

Run:

```bash
uv run main.py
```

Expected startup signals:

- database migration `25` completes or is already applied
- LangBot listens on `http://0.0.0.0:5300`
- plugin runtime listens on port `5401`

### 2. Optionally start the frontend

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

**GUI alternative:** Open `data/langbot.db` in [TablePlus](https://tableplus.com/) or any SQLite client (database path = repo root’s `data/langbot.db`), select the `bots` table, and read `uuid` from the grid—same data as the query above. Example:

![TablePlus browsing the bots table in langbot.db](assets/tableplus-langbot-sqlite-bots.png)

Redact `adapter_config` in screenshots if needed; it can contain tokens. The root **README.md** (*Local development → Inspecting the SQLite database*) documents the same CLI and TablePlus workflow.

Use the UUID for your demo bot (or rely on `./scripts/kuku-bootstrap.sh`, which sets `KUKU_BOT_UUID`).

### 6. Create a temporary API key for demo calls

**Preferred:** run `./scripts/kuku-bootstrap.sh` and `source .kuku-demo.env` — the script inserts or reuses the `demo-kuku` key and keeps `KUKU_API_KEY` in sync.

**Manual:** use the same key string everywhere:

```bash
sqlite3 data/langbot.db "INSERT INTO api_keys (name,key,description) VALUES ('demo-kuku','demo-kuku-key','Temporary local API key for KUKU demo');"
```

Then `export KUKU_API_KEY=demo-kuku-key` (or `source .kuku-demo.env` after running the script).

You can also create keys in the web UI (**API Integration → API Keys**); see `docs/API_KEY_AUTH.md`.

## Demo Commands

After `source .kuku-demo.env` (or defining the same variables yourself), all examples use one key and one bot UUID.

### List personas

```bash
curl -s "${KUKU_API_BASE_URL}/api/v1/kuku/personas" \
  -H "X-API-Key: ${KUKU_API_KEY}"
```

### Save KUKU group settings

```bash
curl -s -X PUT "${KUKU_API_BASE_URL}/api/v1/kuku/groups/${KUKU_BOT_UUID}/discord/${KUKU_GROUP_ID}" \
  -H "X-API-Key: ${KUKU_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"persona_id":"kuku-sunny","silence_minutes":30,"cooldown_minutes":10,"quiet_hours":{"start":"00:00","end":"08:00","timezone":"UTC"},"enabled":true}'
```

### Read KUKU group settings back

```bash
curl -s "${KUKU_API_BASE_URL}/api/v1/kuku/groups/${KUKU_BOT_UUID}/discord/${KUKU_GROUP_ID}" \
  -H "X-API-Key: ${KUKU_API_KEY}"
```

### Show a guardrail failure

```bash
curl -s -X PUT "${KUKU_API_BASE_URL}/api/v1/kuku/groups/${KUKU_BOT_UUID}/slack/${KUKU_GROUP_ID}" \
  -H "X-API-Key: ${KUKU_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"persona_id":"kuku-sunny","enabled":true}'
```

Expected result:

- `personas` returns `kuku-sunny`
- `PUT` returns the saved settings
- `GET` returns the same settings
- the `slack` request returns `KUKU MVP only supports discord`

To use a different Discord group id for a one-off demo, source the file first, then override:

```bash
source .kuku-demo.env
export KUKU_GROUP_ID=my-other-group
```

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

## Notes

- If the Discord bot token was ever shown on screen or in screenshots, rotate it after the demo.
- The KUKU APIs are backend-only today. They do not make KUKU talk in Discord yet.
- If `5300` or `5401` are already in use, check what process is listening before debugging LangBot itself.
