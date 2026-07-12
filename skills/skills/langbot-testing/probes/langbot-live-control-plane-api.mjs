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

function joinUrl(baseUrl, path) {
  const base = baseUrl.replace(/\/+$/, "");
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${base}${suffix}`;
}

function parseJsonObject(value, fallback) {
  if (!value) return fallback;
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
}

function controlPlaneEndpoints() {
  return [
    {
      id: "healthz",
      path: "/healthz",
      expected_status: 200,
      expected_code: 0,
      p95_budget_ms: Number(env.LANGBOT_PERF_HEALTHZ_P95_MS || "500"),
      required_data_fields: [],
    },
    {
      id: "system_info",
      path: "/api/v1/system/info",
      expected_status: 200,
      expected_code: 0,
      p95_budget_ms: Number(env.LANGBOT_PERF_SYSTEM_INFO_P95_MS || "1000"),
      required_data_fields: ["version", "edition", "enable_marketplace"],
    },
  ];
}

async function fetchEndpoint(backendUrl, endpoint, timeoutMs) {
  const url = joinUrl(backendUrl, endpoint.path);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const started = performance.now();
  let bodyText = "";
  let json = null;
  let jsonValid = false;
  let error = "";

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: { "accept": "application/json" },
      signal: controller.signal,
    });
    bodyText = await response.text();
    try {
      json = bodyText ? JSON.parse(bodyText) : null;
      jsonValid = json !== null;
    } catch (parseError) {
      error = parseError instanceof Error ? parseError.message : String(parseError);
    }

    const data = json && typeof json === "object" && json.data && typeof json.data === "object" ? json.data : {};
    const missingFields = endpoint.required_data_fields.filter((field) => !(field in data));
    const statusOk = response.status === endpoint.expected_status;
    const codeOk = !json || typeof json !== "object" ? false : json.code === endpoint.expected_code;
    const shapeOk = jsonValid && missingFields.length === 0;
    const latencyMs = performance.now() - started;
    return {
      endpoint_id: endpoint.id,
      path: endpoint.path,
      url,
      status: response.status,
      ok: statusOk && codeOk && shapeOk,
      status_ok: statusOk,
      code_ok: codeOk,
      json_valid: jsonValid,
      missing_fields: missingFields,
      response_code: json && typeof json === "object" ? json.code : null,
      latency_ms: Number(latencyMs.toFixed(3)),
      error,
    };
  } catch (fetchError) {
    const latencyMs = performance.now() - started;
    return {
      endpoint_id: endpoint.id,
      path: endpoint.path,
      url,
      status: 0,
      ok: false,
      status_ok: false,
      code_ok: false,
      json_valid: false,
      missing_fields: endpoint.required_data_fields,
      response_code: null,
      latency_ms: Number(latencyMs.toFixed(3)),
      error: fetchError instanceof Error ? fetchError.message : String(fetchError),
    };
  } finally {
    clearTimeout(timeout);
  }
}

async function runBatches(backendUrl, endpoints, totalRequests, concurrency, timeoutMs) {
  const queue = Array.from({ length: totalRequests }, (_, index) => endpoints[index % endpoints.length]);
  const results = [];
  while (queue.length > 0) {
    const batch = queue.splice(0, concurrency);
    results.push(...await Promise.all(batch.map((endpoint) => fetchEndpoint(backendUrl, endpoint, timeoutMs))));
  }
  return results;
}

function endpointMetrics(endpoints, results) {
  return Object.fromEntries(endpoints.map((endpoint) => {
    const samples = results.filter((item) => item.endpoint_id === endpoint.id);
    const okSamples = samples.filter((item) => item.ok);
    return [
      endpoint.id,
      {
        path: endpoint.path,
        requests: samples.length,
        ok_count: okSamples.length,
        error_rate: samples.length === 0 ? 1 : Number(((samples.length - okSamples.length) / samples.length).toFixed(4)),
        latency_ms: stats(okSamples.map((item) => item.latency_ms)),
        p95_budget_ms: endpoint.p95_budget_ms,
      },
    ];
  }));
}

async function main() {
  const root = resolve(env.LBS_ROOT || process.cwd());
  const caseId = "langbot-live-control-plane-api";
  const runId = env.LBS_RUN_ID || `${timestampSlug()}-${caseId}`;
  const evidenceDir = resolve(env.LBS_EVIDENCE_DIR || join(root, "reports", "evidence", runId));
  await mkdir(evidenceDir, { recursive: true });

  const startedAt = new Date();
  const backendUrl = env.LANGBOT_BACKEND_URL || "";
  const endpoints = controlPlaneEndpoints();
  const configuredBudgets = parseJsonObject(env.LANGBOT_CONTROL_PLANE_P95_BUDGETS_JSON, {});
  for (const endpoint of endpoints) {
    const budget = configuredBudgets[endpoint.id];
    if (typeof budget === "number" && Number.isFinite(budget)) endpoint.p95_budget_ms = budget;
  }
  const totalRequests = Number(env.LANGBOT_CONTROL_PLANE_REQUESTS || "20");
  const concurrency = Number(env.LANGBOT_CONTROL_PLANE_CONCURRENCY || "4");
  const timeoutMs = Number(env.LANGBOT_CONTROL_PLANE_TIMEOUT_MS || "5000");
  const maxErrorRate = Number(env.LANGBOT_CONTROL_PLANE_MAX_ERROR_RATE || "0");
  const metricsPath = join(evidenceDir, "metrics.json");
  const endpointsPath = join(evidenceDir, "endpoints.json");
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
    results = await runBatches(backendUrl, endpoints, totalRequests, concurrency, timeoutMs);
    const allConnectionFailures = results.length > 0 && results.every((item) => item.status === 0);
    if (allConnectionFailures) {
      status = "env_issue";
      reason = `Backend did not respond at ${backendUrl}.`;
    }
  }

  const okResults = results.filter((item) => item.ok);
  const statusCounts = {};
  for (const item of results) {
    const key = item.status === 0 ? "network_error" : String(item.status);
    statusCounts[key] = (statusCounts[key] || 0) + 1;
  }
  const perEndpoint = endpointMetrics(endpoints, results);
  const responseShapeFailures = results.filter((item) => !item.json_valid || item.missing_fields.length > 0 || !item.code_ok).length;
  const errorRate = results.length === 0 ? 1 : Number(((results.length - okResults.length) / results.length).toFixed(4));
  const thresholds = {
    error_rate: { actual: errorRate, max: maxErrorRate, pass: errorRate <= maxErrorRate },
    response_shape_failures: { actual: responseShapeFailures, max: 0, pass: responseShapeFailures === 0 },
  };
  for (const endpoint of endpoints) {
    const actual = perEndpoint[endpoint.id].latency_ms.p95;
    thresholds[`${endpoint.id}_p95_ms`] = {
      actual,
      max: endpoint.p95_budget_ms,
      pass: actual <= endpoint.p95_budget_ms,
    };
  }

  if (status !== "env_issue") {
    const passed = Object.values(thresholds).every((item) => item.pass);
    status = passed ? "pass" : "fail";
    reason = passed
      ? "Live control-plane API probe passed all thresholds."
      : "Live control-plane API probe breached shape, latency, or error-rate thresholds.";
  }

  const metrics = {
    probe: caseId,
    backend_url: backendUrl,
    total_requests: totalRequests,
    concurrency,
    timeout_ms: timeoutMs,
    ok_count: okResults.length,
    error_count: results.length - okResults.length,
    error_rate: errorRate,
    status_counts: statusCounts,
    response_shape_failures: responseShapeFailures,
    endpoints: perEndpoint,
  };

  await writeFile(metricsPath, `${JSON.stringify({ ...metrics, samples: results }, null, 2)}\n`, "utf8");
  await writeFile(endpointsPath, `${JSON.stringify(endpoints, null, 2)}\n`, "utf8");
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
      response_shape_failures: metrics.response_shape_failures,
      endpoints: Object.fromEntries(Object.entries(metrics.endpoints).map(([id, value]) => [
        id,
        {
          path: value.path,
          ok_count: value.ok_count,
          error_rate: value.error_rate,
          latency_p50_ms: value.latency_ms.p50,
          latency_p95_ms: value.latency_ms.p95,
        },
      ])),
      status_counts: metrics.status_counts,
    },
    thresholds_summary: thresholds,
    artifacts: {
      metrics_json: metricsPath,
      endpoints_json: endpointsPath,
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
