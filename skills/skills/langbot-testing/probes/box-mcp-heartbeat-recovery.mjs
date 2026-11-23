#!/usr/bin/env node

import { execFile } from "node:child_process";
import { readFile, readlink, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { env, exit } from "node:process";
import { promisify } from "node:util";
import {
  apiJson,
  ensureEvidence,
  evidencePaths,
  exitCode,
  loadEnvFiles,
  localIsoWithOffset,
  resetAndAuthLocalUser,
  writeResult,
} from "../../../scripts/e2e/lib/langbot-e2e.mjs";

const execFileAsync = promisify(execFile);
const DEFAULT_LOCAL_PASSWORD = "LangBotE2ELocalPass!2026";
const BOX_COMMAND_RE = /(?:^|\s)-m\s+langbot_plugin\.cli\.__init__\s+box(?:\s|$)/;

await loadEnvFiles();
const caseId = env.LBS_CASE_ID || "box-mcp-heartbeat-recovery";
const paths = evidencePaths(caseId);
await ensureEvidence(paths);

const startedAt = new Date();
const backendUrl = env.LANGBOT_BACKEND_URL || "";
const user = env.LANGBOT_E2E_LOGIN_USER || "";
const password = env.LANGBOT_E2E_LOGIN_PASSWORD || DEFAULT_LOCAL_PASSWORD;
const serverUuid = env.LANGBOT_MCP_QA_STDIO_SERVER_UUID || "";
const expectedTool = env.LANGBOT_E2E_EXPECTED_TOOL || "qa_mcp_echo";
const recoveryTimeoutMs = positiveInteger(env.LANGBOT_BOX_RECOVERY_TIMEOUT_MS, 30_000);
const pollIntervalMs = positiveInteger(env.LANGBOT_BOX_RECOVERY_POLL_INTERVAL_MS, 250);
const faultModelPath = resolve(paths.evidenceDir, "fault-model.json");
const apiDiagnosticPath = resolve(paths.evidenceDir, "api-diagnostic.json");
const resourceLogPath = resolve(paths.evidenceDir, "resource-log.json");
const metricsPath = resolve(paths.evidenceDir, "metrics.json");
const ledgerAuditPath = resolve(paths.evidenceDir, "ledger-audit.json");
const debugChatEvidenceDir = resolve(paths.evidenceDir, "debug-chat");
const probeValue = `box-recovery-${Date.now().toString(36)}`;

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
  evidence: {
    fault_model_json: faultModelPath,
    api_diagnostic_json: apiDiagnosticPath,
    resource_log_json: resourceLogPath,
    metrics_json: metricsPath,
    ledger_audit_json: ledgerAuditPath,
    debug_chat_evidence_dir: debugChatEvidenceDir,
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: [
    "metrics",
    "api_diagnostic",
    "resource_log",
    "filesystem",
  ],
};

let resourceSamples = [];
let apiDiagnostic = {
  expected_tool_call: {
    tool_name: expectedTool,
    parameters: { text: probeValue },
    result_text: `${expectedTool}:${probeValue}`,
  },
};

try {
  requireEnv("LANGBOT_BACKEND_URL", backendUrl);
  requireEnv("LANGBOT_E2E_LOGIN_USER", user);
  requireEnv("LANGBOT_MCP_QA_STDIO_SERVER_UUID", serverUuid);
  requireEnv("LANGBOT_LOCAL_AGENT_PIPELINE_URL", env.LANGBOT_LOCAL_AGENT_PIPELINE_URL || "");
  requireEnv("LANGBOT_FRONTEND_URL", env.LANGBOT_FRONTEND_URL || "");

  const auth = await resetAndAuthLocalUser({ backendUrl, user, password });
  const preflight = await runtimeSnapshot(auth.token);
  apiDiagnostic.preflight = preflight;
  assertReadySnapshot(preflight, "preflight");

  const oldBox = await selectLocalBoxProcess();
  const faultModel = {
    target: "local Box runtime child process owned by the active LangBot checkout",
    injected_fault: "SIGTERM to the selected Box child process",
    destructive: true,
    blast_radius: "single local LangBot development instance",
    old_box_pid: oldBox.pid,
    parent_pid: oldBox.ppid,
    recovery_timeout_ms: recoveryTimeoutMs,
    abort_conditions: [
      "no exact Box command match",
      "multiple eligible Box processes",
      "Box parent is not main.py from LANGBOT_REPO",
    ],
    cleanup: "wait for the LangBot heartbeat to replace Box and restore the MCP session; do not spawn or register anything",
  };
  await writeFile(faultModelPath, `${JSON.stringify(faultModel, null, 2)}\n`, "utf8");

  process.kill(oldBox.pid, "SIGTERM");
  const faultStartedAt = performance.now();
  let observedOldProcessExit = false;
  let observedBoxUnavailable = false;
  let recovered = null;
  const deadline = Date.now() + recoveryTimeoutMs;

  while (Date.now() < deadline) {
    const processes = await boxProcesses();
    const oldAlive = processes.some((item) => item.pid === oldBox.pid);
    observedOldProcessExit ||= !oldAlive;
    const replacement = processes.find((item) => item.pid !== oldBox.pid && item.ppid === oldBox.ppid) || null;
    const snapshot = await runtimeSnapshot(auth.token).catch((error) => ({ error: error.message }));
    observedBoxUnavailable ||= snapshot.box?.available === false;
    const sample = {
      elapsed_ms: Math.round(performance.now() - faultStartedAt),
      old_process_alive: oldAlive,
      replacement_pid: replacement?.pid || null,
      box_available: snapshot.box?.available ?? null,
      box_active_sessions: snapshot.box?.active_sessions ?? null,
      box_managed_processes: snapshot.box?.managed_processes ?? null,
      mcp_status: snapshot.mcp?.status || null,
      mcp_tool_count: snapshot.mcp?.tool_count ?? null,
      mcp_retry_count: snapshot.mcp?.retry_count ?? null,
      tools_has_expected: snapshot.tools?.includes(expectedTool) ?? false,
      error: snapshot.error || "",
    };
    resourceSamples.push(sample);

    if (observedOldProcessExit
      && replacement
      && snapshotReady(snapshot)
      && (snapshot.mcp.retry_count ?? 0) > (preflight.mcp.retry_count ?? 0)) {
      recovered = { replacement, snapshot, elapsedMs: sample.elapsed_ms };
      break;
    }
    await delay(pollIntervalMs);
  }

  if (!recovered) {
    throw new Error(`Box/MCP did not recover within ${recoveryTimeoutMs} ms.`);
  }
  apiDiagnostic.recovered = recovered.snapshot;

  const chat = await runRecoveredDebugChat(probeValue);
  apiDiagnostic.debug_chat = {
    status: chat.status,
    reason: chat.reason,
    expected_assistant_text: probeValue,
    evidence_dir: debugChatEvidenceDir,
  };
  result.evidence_collected.push("ui", "screenshot", "console", "network");
  const ledger = await auditRecoveredToolCall(probeValue, startedAt);
  apiDiagnostic.ledger = {
    status: ledger.status,
    reason: ledger.reason,
    run: ledger.run || null,
    expected_tool_call: ledger.expected_tool_call || null,
    evidence_path: ledgerAuditPath,
  };
  if (chat.status !== "pass") {
    throw new Error(`Recovered Debug Chat tool call failed: ${chat.reason || chat.status}`);
  }
  if (ledger.status !== "pass") {
    throw new Error(`Recovered Debug Chat ledger audit failed: ${ledger.reason || ledger.status}`);
  }

  result.status = "pass";
  result.reason = `Box was replaced in ${recovered.elapsedMs} ms, MCP reconnected without registration, and the browser plus ledger proved ${expectedTool} returned the unique recovery value.`;
  result.metrics_summary = {
    recovery_duration_ms: recovered.elapsedMs,
    old_box_pid: oldBox.pid,
    new_box_pid: recovered.replacement.pid,
    observed_old_process_exit: observedOldProcessExit,
    observed_box_unavailable: observedBoxUnavailable,
    mcp_retry_count_before: preflight.mcp.retry_count ?? 0,
    mcp_retry_count_after: recovered.snapshot.mcp.retry_count ?? 0,
    debug_chat_response_ms: chat.metrics_summary?.response_p95_ms ?? null,
    ledger_run_id: ledger.run?.run_id || null,
  };
  result.thresholds_summary = {
    recovery_duration_ms: {
      actual: recovered.elapsedMs,
      max: recoveryTimeoutMs,
      pass: recovered.elapsedMs <= recoveryTimeoutMs,
    },
    mcp_retry_count_increased: {
      actual: recovered.snapshot.mcp.retry_count ?? 0,
      min: (preflight.mcp.retry_count ?? 0) + 1,
      pass: (recovered.snapshot.mcp.retry_count ?? 0) > (preflight.mcp.retry_count ?? 0),
    },
    debug_chat_status: { actual: chat.status, expected: "pass", pass: chat.status === "pass" },
    ledger_tool_call_status: { actual: ledger.status, expected: "pass", pass: ledger.status === "pass" },
  };
} catch (error) {
  if (result.status === "fail" && /is required/.test(error.message)) result.status = "env_issue";
  result.reason = error.message;
} finally {
  const finishedAt = new Date();
  result.finished_at = finishedAt.toISOString();
  result.finished_at_local = localIsoWithOffset(finishedAt);
  result.duration_ms = finishedAt.getTime() - startedAt.getTime();
  await writeFile(resourceLogPath, `${JSON.stringify(resourceSamples, null, 2)}\n`, "utf8");
  await writeFile(apiDiagnosticPath, `${JSON.stringify(apiDiagnostic, null, 2)}\n`, "utf8");
  await writeFile(metricsPath, `${JSON.stringify({
    probe: caseId,
    status: result.status,
    duration_ms: result.duration_ms,
    metrics_summary: result.metrics_summary || {},
    thresholds_summary: result.thresholds_summary || {},
  }, null, 2)}\n`, "utf8");
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
  exit(exitCode(result.status));
}

function requireEnv(name, value) {
  if (!value) throw new Error(`${name} is required.`);
}

function positiveInteger(value, fallback) {
  const parsed = Number.parseInt(String(value || ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function delay(milliseconds) {
  return new Promise((resolveDelay) => setTimeout(resolveDelay, milliseconds));
}

function isApiFailure(response) {
  return response.status >= 400 || response.json.code !== 0;
}

async function runtimeSnapshot(token) {
  const [boxResponse, serverListResponse, toolsResponse] = await Promise.all([
    apiJson(backendUrl, "/api/v1/box/status", { token }),
    apiJson(backendUrl, "/api/v1/mcp/servers", { token }),
    apiJson(backendUrl, "/api/v1/tools", { token }),
  ]);
  for (const response of [boxResponse, serverListResponse, toolsResponse]) {
    if (isApiFailure(response)) throw new Error(response.json.msg || `API diagnostic failed with HTTP ${response.status}.`);
  }
  const servers = serverListResponse.json.data?.servers || [];
  const listed = servers.find((server) => server.uuid === serverUuid);
  if (!listed) throw new Error(`MCP server UUID ${serverUuid} is not registered.`);
  const detailResponse = await apiJson(
    backendUrl,
    `/api/v1/mcp/servers/${encodeURIComponent(listed.name)}`,
    { token },
  );
  if (isApiFailure(detailResponse)) {
    throw new Error(detailResponse.json.msg || `MCP detail failed with HTTP ${detailResponse.status}.`);
  }
  const server = detailResponse.json.data?.server || listed;
  const runtime = server.runtime_info || {};
  return {
    box: boxResponse.json.data || {},
    mcp: {
      uuid: server.uuid || listed.uuid,
      name: server.name || listed.name,
      status: runtime.status || null,
      tool_count: runtime.tool_count ?? 0,
      retry_count: runtime.retry_count ?? 0,
      error_message: runtime.error_message || "",
    },
    tools: (toolsResponse.json.data?.tools || [])
      .map((tool) => tool.name || tool.tool_name || tool.function?.name || "")
      .filter(Boolean),
  };
}

function snapshotReady(snapshot) {
  return snapshot.box?.available === true
    && (snapshot.box?.active_sessions ?? 0) >= 1
    && (snapshot.box?.managed_processes ?? 0) >= 1
    && snapshot.mcp?.status === "connected"
    && (snapshot.mcp?.tool_count ?? 0) >= 1
    && snapshot.tools?.includes(expectedTool);
}

function assertReadySnapshot(snapshot, phase) {
  if (!snapshotReady(snapshot)) {
    throw new Error(`${phase} Box/MCP state is not ready: ${JSON.stringify(snapshot)}`);
  }
}

async function boxProcesses() {
  const { stdout } = await execFileAsync("ps", ["-ww", "-eo", "pid=,ppid=,args="]);
  return stdout.split(/\r?\n/).map((line) => {
    const match = line.match(/^\s*(\d+)\s+(\d+)\s+(.*)$/);
    return match ? { pid: Number(match[1]), ppid: Number(match[2]), args: match[3] } : null;
  }).filter((item) => item && BOX_COMMAND_RE.test(item.args));
}

async function selectLocalBoxProcess() {
  const processes = await boxProcesses();
  const configuredPid = Number.parseInt(env.LANGBOT_BOX_RUNTIME_PID || "", 10);
  let candidates = Number.isFinite(configuredPid)
    ? processes.filter((item) => item.pid === configuredPid)
    : processes;
  const repo = resolve(env.LANGBOT_REPO || "..");
  const eligible = [];
  for (const candidate of candidates) {
    const parentArgs = await readFile(`/proc/${candidate.ppid}/cmdline`, "utf8").catch(() => "");
    const parentCwd = await readlink(`/proc/${candidate.ppid}/cwd`).catch(() => "");
    if (/main\.py(?:\0|$)/.test(parentArgs) && resolve(parentCwd) === repo) eligible.push(candidate);
  }
  candidates = eligible;
  if (candidates.length !== 1) {
    throw new Error(`Expected exactly one local Box child for ${repo}, found ${candidates.length}. Set LANGBOT_BOX_RUNTIME_PID only after verifying the process.`);
  }
  return candidates[0];
}

async function runRecoveredDebugChat(value) {
  const script = resolve("scripts/e2e/pipeline-debug-chat.mjs");
  const childEnv = {
    ...env,
    LBS_CASE_ID: `${caseId}-debug-chat`,
    LBS_RUN_ID: paths.runId,
    LBS_EVIDENCE_DIR: debugChatEvidenceDir,
    LANGBOT_E2E_PIPELINE_REQUIRED: "1",
    LANGBOT_E2E_PIPELINE_URL: env.LANGBOT_LOCAL_AGENT_PIPELINE_URL,
    LANGBOT_E2E_PIPELINE_NAME: env.LANGBOT_LOCAL_AGENT_PIPELINE_NAME || "",
    LANGBOT_E2E_RESET_DEBUG_CHAT: "1",
    LANGBOT_E2E_RESPONSE_TIMEOUT_MS: env.LANGBOT_E2E_RESPONSE_TIMEOUT_MS || "60000",
    LANGBOT_E2E_EXPECTED_TOOL: expectedTool,
    LANGBOT_E2E_PROMPT: `Call the ${expectedTool} MCP tool with exactly this text: ${value}. Return only the tool result.`,
    LANGBOT_E2E_EXPECTED_TEXT: value,
    LANGBOT_E2E_EXTENSIONS_PATCH_JSON: JSON.stringify({
      enable_all_plugins: false,
      bound_plugins: [{ author: "langbot-team", name: "LocalAgent" }],
      enable_all_mcp_servers: false,
      bound_mcp_servers: [serverUuid],
      enable_all_skills: false,
      bound_skills: [],
    }),
    LANGBOT_E2E_RESTORE_EXTENSIONS: "1",
  };
  for (const key of ["ALL_PROXY", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]) {
    delete childEnv[key];
  }
  try {
    const { stdout } = await execFileAsync(process.execPath, [script], {
      cwd: resolve("."),
      env: childEnv,
      maxBuffer: 4 * 1024 * 1024,
      timeout: positiveInteger(env.LANGBOT_E2E_RESPONSE_TIMEOUT_MS, 60_000) + 30_000,
    });
    return JSON.parse(stdout.trim());
  } catch (error) {
    const childResultPath = resolve(debugChatEvidenceDir, "automation-result.json");
    const childResult = await readFile(childResultPath, "utf8").then(JSON.parse).catch(() => null);
    if (childResult) return childResult;
    throw error;
  }
}

async function auditRecoveredToolCall(value, createdAfter) {
  const repo = resolve(env.LANGBOT_REPO || "..");
  const python = resolve(repo, ".venv/bin/python");
  const script = resolve(repo, "skills/scripts/e2e/agent-run-ledger-audit.py");
  const args = [
    script,
    "--repo", repo,
    "--output", ledgerAuditPath,
    "--created-after", createdAfter.toISOString(),
    "--expected-tool-name", expectedTool,
    "--expected-parameters-json", JSON.stringify({ text: value }),
    "--expected-result-text", `${expectedTool}:${value}`,
  ];
  try {
    await execFileAsync(python, args, {
      cwd: repo,
      env,
      maxBuffer: 4 * 1024 * 1024,
      timeout: 30_000,
    });
  } catch (error) {
    const report = await readFile(ledgerAuditPath, "utf8").then(JSON.parse).catch(() => null);
    if (report) return report;
    throw error;
  }
  return JSON.parse(await readFile(ledgerAuditPath, "utf8"));
}
