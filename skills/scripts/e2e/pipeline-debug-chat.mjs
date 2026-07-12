#!/usr/bin/env node

import { spawn } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { env } from "node:process";
import {
  openPipelineDebugChat,
  runDebugChatPrompt,
  setDebugChatStreamOutput,
} from "./lib/debug-chat.mjs";
import {
  createBrowser,
  ensureAuthenticatedBrowser,
  ensureEvidence,
  evidencePaths,
  exitCode,
  localIsoWithOffset,
  pathExists,
  safeScreenshot,
  scanBrowserDiagnostics,
  writeResult,
} from "./lib/langbot-e2e.mjs";

const caseId = env.LBS_CASE_ID || "pipeline-debug-chat";
const paths = evidencePaths(caseId);
await ensureEvidence(paths);

const expectedText = env.LANGBOT_E2E_EXPECTED_TEXT || "OK";
const prompt = env.LANGBOT_E2E_PROMPT || `请只回复 ${expectedText}，用于前端调试测试。`;
const responseTimeoutMs = Number.parseInt(env.LANGBOT_E2E_RESPONSE_TIMEOUT_MS || "120000", 10);
const safeResponseTimeoutMs = Number.isFinite(responseTimeoutMs) && responseTimeoutMs > 0 ? responseTimeoutMs : 120000;
const streamOutput = /^(0|false)$/i.test(env.LANGBOT_E2E_STREAM_OUTPUT || "")
  ? false
  : /^(1|true)$/i.test(env.LANGBOT_E2E_STREAM_OUTPUT || "")
    ? true
    : null;
const failureSignals = (env.LANGBOT_E2E_FAILURE_SIGNALS || "")
  .split(/\r?\n/)
  .map((item) => item.trim())
  .filter(Boolean);
const imageBase64Path = env.LANGBOT_E2E_IMAGE_BASE64_PATH || "";
const imagePathEnv = env.LANGBOT_E2E_IMAGE_PATH || "";
const backendUrl = env.LANGBOT_BACKEND_URL || "";
const pipelineRequired = env.LANGBOT_E2E_PIPELINE_REQUIRED === "1";
const pipelineUrl = pipelineRequired
  ? env.LANGBOT_E2E_PIPELINE_URL
  : (env.LANGBOT_E2E_PIPELINE_URL || env.LANGBOT_PIPELINE_URL);
const pipelineName = pipelineRequired
  ? env.LANGBOT_E2E_PIPELINE_NAME
  : (env.LANGBOT_E2E_PIPELINE_NAME || env.LANGBOT_PIPELINE_NAME);
const expectedRunnerId = env.LANGBOT_E2E_EXPECTED_RUNNER_ID || "";
const resetDebugChat = boolFromEnv(env.LANGBOT_E2E_RESET_DEBUG_CHAT, false);
const restoreRunnerConfig = boolFromEnv(env.LANGBOT_E2E_RESTORE_RUNNER_CONFIG, true);
const restoreExtensions = boolFromEnv(env.LANGBOT_E2E_RESTORE_EXTENSIONS, true);
const debugChatSessionType = env.LANGBOT_E2E_DEBUG_CHAT_SESSION_TYPE || "person";
const pipelineConfigDiagnosticPath = resolve(paths.evidenceDir, "pipeline-config-diagnostic.json");
const pipelineExtensionsDiagnosticPath = resolve(paths.evidenceDir, "pipeline-extensions-diagnostic.json");
const debugChatResetDiagnosticPath = resolve(paths.evidenceDir, "debug-chat-reset-diagnostic.json");
const pipelineConfigRestoreDiagnosticPath = resolve(paths.evidenceDir, "pipeline-config-restore-diagnostic.json");
const pipelineExtensionsRestoreDiagnosticPath = resolve(paths.evidenceDir, "pipeline-extensions-restore-diagnostic.json");
const metricsPath = resolve(paths.evidenceDir, "metrics.json");
const startedAt = new Date();

let browser;
let restoreConfigPlan = null;
let restoreExtensionsPlan = null;
let result = {
  source: "automation",
  case_id: caseId,
  run_id: paths.runId,
  started_at: startedAt.toISOString(),
  started_at_local: localIsoWithOffset(startedAt),
  finished_at: "",
  finished_at_local: "",
  status: "fail",
  reason: "",
  url: "",
  prompt,
  expected_text: expectedText,
  response_timeout_ms: safeResponseTimeoutMs,
  stream_output: streamOutput,
  image_fixture: imageBase64Path || imagePathEnv,
  prompt_count: 1,
  chat_results: [],
  evidence: {
    console_log: paths.consoleLog,
    network_log: paths.networkLog,
    screenshot: paths.screenshot,
    metrics_json: metricsPath,
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["ui", "screenshot", "console", "network", "metrics"],
};

function boolFromEnv(value, defaultValue) {
  if (value === undefined || value === "") return defaultValue;
  if (/^(0|false|no|off)$/i.test(value)) return false;
  if (/^(1|true|yes|on)$/i.test(value)) return true;
  return defaultValue;
}

function parseJsonEnv(key, fallback) {
  const raw = env[key];
  if (!raw) return fallback;
  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new Error(`${key} must be valid JSON: ${error.message}`);
  }
}

function positiveNumberEnv(key, fallback) {
  const raw = env[key];
  if (raw === undefined || raw === "") return fallback;
  const value = Number(raw);
  return Number.isFinite(value) && value >= 0 ? value : fallback;
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

function promptStepsFromEnv() {
  const rawSteps = parseJsonEnv("LANGBOT_E2E_PROMPTS_JSON", null);
  if (rawSteps === null) {
    return [{ prompt, expectedText, responseTimeoutMs: safeResponseTimeoutMs }];
  }
  if (!Array.isArray(rawSteps) || rawSteps.length === 0) {
    throw new Error("LANGBOT_E2E_PROMPTS_JSON must be a non-empty JSON array.");
  }
  return rawSteps.map((item, index) => {
    if (typeof item === "string") {
      return { prompt: item, expectedText, responseTimeoutMs: safeResponseTimeoutMs };
    }
    if (!item || typeof item !== "object" || typeof item.prompt !== "string" || !item.prompt) {
      throw new Error(`LANGBOT_E2E_PROMPTS_JSON[${index}] must be a string or an object with a prompt string.`);
    }
    const stepTimeout = Number.parseInt(String(item.response_timeout_ms || item.responseTimeoutMs || safeResponseTimeoutMs), 10);
    return {
      prompt: item.prompt,
      expectedText: String(item.expected_text || item.expectedText || expectedText),
      responseTimeoutMs: Number.isFinite(stepTimeout) && stepTimeout > 0 ? stepTimeout : safeResponseTimeoutMs,
    };
  });
}

function expandEnvRefs(value) {
  return String(value || "").replace(/\$\{([A-Z][A-Z0-9_]*)\}|\$([A-Z][A-Z0-9_]*)/g, (_match, braced, bare) => {
    return env[braced || bare] || "";
  });
}

function textList(value) {
  if (value === undefined || value === null || value === "") return [];
  return Array.isArray(value) ? value.map(String) : [String(value)];
}

function runArgv(argv, { cwd = "", timeoutMs = 30_000 } = {}) {
  return new Promise((resolveRun) => {
    if (!Array.isArray(argv) || argv.length === 0 || !argv.every((item) => typeof item === "string" && item)) {
      resolveRun({
        status: "fail",
        reason: "Filesystem command check requires a non-empty argv string array.",
        exit_code: null,
        stdout: "",
        stderr: "",
      });
      return;
    }

    const child = spawn(argv[0], argv.slice(1), {
      cwd: cwd ? resolve(cwd) : undefined,
      env,
      shell: false,
    });
    let stdout = "";
    let stderr = "";
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill("SIGTERM");
    }, timeoutMs);

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      clearTimeout(timer);
      resolveRun({
        status: "fail",
        reason: error.message,
        exit_code: null,
        stdout,
        stderr,
      });
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      resolveRun({
        status: timedOut ? "fail" : "pass",
        reason: timedOut ? `Command timed out after ${timeoutMs} ms.` : "",
        exit_code: code,
        stdout,
        stderr,
      });
    });
  });
}

async function runFilesystemChecks(checks) {
  if (!Array.isArray(checks) || checks.length === 0) {
    return { status: "not_required", checks: [] };
  }
  const results = [];
  for (let index = 0; index < checks.length; index += 1) {
    const check = checks[index];
    if (!check || typeof check !== "object") {
      results.push({ index, status: "fail", reason: "Filesystem check must be an object." });
      continue;
    }
    const contains = textList(check.contains);
    const notContains = textList(check.not_contains || check.notContains);
    const expectedExitCode = Number.isInteger(check.exit_code)
      ? check.exit_code
      : Number.isInteger(check.expected_exit_code)
        ? check.expected_exit_code
        : 0;
    const expectedStdout = textList(check.stdout_contains || check.expected_stdout || check.expectedStdout);

    if (check.path) {
      const path = resolve(expandEnvRefs(check.path));
      let text = "";
      try {
        text = await readFile(path, "utf8");
      } catch (error) {
        results.push({ index, status: "fail", type: "file", path, reason: error.message });
        continue;
      }
      const missing = contains.filter((needle) => !text.includes(needle));
      const forbidden = notContains.filter((needle) => text.includes(needle));
      results.push({
        index,
        status: missing.length || forbidden.length ? "fail" : "pass",
        type: "file",
        path,
        missing,
        forbidden,
        reason: missing.length
          ? `Missing expected text: ${missing.join(", ")}`
          : forbidden.length
            ? `Found forbidden text: ${forbidden.join(", ")}`
            : "",
      });
      continue;
    }

    if (check.argv) {
      const cwd = check.cwd ? expandEnvRefs(check.cwd) : "";
      const timeoutMs = Number.parseInt(String(check.timeout_ms || check.timeoutMs || "30000"), 10);
      const run = await runArgv(check.argv.map(expandEnvRefs), {
        cwd,
        timeoutMs: Number.isFinite(timeoutMs) && timeoutMs > 0 ? timeoutMs : 30_000,
      });
      const missingStdout = expectedStdout.filter((needle) => !run.stdout.includes(needle));
      const exitMatches = run.exit_code === expectedExitCode;
      results.push({
        index,
        status: run.status === "pass" && exitMatches && missingStdout.length === 0 ? "pass" : "fail",
        type: "command",
        argv: check.argv,
        cwd,
        exit_code: run.exit_code,
        expected_exit_code: expectedExitCode,
        missing_stdout: missingStdout,
        stdout_preview: run.stdout.slice(0, 2000),
        stderr_preview: run.stderr.slice(0, 2000),
        reason: run.reason
          || (!exitMatches ? `Expected exit code ${expectedExitCode}, saw ${run.exit_code}.` : "")
          || (missingStdout.length ? `Missing stdout text: ${missingStdout.join(", ")}` : ""),
      });
      continue;
    }

    results.push({ index, status: "fail", reason: "Filesystem check requires either path or argv." });
  }
  const failed = results.filter((item) => item.status !== "pass");
  return {
    status: failed.length ? "fail" : "pass",
    checks: results,
    reason: failed.length ? `Filesystem checks failed: ${failed.map((item) => item.index).join(", ")}` : "",
  };
}

function pipelineIdFromUrl(url) {
  if (!url) return "";
  try {
    const parsed = new URL(url);
    return parsed.searchParams.get("id") || "";
  } catch {
    return "";
  }
}

function sanitizePipelineDiagnostic(diagnostic) {
  const { restore_config: _restoreConfig, ...safe } = diagnostic || {};
  return safe;
}

function sanitizePipelineExtensionsDiagnostic(diagnostic) {
  const { restore_extensions: _restoreExtensions, ...safe } = diagnostic || {};
  return safe;
}

async function prepareImageFixture(paths) {
  if (imagePathEnv) return resolve(imagePathEnv);
  if (!imageBase64Path) return "";
  const source = resolve(imageBase64Path);
  const target = resolve(paths.evidenceDir, "image-fixture.png");
  const encoded = await readFile(source, "utf8");
  await writeFile(target, Buffer.from(encoded.replace(/\s+/g, ""), "base64"));
  return target;
}

async function inspectAndPatchPipelineConfig(page, {
  backendUrl,
  pipelineUrl,
  pipelineName,
  runnerConfigPatch,
  expectedRunnerId,
}) {
  const pipelineIdFromUrlValue = pipelineIdFromUrl(pipelineUrl) || pipelineIdFromUrl(page.url());
  return await page.evaluate(async ({
    backendUrl,
    pipelineIdFromUrlValue,
    pipelineName,
    runnerConfigPatch,
    expectedRunnerId,
  }) => {
    const token = localStorage.getItem("token");
    if (!token) {
      return {
        status: "blocked",
        authenticated: false,
        reason: "Browser profile has no localStorage token.",
      };
    }

    const headers = {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    };
    const getJson = async (path) => {
      const response = await fetch(`${backendUrl}${path}`, { headers });
      return {
        status: response.status,
        json: await response.json().catch(() => ({})),
      };
    };
    const putJson = async (path, body) => {
      const response = await fetch(`${backendUrl}${path}`, {
        method: "PUT",
        headers,
        body: JSON.stringify(body),
      });
      return {
        status: response.status,
        json: await response.json().catch(() => ({})),
      };
    };

    let pipelineId = pipelineIdFromUrlValue || "";
    let matchedBy = pipelineId ? "url" : "";
    if (!pipelineId && pipelineName) {
      const list = await getJson("/api/v1/pipelines");
      const pipelines = list.json.data?.pipelines || [];
      const match = pipelines.find((pipeline) => pipeline.name === pipelineName);
      if (!match) {
        return {
          status: "blocked",
          authenticated: true,
          pipeline_resolved: false,
          list_status: list.status,
          reason: `Could not find pipeline named ${pipelineName}.`,
        };
      }
      pipelineId = match.uuid;
      matchedBy = "name";
    }

    if (!pipelineId) {
      return {
        status: "blocked",
        authenticated: true,
        pipeline_resolved: false,
        reason: "Could not resolve pipeline id from URL or pipeline name.",
      };
    }

    const before = await getJson(`/api/v1/pipelines/${encodeURIComponent(pipelineId)}`);
    const pipeline = before.json.data?.pipeline;
    if (before.status >= 400 || !pipeline) {
      return {
        status: "fail",
        authenticated: true,
        pipeline_resolved: false,
        pipeline_id: pipelineId,
        get_status: before.status,
        reason: before.json.msg || "Could not load pipeline.",
      };
    }

    const config = JSON.parse(JSON.stringify(pipeline.config || {}));
    const aiConfig = config.ai && typeof config.ai === "object" ? config.ai : {};
    const runner = aiConfig.runner && typeof aiConfig.runner === "object" ? aiConfig.runner : {};
    const runnerId = runner.id || "";
    if (!runnerId) {
      return {
        status: "blocked",
        authenticated: true,
        pipeline_resolved: true,
        pipeline_id: pipelineId,
        pipeline_name: pipeline.name,
        matched_by: matchedBy,
        reason: "Pipeline has no ai.runner.id.",
      };
    }
    if (expectedRunnerId && runnerId !== expectedRunnerId) {
      return {
        status: "blocked",
        authenticated: true,
        pipeline_resolved: true,
        pipeline_id: pipelineId,
        pipeline_name: pipeline.name,
        matched_by: matchedBy,
        runner_id: runnerId,
        expected_runner_id: expectedRunnerId,
        reason: `Pipeline runner mismatch: expected ${expectedRunnerId}, got ${runnerId}.`,
      };
    }

    const runnerConfigs = aiConfig.runner_config && typeof aiConfig.runner_config === "object"
      ? aiConfig.runner_config
      : {};
    const currentRunnerConfig = runnerConfigs[runnerId] && typeof runnerConfigs[runnerId] === "object"
      ? runnerConfigs[runnerId]
      : {};
    const patchKeys = Object.keys(runnerConfigPatch || {});
    const sensitiveConfigKeyRe = /(?:api[_-]?key|authorization|bearer|credential|jwt|oauth|password|secret)/i;
    const sanitizeConfigValue = (key, value, depth = 0) => {
      if (sensitiveConfigKeyRe.test(String(key))) return "[redacted]";
      if (typeof value === "string") {
        return value.length > 1200 ? `${value.slice(0, 1200)}...[truncated ${value.length - 1200} chars]` : value;
      }
      if (Array.isArray(value)) {
        const items = value.slice(0, 50).map((item) => sanitizeConfigValue(key, item, depth + 1));
        if (value.length > 50) items.push(`[truncated ${value.length - 50} items]`);
        return items;
      }
      if (value && typeof value === "object") {
        if (depth >= 3) return "[object truncated]";
        return Object.fromEntries(
          Object.entries(value).map(([childKey, childValue]) => [
            childKey,
            sanitizeConfigValue(childKey, childValue, depth + 1),
          ]),
        );
      }
      return value;
    };
    const pickPatchValues = (config) => Object.fromEntries(
      patchKeys.map((key) => [key, sanitizeConfigValue(key, config?.[key])]),
    );
    const baseDiagnostic = {
      status: "ready",
      authenticated: true,
      pipeline_resolved: true,
      pipeline_id: pipelineId,
      pipeline_name: pipeline.name,
      matched_by: matchedBy,
      runner_id: runnerId,
      expected_runner_id: expectedRunnerId || "",
      patch_keys: patchKeys,
      runner_config_before_keys: Object.keys(currentRunnerConfig),
      runner_config_patch_before: pickPatchValues(currentRunnerConfig),
      patched: patchKeys.length > 0,
    };

    if (patchKeys.length === 0) {
      return baseDiagnostic;
    }

    const updatedRunnerConfig = {
      ...currentRunnerConfig,
      ...runnerConfigPatch,
    };
    const updatedConfig = {
      ...config,
      ai: {
        ...aiConfig,
        runner: {
          ...runner,
          id: runnerId,
        },
        runner_config: {
          ...runnerConfigs,
          [runnerId]: updatedRunnerConfig,
        },
      },
    };

    const update = await putJson(`/api/v1/pipelines/${encodeURIComponent(pipelineId)}`, {
      config: updatedConfig,
    });
    if (update.status >= 400) {
      return {
        ...baseDiagnostic,
        status: "fail",
        put_status: update.status,
        put_code: update.json.code ?? null,
        reason: update.json.msg || "Pipeline config update failed.",
      };
    }

    return {
      ...baseDiagnostic,
      put_status: update.status,
      put_code: update.json.code ?? null,
      runner_config_after_keys: Object.keys(updatedRunnerConfig),
      runner_config_patch_after: pickPatchValues(updatedRunnerConfig),
      restore_config: config,
    };
  }, {
    backendUrl,
    pipelineIdFromUrlValue,
    pipelineName,
    runnerConfigPatch,
    expectedRunnerId,
  });
}

async function restorePipelineConfig(page, { backendUrl, pipelineId, config }) {
  return await page.evaluate(async ({ backendUrl, pipelineId, config }) => {
    const token = localStorage.getItem("token");
    if (!token) {
      return {
        status: "blocked",
        authenticated: false,
        pipeline_id: pipelineId,
        reason: "Browser profile has no localStorage token.",
      };
    }
    const response = await fetch(`${backendUrl}/api/v1/pipelines/${encodeURIComponent(pipelineId)}`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ config }),
    });
    const json = await response.json().catch(() => ({}));
    return {
      status: response.status >= 400 ? "fail" : "ready",
      authenticated: true,
      pipeline_id: pipelineId,
      put_status: response.status,
      put_code: json.code ?? null,
      reason: response.status >= 400 ? json.msg || "Pipeline config restore failed." : "Pipeline config restored.",
    };
  }, { backendUrl, pipelineId, config });
}

async function inspectAndPatchPipelineExtensions(page, {
  backendUrl,
  pipelineId,
  extensionsPatch,
}) {
  return await page.evaluate(async ({
    backendUrl,
    pipelineId,
    extensionsPatch,
  }) => {
    const token = localStorage.getItem("token");
    if (!token) {
      return {
        status: "blocked",
        authenticated: false,
        pipeline_id: pipelineId,
        reason: "Browser profile has no localStorage token.",
      };
    }

    const headers = {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    };
    const getJson = async (path) => {
      const response = await fetch(`${backendUrl}${path}`, { headers });
      return {
        status: response.status,
        json: await response.json().catch(() => ({})),
      };
    };
    const putJson = async (path, body) => {
      const response = await fetch(`${backendUrl}${path}`, {
        method: "PUT",
        headers,
        body: JSON.stringify(body),
      });
      return {
        status: response.status,
        json: await response.json().catch(() => ({})),
      };
    };

    if (!pipelineId) {
      return {
        status: "blocked",
        authenticated: true,
        pipeline_resolved: false,
        reason: "Pipeline id is required before patching extensions.",
      };
    }

    const before = await getJson(`/api/v1/pipelines/${encodeURIComponent(pipelineId)}/extensions`);
    let extensions = before.json.data || {};
    let getStatus = before.status;
    let getCode = before.json.code ?? null;
    let fallbackReason = "";
    if (before.status >= 400 || before.json.code !== 0) {
      const pipelineResponse = await getJson(`/api/v1/pipelines/${encodeURIComponent(pipelineId)}`);
      const pipeline = pipelineResponse.json.data?.pipeline || {};
      const prefs = pipeline.extensions_preferences || {};
      if (pipelineResponse.status >= 400 || pipelineResponse.json.code !== 0 || !pipeline.uuid) {
        return {
          status: "fail",
          authenticated: true,
          pipeline_id: pipelineId,
          get_status: before.status,
          get_code: before.json.code ?? null,
          fallback_pipeline_status: pipelineResponse.status,
          fallback_pipeline_code: pipelineResponse.json.code ?? null,
          reason: before.json.msg || "Could not load pipeline extensions.",
        };
      }
      fallbackReason = before.json.msg || "Could not load pipeline extensions; restored from pipeline preferences.";
      extensions = {
        enable_all_plugins: prefs.enable_all_plugins ?? true,
        enable_all_mcp_servers: prefs.enable_all_mcp_servers ?? true,
        enable_all_skills: prefs.enable_all_skills ?? true,
        bound_plugins: prefs.plugins || [],
        bound_mcp_servers: prefs.mcp_servers || [],
        bound_skills: prefs.skills || [],
      };
    }

    const patchKeys = Object.keys(extensionsPatch || {});
    const restoreExtensions = {
      enable_all_plugins: extensions.enable_all_plugins ?? true,
      enable_all_mcp_servers: extensions.enable_all_mcp_servers ?? true,
      enable_all_skills: extensions.enable_all_skills ?? true,
      bound_plugins: extensions.bound_plugins || [],
      bound_mcp_servers: extensions.bound_mcp_servers || [],
      bound_skills: extensions.bound_skills || [],
    };
    const baseDiagnostic = {
      status: "ready",
      authenticated: true,
      pipeline_id: pipelineId,
      patch_keys: patchKeys,
      patched: patchKeys.length > 0,
      get_status: getStatus,
      get_code: getCode,
      fallback_reason: fallbackReason,
      extensions_before: {
        enable_all_plugins: restoreExtensions.enable_all_plugins,
        enable_all_mcp_servers: restoreExtensions.enable_all_mcp_servers,
        enable_all_skills: restoreExtensions.enable_all_skills,
        bound_plugins: restoreExtensions.bound_plugins,
        bound_mcp_servers: restoreExtensions.bound_mcp_servers,
        bound_skills: restoreExtensions.bound_skills,
      },
    };

    if (patchKeys.length === 0) {
      return baseDiagnostic;
    }

    const updateBody = {
      enable_all_plugins: Object.prototype.hasOwnProperty.call(extensionsPatch, "enable_all_plugins")
        ? Boolean(extensionsPatch.enable_all_plugins)
        : restoreExtensions.enable_all_plugins,
      enable_all_mcp_servers: Object.prototype.hasOwnProperty.call(extensionsPatch, "enable_all_mcp_servers")
        ? Boolean(extensionsPatch.enable_all_mcp_servers)
        : restoreExtensions.enable_all_mcp_servers,
      enable_all_skills: Object.prototype.hasOwnProperty.call(extensionsPatch, "enable_all_skills")
        ? Boolean(extensionsPatch.enable_all_skills)
        : restoreExtensions.enable_all_skills,
      bound_plugins: Object.prototype.hasOwnProperty.call(extensionsPatch, "bound_plugins")
        ? extensionsPatch.bound_plugins
        : restoreExtensions.bound_plugins,
      bound_mcp_servers: Object.prototype.hasOwnProperty.call(extensionsPatch, "bound_mcp_servers")
        ? extensionsPatch.bound_mcp_servers
        : restoreExtensions.bound_mcp_servers,
      bound_skills: Object.prototype.hasOwnProperty.call(extensionsPatch, "bound_skills")
        ? extensionsPatch.bound_skills
        : restoreExtensions.bound_skills,
    };

    const update = await putJson(`/api/v1/pipelines/${encodeURIComponent(pipelineId)}/extensions`, updateBody);
    if (update.status >= 400 || update.json.code !== 0) {
      return {
        ...baseDiagnostic,
        status: "fail",
        put_status: update.status,
        put_code: update.json.code ?? null,
        reason: update.json.msg || "Pipeline extensions update failed.",
      };
    }

    return {
      ...baseDiagnostic,
      put_status: update.status,
      put_code: update.json.code ?? null,
      extensions_after: updateBody,
      restore_extensions: restoreExtensions,
    };
  }, {
    backendUrl,
    pipelineId,
    extensionsPatch,
  });
}

async function restorePipelineExtensions(page, { backendUrl, pipelineId, extensions }) {
  return await page.evaluate(async ({ backendUrl, pipelineId, extensions }) => {
    const token = localStorage.getItem("token");
    if (!token) {
      return {
        status: "blocked",
        authenticated: false,
        pipeline_id: pipelineId,
        reason: "Browser profile has no localStorage token.",
      };
    }
    const response = await fetch(`${backendUrl}/api/v1/pipelines/${encodeURIComponent(pipelineId)}/extensions`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(extensions),
    });
    const json = await response.json().catch(() => ({}));
    return {
      status: response.status >= 400 || json.code !== 0 ? "fail" : "ready",
      authenticated: true,
      pipeline_id: pipelineId,
      put_status: response.status,
      put_code: json.code ?? null,
      reason: response.status >= 400 || json.code !== 0
        ? json.msg || "Pipeline extensions restore failed."
        : "Pipeline extensions restored.",
    };
  }, { backendUrl, pipelineId, extensions });
}

async function resetPipelineDebugChat(page, { backendUrl, pipelineId, sessionType }) {
  return await page.evaluate(async ({ backendUrl, pipelineId, sessionType }) => {
    const token = localStorage.getItem("token");
    if (!token) {
      return {
        status: "blocked",
        authenticated: false,
        pipeline_id: pipelineId,
        session_type: sessionType,
        reason: "Browser profile has no localStorage token.",
      };
    }
    const response = await fetch(
      `${backendUrl}/api/v1/pipelines/${encodeURIComponent(pipelineId)}/ws/reset/${encodeURIComponent(sessionType)}`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      },
    );
    const json = await response.json().catch(() => ({}));
    return {
      status: response.status >= 400 ? "fail" : "ready",
      authenticated: true,
      pipeline_id: pipelineId,
      session_type: sessionType,
      reset_status: response.status,
      reset_code: json.code ?? null,
      reason: response.status >= 400 ? json.msg || "Debug Chat reset failed." : "Debug Chat session reset.",
    };
  }, { backendUrl, pipelineId, sessionType });
}

try {
  browser = await createBrowser(paths);
  const { page } = browser;
  const imagePath = await prepareImageFixture(paths);
  const promptSteps = promptStepsFromEnv();
  const filesystemChecks = parseJsonEnv("LANGBOT_E2E_FILESYSTEM_CHECKS_JSON", []);
  const runnerConfigPatch = parseJsonEnv("LANGBOT_E2E_RUNNER_CONFIG_PATCH_JSON", {});
  const extensionsPatch = parseJsonEnv("LANGBOT_E2E_EXTENSIONS_PATCH_JSON", {});
  const runnerPatchKeys = Object.keys(runnerConfigPatch);
  const extensionsPatchKeys = Object.keys(extensionsPatch);
  if (runnerPatchKeys.length > 0 || extensionsPatchKeys.length > 0 || resetDebugChat || expectedRunnerId) {
    if (!backendUrl) {
      result.status = "env_issue";
      result.reason = "LANGBOT_BACKEND_URL is required for runner config patch, extensions patch, runner assertion, or Debug Chat reset.";
      throw new Error(result.reason);
    }
  }
  result.prompt_count = promptSteps.length;
  result.prompt = promptSteps.length === 1 ? promptSteps[0].prompt : `${promptSteps.length} prompts`;
  result.expected_text = promptSteps.at(-1)?.expectedText || expectedText;

  const authDiagnostic = await ensureAuthenticatedBrowser(page, {
    frontendUrl: env.LANGBOT_FRONTEND_URL || "",
    backendUrl,
  });
  result.browser_auth = authDiagnostic;
  if (!result.evidence_collected.includes("api_diagnostic")) result.evidence_collected.push("api_diagnostic");
  const authFailed = authDiagnostic.status === "env_issue" || authDiagnostic.status === "blocked" || authDiagnostic.status === "fail";
  if (authFailed) {
    result.status = authDiagnostic.status;
    result.reason = authDiagnostic.reason || "Browser authentication failed.";
  } else {
    result.status = "running";
    result.reason = "";
  }

  const openResult = authFailed
    ? { opened: false, status: result.status, reason: result.reason }
    : await openPipelineDebugChat(page, {
      pipelineUrl,
      pipelineName,
      envHint: pipelineRequired
        ? "case-specific pipeline env mapped to LANGBOT_E2E_PIPELINE_URL or LANGBOT_E2E_PIPELINE_NAME"
        : "LANGBOT_PIPELINE_URL or LANGBOT_PIPELINE_NAME",
    });
  result.url = page.url();

  if (!openResult.opened) {
    result.status = openResult.status;
    result.reason = openResult.reason;
  } else {
    result.status = "running";
    result.reason = "";
    if (runnerPatchKeys.length > 0 || extensionsPatchKeys.length > 0 || resetDebugChat || expectedRunnerId) {
      const pipelineDiagnostic = await inspectAndPatchPipelineConfig(page, {
        backendUrl,
        pipelineUrl,
        pipelineName,
        runnerConfigPatch,
        expectedRunnerId,
      });
      const safeDiagnostic = sanitizePipelineDiagnostic(pipelineDiagnostic);
      await writeFile(pipelineConfigDiagnosticPath, `${JSON.stringify(safeDiagnostic, null, 2)}\n`, "utf8");
      result.evidence.pipeline_config_diagnostic_json = pipelineConfigDiagnosticPath;
      result.pipeline_config = safeDiagnostic;
      if (!result.evidence_collected.includes("api_diagnostic")) result.evidence_collected.push("api_diagnostic");

      if (pipelineDiagnostic.status === "fail" || pipelineDiagnostic.status === "blocked") {
        result.status = pipelineDiagnostic.status;
        result.reason = pipelineDiagnostic.reason || "Pipeline config preparation failed.";
      } else {
        if (pipelineDiagnostic.restore_config && restoreRunnerConfig) {
          restoreConfigPlan = {
            backendUrl,
            pipelineId: pipelineDiagnostic.pipeline_id,
            config: pipelineDiagnostic.restore_config,
          };
        }
        if (extensionsPatchKeys.length > 0) {
          const extensionsDiagnostic = await inspectAndPatchPipelineExtensions(page, {
            backendUrl,
            pipelineId: pipelineDiagnostic.pipeline_id,
            extensionsPatch,
          });
          const safeExtensionsDiagnostic = sanitizePipelineExtensionsDiagnostic(extensionsDiagnostic);
          await writeFile(pipelineExtensionsDiagnosticPath, `${JSON.stringify(safeExtensionsDiagnostic, null, 2)}\n`, "utf8");
          result.evidence.pipeline_extensions_diagnostic_json = pipelineExtensionsDiagnosticPath;
          result.pipeline_extensions = safeExtensionsDiagnostic;
          if (!result.evidence_collected.includes("api_diagnostic")) result.evidence_collected.push("api_diagnostic");
          if (extensionsDiagnostic.status === "fail" || extensionsDiagnostic.status === "blocked") {
            result.status = extensionsDiagnostic.status;
            result.reason = extensionsDiagnostic.reason || "Pipeline extensions preparation failed.";
          } else if (extensionsDiagnostic.restore_extensions && restoreExtensions) {
            restoreExtensionsPlan = {
              backendUrl,
              pipelineId: extensionsDiagnostic.pipeline_id,
              extensions: extensionsDiagnostic.restore_extensions,
            };
          }
        }
        if (!["fail", "blocked", "env_issue"].includes(result.status) && resetDebugChat) {
          const resetDiagnostic = await resetPipelineDebugChat(page, {
            backendUrl,
            pipelineId: pipelineDiagnostic.pipeline_id,
            sessionType: debugChatSessionType,
          });
          await writeFile(debugChatResetDiagnosticPath, `${JSON.stringify(resetDiagnostic, null, 2)}\n`, "utf8");
          result.evidence.debug_chat_reset_diagnostic_json = debugChatResetDiagnosticPath;
          result.debug_chat_reset = resetDiagnostic;
          if (resetDiagnostic.status === "fail" || resetDiagnostic.status === "blocked") {
            result.status = resetDiagnostic.status;
            result.reason = resetDiagnostic.reason || "Debug Chat reset failed.";
          } else {
            await page.waitForTimeout(1000);
            const reopenResult = await openPipelineDebugChat(page, {
              pipelineUrl,
              pipelineName,
              envHint: pipelineRequired
                ? "case-specific pipeline env mapped to LANGBOT_E2E_PIPELINE_URL or LANGBOT_E2E_PIPELINE_NAME"
                : "LANGBOT_PIPELINE_URL or LANGBOT_PIPELINE_NAME",
            });
            result.url = page.url();
            if (!reopenResult.opened) {
              result.status = reopenResult.status;
              result.reason = reopenResult.reason;
            }
          }
        }
      }
    }

    if (result.status === "fail" || result.status === "blocked" || result.status === "env_issue") {
      // Preparation already determined the outcome.
    } else {
      const streamResult = await setDebugChatStreamOutput(page, streamOutput);
      if (streamResult.status === "blocked" || streamResult.status === "fail") {
        result.status = streamResult.status;
        result.reason = streamResult.reason;
      } else {
        for (let index = 0; index < promptSteps.length; index += 1) {
          const step = promptSteps[index];
          const promptStartedAt = Date.now();
          const chatResult = await runDebugChatPrompt(page, {
            prompt: step.prompt,
            expectedText: step.expectedText,
            responseTimeoutMs: step.responseTimeoutMs,
            imagePath: index === 0 ? imagePath : "",
            failureSignals: failureSignals.length > 0 ? failureSignals : undefined,
          });
          const promptDurationMs = Date.now() - promptStartedAt;
          result.chat_results.push({
            index,
            expected_text: step.expectedText,
            status: chatResult.status,
            reason: chatResult.reason,
            response_duration_ms: promptDurationMs,
            min_expected_count: chatResult.min_expected_count,
            final_count: chatResult.final_count,
            before_assistant_expected_count: chatResult.before_assistant_expected_count,
            after_assistant_expected_count: chatResult.after_assistant_expected_count,
            failure_signal: chatResult.failure_signal || "",
          });
          result.status = chatResult.status;
          result.reason = `Prompt ${index + 1}/${promptSteps.length}: ${chatResult.reason}`;
          if (chatResult.status !== "pass") break;
        }
      }
    }

    if (result.status === "pass" && filesystemChecks.length > 0) {
      const filesystemResult = await runFilesystemChecks(filesystemChecks);
      result.filesystem_checks = filesystemResult;
      if (!result.evidence_collected.includes("filesystem")) result.evidence_collected.push("filesystem");
      if (filesystemResult.status === "fail") {
        result.status = "fail";
        result.reason = filesystemResult.reason || "Filesystem checks failed.";
      }
    }

    if (result.status === "pass" && !boolFromEnv(env.LANGBOT_E2E_ALLOW_BROWSER_ERRORS, false)) {
      const browserDiagnostics = await scanBrowserDiagnostics(paths);
      result.browser_diagnostics = browserDiagnostics;
      if (browserDiagnostics.status === "fail") {
        result.status = "fail";
        result.reason = browserDiagnostics.reason;
      }
    }
  }
} catch (error) {
  if (!["env_issue", "blocked", "fail", "pass"].includes(result.status) || !result.reason) {
    result.status = /Playwright is not installed|LANGBOT_FRONTEND_URL/.test(error.message) ? "env_issue" : "fail";
  }
  result.reason = result.reason || error.message;
} finally {
  if (browser?.page) await safeScreenshot(browser.page, paths.screenshot);
  if (browser?.page && restoreExtensionsPlan) {
    const restoreDiagnostic = await restorePipelineExtensions(browser.page, restoreExtensionsPlan).catch((error) => ({
      status: "fail",
      pipeline_id: restoreExtensionsPlan.pipelineId,
      reason: error.message,
    }));
    await writeFile(pipelineExtensionsRestoreDiagnosticPath, `${JSON.stringify(restoreDiagnostic, null, 2)}\n`, "utf8");
    result.evidence.pipeline_extensions_restore_diagnostic_json = pipelineExtensionsRestoreDiagnosticPath;
    result.pipeline_extensions_restore = restoreDiagnostic;
  }
  if (browser?.page && restoreConfigPlan) {
    const restoreDiagnostic = await restorePipelineConfig(browser.page, restoreConfigPlan).catch((error) => ({
      status: "fail",
      pipeline_id: restoreConfigPlan.pipelineId,
      reason: error.message,
    }));
    await writeFile(pipelineConfigRestoreDiagnosticPath, `${JSON.stringify(restoreDiagnostic, null, 2)}\n`, "utf8");
    result.evidence.pipeline_config_restore_diagnostic_json = pipelineConfigRestoreDiagnosticPath;
    result.pipeline_config_restore = restoreDiagnostic;
  }
  if (browser) await browser.close().catch(() => {});
  const finishedAt = new Date();
  result.finished_at = finishedAt.toISOString();
  result.finished_at_local = localIsoWithOffset(finishedAt);
  result.duration_ms = finishedAt.getTime() - startedAt.getTime();
  const responseDurations = result.chat_results
    .map((item) => item.response_duration_ms)
    .filter((value) => Number.isFinite(value));
  const passedPrompts = result.chat_results.filter((item) => item.status === "pass").length;
  const attemptedPrompts = result.chat_results.length;
  const errorRate = attemptedPrompts === 0 ? 1 : Number(((attemptedPrompts - passedPrompts) / attemptedPrompts).toFixed(4));
  const responseStats = stats(responseDurations);
  const responseP95BudgetMs = positiveNumberEnv(
    "LANGBOT_E2E_DEBUG_CHAT_RESPONSE_P95_MS",
    positiveNumberEnv("LANGBOT_DEBUG_CHAT_RESPONSE_P95_MS", safeResponseTimeoutMs),
  );
  const maxErrorRate = positiveNumberEnv("LANGBOT_E2E_DEBUG_CHAT_MAX_ERROR_RATE", 0);
  const metrics = {
    probe: caseId,
    url: result.url,
    prompt_count: result.prompt_count,
    attempted_prompt_count: attemptedPrompts,
    passed_prompt_count: passedPrompts,
    error_rate: errorRate,
    response_duration_ms: responseStats,
    total_duration_ms: result.duration_ms,
    chat_results: result.chat_results,
  };
  result.metrics_summary = {
    prompt_count: metrics.prompt_count,
    attempted_prompt_count: metrics.attempted_prompt_count,
    passed_prompt_count: metrics.passed_prompt_count,
    error_rate: metrics.error_rate,
    response_p50_ms: metrics.response_duration_ms.p50,
    response_p95_ms: metrics.response_duration_ms.p95,
    total_duration_ms: metrics.total_duration_ms,
  };
  result.thresholds_summary = {
    response_p95_ms: {
      actual: metrics.response_duration_ms.p95,
      max: responseP95BudgetMs,
      pass: attemptedPrompts > 0 && metrics.response_duration_ms.p95 <= responseP95BudgetMs,
    },
    error_rate: {
      actual: metrics.error_rate,
      max: maxErrorRate,
      pass: metrics.error_rate <= maxErrorRate,
    },
  };
  await writeFile(metricsPath, `${JSON.stringify(metrics, null, 2)}\n`, "utf8");
  if (result.status === "pass" && !Object.values(result.thresholds_summary).every((item) => item.pass)) {
    result.status = "fail";
    result.reason = "Debug Chat performance breached response latency or error-rate thresholds.";
  }
  const existingEvidence = {};
  for (const [key, value] of Object.entries(result.evidence)) {
    if (typeof value !== "string") continue;
    const isResultFile = value === paths.automationResultJson || value === paths.resultJson;
    if (isResultFile || await pathExists(value)) existingEvidence[key] = value;
  }
  result.evidence = existingEvidence;
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(exitCode(result.status));
