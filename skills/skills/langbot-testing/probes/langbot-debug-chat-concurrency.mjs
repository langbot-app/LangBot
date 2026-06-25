#!/usr/bin/env node

import crypto from "node:crypto";
import net from "node:net";
import tls from "node:tls";
import { mkdir, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { env, exit } from "node:process";
import {
  apiJson,
  appendLine,
  ensureEvidence,
  evidencePaths,
  loadEnvFiles,
  localIsoWithOffset,
  redact,
  resetAndAuthLocalUser,
  writeResult,
} from "../../../scripts/e2e/lib/langbot-e2e.mjs";

const DEFAULT_LOCAL_PASSWORD = "LangBotE2ELocalPass!2026";

await loadEnvFiles();
const caseId = env.LBS_CASE_ID || "langbot-debug-chat-concurrency";
const paths = evidencePaths(caseId);
await ensureEvidence(paths);

const startedAt = new Date();
const metricsPath = resolve(paths.evidenceDir, "metrics.json");
const samplesPath = resolve(paths.evidenceDir, "samples.json");
const fakeProviderStatePath = resolve(paths.evidenceDir, "fake-provider-state.json");
const resetDiagnosticPath = resolve(paths.evidenceDir, "debug-chat-reset-diagnostic.json");
const backendUrl = env.LANGBOT_BACKEND_URL || "";
const fakeProviderUrl = env.LANGBOT_FAKE_PROVIDER_URL || "";
const pipelineUrl = env.LANGBOT_E2E_PIPELINE_URL || env.LANGBOT_PIPELINE_URL || "";
const pipelineName = env.LANGBOT_E2E_PIPELINE_NAME || env.LANGBOT_PIPELINE_NAME || "";
const sessionType = env.LANGBOT_DEBUG_CHAT_LOAD_SESSION_TYPE || env.LANGBOT_E2E_DEBUG_CHAT_SESSION_TYPE || "person";
const totalRequests = positiveInteger(env.LANGBOT_DEBUG_CHAT_LOAD_REQUESTS, defaultRequests(caseId));
const concurrency = Math.min(totalRequests, positiveInteger(env.LANGBOT_DEBUG_CHAT_LOAD_CONCURRENCY, defaultConcurrency(caseId)));
const timeoutMs = positiveInteger(env.LANGBOT_DEBUG_CHAT_LOAD_TIMEOUT_MS, defaultTimeout(caseId));
const expectedPrefix = env.LANGBOT_DEBUG_CHAT_LOAD_EXPECTED_PREFIX || "LBQA";
const promptTemplate = env.LANGBOT_DEBUG_CHAT_LOAD_PROMPT_TEMPLATE
  || "请只回复 \"{expected}\"，不要解释，不要添加其他字符。";
const stream = bool(env.LANGBOT_DEBUG_CHAT_LOAD_STREAM, true);
const resetBeforeRun = bool(env.LANGBOT_DEBUG_CHAT_LOAD_RESET, true);
const responseP95BudgetMs = positiveNumber(env.LANGBOT_DEBUG_CHAT_LOAD_RESPONSE_P95_MS, defaultP95Budget(caseId));
const firstResponseP95BudgetMs = positiveNumber(env.LANGBOT_DEBUG_CHAT_LOAD_FIRST_RESPONSE_P95_MS, 0);
const maxErrorRate = positiveNumber(env.LANGBOT_DEBUG_CHAT_LOAD_MAX_ERROR_RATE, 0);
const minErrorRate = positiveNumber(env.LANGBOT_DEBUG_CHAT_LOAD_MIN_ERROR_RATE, 0);
const minErrorCount = nonNegativeInteger(env.LANGBOT_DEBUG_CHAT_LOAD_MIN_ERROR_COUNT, 0);
const minOkCount = nonNegativeInteger(env.LANGBOT_DEBUG_CHAT_LOAD_MIN_OK_COUNT, 0);
const minProviderFaultCount = nonNegativeInteger(env.LANGBOT_DEBUG_CHAT_LOAD_MIN_PROVIDER_FAULT_COUNT, 0);
const failOnFinalMismatch = bool(env.LANGBOT_DEBUG_CHAT_LOAD_FAIL_ON_FINAL_MISMATCH, false);
const failureSignals = textList(env.LANGBOT_E2E_FAILURE_SIGNALS || env.LANGBOT_DEBUG_CHAT_LOAD_FAILURE_SIGNALS || "");

const result = {
  source: "automation",
  case_id: caseId,
  run_id: paths.runId,
  status: "fail",
  reason: "",
  started_at: startedAt.toISOString(),
  started_at_local: localIsoWithOffset(startedAt),
  finished_at: "",
  finished_at_local: "",
  duration_ms: 0,
  backend_url: backendUrl,
  pipeline_url: pipelineUrl,
  pipeline_name: pipelineName,
  pipeline_id: "",
  session_type: sessionType,
  load_profile: {
    requests: totalRequests,
    concurrency,
    timeout_ms: timeoutMs,
    stream,
    reset_before_run: resetBeforeRun,
    fail_on_final_mismatch: failOnFinalMismatch,
  },
  evidence: {
    network_log: paths.networkLog,
    metrics_json: metricsPath,
    samples_json: samplesPath,
    fake_provider_state_json: fakeProviderStatePath,
    debug_chat_reset_diagnostic_json: resetDiagnosticPath,
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["metrics", "network", "api_diagnostic", "filesystem"],
};

try {
  if (!backendUrl) {
    result.status = "env_issue";
    throw new Error("LANGBOT_BACKEND_URL is not configured.");
  }
  if (!["person", "group"].includes(sessionType)) {
    throw new Error(`LANGBOT_DEBUG_CHAT_LOAD_SESSION_TYPE must be person or group, got ${sessionType}.`);
  }
  const backendReady = await backendReachable(backendUrl);
  if (!backendReady) {
    result.status = "env_issue";
    throw new Error(`Backend did not respond at ${backendUrl}.`);
  }

  const user = env.LANGBOT_E2E_LOGIN_USER || "";
  const password = env.LANGBOT_E2E_LOGIN_PASSWORD || DEFAULT_LOCAL_PASSWORD;
  if (!user) {
    result.status = "env_issue";
    throw new Error("LANGBOT_E2E_LOGIN_USER is required so this probe can resolve/reset the Debug Chat session.");
  }
  const auth = await resetAndAuthLocalUser({ backendUrl, user, password });

  const pipeline = await resolvePipeline({ backendUrl, token: auth.token, pipelineUrl, pipelineName });
  result.pipeline_id = pipeline.id;
  result.pipeline_name = pipeline.name || pipelineName;
  if (!result.pipeline_url && env.LANGBOT_FRONTEND_URL) {
    result.pipeline_url = `${env.LANGBOT_FRONTEND_URL.replace(/\/$/, "")}/home/pipelines?id=${encodeURIComponent(pipeline.id)}`;
  }

  if (resetBeforeRun) {
    const reset = await apiJson(backendUrl, `/api/v1/pipelines/${encodeURIComponent(pipeline.id)}/ws/reset/${encodeURIComponent(sessionType)}`, {
      method: "POST",
      token: auth.token,
    });
    const resetDiagnostic = {
      status: isApiFailure(reset) ? "fail" : "ready",
      http_status: reset.status,
      code: reset.json.code ?? null,
      reason: isApiFailure(reset) ? reset.json.msg || "Debug Chat reset failed." : "Debug Chat session reset.",
    };
    await writeFile(resetDiagnosticPath, `${JSON.stringify(resetDiagnostic, null, 2)}\n`, "utf8");
    if (resetDiagnostic.status === "fail") {
      throw new Error(resetDiagnostic.reason);
    }
  }

  const wsUrl = websocketUrl(backendUrl, pipeline.id, sessionType);
  const loadStartedAt = performance.now();
  const samples = await runLoad({
    wsUrl,
    totalRequests,
    concurrency,
    timeoutMs,
    promptTemplate,
    expectedPrefix,
    stream,
    failOnFinalMismatch,
    failureSignals,
  });
  const loadDurationMs = performance.now() - loadStartedAt;
  const fakeProviderState = await readFakeProviderState(fakeProviderUrl);
  if (fakeProviderState) {
    await writeFile(fakeProviderStatePath, `${JSON.stringify(fakeProviderState, null, 2)}\n`, "utf8");
  }
  const metrics = buildMetrics({
    samples,
    totalRequests,
    concurrency,
    timeoutMs,
    loadDurationMs,
    backendUrl,
    pipelineId: pipeline.id,
    sessionType,
    fakeProviderState,
  });
  const thresholds = buildThresholds(metrics);
  const passed = Object.values(thresholds).every((item) => item.pass);
  result.status = passed ? "pass" : "fail";
  result.reason = passed
    ? "Debug Chat WebSocket concurrency probe passed all thresholds."
    : "Debug Chat WebSocket concurrency probe breached latency or error-rate thresholds.";
  result.metrics_summary = {
    requests: metrics.total_requests,
    concurrency: metrics.concurrency,
    ok_count: metrics.ok_count,
    error_count: metrics.error_count,
    timeout_count: metrics.timeout_count,
    error_rate: metrics.error_rate,
    response_p50_ms: metrics.response_duration_ms.p50,
    response_p95_ms: metrics.response_duration_ms.p95,
    first_response_p95_ms: metrics.first_response_ms.p95,
    throughput_rps: metrics.throughput_rps,
    status_counts: metrics.status_counts,
    fake_provider_request_count: metrics.fake_provider?.request_count ?? null,
    fake_provider_fault_count: metrics.fake_provider?.fault_count ?? null,
  };
  result.thresholds_summary = thresholds;
  result.artifacts = {
    metrics_json: metricsPath,
    samples_json: samplesPath,
    fake_provider_state_json: fakeProviderState ? fakeProviderStatePath : "",
    network_log: paths.networkLog,
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  };

  await writeFile(metricsPath, `${JSON.stringify({ ...metrics, thresholds }, null, 2)}\n`, "utf8");
  await writeFile(samplesPath, `${JSON.stringify(samples, null, 2)}\n`, "utf8");
} catch (error) {
  if (!["env_issue", "blocked"].includes(result.status)) {
    result.status = looksLikeEnvIssue(error) ? "env_issue" : "fail";
  }
  result.reason = result.reason || safeReason(error.message);
} finally {
  const finishedAt = new Date();
  result.finished_at = finishedAt.toISOString();
  result.finished_at_local = localIsoWithOffset(finishedAt);
  result.duration_ms = finishedAt.getTime() - startedAt.getTime();
  await mkdir(paths.evidenceDir, { recursive: true });
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

exit(result.status === "pass" ? 0 : result.status === "env_issue" || result.status === "blocked" ? 2 : 1);

function defaultRequests(id) {
  return id.includes("space") ? 3 : 12;
}

function defaultConcurrency(id) {
  return id.includes("space") ? 1 : 4;
}

function defaultTimeout(id) {
  return id.includes("space") ? 120_000 : 30_000;
}

function defaultP95Budget(id) {
  return id.includes("space") ? 120_000 : 5_000;
}

function positiveInteger(value, fallback) {
  const parsed = Number.parseInt(String(value || ""), 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

function nonNegativeInteger(value, fallback) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : fallback;
}

function positiveNumber(value, fallback) {
  const parsed = Number(value || "");
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

function bool(value, fallback) {
  if (value === undefined || value === "") return fallback;
  if (/^(1|true|yes|on)$/i.test(String(value))) return true;
  if (/^(0|false|no|off)$/i.test(String(value))) return false;
  return fallback;
}

function textList(value) {
  return String(value || "")
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

async function backendReachable(baseUrl) {
  try {
    const response = await fetch(`${baseUrl.replace(/\/$/, "")}/healthz`, {
      signal: AbortSignal.timeout(3000),
    });
    return response.status < 500;
  } catch {
    return false;
  }
}

async function readFakeProviderState(rootUrl) {
  if (!rootUrl) return null;
  try {
    const response = await fetch(`${normalizeProviderRootUrl(rootUrl)}/__qa/config`, {
      signal: AbortSignal.timeout(3000),
    });
    const json = await response.json().catch(() => ({}));
    return {
      status: response.ok && json.ok === true ? "loaded" : "unavailable",
      url: normalizeProviderRootUrl(rootUrl),
      http_status: response.status,
      model: json.model || "",
      config: json.config || {},
      request_count: Number.isFinite(json.request_count) ? json.request_count : null,
      recent_requests: Array.isArray(json.recent_requests) ? json.recent_requests : [],
    };
  } catch (error) {
    return {
      status: "unavailable",
      url: normalizeProviderRootUrl(rootUrl),
      reason: safeReason(error.message),
      request_count: null,
      recent_requests: [],
    };
  }
}

function normalizeProviderRootUrl(value) {
  const trimmed = String(value || "").trim().replace(/\/$/, "");
  return trimmed.endsWith("/v1") ? trimmed.slice(0, -3) : trimmed;
}

function pipelineIdFromUrl(url) {
  if (!url) return "";
  try {
    const parsed = new URL(url);
    return parsed.searchParams.get("id") || "";
  } catch {
    return "";
  }
}

async function resolvePipeline({ backendUrl, token, pipelineUrl, pipelineName }) {
  const idFromUrl = pipelineIdFromUrl(pipelineUrl);
  if (idFromUrl) {
    const response = await apiJson(backendUrl, `/api/v1/pipelines/${encodeURIComponent(idFromUrl)}`, { token });
    const pipeline = response.json.data?.pipeline;
    if (isApiFailure(response) || !pipeline?.uuid) {
      throw new Error(response.json.msg || `Could not load pipeline ${idFromUrl}.`);
    }
    return { id: pipeline.uuid, name: pipeline.name || "" };
  }
  if (!pipelineName) {
    throw new Error("Set LANGBOT_E2E_PIPELINE_URL or LANGBOT_E2E_PIPELINE_NAME before running this probe.");
  }
  const response = await apiJson(backendUrl, "/api/v1/pipelines", { token });
  if (isApiFailure(response)) {
    throw new Error(response.json.msg || "Failed to list pipelines.");
  }
  const pipeline = (response.json.data?.pipelines || []).find((item) => item.name === pipelineName);
  if (!pipeline?.uuid) {
    throw new Error(`Could not find pipeline named ${pipelineName}.`);
  }
  return { id: pipeline.uuid, name: pipeline.name || pipelineName };
}

function isApiFailure(response) {
  return response.status >= 400 || (response.json.code !== undefined && response.json.code !== 0);
}

function websocketUrl(baseUrl, pipelineId, sessionType) {
  const parsed = new URL(baseUrl);
  parsed.protocol = parsed.protocol === "https:" ? "wss:" : "ws:";
  parsed.pathname = `/api/v1/pipelines/${encodeURIComponent(pipelineId)}/ws/connect`;
  parsed.search = `?session_type=${encodeURIComponent(sessionType)}`;
  return parsed.toString();
}

async function runLoad(options) {
  const samples = [];
  let nextIndex = 0;
  const workers = Array.from({ length: options.concurrency }, async () => {
    while (nextIndex < options.totalRequests) {
      const index = nextIndex;
      nextIndex += 1;
      const sample = await runSingleRequest({ ...options, index });
      samples.push(sample);
    }
  });
  await Promise.all(workers);
  return samples.sort((left, right) => left.index - right.index);
}

function expectedForIndex(prefix, index) {
  return `${prefix}-${String(index + 1).padStart(4, "0")}`;
}

function promptForIndex(template, expected) {
  return template.replaceAll("{expected}", expected);
}

function runSingleRequest({
  wsUrl,
  index,
  timeoutMs,
  promptTemplate,
  expectedPrefix,
  stream,
  failOnFinalMismatch,
  failureSignals,
}) {
  return new Promise((resolve) => {
    const expected = expectedForIndex(expectedPrefix, index);
    const prompt = promptForIndex(promptTemplate, expected);
    const sample = {
      index,
      status: "running",
      ok: false,
      expected_text: expected,
      prompt,
      response_text: "",
      connected_ms: null,
      first_response_ms: null,
      response_duration_ms: null,
      event_count: 0,
      foreign_response_count: 0,
      last_foreign_response_text: "",
      error: "",
      close_code: null,
      close_reason: "",
    };
    let closed = false;
    let connectedAt = 0;
    let sentAt = 0;
    const startedAt = performance.now();
    let client = null;
    const timer = setTimeout(() => {
      finish("timeout", `Timed out after ${timeoutMs} ms.`);
    }, timeoutMs);

    client = openRawWebSocket(wsUrl, {
      onOpen() {
        connectedAt = performance.now();
        sample.connected_ms = rounded(connectedAt - startedAt);
      },
      onMessage(text) {
        sample.event_count += 1;
        let data;
        try {
          data = JSON.parse(String(text || ""));
        } catch (error) {
          finish("error", `Invalid WebSocket JSON: ${error.message}`);
          return;
        }
        appendLine(paths.networkLog, JSON.stringify({
          request_index: index,
          type: data.type,
          session_type: data.session_type || "",
          role: data.data?.role || "",
          is_final: data.data?.is_final ?? null,
          content_preview: redact(String(data.data?.content || data.message || "").slice(0, 200)),
        })).catch(() => {});

        if (data.type === "connected") {
          sentAt = performance.now();
          client.send(JSON.stringify({
            type: "message",
            message: [{ type: "Plain", text: prompt }],
            stream,
          }));
          return;
        }
        if (data.type === "error") {
          finish("error", data.message || "WebSocket error message.");
          return;
        }
        if (data.type !== "response" || data.data?.role !== "assistant") return;

        const content = String(data.data.content || "");
        if (content) sample.response_text = content;
        if (data.data.is_final === true) {
          const ok = sample.response_text.includes(expected);
          if (ok) {
            if (sample.first_response_ms === null && sentAt > 0) {
              sample.first_response_ms = rounded(performance.now() - sentAt);
            }
            finish("pass", "");
          } else if (matchesFailureSignal(sample.response_text, failureSignals)) {
            finish("app_error", `Assistant final response matched a failure signal: ${sample.response_text}`);
          } else if (failOnFinalMismatch && !containsLoadToken(sample.response_text, expectedPrefix)) {
            finish("mismatch", `Final assistant response did not include ${expected}: ${sample.response_text}`);
          } else {
            sample.foreign_response_count += 1;
            sample.last_foreign_response_text = sample.response_text;
          }
        }
      },
      onError(error) {
        finish("connection_error", `WebSocket connection error: ${error.message}`);
      },
      onClose(event) {
        sample.close_code = event.code;
        sample.close_reason = event.reason || "";
        if (!closed) finish("closed", `WebSocket closed before final assistant response: ${event.code}`);
      },
    });

    function finish(status, reason) {
      if (closed) return;
      closed = true;
      clearTimeout(timer);
      sample.status = status;
      sample.ok = status === "pass";
      sample.error = status === "timeout" && sample.foreign_response_count > 0
        ? `${reason || ""} Saw ${sample.foreign_response_count} foreign assistant response(s); last=${sample.last_foreign_response_text}`
        : reason || "";
      if (sentAt > 0) sample.response_duration_ms = rounded(performance.now() - sentAt);
      else sample.response_duration_ms = rounded(performance.now() - startedAt);
      try {
        client?.close();
      } catch {
        // Closing a failed socket should not hide the sample result.
      }
      resolve(sample);
    }
  });
}

function containsLoadToken(text, prefix) {
  const escaped = String(prefix).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`${escaped}-\\d{4}`).test(String(text || ""));
}

function matchesFailureSignal(text, signals) {
  const lower = String(text || "").toLowerCase();
  return signals.some((signal) => lower.includes(signal.toLowerCase()));
}

function openRawWebSocket(wsUrl, handlers) {
  const parsed = new URL(wsUrl);
  const secure = parsed.protocol === "wss:";
  const port = Number(parsed.port || (secure ? 443 : 80));
  const host = parsed.hostname;
  const path = `${parsed.pathname}${parsed.search}`;
  const key = crypto.randomBytes(16).toString("base64");
  const socket = secure
    ? tls.connect({ host, port, servername: host })
    : net.connect({ host, port });
  let opened = false;
  let closed = false;
  let buffer = Buffer.alloc(0);

  socket.setNoDelay(true);
  socket.on("connect", () => {
    const originProtocol = secure ? "https" : "http";
    const request = [
      `GET ${path} HTTP/1.1`,
      `Host: ${parsed.host}`,
      "Upgrade: websocket",
      "Connection: Upgrade",
      `Sec-WebSocket-Key: ${key}`,
      "Sec-WebSocket-Version: 13",
      `Origin: ${originProtocol}://${parsed.host}`,
      "",
      "",
    ].join("\r\n");
    socket.write(request);
  });
  socket.on("data", (chunk) => {
    buffer = Buffer.concat([buffer, chunk]);
    if (!opened) {
      const headerEnd = buffer.indexOf("\r\n\r\n");
      if (headerEnd === -1) return;
      const headerText = buffer.slice(0, headerEnd).toString("utf8");
      buffer = buffer.slice(headerEnd + 4);
      if (!/^HTTP\/1\.1 101\b/i.test(headerText)) {
        handlers.onError(new Error(`Handshake failed: ${headerText.split("\r\n")[0] || "missing status"}`));
        socket.destroy();
        return;
      }
      opened = true;
      handlers.onOpen();
    }
    processFrames();
  });
  socket.on("error", (error) => {
    if (!closed) handlers.onError(error);
  });
  socket.on("close", () => {
    if (closed) return;
    closed = true;
    handlers.onClose({ code: null, reason: "" });
  });

  function processFrames() {
    while (true) {
      const frame = readFrame(buffer);
      if (!frame) return;
      buffer = buffer.slice(frame.consumed);
      if (frame.opcode === 0x1) {
        handlers.onMessage(frame.payload.toString("utf8"));
      } else if (frame.opcode === 0x8) {
        const code = frame.payload.length >= 2 ? frame.payload.readUInt16BE(0) : null;
        const reason = frame.payload.length > 2 ? frame.payload.slice(2).toString("utf8") : "";
        closed = true;
        handlers.onClose({ code, reason });
        socket.end();
        return;
      } else if (frame.opcode === 0x9) {
        writeFrame(socket, 0xA, frame.payload);
      }
    }
  }

  return {
    send(text) {
      if (closed || !opened) return;
      writeFrame(socket, 0x1, Buffer.from(text, "utf8"));
    },
    close() {
      if (closed) return;
      closed = true;
      if (!socket.destroyed) {
        if (opened) writeFrame(socket, 0x8, Buffer.alloc(0));
        setTimeout(() => socket.end(), 50).unref();
      }
    },
  };
}

function readFrame(buffer) {
  if (buffer.length < 2) return null;
  const first = buffer[0];
  const second = buffer[1];
  const opcode = first & 0x0f;
  const masked = Boolean(second & 0x80);
  let length = second & 0x7f;
  let offset = 2;
  if (length === 126) {
    if (buffer.length < offset + 2) return null;
    length = buffer.readUInt16BE(offset);
    offset += 2;
  } else if (length === 127) {
    if (buffer.length < offset + 8) return null;
    const high = buffer.readUInt32BE(offset);
    const low = buffer.readUInt32BE(offset + 4);
    length = high * 2 ** 32 + low;
    offset += 8;
  }
  let mask = null;
  if (masked) {
    if (buffer.length < offset + 4) return null;
    mask = buffer.slice(offset, offset + 4);
    offset += 4;
  }
  if (buffer.length < offset + length) return null;
  let payload = buffer.slice(offset, offset + length);
  if (mask) {
    payload = Buffer.from(payload);
    for (let index = 0; index < payload.length; index += 1) {
      payload[index] ^= mask[index % 4];
    }
  }
  return {
    opcode,
    payload,
    consumed: offset + length,
  };
}

function writeFrame(socket, opcode, payload) {
  const body = Buffer.isBuffer(payload) ? payload : Buffer.from(payload || "");
  const mask = crypto.randomBytes(4);
  const headerLength = body.length < 126 ? 2 : body.length <= 0xffff ? 4 : 10;
  const header = Buffer.alloc(headerLength);
  header[0] = 0x80 | opcode;
  if (body.length < 126) {
    header[1] = 0x80 | body.length;
  } else if (body.length <= 0xffff) {
    header[1] = 0x80 | 126;
    header.writeUInt16BE(body.length, 2);
  } else {
    header[1] = 0x80 | 127;
    header.writeUInt32BE(Math.floor(body.length / 2 ** 32), 2);
    header.writeUInt32BE(body.length >>> 0, 6);
  }
  const masked = Buffer.from(body);
  for (let index = 0; index < masked.length; index += 1) {
    masked[index] ^= mask[index % 4];
  }
  socket.write(Buffer.concat([header, mask, masked]));
}

function rounded(value) {
  return Number(value.toFixed(3));
}

function percentile(values, percentileValue) {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.ceil((percentileValue / 100) * sorted.length) - 1);
  return rounded(sorted[index]);
}

function stats(values) {
  if (values.length === 0) return { min: 0, p50: 0, p95: 0, p99: 0, max: 0 };
  return {
    min: rounded(Math.min(...values)),
    p50: percentile(values, 50),
    p95: percentile(values, 95),
    p99: percentile(values, 99),
    max: rounded(Math.max(...values)),
  };
}

function buildMetrics({ samples, totalRequests, concurrency, timeoutMs, loadDurationMs, backendUrl, pipelineId, sessionType, fakeProviderState }) {
  const okSamples = samples.filter((sample) => sample.ok);
  const statusCounts = {};
  for (const sample of samples) {
    statusCounts[sample.status] = (statusCounts[sample.status] || 0) + 1;
  }
  const errorCount = samples.length - okSamples.length;
  return {
    probe: caseId,
    backend_url: backendUrl,
    pipeline_id: pipelineId,
    session_type: sessionType,
    total_requests: totalRequests,
    completed_requests: samples.length,
    concurrency,
    timeout_ms: timeoutMs,
    ok_count: okSamples.length,
    error_count: errorCount,
    timeout_count: samples.filter((sample) => sample.status === "timeout").length,
    error_rate: samples.length === 0 ? 1 : rounded(errorCount / samples.length),
    load_duration_ms: rounded(loadDurationMs),
    throughput_rps: loadDurationMs <= 0 ? 0 : rounded(okSamples.length / (loadDurationMs / 1000)),
    status_counts: statusCounts,
    connected_ms: stats(samples.map((sample) => sample.connected_ms).filter(Number.isFinite)),
    first_response_ms: stats(okSamples.map((sample) => sample.first_response_ms).filter(Number.isFinite)),
    response_duration_ms: stats(okSamples.map((sample) => sample.response_duration_ms).filter(Number.isFinite)),
    fake_provider: summarizeFakeProviderState(fakeProviderState),
    samples,
  };
}

function summarizeFakeProviderState(state) {
  if (!state) return null;
  const recentRequests = Array.isArray(state.recent_requests) ? state.recent_requests : [];
  return {
    status: state.status || "unknown",
    url: state.url || "",
    request_count: Number.isFinite(state.request_count) ? state.request_count : recentRequests.length,
    recent_request_count: recentRequests.length,
    fault_count: recentRequests.filter((request) => request?.should_fail === true).length,
    streamed_request_count: recentRequests.filter((request) => request?.stream === true).length,
    config: state.config || {},
  };
}

function buildThresholds(metrics) {
  const thresholds = {
    error_rate: { actual: metrics.error_rate, max: maxErrorRate, pass: metrics.error_rate <= maxErrorRate },
    response_p95_ms: {
      actual: metrics.response_duration_ms.p95,
      max: responseP95BudgetMs,
      pass: metrics.ok_count > 0 && metrics.response_duration_ms.p95 <= responseP95BudgetMs,
    },
  };
  if (minErrorRate > 0) {
    thresholds.error_rate_min = {
      actual: metrics.error_rate,
      min: minErrorRate,
      pass: metrics.error_rate >= minErrorRate,
    };
  }
  if (minErrorCount > 0) {
    thresholds.error_count_min = {
      actual: metrics.error_count,
      min: minErrorCount,
      pass: metrics.error_count >= minErrorCount,
    };
  }
  if (minOkCount > 0) {
    thresholds.ok_count_min = {
      actual: metrics.ok_count,
      min: minOkCount,
      pass: metrics.ok_count >= minOkCount,
    };
  }
  if (minProviderFaultCount > 0) {
    const actual = metrics.fake_provider?.fault_count ?? 0;
    thresholds.fake_provider_fault_count_min = {
      actual,
      min: minProviderFaultCount,
      pass: actual >= minProviderFaultCount,
    };
  }
  if (firstResponseP95BudgetMs > 0) {
    thresholds.first_response_p95_ms = {
      actual: metrics.first_response_ms.p95,
      max: firstResponseP95BudgetMs,
      pass: metrics.ok_count > 0 && metrics.first_response_ms.p95 <= firstResponseP95BudgetMs,
    };
  }
  return thresholds;
}

function looksLikeEnvIssue(error) {
  const message = String(error?.message || error || "");
  return /fetch failed|ECONNREFUSED|ENOTFOUND|LANGBOT_.*not configured|Could not read recovery_key|Backend did not respond/i.test(message);
}

function safeReason(value) {
  return redact(String(value || "")).slice(0, 1000);
}
