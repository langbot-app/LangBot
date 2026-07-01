#!/usr/bin/env node

import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { env } from "node:process";
import {
  apiJson,
  ensureEvidence,
  evidencePaths,
  loadEnvFiles,
  resetAndAuthLocalUser,
  writeResult,
} from "./lib/langbot-e2e.mjs";

const caseId = env.LBS_CASE_ID || "install-qa-plugin-smoke";
const paths = evidencePaths(caseId);
await loadEnvFiles();
await ensureEvidence(paths);

const backendUrl = env.LANGBOT_BACKEND_URL || "";
const user = env.LANGBOT_E2E_LOGIN_USER || "";
const password = env.LANGBOT_E2E_LOGIN_PASSWORD || "LangBotE2ELocalPass!2026";
const packagePath = resolve(
  env.LANGBOT_E2E_PLUGIN_PACKAGE
    || env.LANGBOT_QA_PLUGIN_SMOKE_PACKAGE
    || "skills/langbot-testing/fixtures/plugins/qa-plugin-smoke/dist/qa-plugin-smoke-0.1.0.lbpkg",
);
const expectedPluginId = env.LANGBOT_E2E_EXPECTED_PLUGIN_ID || "qa/plugin-smoke";
const expectedTools = (env.LANGBOT_E2E_EXPECTED_TOOLS || env.LANGBOT_E2E_EXPECTED_TOOL || (
  expectedPluginId === "qa/plugin-smoke" ? "qa_plugin_echo" : ""
))
  .split(",")
  .map((item) => item.trim())
  .filter(Boolean);
const expectedRunnerId = env.LANGBOT_E2E_EXPECTED_RUNNER_ID || "";

const result = {
  source: "automation",
  case_id: caseId,
  run_id: paths.runId,
  status: "fail",
  reason: "",
  backend_url: backendUrl,
  package_path: packagePath,
  package_preview: null,
  task_id: null,
  task: null,
  reinstall_reason: "",
  plugin_present_before: false,
  plugin_present_after: false,
  tool_names: [],
  runner_ids: [],
  evidence: {
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["api_diagnostic", "filesystem"],
};

try {
  if (!backendUrl) throw new Error("LANGBOT_BACKEND_URL is not configured.");
  if (!user) throw new Error("LANGBOT_E2E_LOGIN_USER is required.");
  const bytes = await readFile(packagePath);

  const auth = await resetAndAuthLocalUser({ backendUrl, user, password });
  result.package_preview = await previewPackage(backendUrl, auth.token, bytes, packagePath);
  const metadata = result.package_preview.metadata || {};
  if (`${metadata.author}/${metadata.name}` !== expectedPluginId) {
    throw new Error(`Fixture package metadata is ${metadata.author}/${metadata.name}, expected ${expectedPluginId}.`);
  }
  result.plugin_present_before = await hasPlugin(backendUrl, auth.token);

  if (expectedTools.length > 0) {
    result.tool_names = await listToolNames(backendUrl, auth.token);
  }
  const missingToolsBefore = expectedTools.filter((tool) => !result.tool_names.includes(tool));
  if (result.plugin_present_before && missingToolsBefore.length > 0) {
    result.reinstall_reason = `Installed plugin is missing expected tools: ${missingToolsBefore.join(", ")}`;
    const removeTask = await removePlugin(backendUrl, auth.token);
    if (!isTaskComplete(removeTask)) {
      throw new Error(`Plugin reinstall cleanup did not complete successfully: ${JSON.stringify(removeTask)}`);
    }
    result.plugin_present_before = false;
    await sleep(1000);
  }

  if (!result.plugin_present_before) {
    result.task = await installPlugin(backendUrl, auth.token, bytes, packagePath);
    result.task_id = result.task?.id || result.task_id;
    if (!isTaskComplete(result.task)) {
      throw new Error(`Plugin install task did not complete successfully: ${JSON.stringify(result.task)}`);
    }
  }

  await sleep(1000);
  result.plugin_present_after = await hasPlugin(backendUrl, auth.token);
  if (!result.plugin_present_after) throw new Error(`${expectedPluginId} is not listed by /api/v1/plugins after install.`);
  if (expectedTools.length > 0) {
    result.tool_names = await listToolNames(backendUrl, auth.token);
    const missingTools = expectedTools.filter((tool) => !result.tool_names.includes(tool));
    if (missingTools.length > 0) {
      throw new Error(`${missingTools.join(", ")} is not listed by /api/v1/tools after install.`);
    }
  }
  if (expectedRunnerId) {
    result.runner_ids = await listRunnerIds(backendUrl, auth.token);
    if (!result.runner_ids.includes(expectedRunnerId)) {
      throw new Error(`${expectedRunnerId} is not listed by /api/v1/pipelines/_/metadata after install.`);
    }
  }

  result.status = "pass";
  result.reason = `${expectedPluginId} is installed.`;
} catch (error) {
  result.status = "fail";
  result.reason = error.message;
} finally {
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(result.status === "pass" ? 0 : 1);

async function hasPlugin(backendUrl, token) {
  const response = await apiJson(backendUrl, "/api/v1/plugins", { token });
  const plugins = response.json.data?.plugins || [];
  return plugins.some((plugin) => {
    const metadata = plugin.manifest?.manifest?.metadata || plugin.manifest?.metadata || plugin.metadata || {};
    return `${metadata.author}/${metadata.name}` === expectedPluginId;
  });
}

async function installPlugin(backendUrl, token, bytes, packagePath) {
  const form = new FormData();
  form.set("file", new Blob([bytes]), packagePath.split("/").pop());
  const response = await fetch(`${backendUrl.replace(/\/$/, "")}/api/v1/plugins/install/local`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  const json = await response.json().catch(() => ({}));
  if (response.status >= 400 || json.code !== 0) {
    throw new Error(json.msg || `Plugin install request failed with HTTP ${response.status}.`);
  }
  const taskId = json.data?.task_id ?? null;
  if (!taskId) throw new Error("Plugin install response did not include task_id.");
  const task = await waitForTask(backendUrl, token, taskId);
  return { id: taskId, ...task };
}

async function removePlugin(backendUrl, token) {
  const [author, pluginName] = expectedPluginId.split("/");
  if (!author || !pluginName) throw new Error(`Invalid expected plugin id: ${expectedPluginId}`);
  const response = await apiJson(
    backendUrl,
    `/api/v1/plugins/${encodeURIComponent(author)}/${encodeURIComponent(pluginName)}?delete_data=false`,
    { method: "DELETE", token },
  );
  if (response.status >= 400 || response.json.code !== 0) {
    throw new Error(response.json.msg || `Plugin delete request failed with HTTP ${response.status}.`);
  }
  const taskId = response.json.data?.task_id ?? null;
  if (!taskId) throw new Error("Plugin delete response did not include task_id.");
  const task = await waitForTask(backendUrl, token, taskId);
  return { id: taskId, ...task };
}

async function previewPackage(backendUrl, token, bytes, packagePath) {
  const form = new FormData();
  form.set("file", new Blob([bytes]), packagePath.split("/").pop());
  const response = await fetch(`${backendUrl.replace(/\/$/, "")}/api/v1/plugins/install/local/preview`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  const json = await response.json().catch(() => ({}));
  if (response.status >= 400 || json.code !== 0) {
    throw new Error(json.msg || `Plugin package preview failed with HTTP ${response.status}.`);
  }
  return {
    metadata: json.data?.metadata || {},
    component_types: json.data?.component_types || [],
    file_count: json.data?.file_count ?? null,
  };
}

async function listToolNames(backendUrl, token) {
  const response = await apiJson(backendUrl, "/api/v1/tools", { token });
  return (response.json.data?.tools || [])
    .map((tool) => tool.name || tool.tool_name || tool.function?.name || "")
    .filter(Boolean)
    .sort();
}

async function listRunnerIds(backendUrl, token) {
  const response = await apiJson(backendUrl, "/api/v1/pipelines/_/metadata", { token });
  const configs = response.json.data?.configs || [];
  return configs
    .flatMap((section) => section.stages || [])
    .flatMap((stage) => stage.config || [])
    .filter((item) => item.name === "id")
    .flatMap((item) => item.options || [])
    .map((option) => option.name || option.value || option.id || "")
    .filter(Boolean)
    .sort();
}

async function waitForTask(backendUrl, token, taskId) {
  const deadline = Date.now() + Number(env.LANGBOT_PLUGIN_INSTALL_TIMEOUT_MS || 120000);
  let last = null;
  while (Date.now() < deadline) {
    const response = await apiJson(backendUrl, `/api/v1/system/tasks/${encodeURIComponent(taskId)}`, { token });
    last = response.json.data || response.json;
    if (isTaskComplete(last) || isTaskFailed(last)) return last;
    await sleep(1000);
  }
  return last;
}

function isTaskComplete(task) {
  const status = String(task?.status || task?.state || "").toLowerCase();
  const runtimeStatus = String(task?.runtime?.status || task?.runtime?.state || "").toLowerCase();
  return ["done", "completed", "success", "succeeded", "finished"].includes(status)
    || ["done", "completed", "success", "succeeded", "finished"].includes(runtimeStatus)
    || task?.done === true
    || task?.completed === true
    || (task?.runtime?.done === true && !task?.runtime?.exception);
}

function isTaskFailed(task) {
  const status = String(task?.status || task?.state || "").toLowerCase();
  const runtimeStatus = String(task?.runtime?.status || task?.runtime?.state || "").toLowerCase();
  return ["failed", "error", "cancelled", "canceled"].includes(status)
    || ["failed", "error", "cancelled", "canceled"].includes(runtimeStatus)
    || task?.failed === true
    || Boolean(task?.error)
    || Boolean(task?.runtime?.exception);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
