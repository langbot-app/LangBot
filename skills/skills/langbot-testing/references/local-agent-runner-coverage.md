# Local Agent Runner Coverage

Use this matrix when judging whether the external `langbot/local-agent` plugin still behaves like the old built-in local-agent runner.

The QA target is end-to-end behavior. UI cases prove the host, SDK, plugin runtime, and WebUI work together. Unit or component tests are still needed for negative branches that are hard to trigger reliably through a live provider.

## Code Path Basis

- `LangBot/src/langbot/pkg/agent/runner/context_builder.py` builds the Protocol v1 context from the event envelope: `ctx.input.text`, `ctx.input.contents`, attachments, state, resources, and runtime metadata.
- `LangBot/src/langbot/pkg/agent/runner/pipeline_adapter.py` adapts Pipeline-only fields into `ctx.adapter.extra.prompt`, `ctx.adapter.extra.params`, and optional `ctx.bootstrap.messages`.
- `LangBot/src/langbot/pkg/agent/runner/resource_builder.py` authorizes models, fallback models, rerank models, tools, and knowledge bases for the current run.
- `LangBot/src/langbot/pkg/plugin/handler.py` validates run-scoped model/tool/rerank access and calls the host model provider or tool manager with the current query.
- `langbot-local-agent/components/agent_runner/default.py` selects streaming or non-streaming execution, retrieves RAG context, builds messages, invokes models with fallback, and runs tool loops.
- `langbot-local-agent/pkg/messages.py` prefers the host effective prompt from `ctx.adapter.extra.prompt`, uses `ctx.bootstrap.messages` only as a small bootstrap window, and preserves structured/multimodal input while inserting RAG context.

TODO: Treat `ctx.adapter.extra.prompt` as a temporary Pipeline bridge for old
local-agent behavior parity. It is not the final answer for how user plugins or
host hooks should influence agent behavior after Pipeline is replaced.

## Minimum UI Gate

These browser cases are the minimum gate for a local-agent migration check:

| Case | Path Covered | Expected Behavior |
| --- | --- | --- |
| `local-agent-basic-debug-chat` | Streaming LLM invocation with effective host context | Bot returns deterministic `OK`; backend logs streaming completion. |
| `local-agent-effective-prompt-debug-chat` | PromptPreProcessing and host effective prompt handoff through `ctx.adapter.extra.prompt` | Bot returns `PROMPT_PREPROCESS_OK` from the fixture prompt probe. |
| `local-agent-context-compaction-debug-chat` | Runner-owned context budgeting and old-history compaction | Automation temporarily shrinks the runner context window, sends multi-turn Debug Chat history, and the bot still recovers the older sentinel. |
| `local-agent-rag-debug-chat` | Knowledge-base authorization, retrieval, and RAG prompt insertion | Bot returns the KB sentinel, not a generic answer. |
| `mcp-stdio-tool-call` | MCP stdio discovery, tool detail, model function calling, and tool execution | Bot returns `qa_mcp_echo:<input>` and backend logs the MCP tool call. |
| `local-agent-plugin-tool-call-debug-chat` | Plugin tool discovery, tool detail, model function calling, and tool execution | Bot returns `qa-plugin-smoke:<input>` and backend logs the plugin tool call. |
| `local-agent-steering-debug-chat` | Host steering claim, runner pull at turn boundary, and follow-up injection during an active tool loop | Two user messages produce one assistant response containing the steering sentinel. |
| `local-agent-multimodal-debug-chat` | Image upload, structured input contents, and multimodal runner consumption | UI shows uploaded image and bot returns `IMAGE_OK`; backend receives an image input. |
| `local-agent-rag-multimodal-debug-chat` | RAG insertion while structured image input is present | UI shows uploaded image, bot returns the KB sentinel, and backend logs the same request with `[Image]`. |
| `local-agent-nonstreaming-debug-chat` | Host non-streaming adapter path and runner non-streaming invocation | Bot returns `NONSTREAM_OK`; backend completes without the streaming-completed path. |

## Full Coverage Matrix

| Area | How To Cover | Pass Signal |
| --- | --- | --- |
| Effective prompt | Use the `qa-plugin-smoke` prompt probe and send `qa-effective-prompt`. | The answer follows `query.prompt.messages` and returns `PROMPT_PREPROCESS_OK`; plugin-local fallback config prompt is not used when host prompt exists. |
| Current text input | Send a deterministic text-only Debug Chat prompt. | `ctx.input.text` becomes the user text and the bot answers the text request. |
| Structured input contents | Upload an image with text in Debug Chat. | User message shows the image; backend log or request payload contains image content; model can acknowledge it. |
| Multimodal plus RAG | Run `local-agent-rag-multimodal-debug-chat`. | RAG sentinel is still retrievable and the image is not dropped from the user message; exact image-preservation inside the model message is covered by unit tests. |
| History and context compaction | Run `local-agent-context-compaction-debug-chat` with a small temporary `context-window-tokens` budget. | The runner compacts older history into `<conversation_summary>` and the final answer still recovers the older sentinel from the compacted context. |
| Streaming model invocation | Enable Debug Chat streaming and ask for `OK`. | UI receives incremental bot output and backend logs streaming completion. |
| Non-streaming model invocation | Disable Debug Chat streaming or use a non-streaming adapter path. | UI receives a final bot message and backend logs a normal response completion. |
| Model fallback before first chunk | Configure a failing primary and working fallback, preferably with a controlled test provider. | First model failure does not fail the run; fallback model produces the final answer. |
| Failure after streaming commit | Use a controlled provider that emits one chunk and then fails. | Runner reports a terminal run failure and does not fallback after partial output. |
| No authorized model | Clear model config or configure a model not in run resources. | Runner returns `runner.no_model` instead of calling an unauthorized model. |
| MCP tool call | Use `qa-local-stdio` and `qa_mcp_echo`. | Bot returns the exact `qa_mcp_echo:<input>` result; `/api/v1/tools` contains `qa_mcp_echo`. |
| Plugin tool call | Install a fixture plugin exposing a deterministic tool and bind it to the pipeline. | Runner lists the plugin tool and can call it through the same tool loop as MCP tools. |
| Run steering | Use `local-agent-steering-debug-chat` with the fixture `qa_plugin_sleep` tool. | A follow-up sent while the sleep tool keeps the run active is claimed into the same run: two user messages, one assistant response, sentinel included. |
| Tool errors | Make the model request an unauthorized tool or invalid arguments in a controlled unit/component test. | Tool result contains an error message and the run does not bypass authorization. |
| Tool iteration limit | Use a controlled model/tool fixture that repeatedly requests more tool calls. | Runner stops with `runner.tool_loop_limit` at the configured limit. |
| Knowledge retrieval | Bind a KB containing a unique sentinel. | Bot returns the sentinel and backend logs LangRAG retrieval. |
| Legacy `knowledge-base` config | Load a pipeline config using the old single-KB field. | Runner still retrieves from the KB. |
| Rerank | Configure `rerank-model` and `rerank-top-k` with a working rerank provider. | Retrieval order follows rerank output; unauthorized or failing rerank falls back to original retrieval order. |
| Remove-think | Enable output `remove-think` on a model that emits think tags. | Final visible output omits think content on both streaming and non-streaming paths. |
| Model extra args | Configure provider/model extra args and run Debug Chat. | Host merges persisted model extra args before provider invocation. |
| Query-aware tools | Call a tool that needs the current Query/session context. | Tool receives the active query and behaves the same as it did under the built-in runner. |
| Params filtering | Add public and secret-like variables before the run. | Public params are visible to the runner; `_internal`, token, key, password, and credential fields are filtered. |
| Actor/session context | Run through Debug Chat and at least one platform adapter path. | `conversation`, `actor`, `subject`, and state scopes contain stable IDs for the current launcher and sender. |

## Reporting Rules

When reporting a local-agent QA result, separate these categories:

- `Passed by UI`: path was verified through browser-visible behavior and backend/network evidence.
- `Covered by unit/component tests`: path is deterministic in tests but not practical as a live UI case.
- `Not covered`: path still needs a fixture or provider setup.
- `Environment issue`: provider channel, proxy, OAuth, or external marketplace/network problem outside the runner path.

Do not mark the whole runner healthy based only on a single text Debug Chat response.
