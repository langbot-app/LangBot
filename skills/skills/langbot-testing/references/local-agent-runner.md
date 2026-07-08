# Local Agent Runner

Use this reference when validating the pluginized `langbot/local-agent` runner through the WebUI.

The goal is behavior parity with the old built-in local-agent runner. The code does not need to be identical, but the visible behavior should match: effective prompt, current input, history, model selection and fallback, tool calling, knowledge retrieval, multimodal input, streaming and non-streaming output all have to reach the runner through the host and SDK.

For path-by-path coverage, read [Local Agent Runner Coverage](local-agent-runner-coverage.md).

## Main Surface

- Open `LANGBOT_FRONTEND_URL`.
- Navigate to `Pipelines`.
- Open the target pipeline.
- In `Configuration > AI`, select runner `Default`.
- Configure:
  - `Model`: an LLM model that is known to answer Debug Chat.
  - `Knowledge Bases`: only when validating RAG behavior.
  - `Rerank Model`: leave `None` unless the case explicitly tests reranking.
- Save the pipeline before using Debug Chat.

## Debug Chat Checks

Use `Debug Chat` as the primary local-agent validation path.

For a basic runner check, send a deterministic prompt such as:

```text
请只回复 OK，用于前端调试测试。
```

For a RAG check, bind a knowledge base containing a unique sentinel and ask for that sentinel.

For a tool check, ensure the target tool is visible in `/api/v1/tools`, then ask the runner to call it with deterministic input.
Avoid simultaneous fixtures with the same visible tool name. The current MCP fixture uses `qa_mcp_echo` and the plugin fixture uses `qa_plugin_echo` for unambiguous runner checks. If a run returns `qa-plugin-smoke:<input>` during an MCP case, it exercised a plugin tool or stale registration, not the MCP tool.
If the direct MCP fixture passes but `/api/v1/tools` still shows the old MCP name, run `node scripts/e2e/mcp-stdio-register.mjs` to refresh `qa-local-stdio` before rerunning Debug Chat.

For a multimodal check, upload a small image and ask for a deterministic acknowledgement. Prefer the bundled 64x64 red-square fixture over a 1x1 image because some model providers reject tiny images before the runner path is exercised.

For a non-streaming check, disable the Debug Chat stream switch before sending the prompt.

## Timeout And Tool Regression Checks

When validating runner timeout or SDK deadline changes, confirm `Configuration > AI` renders the runner timeout field and that the saved value is the one used by the run context. The default local-agent timeout is expected to be `300` seconds unless the pipeline overrides it.

Pair a basic Debug Chat run with a deterministic plugin tool call, for example `qa_plugin_echo`, then correlate the browser response with backend logs. A healthy run shows the tool call started and completed, and does not emit `runner.timeout`, `Action ... timed out`, `All models failed`, `Traceback`, or unexpected `ERROR` lines for the same request.

## Minimum Regression Gate

Run these cases before saying the pluginized local-agent behavior is healthy:

- `local-agent-basic-debug-chat`: basic streaming model invocation.
- `local-agent-effective-prompt-debug-chat`: host effective prompt after PromptPreProcessing reaches the runner.
- `local-agent-rag-debug-chat`: LangRAG retrieval reaches the runner and affects the answer.
- `mcp-stdio-tool-call`: MCP tool discovery and local-agent tool loop.
- `local-agent-plugin-tool-call-debug-chat`: plugin tool discovery and local-agent tool loop.
- `local-agent-multimodal-debug-chat`: uploaded image reaches `ctx.input.contents`.
- `local-agent-rag-multimodal-debug-chat`: RAG retrieval still works when the same user message carries an image.
- `local-agent-nonstreaming-debug-chat`: runner works when the host adapter cannot or should not stream.

## Pass Criteria

- The UI shows the user message and a bot response.
- Console has no unexpected React/runtime errors.
- Backend logs show the debug-chat request completed rather than timing out in plugin/runtime calls.
- When testing RAG or tools, the answer contains the expected sentinel or tool result, not a generic explanation.
- Provider errors such as `model_not_found` or `no available channel` are environment/model availability failures. They do not prove MCP, RAG, or local-agent runner failure unless the same model works outside the tested runner path.
- A model that works for basic streaming may still fail for tool-call, multimodal, or non-streaming request shapes. Treat `runner.llm_error` and `runner.tool_loop_error` with `model_not_found`, `invalid api key`, or upstream saturation as environment/model-route failures until retested with a known-good model for that exact shape.

## Diagnostic API

API checks are diagnostic only:

- `GET /api/v1/pipelines/{uuid}` confirms saved runner config.
- `GET /api/v1/tools` confirms available MCP/plugin tools.
- `GET /api/v1/knowledge/bases` confirms available knowledge bases.
