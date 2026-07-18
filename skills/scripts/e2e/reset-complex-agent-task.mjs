#!/usr/bin/env node

import { cp, mkdir, rm } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { env } from "node:process";
import { spawnSync } from "node:child_process";
import {
  ensureEvidence,
  evidencePaths,
  loadEnvFiles,
  writeResult,
} from "./lib/langbot-e2e.mjs";

await loadEnvFiles();
const paths = evidencePaths("reset-complex-agent-task");
await ensureEvidence(paths);

const scriptDir = dirname(fileURLToPath(import.meta.url));
const source = resolve(
  scriptDir,
  "../../skills/langbot-testing/fixtures/complex-agent-task/workspace",
);
const repo = env.LANGBOT_REPO || "";
const target = repo ? resolve(repo, "data/box/default/order-orchestrator") : "";
const result = {
  source: "setup_automation",
  case_id: "reset-complex-agent-task",
  run_id: paths.runId,
  status: "fail",
  reason: "",
  target,
  initial_test_exit_code: null,
  evidence_collected: ["filesystem"],
};

try {
  if (!repo) throw new Error("LANGBOT_REPO is required.");
  await rm(target, { recursive: true, force: true });
  await mkdir(dirname(target), { recursive: true });
  await cp(source, target, { recursive: true });

  const baseline = spawnSync(
    "python3",
    ["-m", "unittest", "discover", "-s", "tests", "-v"],
    { cwd: target, encoding: "utf8", timeout: 60_000 },
  );
  result.initial_test_exit_code = baseline.status;
  result.initial_failure_preview = `${baseline.stdout || ""}\n${baseline.stderr || ""}`.slice(0, 4000);
  if (baseline.error) throw baseline.error;
  if (baseline.status === 0) throw new Error("Complex task baseline unexpectedly passes; the fixture must start failing.");

  result.status = "pass";
  result.reason = "Complex task workspace reset and failing baseline confirmed.";
} catch (error) {
  result.status = /required|ENOENT/.test(error.message) ? "env_issue" : "fail";
  result.reason = error.message;
}

await writeResult(paths, result);
console.log(JSON.stringify(result, null, 2));
process.exit(result.status === "pass" ? 0 : result.status === "env_issue" ? 2 : 1);
