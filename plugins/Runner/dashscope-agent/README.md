# DashScope Agent

`remove-think` is a strict boolean (default `false`). Set it to `true` to hide reasoning fields and `<think>` blocks, including split streaming delimiters; answer text and tool-call content are preserved.

Run an Aliyun DashScope application as a LangBot Runner.

## Runner ID

`plugin:langbot-team/DashScopeAgent/default`

## Configuration

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| app-type | select | yes | agent | Application type (agent/workflow) |
| api-key | secret | yes | '' | DashScope API key |
| app-id | string | yes | '' | Application ID |
| advanced-settings | boolean | no | false | Show reference formatting and timeout tuning controls |
| references_quote | string | no | 参考资料来自: | Quote text for references |
| timeout | number | no | 120 | Request timeout in seconds |
| langbot-assets-enabled | boolean | no | false | Register a short-lived LangBot asset token for each run and pass it via biz_params |
| langbot-assets-gateway-host | string | no | 0.0.0.0 | Host for the local LangBot Asset Gateway |
| langbot-assets-gateway-port | integer | no | 8765 | Port for the local LangBot Asset Gateway |
| langbot-assets-gateway-request-timeout | integer | no | 60 | Timeout for individual gateway tool calls |
| langbot-assets-token-ttl | integer | no | 3600 | Lifetime of each run token in seconds |
| langbot-assets-input-name | string | no | langbot_asset_run_token | biz_params key that receives the run token |

## Capabilities

- `streaming`: yes

## LangBot Asset Callback Through 百炼 MCP

The DashScope (百炼) agent app can call back into LangBot assets through the SDK
Asset Gateway, the same mechanism the Dify runner uses. The gateway is a
run-token-authorized MCP server (`POST /mcp`, JSON-RPC) exposing the
run-authorized LangBot tools: `langbot_list_assets`,
`langbot_get_current_event`, `langbot_history_page`,
`langbot_retrieve_knowledge`, `langbot_get_tool_detail`, and `langbot_call_tool`.

### How it works

1. When `langbot-assets-enabled` is true, this runner registers a short-lived,
   run-scoped token before calling the app and passes it through DashScope
   `biz_params` under the key `langbot-assets-input-name` (default
   `langbot_asset_run_token`). This works for both `agent` and `workflow` app
   types; the asset callback needs the **agent** app type (tool-calling).
2. The 百炼 app references that value (e.g. via a prompt/plugin variable bound to
   `biz_params`) and passes it as the `run_token` argument on every LangBot MCP
   tool call.
3. The runner removes the token when the run ends. Tool calls without a valid
   token are rejected by the gateway.

The gateway accepts the token via an `Authorization: Bearer` header or via a
`run_token` tool-call argument. Use the **`run_token` argument** approach here.

### Configure 百炼

1. In the 百炼 agent app, attach the LangBot Asset Gateway as an MCP service whose
   URL routes to the gateway `/mcp` (a public HTTPS URL for 百炼 Cloud).
2. Add an app input/variable bound to `biz_params.langbot_asset_run_token`.
3. In the app prompt, instruct the agent to pass that value as `run_token` on
   every LangBot MCP tool call, and to call `langbot_list_assets` first when it
   needs to discover the run's assets.

### Configure LangBot

Select the DashScope runner and set:

```text
app-type = agent
api-key = <DashScope API key>
app-id = <百炼 app id>
langbot-assets-enabled = true
langbot-assets-gateway-host = 0.0.0.0
langbot-assets-gateway-port = 8765
langbot-assets-token-ttl = 3600
langbot-assets-input-name = langbot_asset_run_token
```

### Limitations

- 百炼 Cloud cannot reach `localhost`; use a public HTTPS URL for the gateway
  `/mcp` endpoint.
- The run token is short-lived and run-scoped; the app must complete its asset
  callbacks within the app run.
- The gateway exposes only the assets permitted by the current run: current
  event, history page, knowledge retrieval, tool detail, and tool call.
- The 百炼 app must support attaching an external MCP service and forwarding the
  `biz_params` value into the tool call. Verify the `tools/list` handshake and
  end-to-end token passing in your 百炼 app before relying on it.

## Legacy Runner

Migrated from `dashscope-app-api` in LangBot.

## Native migration notes

`remove-think=true` also sends `enable_thinking=false` and `has_thoughts=false` in agent requests. Workflow output accepts either `workflow_message.message.content` or the native `text` fallback, without duplicating both. The canonical citation prefix field is `references_quote`; the old seed key `references-quote` was not read by the native runner and is retired (explicitly repair it during migration). Workflow business inputs come from `ctx.adapter.extra.params`. Provider sessions remain in scoped `external.conversation_id` state.

`timeout` defaults to 120 seconds and must be finite and positive. Generated text (including hidden reasoning) is limited to 1 MiB characters; Coze and Tbox uploads are limited to 10 MiB per file. Existing remote conversation IDs require an explicit scoped import or reset when migrating from native runners. These source changes do not publish or install a new plugin version.


## Dedicated runtime placement

This release is unsigned and dedicated. Historical shared-runtime notes in [SHARED_RUNTIME.md](SHARED_RUNTIME.md) do not grant shared-worker eligibility.
