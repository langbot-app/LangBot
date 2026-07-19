#!/usr/bin/env node

import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { env } from "node:process";
import {
  ensureEvidence,
  evidencePaths,
  exitCode,
  loadEnvFiles,
  localIsoWithOffset,
  resolveLangBotRepo,
  writeResult,
} from "./lib/langbot-e2e.mjs";

await loadEnvFiles();
const caseId = env.LBS_CASE_ID || "agent-run-ledger-audit";
const paths = evidencePaths(caseId);
await ensureEvidence(paths);
const startedAt = new Date();
const auditPath = join(paths.evidenceDir, "ledger-audit.json");
const result = {
  source: "automation",
  case_id: caseId,
  run_id: paths.runId,
  started_at: startedAt.toISOString(),
  started_at_local: localIsoWithOffset(startedAt),
  finished_at: "",
  finished_at_local: "",
  status: "fail",
  reason: "",
  audited_run: null,
  metrics_summary: null,
  failures: [],
  warnings: [],
  evidence: {
    ledger_audit_json: auditPath,
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["filesystem", "metrics", "api_diagnostic"],
};

function run(command, args, cwd) {
  return new Promise((resolvePromise) => {
    const child = spawn(command, args, { cwd, env, stdio: ["ignore", "pipe", "pipe"] });
    let stderr = "";
    child.stderr.on("data", (chunk) => { stderr += chunk; });
    child.on("error", (error) => resolvePromise({ status: null, stderr, error }));
    child.on("close", (status) => resolvePromise({ status, stderr, error: null }));
  });
}

try {
  const repo = await resolveLangBotRepo();
  const python = join(repo, ".venv", "bin", "python");
  const args = ["scripts/e2e/agent-run-ledger-audit.py", "--repo", repo, "--output", auditPath];
  if (env.LANGBOT_AGENT_RUN_ID) args.push("--run-id", env.LANGBOT_AGENT_RUN_ID);
  const execution = await run(python, args, process.cwd());
  const report = JSON.parse(await readFile(auditPath, "utf8"));
  result.status = report.status;
  result.reason = report.reason;
  result.audited_run = report.run || null;
  result.metrics_summary = report.metrics || null;
  result.failures = report.failures || [];
  result.warnings = report.warnings || [];
  if (execution.error && result.status === "pass") {
    result.status = "env_issue";
    result.reason = execution.error.message;
  }
} catch (error) {
  result.status = /ENOENT|not found|No matching/i.test(error.message) ? "env_issue" : "fail";
  result.reason = error.message;
} finally {
  const finishedAt = new Date();
  result.finished_at = finishedAt.toISOString();
  result.finished_at_local = localIsoWithOffset(finishedAt);
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(exitCode(result.status));
