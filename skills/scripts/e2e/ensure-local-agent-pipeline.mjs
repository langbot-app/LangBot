#!/usr/bin/env node

import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { env } from "node:process";
import {
  apiJson,
  bodyText,
  createBrowser,
  ensureEvidence,
  evidencePaths,
  loadEnvFiles,
  resetAndAuthLocalUser,
  safeScreenshot,
  setBrowserToken,
  verifyBrowserToken,
  writeResult,
} from "./lib/langbot-e2e.mjs";

const RUNNER_ID = "plugin:langbot/local-agent/default";
const DEFAULT_PIPELINE_NAME = "Agent QA Local Agent Debug Chat";
const DEFAULT_LOCAL_PASSWORD = "LangBotE2ELocalPass!2026";
const caseId = "ensure-local-agent-pipeline";

await loadEnvFiles();
const paths = evidencePaths(caseId);
await ensureEvidence(paths);

const writeEnv = process.argv.includes("--write-env");
const pipelineName = env.LANGBOT_E2E_CREATE_PIPELINE_NAME || env.LANGBOT_LOCAL_AGENT_PIPELINE_NAME || DEFAULT_PIPELINE_NAME;
const frontendUrl = env.LANGBOT_FRONTEND_URL || "";
const backendUrl = env.LANGBOT_BACKEND_URL || "";
const envLocalPath = resolve("skills/.env.local");

const result = {
  source: "automation",
  case_id: caseId,
  run_id: paths.runId,
  status: "fail",
  reason: "",
  frontend_url: frontendUrl,
  backend_url: backendUrl,
  pipeline_name: pipelineName,
  pipeline_id: "",
  pipeline_url: "",
  runner_id: RUNNER_ID,
  selected_model_id: "",
  model_count: 0,
  created: false,
  updated: false,
  wrote_env: false,
  auth: null,
  browser_token_check: null,
  page_signal: "",
  evidence: {
    console_log: paths.consoleLog,
    network_log: paths.networkLog,
    screenshot: paths.screenshot,
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["api_diagnostic", "console", "network", "screenshot"],
};

let browser;

try {
  if (!frontendUrl) throw new Error("LANGBOT_FRONTEND_URL is not configured.");
  if (!backendUrl) throw new Error("LANGBOT_BACKEND_URL is not configured.");

  const user = env.LANGBOT_E2E_LOGIN_USER || "";
  const password = env.LANGBOT_E2E_LOGIN_PASSWORD || DEFAULT_LOCAL_PASSWORD;
  if (!user) {
    throw new Error("LANGBOT_E2E_LOGIN_USER is required so this setup can create/update the pipeline via backend API.");
  }

  const auth = await resetAndAuthLocalUser({ backendUrl, user, password });
  result.auth = {
    source: "local_recovery_login",
    user,
    backend_token_check: auth.check,
  };

  const prepared = await ensureLocalAgentPipeline({
    backendUrl,
    token: auth.token,
    pipelineName,
    runnerId: RUNNER_ID,
  });
  Object.assign(result, prepared);
  if (result.pipeline_id) {
    result.pipeline_url = `${frontendUrl.replace(/\/$/, "")}/home/agents?id=${encodeURIComponent(result.pipeline_id)}`;
  }

  if (writeEnv && result.pipeline_id) {
    await upsertEnvLocal(envLocalPath, {
      LANGBOT_E2E_LOGIN_USER: user,
      LANGBOT_PIPELINE_URL: result.pipeline_url,
      LANGBOT_PIPELINE_NAME: result.pipeline_name || pipelineName,
      LANGBOT_LOCAL_AGENT_PIPELINE_URL: result.pipeline_url,
      LANGBOT_LOCAL_AGENT_PIPELINE_NAME: result.pipeline_name || pipelineName,
    });
    result.wrote_env = true;
  }

  browser = await createBrowser(paths);
  const { page } = browser;
  await setBrowserToken(page, frontendUrl, auth.token);
  const browserCheck = await verifyBrowserToken(page, backendUrl);
  result.browser_token_check = browserCheck;
  if (!browserCheck.authenticated) {
    throw new Error(browserCheck.reason || "Browser token check failed after setup.");
  }
  await page.goto(result.pipeline_url || frontendUrl, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
  const text = await bodyText(page);
  result.page_signal = ["Pipelines", "流水线", pipelineName].find((signal) => text.includes(signal)) || "";
} catch (error) {
  result.status = result.status === "env_issue" ? "env_issue" : "fail";
  result.reason = result.reason || error.message;
} finally {
  if (browser?.page) await safeScreenshot(browser.page, paths.screenshot);
  if (browser) await browser.close().catch(() => {});
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(result.status === "pass" ? 0 : result.status === "env_issue" ? 2 : 1);

async function ensureLocalAgentPipeline({ backendUrl, token, pipelineName, runnerId }) {
  const [pipelineList, modelList] = await Promise.all([
    apiJson(backendUrl, "/api/v1/pipelines", { token }),
    apiJson(backendUrl, "/api/v1/provider/models/llm", { token }),
  ]);

  if (isApiFailure(pipelineList)) {
    return {
      status: "fail",
      reason: pipelineList.json.msg || "Failed to list pipelines.",
      list_status: pipelineList.status,
    };
  }
  if (isApiFailure(modelList)) {
    return {
      status: "fail",
      reason: modelList.json.msg || "Failed to list LLM models.",
      model_status: modelList.status,
    };
  }

  const models = modelList.json.data?.models || [];
  const selectedModel = models.find((model) => model.uuid) || null;
  const pipelines = pipelineList.json.data?.pipelines || [];
  let pipeline = pipelines.find((item) => item.name === pipelineName) || null;
  let created = false;

  if (!pipeline) {
    const createdResponse = await apiJson(backendUrl, "/api/v1/pipelines", {
      method: "POST",
      token,
      body: {
        name: pipelineName,
        description: "Local QA pipeline for AgentRunner Debug Chat smoke tests.",
        emoji: "QA",
      },
    });
    if (isApiFailure(createdResponse)) {
      return {
        status: "fail",
        reason: createdResponse.json.msg || "Failed to create pipeline.",
        create_status: createdResponse.status,
        model_count: models.length,
      };
    }
    const pipelineId = createdResponse.json.data?.uuid || "";
    const loaded = await apiJson(backendUrl, `/api/v1/pipelines/${encodeURIComponent(pipelineId)}`, { token });
    pipeline = loaded.json.data?.pipeline || null;
    created = true;
  }

  if (!pipeline?.uuid) {
    return {
      status: "fail",
      reason: "Pipeline was not created or resolved.",
      model_count: models.length,
    };
  }

  const loaded = await apiJson(backendUrl, `/api/v1/pipelines/${encodeURIComponent(pipeline.uuid)}`, { token });
  if (isApiFailure(loaded) || !loaded.json.data?.pipeline) {
    return {
      status: "fail",
      reason: loaded.json.msg || "Failed to load pipeline.",
      get_status: loaded.status,
      pipeline_id: pipeline.uuid,
      model_count: models.length,
    };
  }
  pipeline = loaded.json.data.pipeline;

  const config = pipeline.config && typeof pipeline.config === "object" ? pipeline.config : {};
  const ai = config.ai && typeof config.ai === "object" ? config.ai : {};
  const runnerConfig = ai.runner_config && typeof ai.runner_config === "object" ? ai.runner_config : {};
  const rawExistingLocalAgentConfig = runnerConfig[runnerId] && typeof runnerConfig[runnerId] === "object"
    ? runnerConfig[runnerId]
    : {};
  const existingLocalAgentConfig = rawExistingLocalAgentConfig;
  const existingModel = existingLocalAgentConfig.model && typeof existingLocalAgentConfig.model === "object"
    ? existingLocalAgentConfig.model
    : {};
  const requestedModelId = env.LANGBOT_LOCAL_AGENT_MODEL_UUID || env.LANGBOT_E2E_MODEL_UUID || "";
  const selectedModelId = requestedModelId || existingModel.primary || selectedModel?.uuid || "";
  const localAgentConfig = {
    timeout: 300,
    prompt: [{ role: "system", content: "You are a helpful assistant." }],
    "remove-think": false,
    "knowledge-bases": [],
    "retrieval-top-k": 5,
    "rerank-model": "",
    "rerank-top-k": 5,
    "max-tool-iterations": 20,
    "tool-execution-mode": "parallel",
    "max-tool-result-chars": 20000,
    "context-history-fetch-limit": 50,
    "context-window-tokens": 200000,
    "context-reserve-tokens": 16384,
    "context-keep-recent-tokens": 20000,
    "context-summary-tokens": 8000,
    ...existingLocalAgentConfig,
    model: {
      primary: selectedModelId,
      fallbacks: requestedModelId ? [] : Array.isArray(existingModel.fallbacks) ? existingModel.fallbacks : [],
    },
  };
  const updatedConfig = {
    ...config,
    ai: {
      ...ai,
      runner: {
        ...(ai.runner && typeof ai.runner === "object" ? ai.runner : {}),
        id: runnerId,
        "expire-time": 0,
      },
      runner_config: {
        ...runnerConfig,
        [runnerId]: localAgentConfig,
      },
    },
  };

  const updateResponse = await apiJson(backendUrl, `/api/v1/pipelines/${encodeURIComponent(pipeline.uuid)}`, {
    method: "PUT",
    token,
    body: {
      name: pipelineName,
      description: "Local QA pipeline for AgentRunner Debug Chat smoke tests.",
      emoji: "QA",
      config: updatedConfig,
    },
  });
  if (isApiFailure(updateResponse)) {
    return {
      status: "fail",
      reason: updateResponse.json.msg || "Failed to update pipeline config.",
      update_status: updateResponse.status,
      pipeline_id: pipeline.uuid,
      model_count: models.length,
      selected_model_id: selectedModelId,
    };
  }

  return {
    status: selectedModelId ? "pass" : "env_issue",
    reason: selectedModelId
      ? "Local-agent pipeline is configured for Debug Chat."
      : "Pipeline was created but no LLM model is configured in this LangBot instance.",
    pipeline_id: pipeline.uuid,
    pipeline_name: pipeline.name,
    model_count: models.length,
    selected_model_id: selectedModelId,
    created,
    updated: true,
  };
}

function isApiFailure(response) {
  return response.status >= 400 || (response.json.code !== undefined && response.json.code !== 0);
}

async function upsertEnvLocal(path, updates) {
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
    const equals = trimmed.indexOf("=");
    if (equals <= 0 || trimmed.startsWith("#")) return line;
    const key = trimmed.slice(0, equals).trim();
    if (!(key in updates)) return line;
    seen.add(key);
    return `${key}=${updates[key]}`;
  });
  for (const [key, value] of Object.entries(updates)) {
    if (!seen.has(key)) next.push(`${key}=${value}`);
  }
  await writeFile(path, `${next.filter((line, index) => line !== "" || index < next.length - 1).join("\n")}\n`, "utf8");
}
