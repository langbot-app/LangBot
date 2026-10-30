# Local Runner

Official LangBot Runner plugin for the local, LangBot-hosted agent path.

This runner is a consumer of LangBot Runner Protocol v1. LangBot provides
the host infrastructure, authorization, facts, and pull APIs; the runner owns
the model-facing agent behavior such as prompt assembly, history selection,
tool loop, RAG orchestration, and optional context compaction.

## Compatibility

This plugin tracks the LangBot 4.11.x Runner integration work. Test it with:

- `langbot-app/LangBot` branch `dev/4.11.x`
- `langbot-app/langbot-plugin-sdk` branch `dev/4.11.x`
- `plugins/Runner` in the same LangBot checkout
- `langbot-app/langbot-agent-control-plane` branch `main`

## Scope

This repository does not define the LangBot host protocol. It consumes the
Protocol v1 run context produced by LangBot. The canonical protocol source is
`LangBot/docs/agent-runner-pluginization/PROTOCOL_V1.md`; this README only
documents how Local Agent consumes that contract:

- `ctx.event`: event-first metadata for the current trigger.
- `ctx.conversation`, `ctx.actor`, `ctx.subject`: current run scope metadata.
- `ctx.input`: current structured input, including text, multimodal contents,
  and lightweight attachment/file references.
- `ctx.context`: context handles, inline policy, and available pull APIs. Local
  Agent uses the Host history API for conversation history instead of adapter
  bootstrap.
- `ctx.resources`: run-scoped authorized models, tools, knowledge bases, skills,
  and storage capabilities.
- `ctx.state`: small Host-projected state for the current run.
- `ctx.runtime`: runtime metadata such as deadline, trace id, query id from
  migration adapter paths, and Host metadata.
- `ctx.delivery`: host delivery surface and streaming/edit capabilities.
- `ctx.config`: runner binding config.
- `ctx.adapter`: migration adapter fields; not part of Protocol v1 core and not
  a place for prompt, history, RAG results, tool schemas, or authorized
  resources.

LangBot does not inline full conversation history by default. When the runner
needs more context, it should use authorized Host APIs through
`RunnerAPIProxy`, for example model, prompt, history, tool,
knowledge-base, state, and storage APIs.

Runner components should obtain that proxy with `self.get_run_api(ctx)`.
They should not use the legacy `self.plugin` proxy that regular non-runner
plugin components use.
The SDK proxy import path is
`from langbot_plugin.api.proxies.runner import RunnerAPIProxy`.

## Runner ID

`plugin:langbot-team/LocalAgent/default`

## Configuration

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| model | model-fallback-selector | yes | primary: '', fallbacks: [], reasoning: {} | LLM model with fallbacks |
| timeout | integer | no | 300 | Total runner execution timeout in seconds. Set to `0` or `null` to disable only the plugin-local timeout; Host deadlines still apply. |
| prompt | prompt-editor | yes | system: "You are a helpful assistant." | Default system prompt edited in LangBot UI |
| remove-think | boolean | no | false | Ask Host model APIs to remove provider thinking output when supported |
| knowledge-bases | knowledge-base-multi-selector | no | [] | Knowledge bases for RAG |
| advanced-settings | boolean | no | false | Show advanced retrieval, tool, timeout, and context controls; affects form visibility only |
| date-grounding | boolean | no | `true` | Add current UTC date and verification guidance |
| retrieval-top-k | integer | no | 5 | Retrieval results requested per knowledge base |
| rerank-model | rerank-model-selector | no | '' | Rerank model for improved retrieval |
| rerank-top-k | integer | no | 5 | Top-K results after reranking |
| max-tool-iterations | integer | no | 100 | Maximum tool-call follow-up iterations |
| tool-execution-mode | select | no | parallel | Same-batch tool execution: `parallel` or `serial` |
| max-tool-result-chars | integer | no | 20000 | Maximum serialized tool result characters injected into the next model request |
| context-history-fetch-limit | integer | no | 50 | Transcript messages pulled from the Host history API |
| context-window-tokens | integer | no | 200000 | Fallback context window, and an upper cap when Host model metadata is available |
| context-reserve-tokens | integer | no | 16384 | Tokens reserved for the model response and provider overhead, clamped to at most 25% of the effective window |
| context-keep-recent-tokens | integer | no | 20000 | Recent history tokens to retain when compaction triggers |
| context-summary-tokens | integer | no | 8000 | Maximum deterministic summary tokens inserted for compacted older history |

`prompt` is the static binding default. When LangBot exposes
`ctx.context.available_apis.prompt_get`, Local Agent pulls the
post-preprocessing effective prompt through `RunnerAPIProxy.get_prompt()` and
uses it instead of the static default so `PromptPreProcessing` changes are
preserved. If the prompt API is unavailable, Local Agent falls back to
`ctx.config.prompt`.

`remove-think` is the first supported thinking-output control for Local Agent.
When enabled, the runner passes `remove_think=True` to Host model APIs for both
streaming and non-streaming calls. It is not Pi-style thinking-level control; it
only requests provider thinking output removal when the active Host model
adapter supports that flag.

Skill support is Host-mediated. When Local Agent advertises
`skill_authoring`, LangBot lists the current pipeline-visible skill facts in
`ctx.resources.skills` and exposes the Host-owned `activate` and
`register_skill` tools according to the same visibility policy. Calling
`activate` returns the full `SKILL.md` instructions as a tool result and
registers the skill package for Box mount resolution under
`/workspace/.skills/<skill-name>`. Local Agent consumes skill facts and tools
through Host APIs; it decides how tool schemas, tool results, prompt context,
or MCP surfaces are presented to the model.

Legacy singular `knowledge-base` values must be normalized by LangBot
configuration migration before runner execution. Local Agent only reads the
manifest-defined `knowledge-bases` binding config.

`max-tool-result-chars` is a runner-level safety fallback for model-facing tool
messages. String results, serialized JSON results, and error results are bounded
before they are appended as `role="tool"` messages for the next model request.
Oversized non-error tool results are reported as bounded previews; Local Agent
does not persist runner-owned large-result assets or expose an internal read
tool for them.
Large files and generated assets should be returned by sandbox or Host tools as
sandbox paths, URLs, or other explicit external references, not inline file
content.

`tool-execution-mode` controls tool calls emitted in the same model turn.
`parallel` runs the batch concurrently and still writes tool-result messages
back in source order. `serial` executes them one by one.

Tools can return a top-level `terminate: true` runtime hint when the tool action
already completes the user-visible work and the automatic follow-up model call
should be skipped. Local Agent stops early only when every finalized tool result
in that batch sets `terminate: true`; mixed batches continue normally. The hint
is stripped from the model-facing `role="tool"` message so it does not become
business data for the next provider request.

When a sandbox or Host tool already returns explicit `path` fields, Local Agent
treats those as authoritative sandbox references. If the surrounding result is
large, the model and Host events receive those references plus a bounded preview
only.

## Context Management

The local agent should be treated as a runner-owned or hybrid-context runner:

- LangBot inlines the current event/input and context handles.
- The runner pulls transcript history through the authorized Host history API.
- The runner decides whether to page history, summarize, compact, or construct
  a model request from scratch.
- Large files, images, audio, and tool outputs should be consumed as sandbox
  paths, URLs, or other explicit references
  instead of large inline payloads.

Local Agent currently uses a runner-owned context pipeline:

1. Assemble effective prompt, host transcript history, RAG context, and current
   structured input.
2. Use the Host-provided model context window from `ctx.runtime.metadata` when
   available, capped by the runner binding's `context-window-tokens`. If Host
   metadata is unavailable, `context-window-tokens` is the fallback window and
   defaults to 200k tokens.
3. Count the final provider-shaped messages through the Host `count_tokens`
   API. LangBot implements this with the active model requester; the LiteLLM
   requester uses `litellm.token_counter` with the same messages and tool
   schemas used for the real model request. Runtime context budgeting fails
   closed if the Host does not expose token counting.
4. When the assembled context exceeds the effective input budget
   (`window - reserve`, with reserve clamped for small windows),
   use the authorized Host model API to generate a structured checkpoint summary,
   wrap it in a `system` message containing
   `<conversation_summary>...</conversation_summary>`, and keep a recent history
   tail bounded by `context-keep-recent-tokens`. If Host exposes the state API,
   Local Agent persists that summary as a conversation-scoped compaction
   checkpoint at `runner.compaction.checkpoint`, anchored by `covers_until`, and
   later runs reuse it before pulling transcript entries after that cursor. If
   model summarization fails or returns empty content, Local Agent falls back to
   a deterministic bounded summary.
5. Re-run the context transform before every model turn, including tool-call
   follow-up turns, so tool results and assistant tool calls are budgeted before
   the next provider request.
6. If a provider fails before producing any streamed content with a
   context-overflow style error, compact the current loop context with a more
   aggressive retry budget and retry the model turn once before surfacing
   `run.failed`.

This is not `max-round` behavior. History is not selected by number of rounds;
the runner budgets prompt, current input, summary, and recent history together,
following the Pi-style context threshold and per-turn transform shape. When the
Host does not expose the state API or a checkpoint cannot be parsed, Local Agent
falls back to the previous tail-history behavior. Token counts are still
provided by Host `count_tokens`; there is no runtime heuristic token-count
fallback.

Pipeline adapter data is intentionally narrow. Local Agent does not consume
`ctx.adapter.extra.prompt`; prompt handoff goes through the run-scoped Host
prompt API when available. New runner logic should prefer event-first context
and Host APIs over adapter fields.

## Host APIs Consumed

Model, prompt, history, state, storage, tool, knowledge-base, rerank, and
steering access go through `RunnerAPIProxy`. LangBot validates these calls
with the current `run_id`, run-scoped resource policy / available APIs, and
caller plugin identity.

Local Agent must not expose the runner process filesystem as an agent
capability. In sandboxed deployments, file access is mediated by Host/sandbox
tools registered in `ctx.resources.tools`; the model can request those tools,
and the runner invokes them through `RunnerAPIProxy.call_tool()`. "Local" here
means the agent loop runs locally as a LangBot plugin, not that the model can
read or write arbitrary files on the runner machine.

Skill activation uses the same tool path. If Host exposes `activate` in the
run's allowed tools, the model calls `activate` like any other function tool and
Local Agent forwards it through `RunnerAPIProxy.call_tool()`; no separate
runner action is required for skill activation.

Typical local-agent usage:

- Invoke authorized LangBot-hosted models.
- Call authorized tools.
- Retrieve authorized knowledge bases and rerank results.
- Page transcript history for the model request.
- Pull authorized steering inputs at turn boundaries.

The runner must not bypass `ctx.resources` or call host-private managers to
access unauthorized models, tools, knowledge bases, storage, or platform APIs.

## Capabilities

- `streaming`: yes
- `tool_calling`: yes
- `knowledge_retrieval`: yes
- `multimodal_input`: yes
- `skill_authoring`: yes
- `interrupt`: yes
- `steering`: yes

`interrupt` is cooperative. When Host exposes the run ledger API, Local Agent
polls the current run through `RunnerAPIProxy.run_get()` at run boundaries and
streaming event boundaries. If Host has recorded `cancel_requested_at`, the
runner stops and emits `run.failed` with `code="cancelled"`.

`skill_authoring` means Local Agent can receive LangBot's Host-owned
`ctx.resources.skills` facts plus `activate`/`register_skill` tools when skills
are available. Skills remain owned by LangBot/Box; the runner owns how
model-facing prompts, tool schemas, tool results, or MCP adapters are assembled
from those Host capabilities.

Local Agent is reentrant and does not keep mutable per-conversation state in
the plugin instance. It can pull Host history each run. When Host state APIs
are available, it persists compacted summary checkpoints through
`RunnerAPIProxy` so later runs can resume from
`runner.compaction.checkpoint`. It does not persist external session IDs or
runner-owned memory outside Host-managed state/storage.

## Event System Boundary

This plugin does not implement LangBot EventGateway, event subscription, event
notification, scheduler, or event fanout. Those systems belong to LangBot host
or separate event-focused branches. This runner only consumes the run context
that LangBot delivers through Runner Protocol v1.

## Current Boundary

This plugin is the target external implementation of LangBot's local agent
runner. LangBot's internal runner code can be used as reference material, but
its host-private structures must not become plugin API.

## Contributing

We welcome contributions. Useful areas include:

- Protocol v1 adapter fixes
- history/state/storage API consumption
- tool loop and RAG behavior
- multimodal input handling
- focused tests and documentation improvements

## Native runner migration decisions

All settings in the Runner descriptor belong to the **per-pipeline Runner binding**
(`ai.runner_config[plugin:langbot-team/LocalAgent/default]` / resolved `binding.runner_config`), not plugin-global settings.
`model.reasoning` is a map from model UUID to a provider-neutral level, default `{}`:
`provider_default`, `disabled`, `enabled`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`.
The Host must freeze these overrides from the descriptor-declared model selector into
the run authorization snapshot and apply them to an authorized, request-local model
copy on every primary, fallback, tool-follow-up and summary request. The plugin does
not translate vendor parameters or add SDK/wire hints. This requires a Host with that
binding-to-model bridge; a saved map alone is not proof that provider reasoning changed.
`remove-think` controls output filtering, not reasoning effort.

`date-grounding` defaults to `true`: before token budgeting, the runner appends the
current UTC date and a time-sensitive fact verification reminder to the first system
prompt, or creates one. UTC is explicit, not an inferred user timezone. Set `false`
when a separately managed prompt supplies time grounding. Effective Host prompts take
precedence over static prompts. SDK-valid structured message content and metadata are
preserved; malformed content fails validation rather than disappearing silently.

Keep the newer defaults when migrating: token budgets and checkpoint compaction replace
`max-round` (there is no rounds-to-tokens conversion); tool results stay bounded at
20,000 characters; run timeout stays 300 seconds; tool iterations stay 100; retrieval
stays bounded and separate from the user message. `timeout=0`/`null` only disables the
plugin-local deadline, never a Host deadline. `retrieval-top-k=5` requests five entries
per KB and, without reranking, keeps five combined chunks; `rerank-top-k=5` bounds
reranked output. These are deliberately not the native unbounded retrieval defaults.

`tool-execution-mode=parallel` is retained as the new default for independent tools,
with results returned in source order. **Completion order is not execution order:**
side-effecting or dependent calls may race. Select `serial` for ordered writes/actions;
neither mode widens the Host allowlist. Tools, MCP attachments/visibility, skills and
Box session isolation remain Host authority; do not copy them into plugin-global
configuration. Legacy `knowledge-base` and string `model` need explicit migration to
`knowledge-bases` and the model selector. Box scope/history import require Host-specific
migration decisions; token compaction does not import old transcripts or shared files.

## Box

`box-enabled`: enables sandbox execution and file tools. `box-session-id-template`: defaults to `{launcher_type}_{launcher_id}` for per-chat reuse; `{global}` shares within the Workspace. Templates also support `{sender_id}`, `{bot_id}`, `{run_id}`, and public request variables. The Runner selects the Box, imports inputs, and explicitly exports the current run outbox on successful completion.
