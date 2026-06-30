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

const scenarios = [
  {
    id: "provider-timeout",
    target: "provider",
    injected_fault: "fake provider request exceeds the configured timeout",
    expected_status: "env_issue",
    recovery_check: "provider route is reachable or the case remains outside product pass/fail",
    cleanup: "stop fake provider or reset proxy route",
  },
  {
    id: "plugin-runtime-disconnect",
    target: "plugin-runtime",
    injected_fault: "runtime control channel disconnects during an action",
    expected_status: "fail",
    recovery_check: "runtime reconnects and a deterministic plugin action succeeds",
    cleanup: "restart the local plugin runtime process",
  },
  {
    id: "mcp-stdio-server-exit",
    target: "mcp",
    injected_fault: "stdio server exits mid-call",
    expected_status: "fail",
    recovery_check: "server can be registered again and exposes the expected tool",
    cleanup: "remove temporary MCP server registration",
  },
  {
    id: "operator-missing-login",
    target: "webui",
    injected_fault: "browser profile is not authenticated",
    expected_status: "blocked",
    recovery_check: "authenticated profile can open the same WebUI origin",
    cleanup: "no product cleanup; refresh local login state",
  },
  {
    id: "transient-marketplace-timeout",
    target: "marketplace",
    injected_fault: "marketplace request times out once and then succeeds",
    expected_status: "flaky",
    recovery_check: "rerun passes with the same product revision and no code change",
    cleanup: "clear retry-only evidence and keep the run classified as flaky",
  },
];

function validateScenario(scenario) {
  const missing = ["id", "target", "injected_fault", "expected_status", "recovery_check", "cleanup"]
    .filter((key) => !scenario[key]);
  const allowedStatuses = new Set(["pass", "fail", "blocked", "env_issue", "flaky"]);
  return {
    id: scenario.id,
    pass: missing.length === 0 && allowedStatuses.has(scenario.expected_status),
    missing,
    expected_status: scenario.expected_status,
  };
}

async function main() {
  const root = resolve(env.LBS_ROOT || process.cwd());
  const caseId = "langbot-fault-taxonomy-contract";
  const runId = env.LBS_RUN_ID || `${timestampSlug()}-${caseId}`;
  const evidenceDir = resolve(env.LBS_EVIDENCE_DIR || join(root, "reports", "evidence", runId));
  await mkdir(evidenceDir, { recursive: true });

  const startedAt = new Date();
  const validations = scenarios.map(validateScenario);
  const statusCounts = {};
  for (const scenario of scenarios) {
    statusCounts[scenario.expected_status] = (statusCounts[scenario.expected_status] || 0) + 1;
  }
  const metrics = {
    probe: caseId,
    scenario_count: scenarios.length,
    status_counts: statusCounts,
    scenarios,
    validations,
  };
  const thresholds = {
    scenario_count: { actual: scenarios.length, min: 5, pass: scenarios.length >= 5 },
    invalid_scenario_count: {
      actual: validations.filter((item) => !item.pass).length,
      max: 0,
      pass: validations.every((item) => item.pass),
    },
    cleanup_declared_count: {
      actual: scenarios.filter((item) => item.cleanup).length,
      min: scenarios.length,
      pass: scenarios.every((item) => item.cleanup),
    },
  };
  const status = Object.values(thresholds).every((item) => item.pass) ? "pass" : "fail";
  const metricsPath = join(evidenceDir, "metrics.json");
  const faultModelPath = join(evidenceDir, "fault-model.json");
  const automationResultPath = join(evidenceDir, "automation-result.json");
  const resultPath = join(evidenceDir, "result.json");

  await writeFile(metricsPath, `${JSON.stringify(metrics, null, 2)}\n`, "utf8");
  await writeFile(faultModelPath, `${JSON.stringify({ scenarios }, null, 2)}\n`, "utf8");

  const finishedAt = new Date();
  const result = {
    source: "automation",
    case_id: caseId,
    run_id: runId,
    status,
    reason: status === "pass"
      ? "Fault taxonomy contract declares status, recovery, and cleanup for every scenario."
      : "Fault taxonomy contract is missing required scenario fields.",
    started_at: startedAt.toISOString(),
    started_at_local: localIsoWithOffset(startedAt),
    finished_at: finishedAt.toISOString(),
    finished_at_local: localIsoWithOffset(finishedAt),
    duration_ms: finishedAt.getTime() - startedAt.getTime(),
    metrics_summary: {
      scenario_count: metrics.scenario_count,
      status_counts: metrics.status_counts,
      invalid_scenario_count: thresholds.invalid_scenario_count.actual,
    },
    thresholds_summary: thresholds,
    artifacts: {
      metrics_json: metricsPath,
      fault_model_json: faultModelPath,
      automation_result_json: automationResultPath,
      result_json: resultPath,
    },
    evidence_collected: ["metrics", "filesystem"],
  };

  const resultText = `${JSON.stringify(result, null, 2)}\n`;
  await writeFile(automationResultPath, resultText, "utf8");
  await writeFile(resultPath, resultText, "utf8");
  console.log(JSON.stringify(result, null, 2));
  exit(status === "pass" ? 0 : 1);
}

await main();
