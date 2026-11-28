# Self-hosted Harness TOTP handoff

The self-hosted encrypted `oauth.password` RPC issues `interaction_required` with
`details.{handoff_ticket,handoff_url,expires_in}` after verifying the password
and Workspace access. The 180-second handle is stored only as a digest and is
bound to the verified device and enrollment. One ticket per account per
window bounds code guesses (five attempts). The HTTPS browser page requires a
same-origin POST and uses the existing single-use TOTP counter check. The page
never issues a grant. Keep the query string out of proxy access logs.

Only `oauth.handoff.poll` from the original device can redeem an approved
ticket. Redemption locks and rechecks link, keys, credentials, and Workspace
membership. The ticket state, device claim, binding, and grant commit together.
An interrupted client may need to start again with a new link if redemption
already committed. The Core schema change is Alembic `0066_harness_handoff`.

## Linux browser reproduction

Use Core on the handoff branch (base `b2dc190cef40305ffcaf307e4ef160d671df44d7`)
and Harness `72c787f15da58aa9fcd55cdb051dad5e27003b39`. Set `HARNESS` to the
absolute path of that Harness checkout and `CHROMIUM_BIN` to your local
Chromium executable (verified with Chromium 157.0.8103.38). From Core:

```bash
export HARNESS=/absolute/path/to/LangBot-Harness
export CHROMIUM_BIN=/absolute/path/to/chromium
pnpm --dir "$HARNESS" install --frozen-lockfile
pnpm --dir "$HARNESS/packages/core" build
pnpm --dir "$HARNESS/apps/web" build
probe_dir=$(mktemp -d)
npm install --prefix "$probe_dir" --no-audit --no-fund playwright-core@1.65.1 esbuild@0.28.2
printf 'export * from "%s";\n' "$HARNESS/packages/core/dist/"{registration,device-keys,rpc-transport,bound-chat}.js > "$probe_dir/probe.mjs"
"$probe_dir/node_modules/.bin/esbuild" "$probe_dir/probe.mjs" --bundle --format=esm --outfile="$probe_dir/bundle.js"
export HARNESS_WEB_DIST="$HARNESS/apps/web/dist"
export HARNESS_HANDOFF_TEST_BUNDLE="$probe_dir/bundle.js"
export HARNESS_PLAYWRIGHT_MODULE="$probe_dir/node_modules/playwright-core"
export HARNESS_SCREENSHOTS="$PWD/handoff-evidence"
uv sync --frozen --dev
uv run --frozen pytest -xq -s tests/integration/harness/test_handoff_browser.py
```

Expected: four passes. The fixture uses isolated HTTPS with a local self-signed
certificate, on-disk SQLite, the in-tree SDK, and real Core HTS1/TOTP/WSS
handlers. It enrolls a real TOTP credential and generates the current code with
the test authenticator secret. On success, Chromium submits the code in the
approval tab, checks the saved IndexedDB entry, rejects replay, and verifies the
encrypted WSS `authenticated` frame using the grant from that enrollment.
The cancellation, expiry (database clock deadline moved into the past), and
cross-device cases assert no claimed device, binding, or grant, with an empty
instance registry after page reload. The cross-device case stops the original
UI poller, then submits the approved ticket over a second enrolled device's
own HTS1 connection.

Test-only probes supply the current code, observe the real grant for a WSS auth
probe, and inspect the isolated database. This is Web/Chromium authentication
acceptance; it does not exercise Tauri packaging, Runner chat, Cloud, or a
production deployment.
