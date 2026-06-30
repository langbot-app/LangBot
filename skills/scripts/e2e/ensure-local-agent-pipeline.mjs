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
  redact,
  resetAndAuthLocalUser,
  safeScreenshot,
  setBrowserToken,
  verifyBrowserToken,
  writeResult,
} from "./lib/langbot-e2e.mjs";

const RUNNER_ID = "local-agent";
const SPACE_PROVIDER_UUID = "00000000-0000-0000-0000-000000000000";
const DEFAULT_PIPELINE_NAME = "Agent QA Local Agent Debug Chat";
const DEFAULT_LOCAL_PASSWORD = "LangBotE2ELocalPass!2026";
const DEFAULT_MODEL_TEST_LIMIT = 8;
const DEFAULT_MODEL_FALLBACK_COUNT = 3;
const caseId = "ensure-local-agent-pipeline";

await loadEnvFiles();
const paths = evidencePaths(caseId);
await ensureEvidence(paths);

const writeEnv = process.argv.includes("--write-env");
const pipelineName =
  env.LANGBOT_E2E_CREATE_PIPELINE_NAME ||
  env.LANGBOT_LOCAL_AGENT_PIPELINE_NAME ||
  DEFAULT_PIPELINE_NAME;
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
  selected_model_name: "",
  fallback_model_ids: [],
  model_count: 0,
  space_model_count: 0,
  scanned_space_model_count: 0,
  tested_model_count: 0,
  model_tests: [],
  created: false,
  updated: false,
  wrote_env: false,
  auth: null,
  wizard: null,
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
    result.status = "env_issue";
    throw new Error(
      "LANGBOT_E2E_LOGIN_USER is required so this setup can create/update the pipeline via backend API.",
    );
  }

  const auth = await resetAndAuthLocalUser({ backendUrl, user, password });
  result.auth = {
    source: "local_recovery_login",
    user,
    backend_token_check: auth.check,
  };

  const wizard = await skipWizard({ backendUrl, token: auth.token });
  result.wizard = wizard;
  if (wizard.status !== "pass") {
    result.status = "fail";
    throw new Error(
      wizard.reason || "Failed to mark the local QA wizard as skipped.",
    );
  }

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
      ...(result.selected_model_id
        ? {
            LANGBOT_LOCAL_AGENT_MODEL_UUID: result.selected_model_id,
            LANGBOT_E2E_MODEL_UUID: result.selected_model_id,
          }
        : {}),
    });
    result.wrote_env = true;
  }

  browser = await createBrowser(paths);
  const { page } = browser;
  await setBrowserToken(page, frontendUrl, auth.token);
  const browserCheck = await verifyBrowserToken(page, backendUrl);
  result.browser_token_check = browserCheck;
  if (!browserCheck.authenticated) {
    throw new Error(
      browserCheck.reason || "Browser token check failed after setup.",
    );
  }
  await page.goto(result.pipeline_url || frontendUrl, {
    waitUntil: "domcontentloaded",
  });
  await page
    .waitForLoadState("networkidle", { timeout: 10_000 })
    .catch(() => {});
  const text = await bodyText(page);
  result.page_signal =
    ["Pipelines", "流水线", pipelineName].find((signal) =>
      text.includes(signal),
    ) || "";
} catch (error) {
  result.status = result.status === "env_issue" ? "env_issue" : "fail";
  result.reason = result.reason || error.message;
} finally {
  if (browser?.page) await safeScreenshot(browser.page, paths.screenshot);
  if (browser) await browser.close().catch(() => {});
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(
  result.status === "pass" ? 0 : result.status === "env_issue" ? 2 : 1,
);

async function skipWizard({ backendUrl, token }) {
  const response = await apiJson(
    backendUrl,
    "/api/v1/system/wizard/completed",
    {
      method: "POST",
      token,
      body: { status: "skipped" },
    },
  );
  const ok = response.status < 400 && response.json.code === 0;
  return {
    status: ok ? "pass" : "fail",
    http_status: response.status,
    code: response.json.code ?? null,
    reason: ok
      ? "Wizard marked skipped for local QA."
      : response.json.msg || "Wizard status update failed.",
  };
}

async function ensureLocalAgentPipeline({
  backendUrl,
  token,
  pipelineName,
  runnerId,
}) {
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
  const skippedModelIds = new Set(
    String(env.LANGBOT_E2E_SKIP_MODEL_UUIDS || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  );
  const skippedModelNames = new Set(
    String(env.LANGBOT_E2E_SKIP_MODEL_NAMES || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  );
  const spaceModels = models.filter(
    (model) => isSpaceModel(model) && !skippedModelIds.has(model.uuid),
  );
  const pipelines = pipelineList.json.data?.pipelines || [];
  let pipeline = pipelines.find((item) => item.name === pipelineName) || null;
  let created = false;

  if (!pipeline) {
    const createdResponse = await apiJson(backendUrl, "/api/v1/pipelines", {
      method: "POST",
      token,
      body: {
        name: pipelineName,
        description:
          "Local QA pipeline for AgentRunner Debug Chat smoke tests.",
        emoji: "QA",
      },
    });
    if (isApiFailure(createdResponse)) {
      return {
        status: "fail",
        reason: createdResponse.json.msg || "Failed to create pipeline.",
        create_status: createdResponse.status,
        model_count: models.length,
        space_model_count: spaceModels.length,
      };
    }
    const pipelineId = createdResponse.json.data?.uuid || "";
    const loaded = await apiJson(
      backendUrl,
      `/api/v1/pipelines/${encodeURIComponent(pipelineId)}`,
      { token },
    );
    pipeline = loaded.json.data?.pipeline || null;
    created = true;
  }

  if (!pipeline?.uuid) {
    return {
      status: "fail",
      reason: "Pipeline was not created or resolved.",
      model_count: models.length,
      space_model_count: spaceModels.length,
    };
  }

  const loaded = await apiJson(
    backendUrl,
    `/api/v1/pipelines/${encodeURIComponent(pipeline.uuid)}`,
    { token },
  );
  if (isApiFailure(loaded) || !loaded.json.data?.pipeline) {
    return {
      status: "fail",
      reason: loaded.json.msg || "Failed to load pipeline.",
      get_status: loaded.status,
      pipeline_id: pipeline.uuid,
      model_count: models.length,
      space_model_count: spaceModels.length,
    };
  }
  pipeline = loaded.json.data.pipeline;

  const config =
    pipeline.config && typeof pipeline.config === "object"
      ? pipeline.config
      : {};
  const ai = config.ai && typeof config.ai === "object" ? config.ai : {};
  const rawExistingLocalAgentConfig =
    ai["local-agent"] && typeof ai["local-agent"] === "object"
      ? ai["local-agent"]
      : {};
  const existingLocalAgentConfig = rawExistingLocalAgentConfig;
  const existingModel =
    existingLocalAgentConfig.model &&
    typeof existingLocalAgentConfig.model === "object"
      ? existingLocalAgentConfig.model
      : {};
  const requestedModelId =
    env.LANGBOT_LOCAL_AGENT_MODEL_UUID || env.LANGBOT_E2E_MODEL_UUID || "";
  const selected = await selectWorkingSpaceModel({
    backendUrl,
    token,
    models,
    skippedModelIds,
    skippedModelNames,
    requestedModelId,
    existingModelId: existingModel.primary || "",
  });
  const selectedModelId = selected.selected_model_id || "";
  const localAgentConfig = {
    timeout: 300,
    prompt: [{ role: "system", content: "You are a helpful assistant." }],
    "remove-think": false,
    "knowledge-bases": [],
    "box-session-id-template": "{launcher_type}_{launcher_id}",
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
    // Current backend truncation still reads this field directly.
    "max-round": positiveInteger(existingLocalAgentConfig["max-round"], 10),
    model: {
      primary: selectedModelId,
      fallbacks: selected.fallback_model_ids || [],
    },
  };
  const updatedConfig = {
    ...config,
    ai: {
      ...ai,
      runner: {
        ...(ai.runner && typeof ai.runner === "object" ? ai.runner : {}),
        id: runnerId,
        runner: runnerId,
        "expire-time": 0,
      },
      "local-agent": localAgentConfig,
    },
  };

  const updateResponse = await apiJson(
    backendUrl,
    `/api/v1/pipelines/${encodeURIComponent(pipeline.uuid)}`,
    {
      method: "PUT",
      token,
      body: {
        name: pipelineName,
        description:
          "Local QA pipeline for AgentRunner Debug Chat smoke tests.",
        emoji: "QA",
        config: updatedConfig,
      },
    },
  );
  if (isApiFailure(updateResponse)) {
    return {
      status: "fail",
      reason: updateResponse.json.msg || "Failed to update pipeline config.",
      update_status: updateResponse.status,
      pipeline_id: pipeline.uuid,
      model_count: models.length,
      space_model_count: spaceModels.length,
      scanned_space_model_count: selected.scanned_space_model_count,
      tested_model_count: selected.tested_model_count,
      model_tests: selected.model_tests,
      selected_model_id: selectedModelId,
      selected_model_name: selected.selected_model_name,
      fallback_model_ids: selected.fallback_model_ids,
    };
  }

  return {
    status: selectedModelId ? "pass" : "env_issue",
    reason: selectedModelId
      ? `Local-agent pipeline is configured for Debug Chat with Space model ${selected.selected_model_name || selectedModelId} and ${selected.fallback_model_ids.length} fallback(s).`
      : selected.reason ||
        "No working Space LLM model is configured in this LangBot instance.",
    pipeline_id: pipeline.uuid,
    pipeline_name: pipelineName,
    model_count: models.length,
    space_model_count: spaceModels.length,
    scanned_space_model_count: selected.scanned_space_model_count,
    tested_model_count: selected.tested_model_count,
    model_tests: selected.model_tests,
    selected_model_id: selectedModelId,
    selected_model_name: selected.selected_model_name,
    fallback_model_ids: selected.fallback_model_ids,
    created,
    updated: true,
  };
}

function isApiFailure(response) {
  return (
    response.status >= 400 ||
    (response.json.code !== undefined && response.json.code !== 0)
  );
}

function isSpaceModel(model) {
  const provider =
    model?.provider && typeof model.provider === "object" ? model.provider : {};
  return (
    model?.provider_uuid === SPACE_PROVIDER_UUID ||
    provider.uuid === SPACE_PROVIDER_UUID ||
    provider.requester === "space-chat-completions" ||
    provider.name === "LangBot Models"
  );
}

async function selectWorkingSpaceModel({
  backendUrl,
  token,
  models,
  skippedModelIds,
  skippedModelNames,
  requestedModelId,
  existingModelId,
}) {
  const modelTests = [];
  const testLimit = positiveInteger(
    env.LANGBOT_E2E_MODEL_TEST_LIMIT,
    DEFAULT_MODEL_TEST_LIMIT,
  );
  const fallbackCount = positiveInteger(
    env.LANGBOT_E2E_MODEL_FALLBACK_COUNT,
    DEFAULT_MODEL_FALLBACK_COUNT,
  );
  const workingModels = [];
  const spaceModels = rankModels(
    models.filter(
      (model) =>
        model.uuid &&
        isSpaceModel(model) &&
        !skippedModelIds.has(model.uuid) &&
        !skippedModelNames.has(model.name),
    ),
  );
  const requestedModel = requestedModelId
    ? spaceModels.find((model) => model.uuid === requestedModelId) || null
    : null;
  const existingModel = existingModelId
    ? spaceModels.find((model) => model.uuid === existingModelId) || null
    : null;
  const candidates = uniqueCandidates([
    ...(requestedModel ? [existingCandidate(requestedModel, "requested")] : []),
    ...(existingModel
      ? [existingCandidate(existingModel, "existing-pipeline")]
      : []),
    ...spaceModels.map((model) => existingCandidate(model, "configured-space")),
  ]);

  let scanResult = { status: "skipped", models: [], reason: "" };
  if (env.LANGBOT_E2E_SCAN_SPACE_MODELS !== "false") {
    scanResult = await scanSpaceModels({ backendUrl, token });
    if (scanResult.status === "pass") {
      const knownNames = new Set(spaceModels.map((model) => model.name));
      candidates.push(
        ...scanResult.models
          .filter(
            (model) =>
              model.name &&
              !knownNames.has(model.name) &&
              !skippedModelNames.has(model.name),
          )
          .map((model) => scannedCandidate(model)),
      );
    }
  }

  const unique = uniqueCandidates(candidates);
  for (const candidate of unique.slice(0, testLimit)) {
    const test = await ensureAndTestModel({ backendUrl, token, candidate });
    modelTests.push(test);
    if (test.status === "pass" && test.model_uuid) {
      workingModels.push(test);
      if (workingModels.length >= fallbackCount + 1) break;
    }
  }

  if (workingModels.length > 0) {
    const [primary, ...fallbacks] = workingModels;
    return {
      status: "pass",
      reason: "",
      selected_model_id: primary.model_uuid,
      selected_model_name: primary.model_name,
      fallback_model_ids: fallbacks.map((model) => model.model_uuid),
      scanned_space_model_count: scanResult.models.length,
      tested_model_count: modelTests.length,
      model_tests: modelTests,
    };
  }

  const baseReason =
    unique.length === 0
      ? scanResult.reason || "No Space LLM model candidates are available."
      : `No working Space LLM model found after testing ${modelTests.length} candidate(s).`;
  return {
    status: "env_issue",
    reason:
      requestedModelId && !requestedModel
        ? `Requested Space LLM model ${requestedModelId} is missing or skipped; ${baseReason}`
        : baseReason,
    selected_model_id: "",
    selected_model_name: "",
    fallback_model_ids: [],
    scanned_space_model_count: scanResult.models.length,
    tested_model_count: modelTests.length,
    model_tests: modelTests,
  };
}

async function scanSpaceModels({ backendUrl, token }) {
  const response = await apiJson(
    backendUrl,
    `/api/v1/provider/providers/${encodeURIComponent(SPACE_PROVIDER_UUID)}/scan-models?type=llm`,
    { token },
  );
  if (isApiFailure(response)) {
    return {
      status: "env_issue",
      models: [],
      reason: safeReason(
        response.json.msg ||
          response.json.message ||
          "Failed to scan Space LLM models.",
      ),
    };
  }
  return {
    status: "pass",
    models: response.json.data?.models || [],
    reason: "",
  };
}

async function ensureAndTestModel({ backendUrl, token, candidate }) {
  let modelUuid = candidate.uuid || "";
  let created = false;
  if (!modelUuid) {
    const create = await apiJson(backendUrl, "/api/v1/provider/models/llm", {
      method: "POST",
      token,
      body: {
        name: candidate.name,
        provider_uuid: SPACE_PROVIDER_UUID,
        abilities: candidate.abilities || [],
        context_length: candidate.context_length ?? null,
        extra_args: {},
        prefered_ranking: positiveInteger(candidate.prefered_ranking, 0),
      },
    });
    modelUuid = create.json.data?.uuid || "";
    if (isApiFailure(create) || !modelUuid) {
      return modelTestResult(candidate, {
        status: "fail",
        reason: safeReason(
          create.json.msg || "Failed to create scanned Space model.",
        ),
        http_status: create.status,
      });
    }
    created = true;
  }

  const test = await apiJson(
    backendUrl,
    `/api/v1/provider/models/llm/${encodeURIComponent(modelUuid)}/test`,
    {
      method: "POST",
      token,
      body: { extra_args: {} },
    },
  );
  const passed = !isApiFailure(test);
  if (!passed && created) {
    await apiJson(
      backendUrl,
      `/api/v1/provider/models/llm/${encodeURIComponent(modelUuid)}`,
      {
        method: "DELETE",
        token,
      },
    ).catch(() => {});
  }
  return modelTestResult(candidate, {
    status: passed ? "pass" : "fail",
    reason: passed
      ? ""
      : safeReason(
          test.json.msg || test.json.message || "Space model test failed.",
        ),
    http_status: test.status,
    model_uuid: modelUuid,
    created,
  });
}

function modelTestResult(candidate, details) {
  return {
    source: candidate.source,
    model_uuid: details.model_uuid || candidate.uuid || "",
    model_name: candidate.name,
    status: details.status,
    reason: details.reason || "",
    http_status: details.http_status ?? null,
    created: Boolean(details.created),
  };
}

function existingCandidate(model, source) {
  return {
    source,
    uuid: model.uuid,
    name: model.name,
    abilities: model.abilities || [],
    context_length: model.context_length,
    prefered_ranking: model.prefered_ranking,
  };
}

function scannedCandidate(model) {
  return {
    source: "scanned-space",
    uuid: "",
    name: model.name || model.id,
    abilities: model.abilities || [],
    context_length: model.context_length,
    prefered_ranking: model.prefered_ranking,
  };
}

function uniqueCandidates(candidates) {
  const seen = new Set();
  const result = [];
  for (const candidate of candidates) {
    const key = candidate.uuid
      ? `uuid:${candidate.uuid}`
      : `name:${candidate.name}`;
    if (!candidate.name || seen.has(key)) continue;
    seen.add(key);
    result.push(candidate);
  }
  return result;
}

function rankModels(models) {
  return [...models].sort((left, right) => {
    const leftRank = Number.isFinite(Number(left.prefered_ranking))
      ? Number(left.prefered_ranking)
      : 9999;
    const rightRank = Number.isFinite(Number(right.prefered_ranking))
      ? Number(right.prefered_ranking)
      : 9999;
    if (leftRank !== rightRank) return leftRank - rightRank;
    return String(left.name || "").localeCompare(String(right.name || ""));
  });
}

function positiveInteger(value, fallback) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

function safeReason(value) {
  return redact(String(value || "")).slice(0, 1000);
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
  await writeFile(
    path,
    `${next.filter((line, index) => line !== "" || index < next.length - 1).join("\n")}\n`,
    "utf8",
  );
}
