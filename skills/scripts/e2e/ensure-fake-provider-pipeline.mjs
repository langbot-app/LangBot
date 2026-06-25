#!/usr/bin/env node

import { spawn } from "node:child_process";
import { open, readFile, mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { env } from "node:process";
import {
  apiJson,
  ensureEvidence,
  evidencePaths,
  loadEnvFiles,
  redact,
  resetAndAuthLocalUser,
  writeResult,
} from "./lib/langbot-e2e.mjs";

const RUNNER_ID = "local-agent";
const DEFAULT_LOCAL_PASSWORD = "LangBotE2ELocalPass!2026";
const DEFAULT_PIPELINE_NAME = "Agent QA Fake Provider Debug Chat";
const DEFAULT_PROVIDER_NAME = "LangBot QA Fake OpenAI Provider";
const DEFAULT_MODEL_NAME = "gpt-4o-mini";
const DEFAULT_REQUESTER = "openai-chat-completions";

const caseId = "ensure-fake-provider-pipeline";

await loadEnvFiles();
const paths = evidencePaths(caseId);
await ensureEvidence(paths);

const writeEnv = process.argv.includes("--write-env");
const frontendUrl = env.LANGBOT_FRONTEND_URL || "";
const backendUrl = env.LANGBOT_BACKEND_URL || "";
const envLocalPath = resolve("skills/.env.local");
const repoRoot = resolve(env.LANGBOT_REPO || "..");
const fakeStateDir = resolve(env.LANGBOT_FAKE_PROVIDER_STATE_DIR || resolve(repoRoot, ".qa/fake-provider"));
const fakeStatePath = resolve(fakeStateDir, "state.json");
const fakeStdoutPath = resolve(fakeStateDir, "fake-provider.stdout.log");
const fakeStderrPath = resolve(fakeStateDir, "fake-provider.stderr.log");
const pipelineName = env.LANGBOT_FAKE_PROVIDER_PIPELINE_NAME || DEFAULT_PIPELINE_NAME;
const providerName = env.LANGBOT_FAKE_PROVIDER_NAME || DEFAULT_PROVIDER_NAME;
const requester = env.LANGBOT_FAKE_PROVIDER_REQUESTER || DEFAULT_REQUESTER;
const modelName = env.LANGBOT_FAKE_PROVIDER_MODEL_NAME || DEFAULT_MODEL_NAME;

const result = {
  source: "automation",
  case_id: caseId,
  run_id: paths.runId,
  status: "fail",
  reason: "",
  frontend_url: frontendUrl,
  backend_url: backendUrl,
  fake_provider: {
    url: "",
    base_url: "",
    pid: null,
    reused: false,
    state_file: fakeStatePath,
    stdout_log: fakeStdoutPath,
    stderr_log: fakeStderrPath,
  },
  provider: {
    uuid: "",
    name: providerName,
    requester,
    created: false,
    updated: false,
  },
  model: {
    uuid: "",
    name: modelName,
    created: false,
    updated: false,
    test_status: "not_run",
    test_reason: "",
  },
  pipeline_id: "",
  pipeline_name: pipelineName,
  pipeline_url: "",
  created: false,
  updated: false,
  wrote_env: false,
  evidence: {
    console_log: paths.consoleLog,
    network_log: paths.networkLog,
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["api_diagnostic", "network", "filesystem"],
};

try {
  if (!backendUrl) {
    result.status = "env_issue";
    throw new Error("LANGBOT_BACKEND_URL is not configured.");
  }
  if (!frontendUrl) {
    result.status = "env_issue";
    throw new Error("LANGBOT_FRONTEND_URL is not configured.");
  }

  const fakeProvider = await ensureFakeProvider();
  result.fake_provider = {
    ...result.fake_provider,
    ...fakeProvider,
  };

  const user = env.LANGBOT_E2E_LOGIN_USER || "";
  const password = env.LANGBOT_E2E_LOGIN_PASSWORD || DEFAULT_LOCAL_PASSWORD;
  if (!user) {
    result.status = "env_issue";
    throw new Error("LANGBOT_E2E_LOGIN_USER is required so this setup can create/update the fake provider pipeline.");
  }

  const auth = await resetAndAuthLocalUser({ backendUrl, user, password });
  const wizard = await skipWizard({ backendUrl, token: auth.token });
  if (wizard.status !== "pass") {
    result.status = "fail";
    throw new Error(wizard.reason || "Failed to mark the local QA wizard as skipped.");
  }

  const provider = await ensureProvider({
    backendUrl,
    token: auth.token,
    name: providerName,
    requester,
    baseUrl: fakeProvider.base_url,
  });
  result.provider = provider;

  const model = await ensureModel({
    backendUrl,
    token: auth.token,
    providerUuid: provider.uuid,
    name: modelName,
  });
  result.model = model;

  const pipeline = await ensurePipeline({
    backendUrl,
    token: auth.token,
    name: pipelineName,
    modelUuid: model.uuid,
  });
  Object.assign(result, pipeline);
  result.pipeline_url = `${frontendUrl.replace(/\/$/, "")}/home/pipelines?id=${encodeURIComponent(pipeline.pipeline_id)}`;

  if (writeEnv) {
    await upsertEnvLocal(envLocalPath, {
      LANGBOT_E2E_LOGIN_USER: user,
      LANGBOT_FAKE_PROVIDER_URL: fakeProvider.url,
      LANGBOT_FAKE_PROVIDER_BASE_URL: fakeProvider.base_url,
      LANGBOT_FAKE_PROVIDER_PID: fakeProvider.pid ? String(fakeProvider.pid) : "",
      LANGBOT_FAKE_PROVIDER_PROVIDER_UUID: provider.uuid,
      LANGBOT_FAKE_PROVIDER_MODEL_UUID: model.uuid,
      LANGBOT_FAKE_PROVIDER_PIPELINE_URL: result.pipeline_url,
      LANGBOT_FAKE_PROVIDER_PIPELINE_NAME: pipelineName,
    });
    result.wrote_env = true;
  }

  result.status = "pass";
  result.reason = `Fake provider pipeline is configured with ${requester}/${modelName}.`;
} catch (error) {
  result.status = result.status === "env_issue" ? "env_issue" : "fail";
  result.reason = result.reason || safeReason(error.message);
} finally {
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(result.status === "pass" ? 0 : result.status === "env_issue" ? 2 : 1);

async function ensureFakeProvider() {
  const envUrl = normalizeProviderRootUrl(env.LANGBOT_FAKE_PROVIDER_URL || "");
  if (envUrl && await fakeProviderHealthy(envUrl)) {
    return {
      url: envUrl,
      base_url: `${envUrl}/v1`,
      pid: null,
      reused: true,
    };
  }

  const state = await readState(fakeStatePath);
  const stateUrl = normalizeProviderRootUrl(state.url || "");
  if (stateUrl && await fakeProviderHealthy(stateUrl)) {
    return {
      url: stateUrl,
      base_url: state.base_url || `${stateUrl}/v1`,
      pid: Number.isInteger(state.pid) ? state.pid : null,
      reused: true,
    };
  }

  await mkdir(fakeStateDir, { recursive: true });
  await writeFile(fakeStatePath, `${JSON.stringify({ status: "starting", started_at: new Date().toISOString() }, null, 2)}\n`, "utf8");
  const stdout = await open(fakeStdoutPath, "a");
  const stderr = await open(fakeStderrPath, "a");
  const scriptPath = resolve("scripts/e2e/fake-openai-provider.mjs");
  const host = env.LANGBOT_FAKE_PROVIDER_HOST || "127.0.0.1";
  const port = env.LANGBOT_FAKE_PROVIDER_PORT || "0";
  const child = spawn(process.execPath, [
    scriptPath,
    `--host=${host}`,
    `--port=${port}`,
    `--state-file=${fakeStatePath}`,
  ], {
    cwd: resolve("."),
    detached: true,
    env: {
      ...env,
      LANGBOT_FAKE_PROVIDER_MODEL_NAME: modelName,
    },
    stdio: ["ignore", stdout.fd, stderr.fd],
  });
  child.unref();
  await stdout.close();
  await stderr.close();

  const started = await waitForFakeProviderState(fakeStatePath, child.pid, 10_000);
  if (!started.url || !await fakeProviderHealthy(started.url)) {
    throw new Error(`Fake provider did not become healthy. See ${fakeStderrPath}`);
  }

  return {
    url: started.url,
    base_url: started.base_url || `${started.url}/v1`,
    pid: child.pid ?? started.pid ?? null,
    reused: false,
  };
}

async function fakeProviderHealthy(rootUrl) {
  try {
    const response = await fetch(`${rootUrl.replace(/\/$/, "")}/healthz`, {
      signal: AbortSignal.timeout(2000),
    });
    if (!response.ok) return false;
    const json = await response.json().catch(() => ({}));
    return json.ok === true;
  } catch {
    return false;
  }
}

async function waitForFakeProviderState(path, expectedPid, timeoutMs) {
  const startedAt = Date.now();
  let lastState = {};
  while (Date.now() - startedAt < timeoutMs) {
    const state = await readState(path);
    if (state.url && (!expectedPid || state.pid === expectedPid)) return state;
    lastState = state;
    await sleep(150);
  }
  return lastState;
}

async function readState(path) {
  try {
    return JSON.parse(await readFile(path, "utf8"));
  } catch {
    return {};
  }
}

function normalizeProviderRootUrl(value) {
  const trimmed = String(value || "").trim().replace(/\/$/, "");
  return trimmed.endsWith("/v1") ? trimmed.slice(0, -3) : trimmed;
}

async function skipWizard({ backendUrl, token }) {
  const response = await apiJson(backendUrl, "/api/v1/system/wizard/completed", {
    method: "POST",
    token,
    body: { status: "skipped" },
  });
  const ok = response.status < 400 && response.json.code === 0;
  return {
    status: ok ? "pass" : "fail",
    http_status: response.status,
    code: response.json.code ?? null,
    reason: ok ? "Wizard marked skipped for local QA." : response.json.msg || "Wizard status update failed.",
  };
}

async function ensureProvider({ backendUrl, token, name, requester, baseUrl }) {
  const list = await apiJson(backendUrl, "/api/v1/provider/providers", { token });
  if (isApiFailure(list)) {
    throw new Error(list.json.msg || "Failed to list providers.");
  }
  const providers = list.json.data?.providers || [];
  const existing = providers.find((provider) => (
    provider.name === name
      || (provider.requester === requester && String(provider.base_url || "").replace(/\/$/, "") === baseUrl.replace(/\/$/, ""))
  ));
  const body = {
    name,
    requester,
    base_url: baseUrl,
    api_keys: [env.LANGBOT_FAKE_PROVIDER_API_KEY || "langbot-fake-provider-key"],
  };

  if (existing?.uuid) {
    const update = await apiJson(backendUrl, `/api/v1/provider/providers/${encodeURIComponent(existing.uuid)}`, {
      method: "PUT",
      token,
      body,
    });
    if (isApiFailure(update)) {
      throw new Error(update.json.msg || "Failed to update fake provider.");
    }
    return {
      uuid: existing.uuid,
      name,
      requester,
      created: false,
      updated: true,
    };
  }

  const create = await apiJson(backendUrl, "/api/v1/provider/providers", {
    method: "POST",
    token,
    body,
  });
  const uuid = create.json.data?.uuid || "";
  if (isApiFailure(create) || !uuid) {
    throw new Error(create.json.msg || "Failed to create fake provider.");
  }
  return {
    uuid,
    name,
    requester,
    created: true,
    updated: false,
  };
}

async function ensureModel({ backendUrl, token, providerUuid, name }) {
  const list = await apiJson(backendUrl, `/api/v1/provider/models/llm?provider_uuid=${encodeURIComponent(providerUuid)}`, { token });
  if (isApiFailure(list)) {
    throw new Error(list.json.msg || "Failed to list fake provider models.");
  }
  const models = list.json.data?.models || [];
  const existing = models.find((model) => model.name === name);
  const body = {
    name,
    provider_uuid: providerUuid,
    abilities: [],
    context_length: positiveInteger(env.LANGBOT_FAKE_PROVIDER_CONTEXT_LENGTH, 8192),
    extra_args: {},
    prefered_ranking: 0,
  };
  let modelUuid = existing?.uuid || "";
  let created = false;
  let updated = false;

  if (modelUuid) {
    const update = await apiJson(backendUrl, `/api/v1/provider/models/llm/${encodeURIComponent(modelUuid)}`, {
      method: "PUT",
      token,
      body,
    });
    if (isApiFailure(update)) {
      throw new Error(update.json.msg || "Failed to update fake provider model.");
    }
    updated = true;
  } else {
    const create = await apiJson(backendUrl, "/api/v1/provider/models/llm", {
      method: "POST",
      token,
      body,
    });
    modelUuid = create.json.data?.uuid || "";
    if (isApiFailure(create) || !modelUuid) {
      throw new Error(create.json.msg || "Failed to create fake provider model.");
    }
    created = true;
  }

  const test = await apiJson(backendUrl, `/api/v1/provider/models/llm/${encodeURIComponent(modelUuid)}/test`, {
    method: "POST",
    token,
    body: { extra_args: {} },
  });
  if (isApiFailure(test)) {
    throw new Error(safeReason(test.json.msg || test.json.message || "Fake provider model test failed."));
  }

  return {
    uuid: modelUuid,
    name,
    created,
    updated,
    test_status: "pass",
    test_reason: "",
  };
}

async function ensurePipeline({ backendUrl, token, name, modelUuid }) {
  const list = await apiJson(backendUrl, "/api/v1/pipelines", { token });
  if (isApiFailure(list)) {
    throw new Error(list.json.msg || "Failed to list pipelines.");
  }
  const pipelines = list.json.data?.pipelines || [];
  let pipeline = pipelines.find((item) => item.name === name) || null;
  let created = false;

  if (!pipeline) {
    const create = await apiJson(backendUrl, "/api/v1/pipelines", {
      method: "POST",
      token,
      body: {
        name,
        description: "Local QA pipeline for controlled fake-provider Debug Chat load tests.",
        emoji: "QA",
      },
    });
    const pipelineId = create.json.data?.uuid || "";
    if (isApiFailure(create) || !pipelineId) {
      throw new Error(create.json.msg || "Failed to create fake provider pipeline.");
    }
    created = true;
    pipeline = { uuid: pipelineId };
  }

  const loaded = await apiJson(backendUrl, `/api/v1/pipelines/${encodeURIComponent(pipeline.uuid)}`, { token });
  pipeline = loaded.json.data?.pipeline || null;
  if (isApiFailure(loaded) || !pipeline?.uuid) {
    throw new Error(loaded.json.msg || "Failed to load fake provider pipeline.");
  }

  const config = pipeline.config && typeof pipeline.config === "object" ? pipeline.config : {};
  const ai = config.ai && typeof config.ai === "object" ? config.ai : {};
  const existingLocalAgentConfig = ai["local-agent"] && typeof ai["local-agent"] === "object"
    ? ai["local-agent"]
    : {};
  const localAgentConfig = {
    timeout: 60,
    prompt: [{ role: "system", content: "You are a deterministic QA assistant. Reply exactly as instructed." }],
    "remove-think": false,
    "knowledge-bases": [],
    "box-session-id-template": "{launcher_type}_{launcher_id}",
    "retrieval-top-k": 5,
    "rerank-model": "",
    "rerank-top-k": 5,
    "max-tool-iterations": 20,
    "tool-execution-mode": "parallel",
    "max-tool-result-chars": 20000,
    "context-history-fetch-limit": 20,
    "context-window-tokens": 8192,
    "context-reserve-tokens": 1024,
    "context-keep-recent-tokens": 2048,
    "context-summary-tokens": 1024,
    ...existingLocalAgentConfig,
    // Current backend truncation still reads this field directly.
    "max-round": positiveInteger(existingLocalAgentConfig["max-round"], 10),
    model: {
      primary: modelUuid,
      fallbacks: [],
    },
  };
  const updatedConfig = {
    ...config,
    ai: {
      ...ai,
      runner: {
        ...(ai.runner && typeof ai.runner === "object" ? ai.runner : {}),
        id: RUNNER_ID,
        runner: RUNNER_ID,
        "expire-time": 0,
      },
      "local-agent": localAgentConfig,
    },
  };

  const update = await apiJson(backendUrl, `/api/v1/pipelines/${encodeURIComponent(pipeline.uuid)}`, {
    method: "PUT",
    token,
    body: {
      name,
      description: "Local QA pipeline for controlled fake-provider Debug Chat load tests.",
      emoji: "QA",
      config: updatedConfig,
    },
  });
  if (isApiFailure(update)) {
    throw new Error(update.json.msg || "Failed to update fake provider pipeline.");
  }

  return {
    pipeline_id: pipeline.uuid,
    pipeline_name: name,
    created,
    updated: true,
  };
}

function isApiFailure(response) {
  return response.status >= 400 || (response.json.code !== undefined && response.json.code !== 0);
}

function positiveInteger(value, fallback) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function safeReason(value) {
  return redact(String(value || "")).slice(0, 1000);
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
