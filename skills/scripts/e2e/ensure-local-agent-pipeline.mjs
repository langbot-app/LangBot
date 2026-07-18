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

const RUNNER_ID = "plugin:langbot-team/LocalAgent/default";
const SPACE_PROVIDER_UUID = "00000000-0000-0000-0000-000000000000";
const DEFAULT_PIPELINE_NAME = "Agent QA Local Agent Debug Chat";
const DEFAULT_LOCAL_PASSWORD = "LangBotE2ELocalPass!2026";
const DEFAULT_MODEL_TEST_LIMIT = 8;
const DEFAULT_MODEL_FALLBACK_COUNT = 3;
const DEFAULT_FAKE_MODEL_UUID = "langbot-e2e-fake-local-agent-model";
const DEFAULT_FAKE_PROVIDER_NAME = "LangBot E2E Fake OpenAI Provider";
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
  fake_provider: null,
  model_count: 0,
  space_model_count: 0,
  scanned_space_model_count: 0,
  tested_model_count: 0,
  model_tests: [],
  plugin_setup: null,
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

  const pluginSetup = await ensureLocalAgentRunner({
    backendUrl,
    token: auth.token,
  });
  result.plugin_setup = pluginSetup;
  if (pluginSetup.status !== "pass") {
    result.status = pluginSetup.status === "env_issue" ? "env_issue" : "fail";
    throw new Error(pluginSetup.reason || "Failed to prepare the LocalAgent runner plugin.");
  }

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

async function ensureLocalAgentRunner({ backendUrl, token }) {
  const [author, name] = RUNNER_ID.replace(/^plugin:/, "").split("/");
  const existingRunnerIds = await listRunnerIds(backendUrl, token);
  if (existingRunnerIds.includes(RUNNER_ID)) {
    return {
      status: "pass",
      reason: "LocalAgent runner is already registered.",
      plugin_id: `${author}/${name}`,
      runner_id: RUNNER_ID,
      installed: false,
    };
  }

  const pluginsResponse = await apiJson(backendUrl, "/api/v1/plugins", {
    token,
  });
  if (isApiFailure(pluginsResponse)) {
    return {
      status: "env_issue",
      reason:
        pluginsResponse.json.msg ||
        "Failed to inspect installed plugins before preparing LocalAgent.",
    };
  }
  const pluginId = `${author}/${name}`;
  const pluginPresent = (pluginsResponse.json.data?.plugins || []).some(
    (plugin) => {
      const metadata =
        plugin.manifest?.manifest?.metadata ||
        plugin.manifest?.metadata ||
        plugin.metadata ||
        {};
      return `${metadata.author}/${metadata.name}` === pluginId;
    },
  );
  if (pluginPresent) {
    const registered = await waitForRunnerRegistration({
      backendUrl,
      token,
      runnerId: RUNNER_ID,
      timeoutMs: 30_000,
    });
    return registered
      ? {
          status: "pass",
          reason: "Installed LocalAgent plugin finished Runner registration.",
          plugin_id: pluginId,
          runner_id: RUNNER_ID,
          installed: false,
        }
      : {
          status: "fail",
          reason: `${pluginId} is installed but ${RUNNER_ID} did not register.`,
          plugin_id: pluginId,
          runner_id: RUNNER_ID,
          installed: false,
        };
  }

  const spaceUrl = String(env.LANGBOT_SPACE_URL || "https://space.langbot.app").replace(
    /\/$/,
    "",
  );
  let detailResponse;
  try {
    detailResponse = await fetch(
      `${spaceUrl}/api/v1/marketplace/plugins/${encodeURIComponent(author)}/${encodeURIComponent(name)}`,
    );
  } catch (error) {
    return {
      status: "env_issue",
      reason: `Could not reach LangBot Space for ${pluginId}: ${error.message}`,
    };
  }
  const detail = await detailResponse.json().catch(() => ({}));
  const version = detail?.data?.plugin?.latest_version || "";
  if (detailResponse.status >= 400 || detail.code !== 0 || !version) {
    return {
      status: "env_issue",
      reason:
        detail.msg ||
        `LangBot Space did not return an installable version for ${pluginId}.`,
    };
  }

  const install = await apiJson(
    backendUrl,
    "/api/v1/plugins/install/marketplace",
    {
      method: "POST",
      token,
      body: {
        plugin_author: author,
        plugin_name: name,
        plugin_version: version,
      },
    },
  );
  const taskId = install.json.data?.task_id ?? null;
  if (isApiFailure(install) || !taskId) {
    return {
      status: "fail",
      reason:
        install.json.msg ||
        `Marketplace install did not create a task for ${pluginId}.`,
      plugin_id: pluginId,
      version,
    };
  }
  const task = await waitForTask({ backendUrl, token, taskId });
  if (!taskComplete(task)) {
    return {
      status: taskFailed(task) ? "fail" : "env_issue",
      reason:
        task?.runtime?.exception ||
        task?.error ||
        `Marketplace install task for ${pluginId} did not complete.`,
      plugin_id: pluginId,
      version,
      task_id: taskId,
    };
  }
  const registered = await waitForRunnerRegistration({
    backendUrl,
    token,
    runnerId: RUNNER_ID,
    timeoutMs: 60_000,
  });
  return registered
    ? {
        status: "pass",
        reason: `Installed ${pluginId} ${version} and registered ${RUNNER_ID}.`,
        plugin_id: pluginId,
        runner_id: RUNNER_ID,
        version,
        task_id: taskId,
        installed: true,
      }
    : {
        status: "fail",
        reason: `Installed ${pluginId} ${version}, but ${RUNNER_ID} did not register.`,
        plugin_id: pluginId,
        runner_id: RUNNER_ID,
        version,
        task_id: taskId,
        installed: true,
      };
}

async function listRunnerIds(backendUrl, token) {
  const response = await apiJson(backendUrl, "/api/v1/pipelines/_/metadata", {
    token,
  });
  if (isApiFailure(response)) return [];
  return (response.json.data?.configs || [])
    .flatMap((section) => section.stages || [])
    .flatMap((stage) => stage.config || [])
    .filter((item) => item.name === "id")
    .flatMap((item) => item.options || [])
    .map((option) => option.name || option.value || option.id || "")
    .filter(Boolean);
}

async function waitForRunnerRegistration({
  backendUrl,
  token,
  runnerId,
  timeoutMs,
}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if ((await listRunnerIds(backendUrl, token)).includes(runnerId)) return true;
    await sleep(1000);
  }
  return false;
}

async function waitForTask({ backendUrl, token, taskId }) {
  const deadline =
    Date.now() + Number(env.LANGBOT_PLUGIN_INSTALL_TIMEOUT_MS || 120_000);
  let task = null;
  while (Date.now() < deadline) {
    const response = await apiJson(
      backendUrl,
      `/api/v1/system/tasks/${encodeURIComponent(taskId)}`,
      { token },
    );
    task = response.json.data || response.json;
    if (taskComplete(task) || taskFailed(task)) return task;
    await sleep(1000);
  }
  return task;
}

function taskComplete(task) {
  const status = String(task?.status || task?.state || "").toLowerCase();
  const runtimeStatus = String(
    task?.runtime?.status || task?.runtime?.state || "",
  ).toLowerCase();
  return (
    ["done", "completed", "success", "succeeded", "finished"].includes(
      status,
    ) ||
    ["done", "completed", "success", "succeeded", "finished"].includes(
      runtimeStatus,
    ) ||
    task?.done === true ||
    task?.completed === true ||
    (task?.runtime?.done === true && !task?.runtime?.exception)
  );
}

function taskFailed(task) {
  const status = String(task?.status || task?.state || "").toLowerCase();
  const runtimeStatus = String(
    task?.runtime?.status || task?.runtime?.state || "",
  ).toLowerCase();
  return (
    ["failed", "error", "cancelled", "canceled"].includes(status) ||
    ["failed", "error", "cancelled", "canceled"].includes(runtimeStatus) ||
    task?.failed === true ||
    Boolean(task?.error) ||
    Boolean(task?.runtime?.exception)
  );
}

function sleep(ms) {
  return new Promise((resolvePromise) => setTimeout(resolvePromise, ms));
}

async function ensureLocalAgentPipeline({
  backendUrl,
  token,
  pipelineName,
  runnerId,
}) {
  // Fake-provider use must be explicit for this pipeline. The generic fake
  // provider variables persist after load tests and must not silently replace
  // a real LocalAgent model in later QA runs.
  const fakeProviderBaseUrl = env.LANGBOT_E2E_FAKE_PROVIDER_BASE_URL || "";
  let fakeModel = null;
  if (fakeProviderBaseUrl) {
    fakeModel = await ensureFakeProviderModel({
      backendUrl,
      token,
      baseUrl: fakeProviderBaseUrl,
    });
    if (fakeModel.status !== "pass") return fakeModel;
  }

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
  const runnerConfigs =
    ai.runner_config && typeof ai.runner_config === "object"
      ? ai.runner_config
      : {};
  const rawExistingLocalAgentConfig =
    runnerConfigs[runnerId] && typeof runnerConfigs[runnerId] === "object"
      ? runnerConfigs[runnerId]
      : {};
  const existingLocalAgentConfig = rawExistingLocalAgentConfig;
  const existingModel =
    existingLocalAgentConfig.model &&
    typeof existingLocalAgentConfig.model === "object"
      ? existingLocalAgentConfig.model
      : {};
  const requestedModelId =
    env.LANGBOT_LOCAL_AGENT_MODEL_UUID || env.LANGBOT_E2E_MODEL_UUID || "";
  const selected = fakeModel
    ? {
        status: "pass",
        reason: "",
        selected_model_id: fakeModel.model_uuid,
        selected_model_name: fakeModel.model_name,
        fallback_model_ids: [],
        scanned_space_model_count: 0,
        tested_model_count: 0,
        model_tests: [],
      }
    : await selectWorkingSpaceModel({
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
        "expire-time": 0,
      },
      runner_config: {
        ...runnerConfigs,
        [runnerId]: localAgentConfig,
      },
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
    fake_provider: fakeModel,
    created,
    updated: true,
  };
}

async function ensureFakeProviderModel({ backendUrl, token, baseUrl }) {
  const modelUuid = env.LANGBOT_E2E_FAKE_MODEL_UUID || DEFAULT_FAKE_MODEL_UUID;
  const modelName =
    env.LANGBOT_E2E_FAKE_MODEL_NAME ||
    env.LANGBOT_FAKE_PROVIDER_MODEL ||
    env.LANGBOT_FAKE_PROVIDER_MODEL_NAME ||
    "langbot-e2e-fake-model";
  const providerName =
    env.LANGBOT_E2E_FAKE_PROVIDER_NAME || DEFAULT_FAKE_PROVIDER_NAME;
  const providerRequester =
    env.LANGBOT_E2E_FAKE_PROVIDER_REQUESTER || "openai-chat-completions";
  const apiKey =
    env.LANGBOT_E2E_FAKE_PROVIDER_API_KEY ||
    env.LANGBOT_FAKE_PROVIDER_API_KEY ||
    "fake-key";

  const providersResponse = await apiJson(
    backendUrl,
    "/api/v1/provider/providers",
    { token },
  );
  if (isApiFailure(providersResponse)) {
    return {
      status: "fail",
      reason:
        providersResponse.json.msg ||
        "Failed to list providers before creating fake provider.",
      provider_status: providersResponse.status,
    };
  }

  const normalizedBaseUrl = String(baseUrl || "").replace(/\/$/, "");
  const providers = providersResponse.json.data?.providers || [];
  let provider = providers.find(
    (item) =>
      item.name === providerName ||
      (item.requester === providerRequester &&
        String(item.base_url || "").replace(/\/$/, "") === normalizedBaseUrl),
  );
  const providerBody = {
    name: providerName,
    requester: providerRequester,
    base_url: normalizedBaseUrl,
    api_keys: [apiKey],
  };

  if (provider?.uuid) {
    const updateResponse = await apiJson(
      backendUrl,
      `/api/v1/provider/providers/${encodeURIComponent(provider.uuid)}`,
      {
        method: "PUT",
        token,
        body: providerBody,
      },
    );
    if (isApiFailure(updateResponse)) {
      return {
        status: "fail",
        reason: updateResponse.json.msg || "Failed to update fake provider.",
        provider_status: updateResponse.status,
      };
    }
  } else {
    const createProviderResponse = await apiJson(
      backendUrl,
      "/api/v1/provider/providers",
      {
        method: "POST",
        token,
        body: providerBody,
      },
    );
    if (isApiFailure(createProviderResponse)) {
      return {
        status: "fail",
        reason:
          createProviderResponse.json.msg || "Failed to create fake provider.",
        provider_status: createProviderResponse.status,
      };
    }
    provider = { uuid: createProviderResponse.json.data?.uuid || "" };
  }

  if (!provider?.uuid) {
    return {
      status: "fail",
      reason: "Fake provider did not return a provider uuid.",
    };
  }

  let resolvedModelUuid = modelUuid;
  let modelResponse = await apiJson(
    backendUrl,
    `/api/v1/provider/models/llm/${encodeURIComponent(modelUuid)}`,
    {
      token,
    },
  );
  if (modelResponse.status === 404) {
    const providerModelsResponse = await apiJson(
      backendUrl,
      `/api/v1/provider/models/llm?provider_uuid=${encodeURIComponent(provider.uuid)}`,
      { token },
    );
    if (!isApiFailure(providerModelsResponse)) {
      const existingModel = (
        providerModelsResponse.json.data?.models || []
      ).find((item) => item.name === modelName);
      if (existingModel?.uuid) {
        resolvedModelUuid = existingModel.uuid;
        modelResponse = await apiJson(
          backendUrl,
          `/api/v1/provider/models/llm/${encodeURIComponent(resolvedModelUuid)}`,
          {
            token,
          },
        );
      }
    }
  }

  const modelBody = {
    name: modelName,
    provider_uuid: provider.uuid,
    abilities: ["func_call", "vision"],
    context_length: 8192,
    extra_args: {},
    prefered_ranking: 0,
  };
  if (modelResponse.status === 404) {
    const createModelResponse = await apiJson(
      backendUrl,
      "/api/v1/provider/models/llm",
      {
        method: "POST",
        token,
        body: {
          uuid: modelUuid,
          ...modelBody,
        },
      },
    );
    if (isApiFailure(createModelResponse)) {
      return {
        status: "fail",
        reason: createModelResponse.json.msg || "Failed to create fake model.",
        model_status: createModelResponse.status,
      };
    }
    resolvedModelUuid = createModelResponse.json.data?.uuid || modelUuid;
  } else if (isApiFailure(modelResponse)) {
    return {
      status: "fail",
      reason: modelResponse.json.msg || "Failed to load fake model.",
      model_status: modelResponse.status,
    };
  } else {
    const updateModelResponse = await apiJson(
      backendUrl,
      `/api/v1/provider/models/llm/${encodeURIComponent(resolvedModelUuid)}`,
      {
        method: "PUT",
        token,
        body: modelBody,
      },
    );
    if (isApiFailure(updateModelResponse)) {
      return {
        status: "fail",
        reason: updateModelResponse.json.msg || "Failed to update fake model.",
        model_status: updateModelResponse.status,
      };
    }
  }

  return {
    status: "pass",
    provider_uuid: provider.uuid,
    provider_requester: providerRequester,
    base_url: normalizedBaseUrl,
    model_uuid: resolvedModelUuid,
    model_name: modelName,
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
