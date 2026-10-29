# Langflow Agent

Tweaks must be a JSON object (a JSON string or an object). Missing, null, empty, or whitespace-only input means no overrides. Invalid JSON and other values fail with `langflow.config_invalid` without logging the payload. Whitespace-only input is a plugin convenience; native Langflow rejected it. Conversation history remains persistent through `external.session_id`; migration does not restore the native fresh-session-per-request behavior.

Run a Langflow flow as a LangBot Runner.

## Runner ID

`plugin:langbot-team/LangflowAgent/default`

## Configuration

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| base-url | string | yes | http://localhost:7860 | Langflow server URL |
| api-key | secret | yes | '' | Langflow API key |
| flow-id | string | yes | '' | Flow ID |
| advanced-settings | boolean | no | false | Show input, output, and flow tweak controls |
| input-type | string | no | chat | Input type |
| output-type | string | no | chat | Output type |
| tweaks | json | no | {} | Flow tweaks |
| langbot-assets-enabled | boolean | no | false | Register a short-lived LangBot asset token for each run and inject it into the flow via a tweak |
| langbot-assets-gateway-host | string | no | 0.0.0.0 | Host for the local LangBot Asset Gateway |
| langbot-assets-gateway-port | integer | no | 8765 | Port for the local LangBot Asset Gateway |
| langbot-assets-gateway-request-timeout | integer | no | 60 | Timeout for individual gateway tool calls |
| langbot-assets-token-ttl | integer | no | 3600 | Lifetime of each run token in seconds |
| langbot-assets-input-name | string | no | langbot_asset_run_token | Flow component (name/id) whose `input_value` receives the run token |

## LangBot Asset Callback Through Langflow MCP Tools

Langflow can call back into LangBot assets through the SDK Asset Gateway, the same
mechanism the Dify runner uses. The gateway is a run-token-authorized MCP server
(`POST /mcp`, JSON-RPC) exposing the run-authorized LangBot tools:
`langbot_list_assets`, `langbot_get_current_event`, `langbot_history_page`,
`langbot_retrieve_knowledge`, `langbot_get_tool_detail`, and `langbot_call_tool`.

### How it works

1. When `langbot-assets-enabled` is true, this runner registers a short-lived,
   run-scoped token before calling the flow and injects it into the run via a
   tweak: it sets the `input_value` of the component named by
   `langbot-assets-input-name` (default `langbot_asset_run_token`) to the token.
2. The flow's Agent reads that value and passes it as the `run_token` argument on
   every LangBot MCP tool call.
3. The runner removes the token when the run ends. Tool calls without a valid
   token are rejected by the gateway.

The gateway accepts the token via an `Authorization: Bearer` header or via a
`run_token` tool-call argument. Use the **`run_token` argument** approach here.

### Build the flow

1. Add a **Text Input** (or similar) component whose name/id matches
   `langbot-assets-input-name`. The runner sets its `input_value` to the token
   each run. (Leave its value empty by default.)
2. Add an **MCP Tools / MCP Connection** component:
   - Transport: streamable HTTP.
   - URL: the public URL routing to the gateway `/mcp`, e.g. `https://example.com/mcp`.
3. Add an **Agent** component, attach the MCP Tools, and wire the token component
   into the Agent so its instructions pass `run_token` on every LangBot tool call,
   for example:

   ```text
   For every LangBot MCP tool call, set run_token exactly to the provided
   LangBot run token. Call langbot_list_assets first to discover available
   LangBot assets for the current run.
   ```

### Configure LangBot

Select the Langflow runner and set:

```text
base-url = http://localhost:7860
api-key = <Langflow API key>
flow-id = <flow id>
langbot-assets-enabled = true
langbot-assets-gateway-host = 0.0.0.0
langbot-assets-gateway-port = 8765
langbot-assets-token-ttl = 3600
langbot-assets-input-name = langbot_asset_run_token
```

The public MCP URL in the flow's MCP component must route to this same gateway
instance. The runner only injects the short-lived token into the flow tweak; it
does not create or update the flow's MCP component.

### Limitations

- A remote/cloud Langflow that cannot reach `localhost` needs a public HTTPS URL
  for the gateway `/mcp` endpoint.
- The run token is short-lived and run-scoped; the flow must complete its asset
  callbacks within the flow run.
- The gateway exposes only the assets permitted by the current run: current
  event, history page, knowledge retrieval, tool detail, and tool call.
- The flow must have a component whose name/id matches `langbot-assets-input-name`
  for the tweak injection to land; otherwise the token never reaches the Agent.
  Verify the `tools/list` handshake against your gateway when setting this up.

## Legacy Runner

Migrated from `langflow-api` in LangBot.


## Dedicated runtime placement

This release is unsigned and dedicated. Historical shared-runtime notes in [SHARED_RUNTIME.md](SHARED_RUNTIME.md) do not grant shared-worker eligibility.
