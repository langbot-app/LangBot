# Plugin E2E Smoke

Use this reference to validate LangBot plugin behavior with a browser-first flow and API/log diagnostics.

## Fixture

Use the bundled local plugin source:

```text
fixtures/plugins/qa-plugin-smoke
```

It registers:

- Plugin id: `qa/plugin-smoke`
- Tool: `qa_echo(text: string)` returning `qa-plugin-smoke:<text>`
- Tool: `qa_plugin_echo(text: string)` returning `qa-plugin-smoke:<text>`
- Tool: `qa_plugin_sleep(seconds: number, text: string)` returning `qa-plugin-smoke:sleep:<seconds>:<text>` after a bounded delay
- Page: `smoke`, with an HTML asset and a backend page API sentinel `qa-plugin-smoke-page`

## SDK Under Test

When validating a local SDK build, install it into the LangBot worktree virtualenv:

```bash
cd "$LANGBOT_REPO"
uv pip install -e /absolute/path/to/langbot-plugin-sdk-test-build
uv run --no-sync python -c "import langbot_plugin, pathlib; print(pathlib.Path(langbot_plugin.__file__).resolve())"
```

The printed path must point into the local SDK source tree. Use `uv run --no-sync` for LangBot startup and tests; plain `uv run` may sync the lockfile and restore the PyPI package.

## Build The Fixture

From the fixture directory, build with the same SDK that LangBot will run:

```bash
cd skills/langbot-testing/fixtures/plugins/qa-plugin-smoke
"$LANGBOT_REPO/.venv/bin/lbp" build
```

The generated zip under `dist/` is the file to upload from the WebUI.

## Browser Flow

1. Start or verify backend and frontend.
2. Open `LANGBOT_FRONTEND_URL`.
3. Initialize or log in to the test instance.
4. Navigate to `Plugins`.
5. Choose local plugin install and upload the generated `qa-plugin-smoke` zip.
6. Wait for the install task to finish.
7. Confirm the plugin list/detail shows `QA Plugin Smoke`, `qa_echo`, and `Smoke Page`.
8. Open the plugin extension page if it appears in the sidebar and verify it renders the sentinel text.

## Diagnostic Checks

Use API checks only to confirm what the UI exercised:

- `GET /api/v1/plugins` contains `qa/plugin-smoke` with initialized status.
- `GET /api/v1/tools` contains `qa_echo`, `qa_plugin_echo`, and `qa_plugin_sleep`.
- `POST /api/v1/plugins/qa/plugin-smoke/page-api` with `page_id=smoke`, `endpoint=/ping`, `method=GET` returns `qa-plugin-smoke-page`.
- Backend logs include `Connected to plugin runtime` and no `Action ... call timed out` entries.

## Cleanup

Delete `qa/plugin-smoke` through the WebUI or `DELETE /api/v1/plugins/qa/plugin-smoke?delete_data=true` after recording results.
