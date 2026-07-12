# Troubleshooting

Troubleshooting entries are now managed as structured YAML under `../troubleshooting/`. Use `bin/lbs trouble add langbot-testing ...` to add new entries when a new failure mode is confirmed.

This Markdown file is a human-readable legacy summary. Prefer the YAML entries for automation.

## plugin-runtime-timeout: Plugin runtime actions time out

Structured entry: `../troubleshooting/plugin-runtime-timeout.yaml`

Date: 2026-05-16

### Symptom

The WebUI can send a Debug Chat message, but the bot response is missing or says `Agent runner temporarily unavailable`. Backend logs may include `Action list_plugins call timed out`, `Action list_agent_runners call timed out`, or `Action invoke_llm_stream call timed out`.

### Likely Cause

An old `langbot_plugin` runtime process survived a backend restart, or multiple runtime processes are active at once. The backend is running, but plugin actions do not get a valid response.

### Fix

Stop the LangBot backend and any orphaned `langbot_plugin.cli` runtime processes, confirm the configured backend URL is free/reachable as appropriate, then start LangBot again. A healthy startup logs `Connected to plugin runtime`, mounts `langbot/local-agent`, and initializes the default agent runner.

### Verification

Run a pipeline Debug Chat prompt. The UI should show a Bot response, and backend logs should include `Streaming completed`.

## proxy-env-mismatch: Uppercase and lowercase proxy variables differ

Structured entry: `../troubleshooting/proxy-env-mismatch.yaml`

Date: 2026-05-16

### Symptom

External model calls time out even though the proxy appears to be configured. Environment inspection shows uppercase proxy variables using `127.0.0.1:7890` while lowercase variables still point to an old WSL gateway such as `172.30.144.1:7890`.

### Likely Cause

Different libraries read different proxy variable names. If lowercase and uppercase values differ, model/provider calls can use the wrong proxy.

### Fix

Start LangBot with consistent `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `http_proxy`, `https_proxy`, `all_proxy`, `NO_PROXY`, and `no_proxy` values.

### Verification

Backend startup should no longer show old proxy addresses, and a pipeline Debug Chat should complete with a Bot response.

## mcp-stdio-args-not-applied: MCP Stdio test runs only the command without arguments

Structured entry: `../troubleshooting/mcp-stdio-args-not-applied.yaml`

The MCP form may appear filled correctly, but the backend logs show bare `uv` help text or `Connection closed`. Confirm command and args are split correctly, then check whether the form test handler reads the latest stdio args.

## survey-widget-blocks-debug-chat: Survey widget blocks Debug Chat controls

Structured entry: `../troubleshooting/survey-widget-blocks-debug-chat.yaml`

If Playwright cannot click Debug Chat `Send` because a fixed bottom-right element intercepts pointer events, close or minimize the survey widget before continuing the browser test.

## dynamic-form-missing-config-id: Dynamic form fields have no stable key

Structured entry: `../troubleshooting/dynamic-form-missing-config-id.yaml`

Dynamic plugin/runner schemas can trigger React unique-key warnings when schema items lack `id`. Prefer backend-generated stable ids and keep frontend fallback keys.

## pipeline-form-controlled-warning: Pipeline form input switches from uncontrolled to controlled

Structured entry: `../troubleshooting/pipeline-form-controlled-warning.yaml`

Pipeline edit forms should initialize string fields to empty strings and coalesce loaded nullable values before rendering inputs.

## marketplace-network-flaky: Marketplace requests are flaky but plugin data may still load

Structured entry: `../troubleshooting/marketplace-network-flaky.yaml`

Marketplace icon/tag/recommendation requests can fail while plugin cards are already visible. Retry first, and use backend component endpoints only to confirm installation results.

## agent-runner-actor-context-fields: AgentRunner reads old actor fields

Structured entry: `../troubleshooting/agent-runner-actor-context-fields.yaml`

If Debug Chat fails and logs include `ActorContext` missing `type` or `id`, update runner code to use protocol v1 fields `actor_type` and `actor_id`.

## ambiguous-runner-default-label: Runner selector shows multiple Default options

Structured entry: `../troubleshooting/ambiguous-runner-default-label.yaml`

Keep `metadata.name: default` for stable component ids, but set user-facing `metadata.label` to provider-specific names such as `Dify` or `本地 Agent`.
