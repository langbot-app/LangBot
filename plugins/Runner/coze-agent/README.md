# Coze Agent

`remove-think` is a strict boolean (default `false`). Set it to `true` to hide reasoning fields and `<think>` blocks, including split streaming delimiters; answer text and tool-call content are preserved.

Run a Coze bot as a LangBot Runner.

## Runner ID

`plugin:langbot-team/CozeAgent/default`

## Configuration

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| api-key | secret | yes | '' | Coze API key |
| bot-id | string | yes | '' | Bot ID |
| api-base | string | yes | https://api.coze.cn | Trusted HTTP(S) API base URL (CN, Global, or custom path prefix) |
| advanced-settings | boolean | no | false | Show history and timeout tuning controls |
| auto-save-history | boolean | no | true | Auto-save conversation history |
| timeout | number | no | 120 | Request timeout (seconds) |
| langbot-assets-enabled | boolean | no | false | Register a short-lived LangBot asset token for each run and pass it via custom_variables |
| langbot-assets-gateway-host | string | no | 0.0.0.0 | Host for the local LangBot Asset Gateway |
| langbot-assets-gateway-port | integer | no | 8765 | Port for the local LangBot Asset Gateway |
| langbot-assets-gateway-request-timeout | integer | no | 60 | Timeout for individual gateway tool calls |
| langbot-assets-token-ttl | integer | no | 3600 | Lifetime of each run token in seconds |
| langbot-assets-input-name | string | no | langbot_asset_run_token | custom_variables key that receives the run token |

## Capabilities

- `streaming`: yes
- `multimodal_input`: yes

## LangBot Asset Callback Through Coze MCP

A Coze bot can call back into LangBot assets through the SDK Asset Gateway, the
same mechanism the Dify runner uses. The gateway is a run-token-authorized MCP
server (`POST /mcp`, JSON-RPC) exposing the run-authorized LangBot tools:
`langbot_list_assets`, `langbot_get_current_event`, `langbot_history_page`,
`langbot_retrieve_knowledge`, `langbot_get_tool_detail`, and `langbot_call_tool`.

### How it works

1. When `langbot-assets-enabled` is true, this runner registers a short-lived,
   run-scoped token before calling the bot and passes it through Coze
   `custom_variables` under the key `langbot-assets-input-name` (default
   `langbot_asset_run_token`).
2. The bot prompt references it as `{{langbot_asset_run_token}}` and passes it as
   the `run_token` argument on every LangBot MCP tool call.
3. The runner removes the token when the run ends. Tool calls without a valid
   token are rejected by the gateway.

The gateway accepts the token via an `Authorization: Bearer` header or via a
`run_token` tool-call argument. Use the **`run_token` argument** approach here.

### Configure Coze

1. Add the LangBot Asset Gateway as an MCP plugin/tool on the bot, with a URL
   routing to the gateway `/mcp` (a public HTTPS URL for Coze Cloud).
2. Declare a bot variable named `langbot_asset_run_token` (matching
   `langbot-assets-input-name`) so `custom_variables` can populate it.
3. In the bot prompt, instruct it to pass `{{langbot_asset_run_token}}` as
   `run_token` on every LangBot MCP tool call, and to call `langbot_list_assets`
   first when it needs to discover the run's assets.

### Configure LangBot

Select the Coze runner and set:

```text
api-key = <Coze API key>
bot-id = <bot id>
api-base = https://api.coze.cn
langbot-assets-enabled = true
langbot-assets-gateway-host = 0.0.0.0
langbot-assets-gateway-port = 8765
langbot-assets-token-ttl = 3600
langbot-assets-input-name = langbot_asset_run_token
```

### Limitations

- Coze Cloud cannot reach `localhost`; use a public HTTPS URL for the gateway
  `/mcp` endpoint.
- The run token is short-lived and run-scoped; the bot must complete its asset
  callbacks within the chat run.
- The gateway exposes only the assets permitted by the current run: current
  event, history page, knowledge retrieval, tool detail, and tool call.
- The bot must support attaching an external MCP tool and forwarding the
  `custom_variables` value into the tool call. Verify the `tools/list` handshake
  and end-to-end token passing in your bot before relying on it.

## Legacy Runner

Migrated from `coze-api` in LangBot.

## Native migration notes

Custom `api-base` values retain their HTTP(S) host, port, and path prefix; credentials, query strings, fragments, and malformed URLs are rejected without echoing their values. Only trusted administrator-configured endpoints should be used. `auto-save-history` remains `true` by default and accepts only booleans. The old `auto_save_history` runtime alias is retired; migration must explicitly map it to `auto-save-history` and resolve conflicting values. Persistent provider conversation state is retained rather than reproducing the native per-turn reset bug. The native launcher identity versus plugin actor identity remains a migration decision, not an automatic compatibility claim.

`timeout` defaults to 120 seconds and must be finite and positive. Generated text (including hidden reasoning) is limited to 1 MiB characters; Coze and Tbox uploads are limited to 10 MiB per file. Existing remote conversation IDs require an explicit scoped import or reset when migrating from native runners. These source changes do not publish or install a new plugin version.

### Provider identity compatibility (`user-id-source`)

Per-pipeline Runner parameter, not plugin-global configuration. `sender` remains the default.
A `sender` run whose Host actor is missing or empty is refused before any upstream request, instead of minting a per-run provider user; select `legacy-session` explicitly when a conversation-scoped provider user is intended.
Explicit `legacy-session` preserves native provider identity using trusted Host run context only;
missing identity fails before any upstream request, never falls back to the sender or business params.
`legacy-session` uses `conversation.launcher_type` (`group`/`person`) plus `_` plus the exact `conversation.launcher_id`. Host must project the Query launcher for Coze into those fields, including interaction/resume runs. Older Hosts that leave these fields empty must be upgraded.
Provider conversation/session persistence remains Runner-owned. Configuration migration does not import old conversation IDs, threads, transcripts, pending forms or files; finish/cancel pending work or perform a separately authorized state migration. Changing identity on an existing stored provider conversation requires an explicit reset/migration decision.


## Dedicated runtime placement

This release is unsigned and dedicated. Historical shared-runtime notes in [SHARED_RUNTIME.md](SHARED_RUNTIME.md) do not grant shared-worker eligibility.
