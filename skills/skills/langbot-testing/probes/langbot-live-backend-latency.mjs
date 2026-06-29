#!/usr/bin/env node

import { mkdir, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { env, exit } from "node:process";

function pad(value, size = 2) {
  return String(value).padStart(size, "0");
}

function localIsoWithOffset(date = new Date()) {
  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absolute = Math.abs(offsetMinutes);
  return [
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}.${pad(date.getMilliseconds(), 3)}`,
    `${sign}${pad(Math.floor(absolute / 60))}:${pad(absolute % 60)}`,
  ].join("");
}

function timestampSlug(date = new Date()) {
  return date.toISOString().replace(/\.\d{3}Z$/, "Z").replace(/[^0-9A-Za-z]+/g, "-").replace(/^-|-$/g, "");
}

function percentile(values, percentileValue) {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.ceil((percentileValue / 100) * sorted.length) - 1);
  return Number(sorted[index].toFixed(3));
}

function stats(values) {
  if (values.length === 0) return { min: 0, p50: 0, p95: 0, p99: 0, max: 0 };
  return {
    min: Number(Math.min(...values).toFixed(3)),
    p50: percentile(values, 50),
    p95: percentile(values, 95),
    p99: percentile(values, 99),
    max: Number(Math.max(...values).toFixed(3)),
  };
}

function parseJsonList(value, fallback) {
  if (!value) return fallback;
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) && parsed.every((item) => typeof item === "string") ? parsed : fallback;
  } catch {
    return fallback;
  }
}

function joinUrl(baseUrl, path) {
  const base = baseUrl.replace(/\/+$/, "");
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${base}${suffix}`;
}

async function fetchOnce(url, timeoutMs) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const started = performance.now();
  try {
    const response = await fetch(url, { method: "GET", signal: controller.signal });
    await response.arrayBuffer();
    const latencyMs = performance.now() - started;
    return {
      url,
      ok: response.status < 500,
      status: response.status,
      latency_ms: Number(latencyMs.toFixed(3)),
      error: "",
    };
  } catch (error) {
    const latencyMs = performance.now() - started;
    return {
      url,
      ok: false,
      status: 0,
      latency_ms: Number(latencyMs.toFixed(3)),
      error: error instanceof Error ? error.message : String(error),
    };
  } finally {
    clearTimeout(timeout);
  }
}

async function runBatches(urls, totalRequests, concurrency, timeoutMs) {
  const queue = Array.from({ length: totalRequests }, (_, index) => urls[index % urls.length]);
  const results = [];
  while (queue.length > 0) {
    const batch = queue.splice(0, concurrency);
    results.push(...await Promise.all(batch.map((url) => fetchOnce(url, timeoutMs))));
  }
  return results;
}

async function main() {
  const root = resolve(env.LBS_ROOT || process.cwd());
  const caseId = "langbot-live-backend-latency";
  const runId = env.LBS_RUN_ID || `${timestampSlug()}-${caseId}`;
  const evidenceDir = resolve(env.LBS_EVIDENCE_DIR || join(root, "reports", "evidence", runId));
  await mkdir(evidenceDir, { recursive: true });

  const startedAt = new Date();
  const backendUrl = env.LANGBOT_BACKEND_URL || "";
  const endpoints = parseJsonList(env.LANGBOT_PERF_ENDPOINTS_JSON, ["/healthz"]);
  const totalRequests = Number(env.LANGBOT_PERF_REQUESTS || "12");
  const concurrency = Number(env.LANGBOT_PERF_CONCURRENCY || "2");
  const timeoutMs = Number(env.LANGBOT_PERF_TIMEOUT_MS || "5000");
  const p95BudgetMs = Number(env.LANGBOT_PERF_BACKEND_P95_MS || "1000");
  const maxErrorRate = Number(env.LANGBOT_PERF_MAX_ERROR_RATE || "0");
  const metricsPath = join(evidenceDir, "metrics.json");
  const networkLogPath = join(evidenceDir, "network.log");
  const automationResultPath = join(evidenceDir, "automation-result.json");
  const resultPath = join(evidenceDir, "result.json");

  let status = "fail";
  let reason = "";
  let results = [];
  if (!backendUrl) {
    status = "env_issue";
    reason = "LANGBOT_BACKEND_URL is not configured.";
  } else {
    const urls = endpoints.map((path) => joinUrl(backendUrl, path));
    results = await runBatches(urls, totalRequests, concurrency, timeoutMs);
    const okCount = results.filter((item) => item.ok).length;
    const errorCount = results.length - okCount;
    const errorRate = results.length === 0 ? 1 : errorCount / results.length;
    const latencies = results.filter((item) => item.ok).map((item) => item.latency_ms);
    const latencyStats = stats(latencies);
    const allConnectionFailures = results.length > 0 && results.every((item) => item.status === 0);
    if (allConnectionFailures) {
      status = "env_issue";
      reason = `Backend did not respond at ${backendUrl}.`;
    } else if (latencyStats.p95 <= p95BudgetMs && errorRate <= maxErrorRate) {
      status = "pass";
      reason = "Live backend latency probe passed all thresholds.";
    } else {
      status = "fail";
      reason = "Live backend latency probe breached latency or error-rate thresholds.";
    }
  }

  const statusCounts = {};
  for (const item of results) {
    const key = item.status === 0 ? "network_error" : String(item.status);
    statusCounts[key] = (statusCounts[key] || 0) + 1;
  }
  const okResults = results.filter((item) => item.ok);
  const metrics = {
    probe: caseId,
    backend_url: backendUrl,
    endpoints,
    total_requests: totalRequests,
    concurrency,
    timeout_ms: timeoutMs,
    ok_count: okResults.length,
    error_count: results.length - okResults.length,
    error_rate: results.length === 0 ? 1 : Number(((results.length - okResults.length) / results.length).toFixed(4)),
    latency_ms: stats(okResults.map((item) => item.latency_ms)),
    status_counts: statusCounts,
  };
  const thresholds = {
    backend_p95_ms: { actual: metrics.latency_ms.p95, max: p95BudgetMs, pass: metrics.latency_ms.p95 <= p95BudgetMs },
    error_rate: { actual: metrics.error_rate, max: maxErrorRate, pass: metrics.error_rate <= maxErrorRate },
  };

  await writeFile(metricsPath, `${JSON.stringify({ ...metrics, samples: results }, null, 2)}\n`, "utf8");
  await writeFile(networkLogPath, results.map((item) => JSON.stringify(item)).join("\n") + (results.length > 0 ? "\n" : ""), "utf8");

  const finishedAt = new Date();
  const result = {
    source: "automation",
    case_id: caseId,
    run_id: runId,
    status,
    reason,
    started_at: startedAt.toISOString(),
    started_at_local: localIsoWithOffset(startedAt),
    finished_at: finishedAt.toISOString(),
    finished_at_local: localIsoWithOffset(finishedAt),
    duration_ms: finishedAt.getTime() - startedAt.getTime(),
    url: backendUrl,
    metrics_summary: {
      requests: metrics.total_requests,
      concurrency: metrics.concurrency,
      ok_count: metrics.ok_count,
      error_rate: metrics.error_rate,
      latency_p50_ms: metrics.latency_ms.p50,
      latency_p95_ms: metrics.latency_ms.p95,
      status_counts: metrics.status_counts,
    },
    thresholds_summary: thresholds,
    artifacts: {
      metrics_json: metricsPath,
      network_log: networkLogPath,
      automation_result_json: automationResultPath,
      result_json: resultPath,
    },
    evidence_collected: ["metrics", "network", "api_diagnostic", "filesystem"],
  };

  const resultText = `${JSON.stringify(result, null, 2)}\n`;
  await writeFile(automationResultPath, resultText, "utf8");
  await writeFile(resultPath, resultText, "utf8");
  console.log(JSON.stringify(result, null, 2));
  exit(status === "pass" ? 0 : status === "env_issue" ? 2 : 1);
}

await main();
