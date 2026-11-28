# Harness Space code redemption (L1)

`oauth.space_code` is an encrypted one-request HTS1 method. It accepts
`code`, `code_verifier`, `redirect_uri`, `workspace_uuid`, and `account_uuid`.
Core takes binding and device identifiers from the verified handshake, not the
body. The Space account UUID is a candidate selector for the local preflight;
Space independently verifies it as part of the conditional code consumption.

The pilot is disabled by default. Configure `harness.space_oauth` with
`enabled`, `space_origin`, `redirect_uri`, and `workspace_uuid`. The confidential
credential comes only from `LANGBOT_HARNESS_SPACE_CLIENT_SECRET`. The link must
select `space` authorization and match the registered Workspace. Core checks the
local account/Workspace projection, locks the live membership and pending
enrollment, then consumes at Space. It commits the binding, device claim, and
grant together. If Space may have spent the code but Core did not commit, start
a fresh consent flow; neither side retries the exchange automatically.

This change does not open the production Cloud route gate. Restricted-role
tenant RLS and the production Web/Tauri consent callback still require
integration and verification. The browser test uses local consent and callback
pages, a seeded Space session, and the actual Space and Core transports.

## Local verification

Use an isolated PostgreSQL server with two disposable databases and isolated
Redis. The Space suite migrates its test database; Core creates and drops a
unique schema in its database. Core uses the in-tree SDK. Install the Core dev
environment (`uv sync --dev`) and use Node 26 or a compatible Node with WebSocket
and WebCrypto support. From a directory containing all three checkouts:

```bash
ROOT=$PWD
BROWSER_TOOLS=$(mktemp -d)
npm install --prefix "$BROWSER_TOOLS" playwright-core esbuild
cd "$ROOT/LangBot-Harness"
pnpm install --frozen-lockfile
pnpm --dir packages/core build
printf '%s\n' "export * from './packages/core/dist/rpc-transport.js';" \
  "export * from './packages/core/dist/transport.js';" > .space-test-entry.mjs
"$BROWSER_TOOLS/node_modules/.bin/esbuild" .space-test-entry.mjs --bundle --format=esm \
  --outfile="$BROWSER_TOOLS/core.js"
rm .space-test-entry.mjs
export HARNESS_TS_RPC_TRANSPORT="$PWD/packages/core/dist/rpc-transport.js"
export HARNESS_TS_TRANSPORT="$PWD/packages/core/dist/transport.js"
export HARNESS_PLAYWRIGHT="$BROWSER_TOOLS/node_modules/playwright-core/index.mjs"
export HARNESS_BROWSER_BUNDLE="$BROWSER_TOOLS/core.js"
export HARNESS_CHROMIUM="$(command -v chromium)"
export HARNESS_PYTHON="$ROOT/LangBot/.venv/bin/python"
export HARNESS_CORE_TEST_SCRIPT="$ROOT/LangBot/tests/integration/harness/run-space-acceptance.sh"
export HARNESS_TEST_POSTGRES_URL=postgresql+asyncpg://typer@127.0.0.1:56491/harness_core_l1

cd "$ROOT/langbot-space"
SPACE_DATABASE_MIGRATION_TEST_DSN='host=127.0.0.1 port=56491 user=typer dbname=harness_space_l1 sslmode=disable' \
  TEST_REDIS_ADDR=127.0.0.1:56502 go test ./internal/controller/groups \
  -run '^TestHarnessOAuthCrossRepository$' -count=1 -v
```

The two selected pytest cases must pass: the negative/concurrency matrix and
the Chromium consent → pinned HTS1 → encrypted WSS authentication flow. The
temporary browser context accepts the local fixture certificates; the Core
exchange uses certificate verification against the fixture CA.
