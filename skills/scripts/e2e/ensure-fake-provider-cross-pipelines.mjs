#!/usr/bin/env node

import { spawn } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { env } from "node:process";
import {
  appendLine,
  ensureEvidence,
  evidencePaths,
  loadEnvFiles,
  redact,
  writeResult,
} from "./lib/langbot-e2e.mjs";

const caseId = "ensure-fake-provider-cross-pipelines";
const DEFAULT_PIPELINE_A_NAME = "LangBot QA Fake Provider Debug Chat A";
const DEFAULT_PIPELINE_B_NAME = "LangBot QA Fake Provider Debug Chat B";

await loadEnvFiles();
const paths = evidencePaths(caseId);
await ensureEvidence(paths);

const writeEnv = process.argv.includes("--write-env");
const envLocalPath = resolve("skills/.env.local");
const pipelineAName = env.LANGBOT_FAKE_PROVIDER_PIPELINE_A_NAME || DEFAULT_PIPELINE_A_NAME;
const pipelineBName = env.LANGBOT_FAKE_PROVIDER_PIPELINE_B_NAME || DEFAULT_PIPELINE_B_NAME;

const result = {
  source: "setup_automation",
  case_id: caseId,
  run_id: paths.runId,
  status: "fail",
  reason: "",
  pipeline_a: {
    name: pipelineAName,
    id: "",
    url: "",
  },
  pipeline_b: {
    name: pipelineBName,
    id: "",
    url: "",
  },
  fake_provider: {
    url: "",
    base_url: "",
    pid: null,
  },
  wrote_env: false,
  evidence: {
    console_log: paths.consoleLog,
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["api_diagnostic", "filesystem"],
};

try {
  console.error(`[langbot-qa] configuring cross-pipeline QA fixtures: pipeline_a=\"${pipelineAName}\", pipeline_b=\"${pipelineBName}\"`);
  console.error("[langbot-qa] run these fake-provider setup/probe commands serially when they share LANGBOT_FAKE_PROVIDER_URL.");
  if (pipelineAName === pipelineBName) {
    throw new Error("LANGBOT_FAKE_PROVIDER_PIPELINE_A_NAME and LANGBOT_FAKE_PROVIDER_PIPELINE_B_NAME must be different.");
  }

  const setupA = await runPipelineSetup(pipelineAName, "A");
  const setupB = await runPipelineSetup(pipelineBName, "B");
  result.pipeline_a = {
    name: setupA.pipeline_name || pipelineAName,
    id: setupA.pipeline_id || "",
    url: setupA.pipeline_url || "",
  };
  result.pipeline_b = {
    name: setupB.pipeline_name || pipelineBName,
    id: setupB.pipeline_id || "",
    url: setupB.pipeline_url || "",
  };
  result.fake_provider = {
    url: setupB.fake_provider?.url || setupA.fake_provider?.url || "",
    base_url: setupB.fake_provider?.base_url || setupA.fake_provider?.base_url || "",
    pid: setupB.fake_provider?.pid ?? setupA.fake_provider?.pid ?? null,
  };

  if (!result.pipeline_a.url || !result.pipeline_b.url || !result.fake_provider.url) {
    throw new Error("Cross-pipeline fake provider setup did not return both pipeline URLs and provider URL.");
  }

  if (writeEnv) {
    await upsertEnvLocal(envLocalPath, {
      LANGBOT_FAKE_PROVIDER_URL: result.fake_provider.url,
      LANGBOT_FAKE_PROVIDER_BASE_URL: result.fake_provider.base_url,
      LANGBOT_FAKE_PROVIDER_PID: result.fake_provider.pid ? String(result.fake_provider.pid) : "",
      LANGBOT_FAKE_PROVIDER_PIPELINE_A_URL: result.pipeline_a.url,
      LANGBOT_FAKE_PROVIDER_PIPELINE_A_NAME: result.pipeline_a.name,
      LANGBOT_FAKE_PROVIDER_PIPELINE_B_URL: result.pipeline_b.url,
      LANGBOT_FAKE_PROVIDER_PIPELINE_B_NAME: result.pipeline_b.name,
    });
    result.wrote_env = true;
  }

  result.status = "pass";
  result.reason = "Fake provider cross-pipeline fixtures are configured.";
} catch (error) {
  result.status = looksLikeEnvIssue(error) ? "env_issue" : "fail";
  result.reason = safeReason(error.message);
} finally {
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(result.status === "pass" ? 0 : result.status === "env_issue" ? 2 : 1);

function runPipelineSetup(pipelineName, label) {
  return new Promise((resolvePromise, rejectPromise) => {
    const child = spawn(process.execPath, ["scripts/e2e/ensure-fake-provider-pipeline.mjs"], {
      cwd: resolve("."),
      env: {
        ...env,
        LANGBOT_FAKE_PROVIDER_PIPELINE_NAME: pipelineName,
        LANGBOT_FAKE_PROVIDER_FIRST_TOKEN_DELAY_MS: env.LANGBOT_FAKE_PROVIDER_FIRST_TOKEN_DELAY_MS || "25",
        LANGBOT_FAKE_PROVIDER_CHUNK_DELAY_MS: env.LANGBOT_FAKE_PROVIDER_CHUNK_DELAY_MS || "10",
        LANGBOT_FAKE_PROVIDER_CHUNK_COUNT: env.LANGBOT_FAKE_PROVIDER_CHUNK_COUNT || "0",
        LANGBOT_FAKE_PROVIDER_FAIL_FIRST_N: "0",
        LANGBOT_FAKE_PROVIDER_FAIL_EVERY_N: "0",
        LANGBOT_FAKE_PROVIDER_FAULT_STATUS: env.LANGBOT_FAKE_PROVIDER_FAULT_STATUS || "500",
        LANGBOT_FAKE_PROVIDER_FAIL_AFTER_FIRST_CHUNK: "false",
        LANGBOT_FAKE_PROVIDER_DYNAMIC_RESPONSE: "true",
      },
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      const text = chunk.toString();
      stdout += text;
      appendLine(paths.consoleLog, `[setup ${label} stdout] ${text.trimEnd()}`).catch(() => {});
    });
    child.stderr.on("data", (chunk) => {
      const text = chunk.toString();
      stderr += text;
      appendLine(paths.consoleLog, `[setup ${label} stderr] ${text.trimEnd()}`).catch(() => {});
    });
    child.on("error", rejectPromise);
    child.on("close", (code) => {
      const parsed = parseJsonOutput(stdout);
      if (code !== 0 || parsed.status !== "pass") {
        rejectPromise(new Error(parsed.reason || stderr || `Fake provider pipeline setup ${label} exited with ${code}.`));
        return;
      }
      resolvePromise(parsed);
    });
  });
}

function parseJsonOutput(text) {
  const trimmed = String(text || "").trim();
  if (!trimmed) return {};
  try {
    return JSON.parse(trimmed);
  } catch {
    const start = trimmed.indexOf("{");
    const end = trimmed.lastIndexOf("}");
    if (start >= 0 && end > start) {
      try {
        return JSON.parse(trimmed.slice(start, end + 1));
      } catch {
        return {};
      }
    }
    return {};
  }
}

async function upsertEnvLocal(path, updates) {
  await mkdir(dirname(path), { recursive: true });
  let text = "";
  try {
    text = await readFile(path, "utf8");
  } catch {
    text = "";
  }
  const lines = text.split(/\r?\n/);
  const seen = new Set();
  const next = lines.map((line) => {
    const trimmed = line.trim();
    const match = trimmed.match(/^([A-Z][A-Z0-9_]*)=/);
    if (!match || updates[match[1]] === undefined) return line;
    seen.add(match[1]);
    return `${match[1]}=${updates[match[1]]}`;
  });
  for (const [key, value] of Object.entries(updates)) {
    if (!seen.has(key)) next.push(`${key}=${value}`);
  }
  await writeFile(path, `${next.join("\n").replace(/\n+$/, "")}\n`, "utf8");
}

function looksLikeEnvIssue(error) {
  const message = String(error?.message || error || "");
  return /fetch failed|ECONNREFUSED|ENOTFOUND|LANGBOT_.*not configured|Could not read recovery_key|Backend did not respond/i.test(message);
}

function safeReason(value) {
  return redact(String(value || "")).slice(0, 1000);
}
