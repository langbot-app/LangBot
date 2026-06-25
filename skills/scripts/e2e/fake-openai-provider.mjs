#!/usr/bin/env node

import { createServer } from "node:http";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { env, exit } from "node:process";

const args = parseArgs(process.argv.slice(2));
const host = args.host || env.LANGBOT_FAKE_PROVIDER_HOST || "127.0.0.1";
const port = integer(args.port ?? env.LANGBOT_FAKE_PROVIDER_PORT, 0);
const stateFile = args["state-file"] || env.LANGBOT_FAKE_PROVIDER_STATE_FILE || "";
const modelName = env.LANGBOT_FAKE_PROVIDER_MODEL_NAME || "gpt-4o-mini";
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
      recordRequest({
        id: requestId,
        path: url.pathname,
        stream: Boolean(body.stream),
        model: body.model || "",
        message_count: Array.isArray(body.messages) ? body.messages.length : 0,
        should_fail: shouldFail,
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
        return;
      }

      const replyText = responseTextForBody(body);

      if (body.stream) {
        await streamCompletion(response, {
          requestId,
          model: body.model || modelName,
          content: replyText,
          failAfterFirstChunk: config.fail_after_first_chunk,
        });
      } else {
        await sleep(config.first_token_delay_ms + config.chunk_delay_ms);
        sendJson(response, 200, completionPayload({
          requestId,
          model: body.model || modelName,
          content: replyText,
        }));
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

function completionPayload({ requestId, model, content }) {
  const completionTokens = tokenEstimate(content);
  return {
    id: requestId,
    object: "chat.completion",
    created: Math.floor(Date.now() / 1000),
    model,
    choices: [
      {
        index: 0,
        message: {
          role: "assistant",
          content,
        },
        finish_reason: "stop",
      },
    ],
    usage: {
      prompt_tokens: 8,
      completion_tokens: completionTokens,
      total_tokens: 8 + completionTokens,
    },
  };
}

async function streamCompletion(response, { requestId, model, content, failAfterFirstChunk: failMidStream }) {
  response.writeHead(200, {
    "content-type": "text/event-stream; charset=utf-8",
    "cache-control": "no-cache",
    "connection": "keep-alive",
  });

  await sleep(config.first_token_delay_ms);
  writeSse(response, {
    id: requestId,
    object: "chat.completion.chunk",
    created: Math.floor(Date.now() / 1000),
    model,
    choices: [{ index: 0, delta: { role: "assistant" }, finish_reason: null }],
  });

  const chunks = splitContent(content);
  for (let index = 0; index < chunks.length; index += 1) {
    await sleep(config.chunk_delay_ms);
    writeSse(response, {
      id: requestId,
      object: "chat.completion.chunk",
      created: Math.floor(Date.now() / 1000),
      model,
      choices: [{ index: 0, delta: { content: chunks[index] }, finish_reason: null }],
    });
    if (failMidStream && index === 0) {
      response.destroy(new Error("LangBot fake provider injected mid-stream disconnect"));
      return;
    }
  }

  await sleep(config.chunk_delay_ms);
  const completionTokens = tokenEstimate(content);
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
  recentRequests.push({
    ...entry,
    at: new Date().toISOString(),
  });
  while (recentRequests.length > config.request_log_limit) recentRequests.shift();
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
