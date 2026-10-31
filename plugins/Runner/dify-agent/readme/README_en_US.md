# Dify Agent

`remove-think` (boolean, default `false`) hides think-tagged reasoning, including unfinished reasoning. `app-type` also accepts `chatflow`.

Run a Dify application as a LangBot Runner.

## Runner ID

`plugin:langbot-team/DifyAgent/default`

## Configuration (Static)

Configuration is **static** and should not contain runtime state. Only the following static fields are supported:

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| base-url | string | yes | https://api.dify.ai/v1 | Dify API base URL |
| advanced-settings | boolean | no | false | Show prompt and timeout tuning controls |
| api-key | secret | yes | '' | Dify Service API key |
| app-type | select | yes | chat | Application type (chat/chatflow/agent/workflow) |
| base-prompt | text | yes | File-handling instruction | Fallback instruction when LangBot input is empty |
| timeout | integer | no | 30 | Request timeout (seconds) |
| langbot-assets-enabled | boolean | no | false | Register a short-lived LangBot asset token for each run and pass it to Dify inputs |
| langbot-assets-gateway-host | string | no | 0.0.0.0 | Host for the local LangBot Asset Gateway |
| langbot-assets-gateway-port | integer | no | 8765 | Port for the local LangBot Asset Gateway |
| langbot-assets-gateway-request-timeout | integer | no | 60 | Timeout for individual gateway tool calls |
| langbot-assets-token-ttl | integer | no | 3600 | Lifetime of each run token in seconds |
| langbot-assets-input-name | string | no | langbot_asset_run_token | Dify input variable that receives the run token |

**Note:** Do not put `conversation_id` in config. Use `RunnerContext.state` for conversation state.

## Capabilities

- `streaming`: yes
- `multimodal_input`: yes
- `interactions`: yes

## Workflow Human Input

When Dify emits `workflow_paused` with a `human_input_required` reason, the
runner asks LangBot to deliver a structured interaction. A validated
`interaction.submitted` event resumes Dify through
`/form/human_input/{form_token}` and `/workflow/{workflow_run_id}/events`.
Workflows that pause again produce a new interaction and can be resumed again.
Forms are emitted as atomic steps: the runner collects one field at a time and
then emits the action buttons. This matches LangBot delivery adapters that
support a single select or an action-only confirmation.

Provider continuation data is not included in the interaction payload. The
runner stores `form_token`, `workflow_run_id`, the Dify user tag, and field/action
mappings in authorized plugin storage under a random LangBot `interaction_id`.
The continuation is deleted after a successful terminal event or after it is
replaced by a later pause.

The selected Runner binding must allow interactions, and the delivery
adapter must support the requested field/action shape. Adapters with a smaller
interaction subset deliver the request's plain-text fallback instead.
The current official adapters expose buttons and single-select callbacks;
free-text and file form fields therefore require a future adapter capability
before they can be resumed from those surfaces.

## Runtime State

Conversation state is managed through `RunnerContext.state` and `RunnerResult.state_updated`:

### Reading State

The runner reads `external.conversation_id` from scoped state:

```python
conversation_id = ctx.state.conversation.get("external.conversation_id")
```

Priority:
1. `ctx.state.conversation["external.conversation_id"]` when it is a Dify UUID
2. Empty string (start a new Dify conversation)

Host-provided LangBot conversation IDs are intentionally not sent to Dify,
because Dify rejects non-UUID `conversation_id` values.

### Updating State

The runner outputs `state.updated` with proper scope:

```python
yield RunnerResult.state_updated(
    ctx.run_id,
    "external.conversation_id",
    dify_conversation_id,
    scope="conversation",
)
```

LangBot host persists this state and loads it on the next run.

## LangBot Asset Callback Through Dify MCP

Dify can call back into LangBot assets through the SDK Asset Gateway when the
Dify app has an MCP provider registered against the gateway URL.

### Prerequisites

- The Dify app must be an Agent app with MCP tools enabled.
- The LangBot runner must be installed from this plugin and selected by the
  pipeline as `plugin:langbot-team/DifyAgent/default`.
- The SDK Asset Gateway must be reachable by Dify. For Dify Cloud, this means a
  public HTTPS URL that forwards to the gateway `/mcp` endpoint. A temporary
  tunnel is fine for testing, but use a stable domain or reverse proxy for
  production.
- The Dify app needs a Service API key for LangBot to call `https://api.dify.ai/v1`.

For Dify Cloud, the MCP provider URL should look like:

```text
https://example.com/mcp
```

### Configure Dify Cloud

1. Open Dify Cloud and go to **Tools -> MCP**.
2. Create an MCP provider for the LangBot Asset Gateway.
3. Set the provider URL to the public gateway URL, for example
   `https://example.com/mcp`.
4. Confirm Dify can discover the LangBot tools. The expected tool set is:
   `langbot_list_assets`, `langbot_get_current_event`,
   `langbot_history_page`, `langbot_retrieve_knowledge`,
   `langbot_get_tool_detail`, and `langbot_call_tool`.
5. Open the target Dify Agent app configuration and attach the LangBot MCP tools.
6. Add a hidden text input variable matching `langbot-assets-input-name`,
   defaulting to:

```text
langbot_asset_run_token
```

7. Add prompt guidance telling the app to pass that input value as the
   `run_token` argument on every LangBot MCP tool call. A minimal prompt pattern
   is:

```text
For every LangBot MCP tool call, set run_token exactly to:
{{langbot_asset_run_token}}
Call langbot_list_assets first when you need to discover available LangBot
assets for the current run.
```

8. Use a tool-compatible chat model. For example, `gpt-4o-mini` works for this
   flow. Avoid models that reject Dify's tool result message format; `o3-mini`
   has been observed to fail with:

```text
Unsupported value: 'messages[3].role' does not support 'function' with this model.
```

### Configure LangBot

Select the Dify runner on the LangBot pipeline and set:

```text
base-url = https://api.dify.ai/v1
api-key = <Dify app Service API key>
app-type = agent
timeout = 120
langbot-assets-enabled = true
langbot-assets-gateway-host = 0.0.0.0
langbot-assets-gateway-port = 8765
langbot-assets-gateway-request-timeout = 60
langbot-assets-token-ttl = 3600
langbot-assets-input-name = langbot_asset_run_token
```

The runner registers a run-scoped token before calling Dify and removes it when
the run ends. Tool calls without a valid token are rejected by the gateway.

The public Dify MCP provider URL must route to this same gateway instance. The
runner only injects the short-lived token into Dify inputs; it does not create
or update the Dify MCP provider.

### Verify the Flow

Use LangBot Debug Chat or another real LangBot run. Do not rely on Dify Cloud
preview alone, because preview does not automatically receive a live
`langbot_asset_run_token`.

Send a prompt like:

```text
Call LangBot MCP tool langbot_list_assets first, using the injected run_token.
If the tool call succeeds, reply only LANGBOT_DIFY_MCP_OK.
If the token is missing or invalid, reply RUN_TOKEN_FAILED.
```

A passing run should show the sentinel response in LangBot and backend logs
similar to:

```text
assistant: requested tools: langbot_list_assets
```

### Limitations

- Dify Cloud cannot reach `localhost` or a private LAN gateway. Use public HTTPS
  for the MCP provider URL.
- Temporary tunnel URLs such as `trycloudflare.com` are only suitable for
  testing. When the tunnel stops or changes, the Dify MCP provider URL becomes
  invalid.
- The run token is short-lived and run-scoped. It is injected only when LangBot
  calls Dify through this runner, then stopped when the run finishes.
- Dify Cloud preview calls usually fail for LangBot MCP tools unless a valid
  token from a live LangBot run is supplied manually.
- The Dify app prompt must consistently pass `run_token` to every LangBot MCP
  tool call. Missing or invalid tokens are rejected by the gateway.
- Model compatibility matters. The Dify Agent model must support the function
  or tool message roles produced by Dify's tool executor.
- The gateway exposes only the assets permitted by the current LangBot run:
  current event, history page, knowledge retrieval, tool detail, and tool call.
- The gateway lifetime is tied to the LangBot process and configured port. Port
  conflicts or process restarts will break the public MCP endpoint until the
  proxy points at the new live gateway.
- Keep the gateway behind HTTPS and avoid logging or exposing run tokens. Tune
  `langbot-assets-token-ttl` to the minimum value that still covers expected
  Dify tool latency.

## Workflow Inputs

Workflow inputs are passed through `ctx.adapter.extra.params`:

```python
# Runner uses adapter params as Dify inputs
inputs = dict((ctx.adapter.extra or {}).get("params") or {})
```

Legacy input variables are derived from context:

| Variable | Source |
| --- | --- |
| langbot_user_message_text | `ctx.input.to_text()` |
| langbot_session_id | `ctx.conversation.session_id` or `ctx.run_id` |
| langbot_conversation_id | `ctx.state.conversation.get("external.conversation_id")` when it is a Dify UUID |
| langbot_msg_create_time | `ctx.adapter.extra.params["msg_create_time"]` if provided |

## Example Usage

### Chat/Agent Mode with Stateful Session

LangBot host provides state snapshot:

```python
ctx = RunnerContext(
    run_id="run_001",
    input=AgentInput(text="Hello"),
    config={
        "base-url": "https://api.dify.ai/v1",
        "api-key": "app-xxx",
        "app-type": "chat",
    },
    state=AgentRunState(
        conversation={"external.conversation_id": "4f4f8c1b-b1f4-4c9f-9e9f-0f144af69f10"},
    ),
    params={},
)
```

Runner will use the Dify UUID as the Dify conversation ID, maintaining session
continuity.

### Workflow Mode with Custom Inputs

```python
ctx = RunnerContext(
    run_id="run_002",
    input=AgentInput(text="Process this"),
    config={
        "base-url": "https://api.dify.ai/v1",
        "api-key": "app-yyy",
        "app-type": "workflow",
    },
    params={
        "custom_var": "value1",
        "workflow_input": "data",
    },
)
```

Runner passes `params` to Dify workflow inputs.

## Replaced Runner

Migrated from `dify-service-api` in LangBot.

### Key Changes

1. **Config is static only**: No `conversation_id` in config
2. **State via protocol**: Use `ctx.state` and `state.updated`
3. **Inputs via adapter params**: Use `ctx.adapter.extra.params` for workflow inputs
4. **Scoped state**: `external.conversation_id` with `scope="conversation"`

### Provider identity compatibility (`user-id-source`)

Per-pipeline Runner parameter, not plugin-global configuration. `sender` remains the default.
A `sender` run whose Host actor is missing or empty is refused before any upstream request, instead of minting a per-run provider user; select `legacy-session` explicitly when a conversation-scoped provider user is intended.
Explicit `legacy-session` preserves native provider identity using trusted Host run context only;
missing identity fails before any upstream request, never falls back to the sender or business params.
`legacy-session` uses `conversation.launcher_type` (`group`/`person`) plus `_` plus the exact `conversation.launcher_id`. Host must project the native Query.session launcher into those fields, including interaction/resume runs. Older Hosts that leave these fields empty must be upgraded.
Provider conversation/session persistence remains Runner-owned. Configuration migration does not import old conversation IDs, threads, transcripts, pending forms or files; finish/cancel pending work or perform a separately authorized state migration. Changing identity on an existing stored provider conversation requires an explicit reset/migration decision.


## Dedicated runtime placement

This release is unsigned and dedicated. Historical shared-runtime notes in [SHARED_RUNTIME.md](SHARED_RUNTIME.md) do not grant shared-worker eligibility.
