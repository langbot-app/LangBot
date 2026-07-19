#!/usr/bin/env node

import { createServer } from "node:http";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { env, exit } from "node:process";

const args = parseArgs(process.argv.slice(2));
const host = args.host || env.LANGBOT_FAKE_PROVIDER_HOST || "127.0.0.1";
const port = integer(args.port ?? env.LANGBOT_FAKE_PROVIDER_PORT, 0);
const stateFile = args["state-file"] || env.LANGBOT_FAKE_PROVIDER_STATE_FILE || "";
const modelName = args.model || env.LANGBOT_FAKE_PROVIDER_MODEL_NAME || env.LANGBOT_FAKE_PROVIDER_MODEL || "gpt-4o-mini";
const COMPACTION_SENTINEL = "qa_compaction_sentinel_7391";
const COMBO_SENTINEL = "qa_combo_compaction_sentinel_2406";
const RAG_SENTINEL = "azalea-cobalt-7421";
const COMBO_TOOL_INPUT = "combo-tool-ok-local-agent";
const COMBO_TOOL_RESULT = `qa-plugin-smoke:${COMBO_TOOL_INPUT}`;
const COMBO_FINAL = `COMBO_FINAL ${COMBO_SENTINEL} ${RAG_SENTINEL} ${COMBO_TOOL_RESULT}`;
const MULTITOOL_SENTINEL = "qa_multitool_compaction_sentinel_6718";
const MULTITOOL_TOOL_A_INPUT = "multi-tool-a-local-agent";
const MULTITOOL_TOOL_B_INPUT = "multi-tool-b-local-agent";
const MULTITOOL_TOOL_A_RESULT = `qa-plugin-smoke:${MULTITOOL_TOOL_A_INPUT}`;
const MULTITOOL_TOOL_B_RESULT = `qa-plugin-smoke:${MULTITOOL_TOOL_B_INPUT}`;
const MULTITOOL_FINAL = [
  "MULTITOOL_COMBO_FINAL",
  MULTITOOL_SENTINEL,
  RAG_SENTINEL,
  MULTITOOL_TOOL_A_RESULT,
  MULTITOOL_TOOL_B_RESULT,
].join(" ");
const PARALLEL_SENTINEL = "qa_parallel_compaction_sentinel_8142";
const PARALLEL_TOOL_A_INPUT = "parallel-tool-a-local-agent";
const PARALLEL_TOOL_B_INPUT = "parallel-tool-b-local-agent";
const PARALLEL_TOOL_A_RESULT = `qa-plugin-smoke:${PARALLEL_TOOL_A_INPUT}`;
const PARALLEL_TOOL_B_RESULT = `qa-plugin-smoke:${PARALLEL_TOOL_B_INPUT}`;
const PARALLEL_FINAL = [
  "PARALLEL_COMBO_FINAL",
  PARALLEL_SENTINEL,
  RAG_SENTINEL,
  PARALLEL_TOOL_A_RESULT,
  PARALLEL_TOOL_B_RESULT,
].join(" ");
const LOOP_LIMIT_INPUT = "loop-limit-repeat-local-agent";
const TOOL_ERROR_INPUT = "tool-error-recovery-local-agent";
const TOOL_ERROR_FINAL = "TOOL_ERROR_RECOVERY_FINAL qa-plugin-smoke forced failure observed";
const STEERING_FOLLOWUP_SENTINEL = "qa_steering_sentinel_6194";
const STEERING_SLEEP_INPUT = "steering-e2e-anchor";
const STEERING_SLEEP_RESULT = `qa-plugin-smoke:sleep:8:${STEERING_SLEEP_INPUT}`;
const config = {
  response_text: env.LANGBOT_FAKE_PROVIDER_RESPONSE_TEXT || "OK",
  first_token_delay_ms: integer(env.LANGBOT_FAKE_PROVIDER_FIRST_TOKEN_DELAY_MS, 25),
  chunk_delay_ms: integer(env.LANGBOT_FAKE_PROVIDER_CHUNK_DELAY_MS, 10),
  chunk_count: integer(env.LANGBOT_FAKE_PROVIDER_CHUNK_COUNT, 0),
  fault_status: integer(env.LANGBOT_FAKE_PROVIDER_FAULT_STATUS, 500),
  fail_first_n: integer(env.LANGBOT_FAKE_PROVIDER_FAIL_FIRST_N, 0),
  fail_every_n: integer(env.LANGBOT_FAKE_PROVIDER_FAIL_EVERY_N, 0),
  fail_after_first_chunk: bool(env.LANGBOT_FAKE_PROVIDER_FAIL_AFTER_FIRST_CHUNK, false),
  dynamic_response: !/^(0|false|no|off)$/i.test(env.LANGBOT_FAKE_PROVIDER_DYNAMIC_RESPONSE || ""),
  request_log_limit: integer(env.LANGBOT_FAKE_PROVIDER_REQUEST_LOG_LIMIT, 500),
};

let requestCount = 0;
const recentRequests = [];

const server = createServer(async (request, response) => {
  const startedAt = Date.now();
  const startedPerf = performance.now();
  let requestRecord = null;
  const url = new URL(request.url || "/", `http://${request.headers.host || `${host}:${port}`}`);
  try {
    if (request.method === "GET" && url.pathname === "/healthz") {
      sendJson(response, 200, {
        ok: true,
        model: modelName,
        config,
        request_count: requestCount,
        recent_request_count: recentRequests.length,
      });
      return;
    }

    if (request.method === "GET" && url.pathname === "/__qa/config") {
      sendJson(response, 200, {
        ok: true,
        model: modelName,
        config,
        request_count: requestCount,
        recent_requests: recentRequests,
      });
      return;
    }

    if (request.method === "POST" && url.pathname === "/__qa/config") {
      const body = await readJson(request);
      applyConfig(body.config && typeof body.config === "object" ? body.config : body);
      if (body.reset_request_count !== false) resetRequestState();
      sendJson(response, 200, {
        ok: true,
        model: modelName,
        config,
        request_count: requestCount,
      });
      return;
    }

    if (request.method === "POST" && url.pathname === "/__qa/reset") {
      resetRequestState();
      sendJson(response, 200, {
        ok: true,
        model: modelName,
        config,
        request_count: requestCount,
      });
      return;
    }

    if (request.method === "GET" && ["/models", "/v1/models"].includes(url.pathname)) {
      sendJson(response, 200, {
        object: "list",
        data: [
          {
            id: modelName,
            object: "model",
            created: 1,
            owned_by: "langbot-qa",
            type: "llm",
            context_length: 8192,
          },
        ],
      });
      return;
    }

    if (request.method === "POST" && ["/chat/completions", "/v1/chat/completions"].includes(url.pathname)) {
      requestCount += 1;
      const body = await readJson(request);
      const requestId = `chatcmpl-langbot-fake-${requestCount}`;
      const shouldFail = requestCount <= config.fail_first_n
        || (config.fail_every_n > 0 && requestCount % config.fail_every_n === 0);
      const replyMessage = buildResponse(body);
      const replyText = replyMessage.content || "";
      requestRecord = recordRequest({
        id: requestId,
        request_number: requestCount,
        path: url.pathname,
        stream: Boolean(body.stream),
        model: body.model || "",
        message_count: Array.isArray(body.messages) ? body.messages.length : 0,
        should_fail: shouldFail,
        status: "running",
        http_status: null,
        expected_text: replyText,
        response_text_preview: previewText(replyText),
        started_at: new Date(startedAt).toISOString(),
        started_epoch_ms: startedAt,
        configured_first_token_delay_ms: config.first_token_delay_ms,
        configured_chunk_delay_ms: config.chunk_delay_ms,
        configured_chunk_count: config.chunk_count,
      });

      if (shouldFail) {
        await sleep(config.first_token_delay_ms);
        sendJson(response, config.fault_status, {
          error: {
            message: `LangBot fake provider injected HTTP ${config.fault_status}`,
            type: "fake_provider_fault",
            code: "fake_provider_fault",
          },
        });
        finishRequestRecord(requestRecord, startedPerf, {
          status: "http_fault",
          http_status: config.fault_status,
        });
        return;
      }

      if (body.stream) {
        await streamCompletion(response, {
          requestId,
          model: body.model || modelName,
          message: replyMessage,
          failAfterFirstChunk: config.fail_after_first_chunk,
          requestRecord,
          startedPerf,
        });
      } else {
        await sleep(config.first_token_delay_ms + config.chunk_delay_ms);
        sendJson(response, 200, completionPayload({
          requestId,
          model: body.model || modelName,
          message: replyMessage,
        }));
        markRequestTiming(requestRecord, "first_chunk", startedPerf);
        markRequestTiming(requestRecord, "first_content_chunk", startedPerf);
        requestRecord.content_chunk_count = 1;
        finishRequestRecord(requestRecord, startedPerf, {
          status: "ok",
          http_status: 200,
        });
      }
      return;
    }

    sendJson(response, 404, {
      error: {
        message: `No fake provider route for ${request.method} ${url.pathname}`,
        type: "not_found",
      },
    });
  } catch (error) {
    if (requestRecord) {
      finishRequestRecord(requestRecord, startedPerf, {
        status: "fake_provider_error",
        http_status: 500,
        error: error instanceof Error ? error.message : String(error),
      });
    }
    sendJson(response, 500, {
      error: {
        message: error instanceof Error ? error.message : String(error),
        type: "fake_provider_error",
      },
    });
  } finally {
    const durationMs = Date.now() - startedAt;
    if (url.pathname !== "/healthz") {
      console.log(JSON.stringify({
        at: new Date().toISOString(),
        method: request.method,
        path: url.pathname,
        duration_ms: durationMs,
      }));
    }
  }
});

server.listen(port, host, async () => {
  const address = server.address();
  const selectedPort = typeof address === "object" && address ? address.port : port;
  const url = `http://${host}:${selectedPort}`;
  const state = {
    status: "ready",
    pid: process.pid,
    url,
    base_url: `${url}/v1`,
    model: modelName,
    started_at: new Date().toISOString(),
  };
  if (stateFile) {
    const path = resolve(stateFile);
    await mkdir(dirname(path), { recursive: true });
    await writeFile(path, `${JSON.stringify(state, null, 2)}\n`, "utf8");
  }
  console.log(JSON.stringify(state));
});

server.on("error", (error) => {
  console.error(JSON.stringify({
    status: "error",
    reason: error instanceof Error ? error.message : String(error),
  }));
  exit(1);
});

process.on("SIGTERM", () => {
  server.close(() => exit(0));
});

function parseArgs(argv) {
  const result = {};
  for (const item of argv) {
    const match = item.match(/^--([^=]+)(?:=(.*))?$/);
    if (!match) continue;
    result[match[1]] = match[2] ?? "1";
  }
  return result;
}

function integer(value, fallback) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

function bool(value, fallback) {
  if (value === undefined || value === "") return fallback;
  if (/^(1|true|yes|on)$/i.test(String(value))) return true;
  if (/^(0|false|no|off)$/i.test(String(value))) return false;
  return fallback;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, Math.max(0, ms)));
}

async function readJson(request) {
  let text = "";
  for await (const chunk of request) text += chunk.toString();
  if (!text) return {};
  return JSON.parse(text);
}

function sendJson(response, status, payload) {
  const text = `${JSON.stringify(payload)}\n`;
  response.writeHead(status, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(text),
  });
  response.end(text);
}

function completionPayload({ requestId, model, message }) {
  const completionTokens = tokenEstimate(message.content || JSON.stringify(message.tool_calls || []));
  return {
    id: requestId,
    object: "chat.completion",
    created: Math.floor(Date.now() / 1000),
    model,
    choices: [
      {
        index: 0,
        message,
        finish_reason: message.tool_calls?.length ? "tool_calls" : "stop",
      },
    ],
    usage: {
      prompt_tokens: 8,
      completion_tokens: completionTokens,
      total_tokens: 8 + completionTokens,
    },
  };
}

async function streamCompletion(response, {
  requestId,
  model,
  message,
  failAfterFirstChunk: failMidStream,
  requestRecord,
  startedPerf,
}) {
  response.writeHead(200, {
    "content-type": "text/event-stream; charset=utf-8",
    "cache-control": "no-cache",
    "connection": "keep-alive",
  });

  await sleep(config.first_token_delay_ms);
  markRequestTiming(requestRecord, "first_chunk", startedPerf);
  writeSse(response, {
    id: requestId,
    object: "chat.completion.chunk",
    created: Math.floor(Date.now() / 1000),
    model,
    choices: [{ index: 0, delta: { role: "assistant" }, finish_reason: null }],
  });

  const chunks = message.tool_calls?.length ? [] : splitContent(message.content || "");
  if (message.tool_calls?.length) {
    await sleep(config.chunk_delay_ms);
    markRequestTiming(requestRecord, "first_content_chunk", startedPerf);
    requestRecord.content_chunk_count = (requestRecord.content_chunk_count || 0) + 1;
    writeSse(response, {
      id: requestId,
      object: "chat.completion.chunk",
      created: Math.floor(Date.now() / 1000),
      model,
      choices: [
        {
          index: 0,
          delta: {
            tool_calls: message.tool_calls.map((call, index) => ({
              index,
              id: call.id,
              type: call.type,
              function: {
                name: call.function.name,
                arguments: call.function.arguments,
              },
            })),
          },
          finish_reason: null,
        },
      ],
    });
    await sleep(config.chunk_delay_ms);
    writeSse(response, {
      id: requestId,
      object: "chat.completion.chunk",
      created: Math.floor(Date.now() / 1000),
      model,
      choices: [{ index: 0, delta: {}, finish_reason: "tool_calls" }],
      usage: {
        prompt_tokens: 8,
        completion_tokens: tokenEstimate(JSON.stringify(message.tool_calls)),
        total_tokens: 8 + tokenEstimate(JSON.stringify(message.tool_calls)),
      },
    });
    response.write("data: [DONE]\n\n");
    response.end();
    finishRequestRecord(requestRecord, startedPerf, {
      status: "ok",
      http_status: 200,
    });
    return;
  }

  for (let index = 0; index < chunks.length; index += 1) {
    await sleep(config.chunk_delay_ms);
    if (index === 0) markRequestTiming(requestRecord, "first_content_chunk", startedPerf);
    requestRecord.content_chunk_count = (requestRecord.content_chunk_count || 0) + 1;
    writeSse(response, {
      id: requestId,
      object: "chat.completion.chunk",
      created: Math.floor(Date.now() / 1000),
      model,
      choices: [{ index: 0, delta: { content: chunks[index] }, finish_reason: null }],
    });
    if (failMidStream && index === 0) {
      finishRequestRecord(requestRecord, startedPerf, {
        status: "mid_stream_disconnect",
        http_status: 200,
      });
      response.destroy(new Error("LangBot fake provider injected mid-stream disconnect"));
      return;
    }
  }

  await sleep(config.chunk_delay_ms);
  const completionTokens = tokenEstimate(message.content || "");
  writeSse(response, {
    id: requestId,
    object: "chat.completion.chunk",
    created: Math.floor(Date.now() / 1000),
    model,
    choices: [{ index: 0, delta: {}, finish_reason: "stop" }],
    usage: {
      prompt_tokens: 8,
      completion_tokens: completionTokens,
      total_tokens: 8 + completionTokens,
    },
  });
  response.write("data: [DONE]\n\n");
  response.end();
  finishRequestRecord(requestRecord, startedPerf, {
    status: "ok",
    http_status: 200,
  });
}

function writeSse(response, payload) {
  response.write(`data: ${JSON.stringify(payload)}\n\n`);
}

function splitContent(content) {
  const text = String(content);
  const requested = config.chunk_count;
  if (requested <= 1 || text.length <= 1) return [text];
  const chunkSize = Math.max(1, Math.ceil(text.length / requested));
  const chunks = [];
  for (let index = 0; index < text.length; index += chunkSize) {
    chunks.push(text.slice(index, index + chunkSize));
  }
  return chunks;
}

function tokenEstimate(content) {
  return Math.max(1, Math.ceil(String(content || "").length / 4));
}

function responseTextForBody(body) {
  if (!config.dynamic_response) {
    return config.response_text;
  }
  const messages = Array.isArray(body.messages) ? body.messages : [];
  const lastUser = [...messages].reverse().find((message) => message?.role === "user");
  const text = flattenContent(lastUser?.content || "");
  const quoted = text.match(/["'“”](.{1,80}?)["'“”]/);
  if (quoted?.[1]) return quoted[1].trim();
  const exact = text.match(/(?:reply|回复|输出|return)\s+(?:exactly\s+)?([A-Za-z0-9_.:@-]{1,80})/i);
  if (exact?.[1]) return exact[1].trim().replace(/[。.!?]+$/, "");
  const only = text.match(/只回复\s*([A-Za-z0-9_.:@-]{1,80})/);
  if (only?.[1]) return only[1].trim().replace(/[。.!?]+$/, "");
  return config.response_text;
}

function messageText(messages = []) {
  return messages
    .map((message) => {
      const parts = [contentText(message?.content)];
      if (Array.isArray(message?.tool_calls)) {
        parts.push(
          message.tool_calls
            .map((call) => `${call?.function?.name || call?.name || ""} ${call?.function?.arguments || ""}`)
            .join("\n"),
        );
      }
      return parts.filter(Boolean).join("\n");
    })
    .join("\n");
}

function contentText(content) {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) return content.map((part) => contentText(part)).join("");
  if (content && typeof content === "object") {
    for (const key of ["text", "content", "message", "error", "value"]) {
      if (content[key] !== undefined && content[key] !== null) {
        return contentText(content[key]);
      }
    }
    return JSON.stringify(content);
  }
  return "";
}

function latestUserText(messages = []) {
  const latest = [...messages].reverse().find((message) => message?.role === "user");
  return contentText(latest?.content);
}

function toolNames(tools = []) {
  return tools
    .map((tool) => tool?.function?.name || tool?.name || "")
    .filter(Boolean);
}

function firstToolName(tools = [], candidates = []) {
  const names = toolNames(tools);
  return candidates.find((candidate) => names.includes(candidate)) || "";
}

function isSummarizationRequest(messages = []) {
  const text = messageText(messages);
  return /context summarization assistant|conversation to summarize|<previous-summary>/i.test(text);
}

function buildSummaryResponse(text) {
  const references = [];
  if (text.includes(COMPACTION_SENTINEL)) references.push(COMPACTION_SENTINEL);
  if (text.includes(COMBO_SENTINEL)) references.push(COMBO_SENTINEL);
  if (text.includes(MULTITOOL_SENTINEL)) references.push(MULTITOOL_SENTINEL);
  if (text.includes(PARALLEL_SENTINEL)) references.push(PARALLEL_SENTINEL);
  if (/RAG_TOOL_COMBO_GOAL/i.test(text)) references.push("RAG_TOOL_COMBO_GOAL");
  if (/MULTITOOL_RAG_GOAL/i.test(text)) references.push("MULTITOOL_RAG_GOAL");
  if (/PARALLEL_RAG_GOAL/i.test(text)) references.push("PARALLEL_RAG_GOAL");
  const critical = references.length
    ? references.map((reference) => `- ${reference}`).join("\n")
    : "- (none)";
  return {
    role: "assistant",
    content: [
      "## Goal",
      "Preserve deterministic LangBot E2E context across compaction.",
      "",
      "## Constraints & Preferences",
      "- Keep exact sentinel values verbatim.",
      "",
      "## Progress",
      "### Done",
      "- [x] Earlier conversation was compacted by the fake provider.",
      "",
      "### In Progress",
      "- [ ] Continue the current Debug Chat run.",
      "",
      "### Blocked",
      "- (none)",
      "",
      "## Key Decisions",
      "- **Deterministic QA**: Return only known sentinel values from compacted input.",
      "",
      "## Next Steps",
      "1. Answer the current user request using preserved context.",
      "",
      "## Critical Context",
      critical,
    ].join("\n"),
  };
}

function buildResponse(payload) {
  const text = messageText(payload.messages || []);
  const current = latestUserText(payload.messages || []);
  const tools = payload.tools || [];
  if (isSummarizationRequest(payload.messages || [])) {
    return buildSummaryResponse(text);
  }

  if (/qa-effective-prompt/i.test(current) && /PROMPT_PREPROCESS_OK/.test(text)) {
    return { role: "assistant", content: "PROMPT_PREPROCESS_OK" };
  }

  const pluginTool = firstToolName(tools, ["qa_plugin_echo"]);
  const pluginFailTool = firstToolName(tools, ["qa_plugin_fail"]);
  const pluginSleepTool = firstToolName(tools, ["qa_plugin_sleep"]);
  const mcpTool = firstToolName(tools, ["qa_mcp_echo"]);
  const requestedMcpEchoText = current.match(
    /qa_mcp_echo[\s\S]*?exactly this text:\s*([A-Za-z0-9_:-]+)/i,
  )?.[1] || "mcp-ok-local-agent";
  const expectedMcpEchoResult = `qa_mcp_echo:${requestedMcpEchoText}`;

  if (/STEERING_NO_FOLLOWUP|qa_plugin_sleep|steering-e2e-anchor|qa_steering_sentinel_6194/i.test(current || text)) {
    if (text.includes(STEERING_FOLLOWUP_SENTINEL) && text.includes(STEERING_SLEEP_RESULT)) {
      return { role: "assistant", content: STEERING_FOLLOWUP_SENTINEL };
    }
    if (text.includes(STEERING_SLEEP_RESULT) && !text.includes(STEERING_FOLLOWUP_SENTINEL)) {
      return { role: "assistant", content: "STEERING_NO_FOLLOWUP" };
    }
    if (pluginSleepTool && !text.includes(STEERING_SLEEP_RESULT)) {
      return toolCall("call_qa_plugin_sleep_steering", pluginSleepTool, { seconds: 8, text: STEERING_SLEEP_INPUT });
    }
  }

  if (/测试暗号是什么|original sentinel|first.*sentinel/i.test(current)) {
    return {
      role: "assistant",
      content: text.includes(COMPACTION_SENTINEL) ? COMPACTION_SENTINEL : "COMPACTION_SENTINEL_MISSING",
    };
  }
  if ((current.includes(COMPACTION_SENTINEL)
    || current.includes(COMBO_SENTINEL)
    || current.includes(MULTITOOL_SENTINEL)
    || current.includes(PARALLEL_SENTINEL))
    && /请只回复 MEMORY_SET|only reply MEMORY_SET/i.test(current)) {
    return { role: "assistant", content: "MEMORY_SET" };
  }
  if (/PARALLEL_CONTEXT_PRESSURE_READY/.test(current)) return { role: "assistant", content: "PARALLEL_CONTEXT_PRESSURE_READY" };
  if (/MULTITOOL_CONTEXT_PRESSURE_READY/.test(current)) return { role: "assistant", content: "MULTITOOL_CONTEXT_PRESSURE_READY" };
  if (/COMBO_CONTEXT_PRESSURE_READY/.test(current)) return { role: "assistant", content: "COMBO_CONTEXT_PRESSURE_READY" };
  if (/CONTEXT_PRESSURE_READY/.test(current)) return { role: "assistant", content: "CONTEXT_PRESSURE_READY" };

  if (text.includes(expectedMcpEchoResult)) return { role: "assistant", content: expectedMcpEchoResult };
  if (/qa_mcp_echo|mcp-ok-local-agent/i.test(current || text) && mcpTool && !text.includes(expectedMcpEchoResult)) {
    return toolCall("call_qa_mcp_echo", mcpTool, { text: requestedMcpEchoText });
  }

  if (/LOOP_LIMIT|loop-limit-repeat-local-agent|iteration limit/i.test(current || text) && pluginTool) {
    return toolCall(`call_qa_plugin_echo_loop_limit_${Date.now()}`, pluginTool, { text: LOOP_LIMIT_INPUT });
  }

  if (/TOOL_ERROR_RECOVERY|tool-error-recovery-local-agent|qa_plugin_fail/i.test(current || text)) {
    if (/(?:Error:|Tool execution failed:|ActionCallError:|RuntimeError:)/i.test(text)
      && /(?:qa-plugin-smoke forced failure|qa_plugin_fail|tool-error-recovery-local-agent)/i.test(text)) {
      return { role: "assistant", content: TOOL_ERROR_FINAL };
    }
    if (pluginFailTool) {
      return toolCall("call_qa_plugin_fail_recovery", pluginFailTool, { text: TOOL_ERROR_INPUT });
    }
  }

  const isParallelComboRequest = /PARALLEL_COMBO|parallel-tool-a-local-agent|parallel-tool-b-local-agent|PARALLEL_RAG_GOAL/i.test(current || text);
  if (isParallelComboRequest && pluginTool && !text.includes(PARALLEL_TOOL_A_RESULT) && !text.includes(PARALLEL_TOOL_B_RESULT)) {
    return toolCalls([
      ["call_qa_plugin_echo_parallel_a", pluginTool, { text: PARALLEL_TOOL_A_INPUT }],
      ["call_qa_plugin_echo_parallel_b", pluginTool, { text: PARALLEL_TOOL_B_INPUT }],
    ]);
  }
  if (isParallelComboRequest && (text.includes(PARALLEL_TOOL_A_RESULT) || text.includes(PARALLEL_TOOL_B_RESULT))) {
    return missingOrFinal(text, [
      [PARALLEL_SENTINEL, "parallel-memory"],
      [RAG_SENTINEL, "rag"],
      [PARALLEL_TOOL_A_RESULT, "tool-a"],
      [PARALLEL_TOOL_B_RESULT, "tool-b"],
    ], "PARALLEL_COMBO_MISSING", PARALLEL_FINAL);
  }

  const isMultiToolComboRequest = /MULTITOOL_COMBO|multi-tool-a-local-agent|multi-tool-b-local-agent|MULTITOOL_RAG_GOAL/i.test(current || text);
  if (isMultiToolComboRequest && pluginTool && !text.includes(MULTITOOL_TOOL_A_RESULT)) {
    return toolCall("call_qa_plugin_echo_multi_a", pluginTool, { text: MULTITOOL_TOOL_A_INPUT });
  }
  if (isMultiToolComboRequest && pluginTool && text.includes(MULTITOOL_TOOL_A_RESULT) && !text.includes(MULTITOOL_TOOL_B_RESULT)) {
    return toolCall("call_qa_plugin_echo_multi_b", pluginTool, { text: MULTITOOL_TOOL_B_INPUT });
  }
  if (isMultiToolComboRequest && text.includes(MULTITOOL_TOOL_A_RESULT) && text.includes(MULTITOOL_TOOL_B_RESULT)) {
    return missingOrFinal(text, [
      [MULTITOOL_SENTINEL, "multi-memory"],
      [RAG_SENTINEL, "rag"],
      [MULTITOOL_TOOL_A_RESULT, "tool-a"],
      [MULTITOOL_TOOL_B_RESULT, "tool-b"],
    ], "MULTITOOL_COMBO_MISSING", MULTITOOL_FINAL);
  }

  const isComboRequest = /qa_combo|\bCOMBO_FINAL\b|combo-tool-ok-local-agent|RAG_TOOL_COMBO_GOAL/i.test(current || text);
  if (isComboRequest && pluginTool && !text.includes(COMBO_TOOL_RESULT)) {
    return toolCall("call_qa_plugin_echo_combo", pluginTool, { text: COMBO_TOOL_INPUT });
  }
  if (isComboRequest && text.includes(COMBO_TOOL_RESULT)) {
    return missingOrFinal(text, [
      [COMBO_SENTINEL, "combo-memory"],
      [RAG_SENTINEL, "rag"],
      [COMBO_TOOL_RESULT, "tool-result"],
    ], "COMBO_MISSING", COMBO_FINAL);
  }

  if (/qa-plugin-smoke:plugin-tool-ok-local-agent/.test(text)) {
    return { role: "assistant", content: "qa-plugin-smoke:plugin-tool-ok-local-agent" };
  }
  if (/qa_plugin_echo|plugin-tool-ok-local-agent/i.test(current || text) && pluginTool && !/qa-plugin-smoke:plugin-tool-ok-local-agent/.test(text)) {
    return toolCall("call_qa_plugin_echo", pluginTool, { text: "plugin-tool-ok-local-agent" });
  }

  const e2eTool = firstToolName(tools, ["e2e_lookup"]);
  if (/Use the e2e lookup tool|e2e lookup tool|tool loop/i.test(current || text) && e2eTool && !/tool-result:alpha/.test(text)) {
    return toolCall("call_e2e_lookup", e2eTool, { query: "alpha" });
  }
  if (/tool-result:alpha/.test(text)) return { role: "assistant", content: "Tool loop final answer after tool-result:alpha" };
  if (/RAG_SENTINEL/.test(text)) return { role: "assistant", content: "RAG final answer with RAG_SENTINEL" };
  if (/NONSTREAM_OK/i.test(current || text)) return { role: "assistant", content: "NONSTREAM_OK" };
  if (/IMAGE_OK/i.test(current || text)
    && /(?:\[Image\]|langbot_input_attachments|data:image\/|\"type\":\s*\"image\")/i.test(current || text)) {
    return { role: "assistant", content: "IMAGE_OK" };
  }
  if (/azalea-cobalt-7421/.test(text)) return { role: "assistant", content: "azalea-cobalt-7421" };

  return { role: "assistant", content: responseTextForBody(payload) };
}

function toolCall(id, name, args) {
  return toolCalls([[id, name, args]]);
}

function toolCalls(calls) {
  return {
    role: "assistant",
    content: "",
    tool_calls: calls.map(([id, name, args]) => ({
      id,
      type: "function",
      function: {
        name,
        arguments: JSON.stringify(args),
      },
    })),
  };
}

function missingOrFinal(text, requirements, prefix, finalText) {
  const missing = requirements
    .filter(([needle]) => !text.includes(needle))
    .map(([, label]) => label);
  return {
    role: "assistant",
    content: missing.length ? `${prefix}_${missing.join("_")}` : finalText,
  };
}

function flattenContent(content) {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") return item.text || "";
        return "";
      })
      .join("\n");
  }
  return "";
}

function recordRequest(entry) {
  const item = {
    ...entry,
    at: new Date().toISOString(),
    finished_at: null,
    finished_epoch_ms: null,
    duration_ms: null,
    first_chunk_at: null,
    first_chunk_epoch_ms: null,
    first_chunk_ms: null,
    first_content_chunk_at: null,
    first_content_chunk_epoch_ms: null,
    first_content_chunk_ms: null,
    content_chunk_count: 0,
  };
  recentRequests.push(item);
  while (recentRequests.length > config.request_log_limit) recentRequests.shift();
  return item;
}

function markRequestTiming(entry, key, startedPerf) {
  if (!entry || entry[`${key}_at`]) return;
  const now = Date.now();
  entry[`${key}_at`] = new Date(now).toISOString();
  entry[`${key}_epoch_ms`] = now;
  entry[`${key}_ms`] = rounded(performance.now() - startedPerf);
}

function finishRequestRecord(entry, startedPerf, updates = {}) {
  if (!entry || entry.finished_at) return;
  const now = Date.now();
  Object.assign(entry, updates);
  entry.finished_at = new Date(now).toISOString();
  entry.finished_epoch_ms = now;
  entry.duration_ms = rounded(performance.now() - startedPerf);
}

function rounded(value) {
  return Number(value.toFixed(3));
}

function previewText(value) {
  return String(value || "").slice(0, 120);
}

function resetRequestState() {
  requestCount = 0;
  recentRequests.length = 0;
}

function applyConfig(updates) {
  if (!updates || typeof updates !== "object") return;
  assignString(updates, "response_text");
  assignNonNegativeInteger(updates, "first_token_delay_ms");
  assignNonNegativeInteger(updates, "chunk_delay_ms");
  assignNonNegativeInteger(updates, "chunk_count");
  assignNonNegativeInteger(updates, "fail_first_n");
  assignNonNegativeInteger(updates, "fail_every_n");
  assignNonNegativeInteger(updates, "request_log_limit");
  if (updates.fault_status !== undefined) {
    const parsed = Number.parseInt(String(updates.fault_status), 10);
    if (Number.isInteger(parsed) && parsed >= 400 && parsed <= 599) config.fault_status = parsed;
  }
  assignBoolean(updates, "fail_after_first_chunk");
  assignBoolean(updates, "dynamic_response");
}

function assignString(updates, key) {
  if (updates[key] !== undefined) config[key] = String(updates[key]);
}

function assignNonNegativeInteger(updates, key) {
  if (updates[key] === undefined) return;
  const parsed = Number.parseInt(String(updates[key]), 10);
  if (Number.isInteger(parsed) && parsed >= 0) config[key] = parsed;
}

function assignBoolean(updates, key) {
  if (updates[key] === undefined) return;
  config[key] = bool(updates[key], config[key]);
}
