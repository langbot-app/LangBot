# n8n Workflow Agent

Run an n8n workflow webhook as a LangBot Runner.

[简体中文](readme/README_zh_Hans.md) · [日本語](readme/README_ja_JP.md)

## Runner ID

`plugin:langbot-team/N8nAgent/default`

## Configuration

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| webhook-url | string | yes | '' | n8n webhook URL |
| auth-type | select | yes | none | Authentication type (none/basic/jwt/header) |
| basic-username | string | no | '' | Basic auth username |
| basic-password | secret | no | '' | Basic auth password |
| basic-encoding | select | no | utf-8 | `utf-8` keeps the plugin default; `latin1` preserves native non-ASCII Basic credentials |
| jwt-secret | secret | no | '' | JWT secret |
| jwt-algorithm | string | no | HS256 | JWT algorithm |
| header-name | string | no | '' | Custom header name |
| header-value | secret | no | '' | Custom header value |
| advanced-settings | boolean | no | false | Show timeout and response mapping controls |
| timeout | integer | no | 120 | Request timeout (seconds) |
| output-key | string | no | response | Response output key |
| response-handling | select | no | reply | `reply` forwards HTTP 200 output; `ignore` accepts any HTTP 2xx without reading or forwarding its body |
| langbot-assets-enabled | boolean | no | false | Register a short-lived LangBot asset token for each run and inject it into the webhook payload |
| langbot-assets-gateway-host | string | no | 0.0.0.0 | Host for the local LangBot Asset Gateway |
| langbot-assets-gateway-port | integer | no | 8765 | Port for the local LangBot Asset Gateway |
| langbot-assets-gateway-request-timeout | integer | no | 60 | Timeout for individual gateway tool calls |
| langbot-assets-token-ttl | integer | no | 3600 | Lifetime of each run token in seconds |
| langbot-assets-input-name | string | no | langbot_asset_run_token | Webhook payload field that receives the run token |

## Response handling and native migration

- `reply` is the default and requires HTTP 200. It parses streaming `item`/`end`
  objects, the configured JSON `output-key`, or plain text. JSON objects without
  that key are serialized whole; arrays fall back to the original text.
- `ignore` waits for HTTP response headers, accepts **all 2xx statuses**, closes
  the response without reading its body, and completes without a chat reply.
  It is **not** background fire-and-forget: configure n8n's Webhook to **Respond
  Immediately**. Non-2xx responses and timeouts still fail.
- `timeout` (default 120 seconds) bounds the entire webhook request, including
  headers and reply body, in addition to HTTPX's per-phase timeout. Reply data is
  capped at 1,048,576 characters, matching the native runner's runtime limit.
- Ignored responses end the run immediately after acceptance. Asset tokens are
  revoked then, so a background workflow **cannot** keep using the run's LangBot
  resources. Leave `langbot-assets-enabled=false` unless callbacks are explicitly
  authorized and finish before the webhook responds.

Configuration moves from `ai.n8n-service-api` to
`ai.runner_config["plugin:langbot-team/N8nAgent/default"]`; this is pipeline Runner
configuration, not plugin-instance settings. All eleven native fields retain
their names, including `response-handling`. The placeholder webhook URL is no
longer a default: an explicit working URL is required. Authentication remains
none/Basic/JWT/custom-header, with JWT `sub=n8n-webhook` and one-hour expiry.
Secrets are not trimmed. Error bodies and exception details are deliberately
not echoed to chat/logs; use the n8n service's diagnostics to investigate errors.

Native aiohttp Basic auth used Latin-1; HTTPX defaults to UTF-8. Both are now
supported through `basic-encoding`. Keep the plugin default `utf-8` for existing
plugin setups; select `latin1` when preserving native Basic-auth bytes, especially
for non-ASCII credentials. ASCII credentials produce identical bytes in both.
Encoding differences are not assumed to be a security improvement.

The modern Host/SDK architecture is retained, with these explicit differences:

- The plugin streams each item rather than batching every eight native items;
  Host delivery decides how the channel displays chunks. Incremental UTF-8
  decoding preserves characters split across network packets.
- Empty **reply** output remains an explicit `n8n.empty_response` failure rather
  than a native empty message. It is never a failure in **ignore** mode.
- `msg_create_time` is always present (default empty string); provided values,
  including zero, are preserved. Business parameters come from
  `ctx.adapter.extra.params`, not the old unrestricted `query.variables` object.
- `external.conversation_id` and `external.session_id` live in Host conversation
  state; generated IDs do not automatically reuse native session UUIDs. `user_id`
  still derives from the SDK actor, whereas native used launcher/chat identity.
  **These are identity/scope changes, not proven security improvements.** Existing
  workflows require an explicit scoped state/identity migration or approved reset;
  this change does not migrate state or claim remote conversation continuity.
- Reserved identity fields cannot be overwritten by adapter parameters. HTTP
  redirects are not followed automatically; configure the final webhook URL.
- No native history/max-round loop is restored: native n8n sent current input,
  not local-agent history. Host history/tools/knowledge callbacks are a separate,
  opt-in capability; migration must not silently enable them.

## LangBot Asset Callback Through n8n MCP Client Tool

n8n can call back into LangBot assets through the SDK Asset Gateway, the same
mechanism the Dify runner uses. The gateway is a run-token-authorized MCP server
(`POST /mcp`, JSON-RPC) that exposes the run-authorized LangBot tools:
`langbot_list_assets`, `langbot_get_current_event`, `langbot_history_page`,
`langbot_retrieve_knowledge`, `langbot_get_tool_detail`, and `langbot_call_tool`.

### How it works

1. When `langbot-assets-enabled` is true, this runner registers a short-lived,
   run-scoped token before calling the webhook and injects it into the webhook
   payload under `langbot-assets-input-name` (default `langbot_asset_run_token`).
2. The n8n workflow consumes the webhook, reads that field, and passes it as the
   `run_token` argument on every LangBot MCP tool call.
3. The runner removes the token when the run ends. Tool calls without a valid
   token are rejected by the gateway.

The gateway accepts the token either via an `Authorization: Bearer` header or via
a `run_token` tool-call argument. Because n8n credentials are static and cannot
carry a per-run header, use the **`run_token` argument** approach (same as Dify).

### Build the n8n workflow

The n8n workflow behind the webhook must use an **AI Agent** node with an
**MCP Client Tool** node attached:

1. **Webhook** trigger node — receives the LangBot payload, including
   `langbot_asset_run_token`. Respond when the last node finishes so the asset
   callbacks happen inside the request window (before the token is revoked).
2. **MCP Client Tool** node (n8n version >= 1.2, `defaultVersion` 1.3):
   - Transport: **HTTP Streamable**.
   - Endpoint: the public URL that routes to the gateway `/mcp`, e.g.
     `https://example.com/mcp`.
   - Authentication: **None** (the token travels as a tool argument, not a header).
3. **AI Agent** node — attach the MCP Client Tool. In the system prompt, instruct
   the agent to pass `run_token` on every LangBot tool call, for example:

   ```text
   For every LangBot MCP tool call, set run_token exactly to:
   {{ $json.langbot_asset_run_token }}
   Call langbot_list_assets first when you need to discover available LangBot
   assets for the current run.
   ```

4. Return the agent output in the webhook response (streaming `type: item`/`end`
   chunks, or a JSON object keyed by `output-key`).

### Configure LangBot

Select the n8n runner on the LangBot pipeline and set:

```text
webhook-url = <your n8n webhook URL>
auth-type = none
timeout = 120
langbot-assets-enabled = true
langbot-assets-gateway-host = 0.0.0.0
langbot-assets-gateway-port = 8765
langbot-assets-gateway-request-timeout = 60
langbot-assets-token-ttl = 3600
langbot-assets-input-name = langbot_asset_run_token
```

The public MCP endpoint configured in the n8n MCP Client Tool node must route to
this same gateway instance. The runner only injects the short-lived token into
the webhook payload; it does not create or update the n8n MCP Client Tool node.

### Limitations

- n8n Cloud (and any n8n that cannot reach `localhost`) needs a public HTTPS URL
  for the gateway `/mcp` endpoint. Temporary tunnel URLs are for testing only.
- The run token is short-lived and run-scoped, injected only while LangBot calls
  the webhook and revoked when the run finishes. The workflow must complete its
  asset callbacks within the webhook request.
- The gateway exposes only the assets permitted by the current run: current
  event, history page, knowledge retrieval, tool detail, and tool call.
- n8n's MCP Client Tool uses the official MCP SDK (`StreamableHTTPClientTransport`).
  Verify the `initialize` + `tools/list` handshake against your gateway once when
  setting it up.

## Legacy Runner

Migrated from `n8n-service-api` in LangBot.

### Provider identity compatibility (`user-id-source`)

Per-pipeline Runner parameter, not plugin-global configuration. `sender` remains the default.
A `sender` run whose Host actor is missing or empty is refused before any upstream request, instead of minting a per-run provider user; select `legacy-session` explicitly when a conversation-scoped provider user is intended.
Explicit `legacy-session` preserves native provider identity using trusted Host run context only;
missing identity fails before any upstream request, never falls back to the sender or business params.
`legacy-session` uses `conversation.launcher_type` (`group`/`person`) plus `_` plus the exact `conversation.launcher_id`. Host must project the native Query.session launcher into those fields, including interaction/resume runs. Older Hosts that leave these fields empty must be upgraded.
Provider conversation/session persistence remains Runner-owned. Configuration migration does not import old conversation IDs, threads, transcripts, pending forms or files; finish/cancel pending work or perform a separately authorized state migration. Changing identity on an existing stored provider conversation requires an explicit reset/migration decision.


## Dedicated runtime placement

This release is unsigned and dedicated. Historical shared-runtime notes in [SHARED_RUNTIME.md](SHARED_RUNTIME.md) do not grant shared-worker eligibility.
