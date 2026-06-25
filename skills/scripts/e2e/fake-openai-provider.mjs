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
const responseText = env.LANGBOT_FAKE_PROVIDER_RESPONSE_TEXT || "OK";
const firstTokenDelayMs = integer(env.LANGBOT_FAKE_PROVIDER_FIRST_TOKEN_DELAY_MS, 25);
const chunkDelayMs = integer(env.LANGBOT_FAKE_PROVIDER_CHUNK_DELAY_MS, 10);
const faultStatus = integer(env.LANGBOT_FAKE_PROVIDER_FAULT_STATUS, 500);
const failFirstN = integer(env.LANGBOT_FAKE_PROVIDER_FAIL_FIRST_N, 0);
const failEveryN = integer(env.LANGBOT_FAKE_PROVIDER_FAIL_EVERY_N, 0);
const failAfterFirstChunk = bool(env.LANGBOT_FAKE_PROVIDER_FAIL_AFTER_FIRST_CHUNK, false);
const requestLogLimit = integer(env.LANGBOT_FAKE_PROVIDER_REQUEST_LOG_LIMIT, 500);

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
        request_count: requestCount,
        recent_request_count: recentRequests.length,
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
      const shouldFail = requestCount <= failFirstN || (failEveryN > 0 && requestCount % failEveryN === 0);
      recordRequest({
        id: requestId,
        path: url.pathname,
        stream: Boolean(body.stream),
        model: body.model || "",
        message_count: Array.isArray(body.messages) ? body.messages.length : 0,
        should_fail: shouldFail,
      });

      if (shouldFail) {
        await sleep(firstTokenDelayMs);
        sendJson(response, faultStatus, {
          error: {
            message: `LangBot fake provider injected HTTP ${faultStatus}`,
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
          failAfterFirstChunk,
        });
      } else {
        await sleep(firstTokenDelayMs + chunkDelayMs);
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

  await sleep(firstTokenDelayMs);
  writeSse(response, {
    id: requestId,
    object: "chat.completion.chunk",
    created: Math.floor(Date.now() / 1000),
    model,
    choices: [{ index: 0, delta: { role: "assistant" }, finish_reason: null }],
  });

  const chunks = splitContent(content);
  for (let index = 0; index < chunks.length; index += 1) {
    await sleep(chunkDelayMs);
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

  await sleep(chunkDelayMs);
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
  const requested = integer(env.LANGBOT_FAKE_PROVIDER_CHUNK_COUNT, 0);
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
  if (/^(0|false|no|off)$/i.test(env.LANGBOT_FAKE_PROVIDER_DYNAMIC_RESPONSE || "")) {
    return responseText;
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
  return responseText;
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
  while (recentRequests.length > requestLogLimit) recentRequests.shift();
}
