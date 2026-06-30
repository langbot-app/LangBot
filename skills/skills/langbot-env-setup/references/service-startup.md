# Service Startup

Use this reference for LangBot backend/frontend readiness checks regardless of OS or browser-control method. Read `skills/.env` first and override those defaults with user-provided values or detected running services.

## Variables

- `LANGBOT_REPO`
- `LANGBOT_WEB_REPO`
- `LANGBOT_BACKEND_URL`
- `LANGBOT_FRONTEND_URL`
- `LANGBOT_DEV_FRONTEND_URL`

## Backend

Start LangBot from the backend repo:

```bash
cd "$LANGBOT_REPO"
uv run main.py
```

Healthy startup includes:

```text
Running on http://0.0.0.0:<backend-port>
Connected to plugin runtime.
Plugin langbot/local-agent initialized
```

Quick check:

```bash
curl -I --max-time 3 "$LANGBOT_BACKEND_URL/login"
```

If `bin/lbs env doctor` reports that `LANGBOT_BACKEND_URL` has no TCP listener,
the backend is not running at the configured host and port. A reachable
standalone frontend on `LANGBOT_FRONTEND_URL` does not prove backend readiness.

Prefer a visible terminal session while debugging backend startup. Detached
background startup methods can hide early process exits in local agent runs; if
you use one, immediately verify both the process and the listener:

```bash
ps -eo pid,cmd | rg 'main.py|uv run main|langbot'
ss -ltnp | rg ':5300'
curl -I --max-time 3 "$LANGBOT_BACKEND_URL/login"
```

## Frontend

Start the new frontend from the web repo:

```bash
cd "$LANGBOT_WEB_REPO"
VITE_API_BASE_URL="$LANGBOT_BACKEND_URL" pnpm dev --host 0.0.0.0
```

Healthy startup includes:

```text
Local: <frontend-url>
```

Quick check:

```bash
curl -I --max-time 3 "$LANGBOT_FRONTEND_URL"
```

If `VITE_API_BASE_URL` is missing, Vite still serves the page but frontend API
calls may go to the frontend port instead of the backend port. That produces
false browser failures in login, wizard, pipeline, and Debug Chat cases.

## Completion Signal

Environment setup is not complete until the required frontend/backend URLs are reachable and the chosen browser-control path can open the WebUI.
