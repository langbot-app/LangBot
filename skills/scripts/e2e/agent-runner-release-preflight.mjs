#!/usr/bin/env node

import { existsSync, readFileSync } from "node:fs";
import { writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { env } from "node:process";
import {
  createBrowser,
  ensureEvidence,
  evidencePaths,
  exitCode,
  localIsoWithOffset,
  safeScreenshot,
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

function boolFromEnv(value, defaultValue) {
  if (value === undefined || value === "") return defaultValue;
  if (/^(0|false|no|off)$/i.test(value)) return false;
  if (/^(1|true|yes|on)$/i.test(value)) return true;
  return defaultValue;
}

function firstEnv(...keys) {
  for (const key of keys) {
    if (env[key]) return env[key];
  }
  return "";
}

function redactMessage(text) {
  return String(text ?? "")
    .replace(/\bbearer\s+[A-Za-z0-9._~+/=-]{8,}/gi, "Bearer [redacted]")
    .replace(/\bsk-[A-Za-z0-9_-]{6,}\b/g, "[redacted]")
    .replace(/(api[_-]?key|authorization|credential|jwt|oauth|password|secret|token)\s*[:=]\s*["']?[^"',\s]+/gi, "$1=[redacted]");
}

function isEnvironmentError(message) {
  return /Playwright is not installed|LANGBOT_FRONTEND_URL|LANGBOT_BACKEND_URL|ERR_CONNECTION_REFUSED|ECONNREFUSED|net::ERR_|fetch failed|timed out/i
    .test(message);
}

loadEnvDefaults("skills/.env");
loadEnvDefaults("skills/.env.local");

const caseId = env.LBS_CASE_ID || "agent-runner-release-preflight";
const paths = evidencePaths(caseId);
await ensureEvidence(paths);

const backendUrl = env.LANGBOT_BACKEND_URL || "";
const frontendUrl = env.LANGBOT_FRONTEND_URL || backendUrl;
const testModels = boolFromEnv(env.LANGBOT_PREFLIGHT_TEST_MODELS, true);
const requireVision = boolFromEnv(env.LANGBOT_PREFLIGHT_REQUIRE_VISION, true);
const diagnosticPath = resolve(paths.evidenceDir, "api-diagnostic.json");
const startedAt = new Date();

const targets = [
  {
    id: "local-agent",
    expected_runner_id: "plugin:langbot-team/LocalAgent/default",
    pipeline_url: firstEnv("LANGBOT_LOCAL_AGENT_PIPELINE_URL"),
    pipeline_name: firstEnv("LANGBOT_LOCAL_AGENT_PIPELINE_NAME"),
    require_func_call_model: true,
    require_vision_model: requireVision,
    require_langbot_mcp: false,
  },
  {
    id: "acp-agent-runner",
    expected_runner_id: "plugin:langbot-team/ACPAgentRunner/default",
    pipeline_url: firstEnv("LANGBOT_ACP_AGENT_RUNNER_PIPELINE_URL", "LANGBOT_AGENT_RUNNER_PIPELINE_URL"),
    pipeline_name: firstEnv("LANGBOT_ACP_AGENT_RUNNER_PIPELINE_NAME", "LANGBOT_AGENT_RUNNER_PIPELINE_NAME"),
    require_func_call_model: false,
    require_vision_model: false,
  },
];

let browser;
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
  frontend_url: frontendUrl,
  backend_url: backendUrl,
  test_models: testModels,
  require_vision_model: requireVision,
  evidence: {
    console_log: paths.consoleLog,
    network_log: paths.networkLog,
    screenshot: paths.screenshot,
    api_diagnostic_json: diagnosticPath,
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["ui", "screenshot", "console", "network", "api_diagnostic"],
};

async function run() {
  if (!backendUrl || !frontendUrl) {
    result.status = "env_issue";
    result.reason = "LANGBOT_FRONTEND_URL and LANGBOT_BACKEND_URL must be configured.";
    return;
  }

  browser = await createBrowser(paths);
  const { page } = browser;
  await page.goto(frontendUrl, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});

  const diagnostic = await page.evaluate(async ({ backendUrl, targets, testModels }) => {
    const blockers = [];
    const envIssues = [];
    const warnings = [];
    const checks = [];

    const addCheck = (name, status, detail = {}) => {
      checks.push({ name, status, ...detail });
      if (status === "blocked") blockers.push({ name, ...detail });
      if (status === "env_issue") envIssues.push({ name, ...detail });
    };
    const safeMessage = (value) => String(value ?? "")
      .replace(/\bbearer\s+[A-Za-z0-9._~+/=-]{8,}/gi, "Bearer [redacted]")
      .replace(/\bsk-[A-Za-z0-9_-]{6,}\b/g, "[redacted]")
      .replace(/(api[_-]?key|authorization|credential|jwt|oauth|password|secret|token)\s*[:=]\s*["']?[^"',\s]+/gi, "$1=[redacted]");

    const token = localStorage.getItem("token");
    if (!token) {
      addCheck("browser-auth", "blocked", { reason: "Browser profile has no localStorage token." });
      return { authenticated: false, blockers, env_issues: envIssues, warnings, checks };
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
    const postJson = async (path, body) => {
      const response = await fetch(`${backendUrl}${path}`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
      return {
        status: response.status,
        json: await response.json().catch(() => ({})),
      };
    };

    const tokenCheck = await getJson("/api/v1/user/check-token");
    addCheck(
      "browser-auth",
      tokenCheck.status < 400 && (tokenCheck.json.code ?? 0) === 0 ? "pass" : "blocked",
      { http_status: tokenCheck.status, code: tokenCheck.json.code ?? null, reason: safeMessage(tokenCheck.json.msg || "") },
    );

    const systemInfo = await getJson("/api/v1/system/info");
    addCheck(
      "backend-system-info",
      systemInfo.status < 400 ? "pass" : "env_issue",
      {
        http_status: systemInfo.status,
        version: systemInfo.json.data?.version || systemInfo.json.data?.system?.version || "",
      },
    );

    const pluginSystem = await getJson("/api/v1/system/status/plugin-system");
    addCheck(
      "plugin-system",
      pluginSystem.status < 400 && (pluginSystem.json.code ?? 0) === 0 ? "pass" : "env_issue",
      {
        http_status: pluginSystem.status,
        code: pluginSystem.json.code ?? null,
        status: pluginSystem.json.data?.status || pluginSystem.json.data?.state || "",
        reason: safeMessage(pluginSystem.json.msg || ""),
      },
    );

    const boxStatus = await getJson("/api/v1/box/status");
    addCheck(
      "box-runtime",
      boxStatus.status < 400 && (boxStatus.json.code ?? 0) === 0 ? "pass" : "env_issue",
      {
        http_status: boxStatus.status,
        code: boxStatus.json.code ?? null,
        status: boxStatus.json.data?.status || "",
        backend: boxStatus.json.data?.backend || "",
        reason: safeMessage(boxStatus.json.msg || ""),
      },
    );

    const plugins = await getJson("/api/v1/plugins");
    const installedPluginIds = (plugins.json.data?.plugins || [])
      .map((plugin) => {
        const metadata = plugin.manifest?.manifest?.metadata || plugin.manifest?.metadata || plugin.metadata || {};
        return metadata.author && metadata.name ? `${metadata.author}/${metadata.name}` : "";
      })
      .filter(Boolean);
    const requiredPlugins = ["langbot-team/LocalAgent", "langbot-team/ACPAgentRunner", "qa/plugin-smoke"];
    const pluginPresence = Object.fromEntries(requiredPlugins.map((id) => [id, installedPluginIds.includes(id)]));
    for (const [id, present] of Object.entries(pluginPresence)) {
      addCheck(`plugin:${id}`, present ? "pass" : "blocked", { plugin_id: id, reason: present ? "" : "Required plugin is not listed by /api/v1/plugins." });
    }

    const tools = await getJson("/api/v1/tools");
    const toolNames = (tools.json.data?.tools || [])
      .map((tool) => tool.name || tool.tool_name || tool.function?.name || "")
      .filter(Boolean)
      .sort();
    addCheck(
      "tool:qa_plugin_echo",
      toolNames.includes("qa_plugin_echo") ? "pass" : "blocked",
      { reason: toolNames.includes("qa_plugin_echo") ? "" : "qa-plugin-smoke tool qa_plugin_echo is not exposed through /api/v1/tools." },
    );
    if (!toolNames.includes("qa_mcp_echo")) {
      warnings.push({
        name: "tool:qa_mcp_echo",
        reason: "qa_mcp_echo is not currently exposed. This is acceptable before mcp-stdio-register, but mcp-stdio-tool-call must run after registration.",
      });
    }

    const modelResponse = await getJson("/api/v1/provider/models/llm");
    const models = (modelResponse.json.data?.models || []).map((model) => ({
      uuid: model.uuid,
      name: model.name,
      abilities: Array.isArray(model.abilities) ? model.abilities : [],
      provider_uuid: model.provider_uuid || model.provider?.uuid || "",
      provider_name: model.provider_name || model.provider?.name || "",
      requester: model.requester || model.provider?.requester || "",
    }));
    addCheck(
      "llm-model-list",
      modelResponse.status < 400 && (modelResponse.json.code ?? 0) === 0 ? "pass" : "env_issue",
      { http_status: modelResponse.status, model_count: models.length, reason: safeMessage(modelResponse.json.msg || "") },
    );
    const modelById = new Map(models.map((model) => [model.uuid, model]));

    const pipelineList = await getJson("/api/v1/pipelines");
    const pipelines = pipelineList.json.data?.pipelines || [];
    addCheck(
      "pipeline-list",
      pipelineList.status < 400 && (pipelineList.json.code ?? 0) === 0 ? "pass" : "blocked",
      { http_status: pipelineList.status, pipeline_count: pipelines.length, reason: safeMessage(pipelineList.json.msg || "") },
    );

    const resolvedPipelines = [];
    const modelTested = new Set();
    for (const target of targets) {
      let pipelineId = "";
      let matchedBy = "";
      if (target.pipeline_url) {
        try {
          pipelineId = new URL(target.pipeline_url).searchParams.get("id") || "";
          matchedBy = pipelineId ? "url" : "";
        } catch {
          pipelineId = "";
        }
      }
      if (!pipelineId && target.pipeline_name) {
        const match = pipelines.find((pipeline) => pipeline.name === target.pipeline_name);
        if (match) {
          pipelineId = match.uuid;
          matchedBy = "name";
        }
      }
      if (!pipelineId) {
        addCheck(`pipeline:${target.id}`, "blocked", {
          target: target.id,
          reason: "Required pipeline env is missing or could not resolve to a pipeline id.",
        });
        continue;
      }

      const response = await getJson(`/api/v1/pipelines/${encodeURIComponent(pipelineId)}`);
      const pipeline = response.json.data?.pipeline;
      if (response.status >= 400 || !pipeline) {
        addCheck(`pipeline:${target.id}`, "blocked", {
          target: target.id,
          pipeline_id: pipelineId,
          http_status: response.status,
          reason: safeMessage(response.json.msg || "Could not load pipeline."),
        });
        continue;
      }

      const config = pipeline.config || {};
      const aiConfig = config.ai && typeof config.ai === "object" ? config.ai : {};
      const runner = aiConfig.runner && typeof aiConfig.runner === "object" ? aiConfig.runner : {};
      const runnerId = runner.id || "";
      const runnerConfigs = aiConfig.runner_config && typeof aiConfig.runner_config === "object" ? aiConfig.runner_config : {};
      const runnerConfig = runnerConfigs[runnerId] && typeof runnerConfigs[runnerId] === "object" ? runnerConfigs[runnerId] : {};
      const pipelineSummary = {
        target: target.id,
        pipeline_id: pipelineId,
        pipeline_name: pipeline.name,
        matched_by: matchedBy,
        runner_id: runnerId,
        expected_runner_id: target.expected_runner_id,
        runner_config_keys: Object.keys(runnerConfig).sort(),
      };
      resolvedPipelines.push(pipelineSummary);

      addCheck(
        `pipeline:${target.id}:runner`,
        runnerId === target.expected_runner_id ? "pass" : "blocked",
        {
          ...pipelineSummary,
          reason: runnerId === target.expected_runner_id ? "" : `Expected ${target.expected_runner_id}, got ${runnerId || "<missing>"}.`,
        },
      );

      if (target.require_func_call_model || target.require_vision_model || (testModels && target.id === "local-agent")) {
        const modelConfig = runnerConfig.model;
        const primaryModelId = typeof modelConfig === "string"
          ? modelConfig
          : modelConfig && typeof modelConfig === "object"
            ? modelConfig.primary || ""
            : "";
        if (!primaryModelId) {
          addCheck(`pipeline:${target.id}:primary-model`, "blocked", {
            ...pipelineSummary,
            reason: "Local-agent runner config has no primary model.",
          });
          continue;
        }
        const model = modelById.get(primaryModelId);
        if (!model) {
          addCheck(`pipeline:${target.id}:primary-model`, "blocked", {
            ...pipelineSummary,
            model_uuid: primaryModelId,
            reason: "Primary model is not listed by /api/v1/provider/models/llm.",
          });
          continue;
        }
        addCheck(`pipeline:${target.id}:primary-model`, "pass", {
          ...pipelineSummary,
          model: {
            uuid: model.uuid,
            name: model.name,
            abilities: model.abilities,
            provider_name: model.provider_name,
            requester: model.requester,
          },
        });
        if (target.require_func_call_model) {
          addCheck(
            `pipeline:${target.id}:func-call-model`,
            model.abilities.includes("func_call") ? "pass" : "env_issue",
            {
              model_uuid: model.uuid,
              model_name: model.name,
              abilities: model.abilities,
              reason: model.abilities.includes("func_call") ? "" : "Release gate includes tool-call cases; the local-agent primary model must advertise func_call.",
            },
          );
        }
        if (target.require_vision_model) {
          addCheck(
            `pipeline:${target.id}:vision-model`,
            model.abilities.includes("vision") ? "pass" : "env_issue",
            {
              model_uuid: model.uuid,
              model_name: model.name,
              abilities: model.abilities,
              reason: model.abilities.includes("vision") ? "" : "Release gate includes multimodal cases; the local-agent primary model must advertise vision.",
            },
          );
        }
        if (testModels && !modelTested.has(model.uuid)) {
          modelTested.add(model.uuid);
          const modelTest = await postJson(`/api/v1/provider/models/llm/${encodeURIComponent(model.uuid)}/test`, { extra_args: {} });
          const passed = modelTest.status < 400 && (modelTest.json.code ?? 0) === 0;
          addCheck(
            `model-test:${model.name}`,
            passed ? "pass" : "env_issue",
            {
              model_uuid: model.uuid,
              model_name: model.name,
              http_status: modelTest.status,
              code: modelTest.json.code ?? null,
              reason: passed ? "" : safeMessage(modelTest.json.msg || modelTest.json.message || "Model test failed."),
            },
          );
        }
      }
    }

    return {
      authenticated: true,
      blockers,
      env_issues: envIssues,
      warnings,
      checks,
      resolved_pipelines: resolvedPipelines,
      tools: {
        required: ["qa_plugin_echo"],
        optional_before_register: ["qa_mcp_echo"],
        present: toolNames.filter((name) => ["qa_plugin_echo", "qa_mcp_echo"].includes(name)),
      },
      models,
    };
  }, { backendUrl, targets, testModels });

  diagnostic.blockers = (diagnostic.blockers || []).map((item) => ({ ...item, reason: redactMessage(item.reason || "") }));
  diagnostic.env_issues = (diagnostic.env_issues || []).map((item) => ({ ...item, reason: redactMessage(item.reason || "") }));
  await writeFile(diagnosticPath, `${JSON.stringify(diagnostic, null, 2)}\n`, "utf8");
  await safeScreenshot(page, paths.screenshot);

  const blockers = diagnostic.blockers || [];
  const envIssues = diagnostic.env_issues || [];
  if (blockers.length > 0) {
    result.status = "blocked";
    result.reason = `Preflight blocked: ${blockers.map((item) => item.name).join(", ")}`;
  } else if (envIssues.length > 0) {
    result.status = "env_issue";
    result.reason = `Preflight environment issue: ${envIssues.map((item) => item.name).join(", ")}`;
  } else {
    result.status = "pass";
    result.reason = "Release gate preflight passed: auth, plugin runtime, required pipelines, runner ids, tools, and local-agent model checks are ready.";
  }
  result.check_count = Array.isArray(diagnostic.checks) ? diagnostic.checks.length : 0;
  result.warning_count = Array.isArray(diagnostic.warnings) ? diagnostic.warnings.length : 0;
}

try {
  await run();
} catch (error) {
  const message = redactMessage(error instanceof Error ? error.message : String(error));
  result.status = isEnvironmentError(message) ? "env_issue" : "fail";
  result.reason = message;
  await writeFile(diagnosticPath, `${JSON.stringify({
    authenticated: false,
    blockers: [],
    env_issues: result.status === "env_issue" ? [{ name: "preflight-runtime", reason: message }] : [],
    warnings: [],
    checks: [
      {
        name: "preflight-runtime",
        status: result.status,
        reason: message,
      },
    ],
  }, null, 2)}\n`, "utf8").catch(() => {});
} finally {
  if (browser) await browser.close().catch(() => {});
  const finishedAt = new Date();
  result.finished_at = finishedAt.toISOString();
  result.finished_at_local = localIsoWithOffset(finishedAt);
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(exitCode(result.status));
