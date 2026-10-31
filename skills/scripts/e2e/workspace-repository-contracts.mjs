#!/usr/bin/env node

import { spawn } from "node:child_process";
import { access, mkdir, writeFile } from "node:fs/promises";
import { basename, delimiter, dirname, join, resolve } from "node:path";
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
const caseId = env.LBS_CASE_ID || "workspace-repository-contracts";
const paths = evidencePaths(caseId);
await ensureEvidence(paths);
const startedAt = new Date();
const logsDir = join(paths.evidenceDir, "repository-contracts");
await mkdir(logsDir, { recursive: true });

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
  repositories: [],
  evidence: {
    contracts_dir: logsDir,
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["filesystem", "metrics"],
};

function run(command, args, { cwd, processEnv, timeoutMs = 900_000 }) {
  return new Promise((resolvePromise) => {
    const started = Date.now();
    const child = spawn(command, args, { cwd, env: processEnv, stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill("SIGTERM");
    }, timeoutMs);
    child.stdout.on("data", (chunk) => { stdout += chunk; });
    child.stderr.on("data", (chunk) => { stderr += chunk; });
    child.on("error", (error) => {
      clearTimeout(timer);
      resolvePromise({ status: null, stdout, stderr, error, timedOut, durationMs: Date.now() - started });
    });
    child.on("close", (status) => {
      clearTimeout(timer);
      resolvePromise({ status, stdout, stderr, error: null, timedOut, durationMs: Date.now() - started });
    });
  });
}

try {
  const langbotRepo = await resolveLangBotRepo();
  const workspaceRoot = resolve(env.LANGBOT_WORKSPACE_ROOT || dirname(langbotRepo));
  const sdkRepo = resolve(env.LANGBOT_PLUGIN_SDK_REPO || join(workspaceRoot, "langbot-plugin-sdk"));
  const python = join(langbotRepo, ".venv", "bin", "python");
  await access(python);
  await access(join(sdkRepo, "src", "langbot_plugin"));
  const processEnv = {
    ...env,
    PYTHONPATH: [join(sdkRepo, "src"), env.PYTHONPATH].filter(Boolean).join(delimiter),
  };
  const specs = [
    ["agent-runner", "langbot-agent-runner", ["-m", "pytest", "tests", "-q"]],
    ["control-plane", "langbot-agent-control-plane", ["-m", "pytest", "tests", "-q"]],
    ["longterm-memory", "langbot-longterm-memory", ["-m", "pytest", "tests", "-q"]],
    ["parser", "langbot-parser", ["-m", "pytest", "tests", "-q"]],
    ["rag", "langbot-rag", ["-m", "pytest", "tests", "-q"]],
    ["skill-authoring", "langbot-skill-authoring", ["-m", "pytest", "tests", "-q"]],
    ["local-agent", "langbot-local-agent", ["-m", "pytest", "tests", "-q"]],
    ["langbot-agent-provider", "LangBot", ["-m", "pytest", "tests/unit_tests/agent", "tests/unit_tests/provider", "-q"]],
    ["skills-cli", "LangBot/skills", ["--test", "test/lbs-cli.test.ts"]],
    ["plugin-sdk-runtime", "langbot-plugin-sdk", ["-m", "pytest", "tests", "-q", "--ignore=tests/packaging/test_installed_cli_blackbox.py"]],
    ["plugin-sdk-packaging", "langbot-plugin-sdk", ["-m", "pytest", "tests/packaging/test_installed_cli_blackbox.py", "-q"]],
  ];

  for (const [id, directory, args] of specs) {
    const cwd = resolve(workspaceRoot, directory);
    const command = id === "skills-cli" ? env.LANGBOT_NODE || "node" : python;
    const execution = await run(command, args, { cwd, processEnv });
    const stdoutPath = join(logsDir, `${id}.stdout.log`);
    const stderrPath = join(logsDir, `${id}.stderr.log`);
    await writeFile(stdoutPath, execution.stdout, "utf8");
    await writeFile(stderrPath, execution.stderr, "utf8");
    const combined = `${execution.stdout}\n${execution.stderr}`;
    const packagingNetworkIssue = id === "plugin-sdk-packaging"
      && execution.status !== 0
      && /hatchling|PyPI|TLS|SSL|network|timed out|Temporary failure|connection|EOF/i.test(combined);
    const status = execution.status === 0 ? "pass" : packagingNetworkIssue ? "env_issue" : "fail";
    result.repositories.push({
      id,
      repository: basename(cwd),
      status,
      exit_status: execution.status,
      timed_out: execution.timedOut,
      duration_ms: execution.durationMs,
      stdout_log: stdoutPath,
      stderr_log: stderrPath,
      reason: execution.error?.message || (execution.timedOut ? "Test command timed out." : packagingNetworkIssue ? "Packaging blackbox could not fetch its isolated build dependency." : ""),
    });
  }

  const productFailures = result.repositories.filter((item) => item.status === "fail");
  const envIssues = result.repositories.filter((item) => item.status === "env_issue");
  result.status = productFailures.length === 0 ? "pass" : "fail";
  result.reason = productFailures.length === 0
    ? `All repository product contracts passed; ${envIssues.length} packaging environment issue(s) were classified separately.`
    : `${productFailures.length} repository product contract group(s) failed.`;
} catch (error) {
  result.status = "env_issue";
  result.reason = error.message;
} finally {
  const finishedAt = new Date();
  result.finished_at = finishedAt.toISOString();
  result.finished_at_local = localIsoWithOffset(finishedAt);
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(exitCode(result.status));
