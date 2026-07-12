#!/usr/bin/env node

import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { env } from "node:process";
import {
  ensureEvidence,
  evidencePaths,
  exitCode,
  localIsoWithOffset,
  writeResult,
} from "./lib/langbot-e2e.mjs";

function loadEnvDefaults(path) {
  if (!existsSync(path)) return;
  for (const rawLine of readFileSync(path, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const sep = line.indexOf("=");
    if (sep === -1) continue;
    const key = line.slice(0, sep).trim();
    if (env[key]) continue;
    env[key] = line.slice(sep + 1).trim().replace(/^["']|["']$/g, "");
  }
}

loadEnvDefaults("skills/.env");
loadEnvDefaults("skills/.env.local");

const caseId = env.LBS_CASE_ID || "mcp-stdio-fixture-direct";
const paths = evidencePaths(caseId);
await ensureEvidence(paths);

const startedAt = new Date();
const fixturePath = resolve(env.LANGBOT_MCP_FIXTURE_PATH || "skills/langbot-testing/fixtures/mcp/qa_mcp_echo_server.py");
const langbotRepo = env.LANGBOT_REPO ? resolve(env.LANGBOT_REPO) : "";
const uvCandidates = [
  env.LANGBOT_MCP_FIXTURE_UV,
  "uv",
].filter(Boolean);
const uv = uvCandidates.find((candidate) => candidate === "uv" || existsSync(candidate));
const pythonCandidates = [
  env.LANGBOT_MCP_FIXTURE_PYTHON,
  langbotRepo ? `${langbotRepo}/.venv/bin/python` : "",
  "python3",
].filter(Boolean);
const python = pythonCandidates.find((candidate) => candidate === "python3" || existsSync(candidate));
const command = langbotRepo && uv
  ? { executable: uv, args: ["run", "python", fixturePath], cwd: langbotRepo, mode: "uv" }
  : python
    ? { executable: python, args: [fixturePath], cwd: resolve("."), mode: "python" }
    : null;
const expectedText = "qa_mcp_echo:mcp-stdio-fixture-ok";

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
  fixture_path: fixturePath,
  command,
  expected_text: expectedText,
  evidence: {
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
};

function parseJsonLines(buffer) {
  return buffer
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch {
        return null;
      }
    })
    .filter(Boolean);
}

async function request(child, id, method, params) {
  child.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", id, method, params })}\n`);
}

async function run() {
  if (!command) {
    result.status = "env_issue";
    result.reason = "No uv or Python interpreter found. Set LANGBOT_REPO, LANGBOT_MCP_FIXTURE_UV, or LANGBOT_MCP_FIXTURE_PYTHON.";
    return;
  }
  if (!existsSync(fixturePath)) {
    result.status = "env_issue";
    result.reason = `MCP fixture not found: ${fixturePath}`;
    return;
  }

  const child = spawn(command.executable, command.args, {
    cwd: command.cwd,
    stdio: ["pipe", "pipe", "pipe"],
  });
  let stdout = "";
  let stderr = "";
  child.stdout.setEncoding("utf8");
  child.stderr.setEncoding("utf8");
  child.stdout.on("data", (chunk) => {
    stdout += chunk;
  });
  child.stderr.on("data", (chunk) => {
    stderr += chunk;
  });

  const timeout = setTimeout(() => child.kill("SIGTERM"), 10_000);
  try {
    await new Promise((resolveReady) => setTimeout(resolveReady, 100));
    await request(child, 1, "initialize", {
      protocolVersion: "2024-11-05",
      capabilities: {},
      clientInfo: { name: "langbot-skills", version: "0" },
    });
    await new Promise((resolveReady) => setTimeout(resolveReady, 200));
    child.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized", params: {} })}\n`);
    await request(child, 2, "tools/list", {});
    await request(child, 3, "tools/call", {
      name: "qa_mcp_echo",
      arguments: { text: "mcp-stdio-fixture-ok" },
    });
    await new Promise((resolveDone) => setTimeout(resolveDone, 1500));
  } finally {
    clearTimeout(timeout);
    child.kill("SIGTERM");
  }

  const messages = parseJsonLines(stdout);
  if (/No module named ['"]mcp['"]|ModuleNotFoundError/i.test(stderr)) {
    result.status = "env_issue";
    result.reason = `Python environment cannot import mcp. Set LANGBOT_MCP_FIXTURE_PYTHON to a LangBot venv Python. stderr=${stderr.trim()}`;
    return;
  }
  const listResult = messages.find((message) => message.id === 2)?.result;
  const callResult = messages.find((message) => message.id === 3)?.result;
  const toolNames = Array.isArray(listResult?.tools)
    ? listResult.tools.map((tool) => tool.name)
    : [];
  const callText = Array.isArray(callResult?.content)
    ? callResult.content.map((item) => item.text || "").join("\n")
    : "";

  if (!toolNames.includes("qa_mcp_echo")) {
    result.status = "fail";
    result.reason = `MCP fixture did not list qa_mcp_echo. stderr=${stderr.trim()}`;
    return;
  }
  if (!callText.includes(expectedText)) {
    result.status = "fail";
    result.reason = `MCP fixture call did not return ${expectedText}. stderr=${stderr.trim()}`;
    return;
  }

  result.status = "pass";
  result.reason = "MCP stdio fixture listed qa_mcp_echo and returned the deterministic tool result without a model provider.";
}

try {
  await run();
} catch (error) {
  result.status = "fail";
  result.reason = error instanceof Error ? error.message : String(error);
} finally {
  const finishedAt = new Date();
  result.finished_at = finishedAt.toISOString();
  result.finished_at_local = localIsoWithOffset(finishedAt);
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(exitCode(result.status));
