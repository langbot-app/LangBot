# LangBot QA Skills User Guide

Use this guide as the first operational path after reading `README.md` and
`AGENTS.md`.

## 1. Configure Local Inputs

Read `skills/.env`, then create `skills/.env.local` for machine-local values.
Do not commit `.env.local`, browser profiles, reports, tokens, API keys, OAuth
state, or provider credentials.

Minimum local fields for live browser QA:

```bash
LANGBOT_REPO=/path/to/LangBot
LANGBOT_WEB_REPO=/path/to/LangBot/web
LANGBOT_BACKEND_URL=http://127.0.0.1:5300
LANGBOT_FRONTEND_URL=http://127.0.0.1:3000
LANGBOT_DEV_FRONTEND_URL=http://127.0.0.1:3000
LANGBOT_BROWSER_PROFILE=/path/to/langbot-browser-profile
LANGBOT_CHROMIUM_EXECUTABLE=/path/to/chromium-or-playwright-chrome
LANGBOT_E2E_LOGIN_USER=qa-local@example.com
```

`LANGBOT_E2E_LOGIN_USER` is a local QA account. The setup automation uses the
LangBot recovery key from the active checkout to initialize or refresh that
local account and write a browser `localStorage` token. It does not need the
user's GitHub or Space credentials.

## 2. Check Readiness

From `skills/`:

```bash
bin/lbs env show
bin/lbs env doctor
bin/lbs validate
bin/lbs index --check
```

`env doctor` should report reachable backend and frontend URLs before live
browser cases are run. Missing Space provider credentials are not a LangBot
product pass; classify them as `env_issue` and configure the local Space
provider before measuring Debug Chat performance.

## 3. Start Services

Start the backend from `LANGBOT_REPO`:

```bash
cd "$LANGBOT_REPO"
uv run main.py
```

Start the standalone frontend from `LANGBOT_WEB_REPO` and point it at the
backend:

```bash
cd "$LANGBOT_WEB_REPO"
VITE_API_BASE_URL="$LANGBOT_BACKEND_URL" pnpm dev --host 0.0.0.0
```

If `VITE_API_BASE_URL` is missing, browser tests can load the Vite page but send
API requests to the frontend port, which produces false UI failures.

## 4. Prepare User-Path Fixtures

For local-agent Debug Chat cases and the user-path performance gate:

```bash
node scripts/e2e/ensure-local-agent-pipeline.mjs --write-env
```

The script:

- refreshes the local QA login and browser token;
- marks the local wizard as skipped;
- creates or updates a local QA pipeline;
- scans Space LLM models, tests candidates, and switches to the first working
  Space model with tested fallback models;
- writes `LANGBOT_PIPELINE_URL`, `LANGBOT_PIPELINE_NAME`, and local-agent
  pipeline/model variables into `skills/.env.local`;
- returns `env_issue` when no Space model can be scanned or tested.

Useful model controls:

```bash
LANGBOT_E2E_MODEL_TEST_LIMIT=8
LANGBOT_E2E_MODEL_FALLBACK_COUNT=3
LANGBOT_E2E_SKIP_MODEL_UUIDS=uuid-a,uuid-b
LANGBOT_E2E_SKIP_MODEL_NAMES=model-a,model-b
LANGBOT_E2E_SCAN_SPACE_MODELS=true
```

The setup writes a current-runtime compatibility `max-round` value into the
pipeline config because this backend still reads that field directly during
message truncation. Do not treat it as a long-term QA contract.

## 5. Run Gates

Fast contract gate, no live service required:

```bash
bin/lbs suite run langbot-performance-contract-gate --run-id langbot-contract-local
```

Live backend gate:

```bash
bin/lbs suite run langbot-live-backend-gate --run-id langbot-backend-local
```

Browser-visible user-path performance gate:

```bash
bin/lbs suite plan langbot-user-path-performance-gate
bin/lbs suite run langbot-user-path-performance-gate --run-id langbot-user-path-local --include-manual-check
```

`manual_check` means the agent must confirm the declared preconditions for that
run window. When setup automation is declared, run output may stop early with
`env_issue`; fix that environment input before treating the product path as
measured.

## 6. Read Results

Suite reports live under `skills/reports/`. Evidence lives under
`skills/reports/evidence/<run-id>/`.

For performance cases, inspect:

- `metrics.json` for p50/p95/p99, error rate, and total duration;
- `automation-result.json` for threshold decisions and artifacts;
- `console.log` and `network.log` for frontend/API failures;
- backend logs for provider, runner, WebSocket, or persistence failures.

Do not call a user-path performance result a LangBot overhead regression until
provider/tool/network time has been separated or ruled out.
