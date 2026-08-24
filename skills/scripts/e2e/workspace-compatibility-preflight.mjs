#!/usr/bin/env node

import { spawn } from "node:child_process";
import { access, readFile, writeFile } from "node:fs/promises";
import { delimiter, dirname, join, resolve } from "node:path";
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
const caseId = env.LBS_CASE_ID || "workspace-compatibility-preflight";
const paths = evidencePaths(caseId);
await ensureEvidence(paths);
const startedAt = new Date();
const detailsPath = join(paths.evidenceDir, "workspace-preflight.json");

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
  checks: [],
  warnings: [],
  evidence: {
    workspace_preflight_json: detailsPath,
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["filesystem", "api_diagnostic"],
};

const repositories = [
  { id: "langbot", directory: "LangBot", envKey: "LANGBOT_REPO", manifest: false },
  { id: "plugin-sdk", directory: "langbot-plugin-sdk", envKey: "LANGBOT_PLUGIN_SDK_REPO", manifest: false },
  { id: "agent-runner", directory: "langbot-agent-runner", envKey: "LANGBOT_AGENT_RUNNER_REPO", manifest: false },
  { id: "local-agent", directory: "langbot-local-agent", envKey: "LANGBOT_LOCAL_AGENT_REPO", identity: "langbot-team/LocalAgent" },
  { id: "control-plane", directory: "langbot-agent-control-plane", envKey: "LANGBOT_AGENT_CONTROL_PLANE_REPO", identity: "langbot/agent-control-plane" },
  { id: "longterm-memory", directory: "langbot-longterm-memory", envKey: "LANGBOT_LONGTERM_MEMORY_REPO", identity: "langbot-team/LongTermMemory" },
  { id: "parser", directory: "langbot-parser", envKey: "LANGBOT_PARSER_PLUGIN_REPO", identity: "langbot-team/GeneralParsers" },
  { id: "rag", directory: "langbot-rag", envKey: "LANGBOT_RAG_PLUGIN_REPO", identity: "langbot-team/LangRAG" },
  { id: "skill-authoring", directory: "langbot-skill-authoring", envKey: "LANGBOT_SKILL_AUTHORING_REPO", identity: "huanghuoguoguo/skill-authoring" },
];

function run(command, args, options = {}) {
  return new Promise((resolvePromise) => {
    const child = spawn(command, args, { ...options, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => { stdout += chunk; });
    child.stderr.on("data", (chunk) => { stderr += chunk; });
    child.on("error", (error) => resolvePromise({ status: null, stdout, stderr, error }));
    child.on("close", (status) => resolvePromise({ status, stdout, stderr, error: null }));
  });
}

function addCheck(name, status, detail = {}) {
  result.checks.push({ name, status, ...detail });
}

try {
  const langbotRepo = await resolveLangBotRepo();
  const workspaceRoot = resolve(env.LANGBOT_WORKSPACE_ROOT || dirname(langbotRepo));
  const resolved = {};

  for (const repository of repositories) {
    const path = resolve(env[repository.envKey] || (repository.id === "langbot" ? langbotRepo : join(workspaceRoot, repository.directory)));
    resolved[repository.id] = path;
    try {
      await access(join(path, ".git"));
    } catch {
      addCheck(`repo:${repository.id}`, "fail", { path, reason: "Git checkout is missing." });
      continue;
    }

    const branch = await run("git", ["branch", "--show-current"], { cwd: path });
    const branchName = branch.stdout.trim();
    const compatible = branch.status === 0 && /^(?:main|dev\/4\.11\.x)$/.test(branchName);
    addCheck(`repo:${repository.id}`, compatible ? "pass" : "fail", {
      path,
      branch: branchName,
      reason: compatible ? "" : "Expected main or dev/4.11.x compatibility branch.",
    });

    const dirty = await run("git", ["status", "--short"], { cwd: path });
    if (dirty.stdout.trim()) {
      result.warnings.push({ name: `dirty:${repository.id}`, path, entries: dirty.stdout.trim().split(/\r?\n/).length });
    }

    if (repository.identity) {
      const manifestPath = join(path, "manifest.yaml");
      try {
        const manifest = await readFile(manifestPath, "utf8");
        const author = manifest.match(/^\s{2}author:\s*([^\s#]+)/m)?.[1] || "";
        const name = manifest.match(/^\s{2}name:\s*([^\s#]+)/m)?.[1] || "";
        const identity = `${author}/${name}`;
        addCheck(`manifest:${repository.id}`, identity === repository.identity ? "pass" : "fail", {
          path: manifestPath,
          identity,
          expected_identity: repository.identity,
        });
      } catch (error) {
        addCheck(`manifest:${repository.id}`, "fail", { path: manifestPath, reason: error.message });
      }
    }
  }

  const python = join(resolved.langbot, ".venv", "bin", "python");
  try {
    await access(python);
    addCheck("langbot-venv", "pass", { python });
  } catch {
    addCheck("langbot-venv", "fail", { python, reason: "LangBot virtualenv Python is missing." });
  }

  const sdkSrc = join(resolved["plugin-sdk"], "src");
  const importProbe = await run(python, ["-c", [
    "import json, pathlib, langbot_plugin",
    "from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput",
    "from langbot_plugin.api.entities.builtin.agent_runner.result import AgentRunResult",
    "print(json.dumps({'path': str(pathlib.Path(langbot_plugin.__file__).resolve()), 'entities': [AgentInput.__name__, AgentRunResult.__name__]}))",
  ].join("; ")], {
    cwd: resolved.langbot,
    env: { ...env, PYTHONPATH: [sdkSrc, env.PYTHONPATH].filter(Boolean).join(delimiter) },
  });
  let importDetail = {};
  try { importDetail = JSON.parse(importProbe.stdout.trim()); } catch { importDetail = { stderr: importProbe.stderr.trim() }; }
  const localSdkLoaded = importProbe.status === 0 && resolve(importDetail.path || "").startsWith(resolve(sdkSrc));
  addCheck("local-sdk-import", localSdkLoaded ? "pass" : "fail", {
    expected_root: resolve(sdkSrc),
    ...importDetail,
    reason: localSdkLoaded ? "" : "langbot_plugin did not load from the workspace SDK source tree.",
  });

  const failures = result.checks.filter((check) => check.status === "fail");
  result.status = failures.length === 0 ? "pass" : "fail";
  result.reason = failures.length === 0
    ? `Workspace compatibility preflight passed with ${result.warnings.length} non-blocking dirty-worktree warning(s).`
    : `Workspace compatibility preflight found ${failures.length} blocking check(s).`;
} catch (error) {
  result.status = /missing|ENOENT|not found/i.test(error.message) ? "env_issue" : "fail";
  result.reason = error.message;
} finally {
  const finishedAt = new Date();
  result.finished_at = finishedAt.toISOString();
  result.finished_at_local = localIsoWithOffset(finishedAt);
  await writeFile(detailsPath, `${JSON.stringify({ checks: result.checks, warnings: result.warnings }, null, 2)}\n`, "utf8");
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(exitCode(result.status));
