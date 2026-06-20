#!/usr/bin/env node

import { readFile, writeFile } from "node:fs/promises";
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

const RUNNER_ID = "plugin:langbot/acp-agent-runner/default";
const DEFAULT_PIPELINE_NAME = "Agent QA ACP Claude Debug Chat";
const DEFAULT_LOCAL_PASSWORD = "LangBotE2ELocalPass!2026";
const caseId = "ensure-acp-agent-runner-pipeline";

await loadEnvFiles();
const paths = evidencePaths(caseId);
await ensureEvidence(paths);

const writeEnv = process.argv.includes("--write-env");
const frontendUrl = env.LANGBOT_FRONTEND_URL || "";
const backendUrl = env.LANGBOT_BACKEND_URL || "";
const pipelineName = env.LANGBOT_E2E_CREATE_PIPELINE_NAME || env.LANGBOT_ACP_AGENT_RUNNER_PIPELINE_NAME || DEFAULT_PIPELINE_NAME;
const sshTarget = env.LANGBOT_ACP_AGENT_RUNNER_SSH_TARGET || "yhh@101.34.71.12";
const sshConnectTimeout = env.LANGBOT_ACP_AGENT_RUNNER_SSH_CONNECT_TIMEOUT || "8";
const sshPort = env.LANGBOT_ACP_AGENT_RUNNER_SSH_PORT || "22";
const sshIdentityFile = env.LANGBOT_ACP_AGENT_RUNNER_SSH_IDENTITY_FILE || "";
const sshExtraOptions = env.LANGBOT_ACP_AGENT_RUNNER_SSH_EXTRA_OPTIONS || "";
const remoteWorkspace = env.LANGBOT_ACP_AGENT_RUNNER_REMOTE_WORKSPACE || "/home/yhh/langbot-e2e/acp-workspace";
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
  ssh_target: sshTarget,
  ssh_port: sshPort,
  remote_workspace: remoteWorkspace,
  wrote_env: false,
  auth: null,
  evidence: {
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["api_diagnostic"],
};

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

  const runnerConfig = {
    provider: "claude-code",
    location: "remote-ssh",
    workspace: remoteWorkspace,
    "ssh-target": sshTarget,
    "ssh-port": Number.parseInt(sshPort, 10),
    "ssh-identity-file": sshIdentityFile,
    "ssh-connect-timeout": Number.parseInt(sshConnectTimeout, 10),
    "ssh-extra-options": sshExtraOptions,
    "langbot-assets-enabled": true,
    "mcp-bridge-request-timeout": 90,
    "reuse-session": false,
    "create-session-if-missing": true,
    "append-run-scope-prompt": true,
    "startup-timeout": 30,
    "initialize-timeout": 120,
    timeout: 300,
  };

  const prepared = await ensurePipeline({
    backendUrl,
    token: auth.token,
    pipelineName,
    runnerId: RUNNER_ID,
    runnerConfig,
  });
  Object.assign(result, prepared);
  if (result.pipeline_id) {
    result.pipeline_url = `${frontendUrl.replace(/\/$/, "")}/home/pipelines?id=${encodeURIComponent(result.pipeline_id)}`;
  }

  if (writeEnv && result.pipeline_id) {
    await upsertEnvLocal(envLocalPath, {
      LANGBOT_E2E_LOGIN_USER: user,
      LANGBOT_ACP_AGENT_RUNNER_SSH_TARGET: sshTarget,
      LANGBOT_ACP_AGENT_RUNNER_SSH_PORT: sshPort,
      LANGBOT_ACP_AGENT_RUNNER_SSH_IDENTITY_FILE: sshIdentityFile,
      LANGBOT_ACP_AGENT_RUNNER_SSH_EXTRA_OPTIONS: sshExtraOptions,
      LANGBOT_ACP_AGENT_RUNNER_REMOTE_WORKSPACE: remoteWorkspace,
      LANGBOT_ACP_AGENT_RUNNER_PIPELINE_URL: result.pipeline_url,
      LANGBOT_ACP_AGENT_RUNNER_PIPELINE_NAME: result.pipeline_name || pipelineName,
    });
    result.wrote_env = true;
  }
} catch (error) {
  result.reason = result.reason || error.message;
} finally {
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(result.status === "pass" ? 0 : result.status === "env_issue" ? 2 : 1);

async function ensurePipeline({ backendUrl, token, pipelineName, runnerId, runnerConfig }) {
  const pipelineList = await apiJson(backendUrl, "/api/v1/pipelines", { token });
  if (isApiFailure(pipelineList)) {
    return {
      status: "fail",
      reason: pipelineList.json.msg || "Failed to list pipelines.",
      list_status: pipelineList.status,
    };
  }

  const pipelines = pipelineList.json.data?.pipelines || [];
  let pipeline = pipelines.find((item) => item.name === pipelineName) || null;
  let created = false;

  if (!pipeline) {
    const createdResponse = await apiJson(backendUrl, "/api/v1/pipelines", {
      method: "POST",
      token,
      body: {
        name: pipelineName,
        description: "Local QA pipeline for real ACP Claude AgentRunner Debug Chat smoke tests.",
        emoji: "QA",
      },
    });
    if (isApiFailure(createdResponse)) {
      return {
        status: "fail",
        reason: createdResponse.json.msg || "Failed to create pipeline.",
        create_status: createdResponse.status,
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
    };
  }

  const loaded = await apiJson(backendUrl, `/api/v1/pipelines/${encodeURIComponent(pipeline.uuid)}`, { token });
  if (isApiFailure(loaded) || !loaded.json.data?.pipeline) {
    return {
      status: "fail",
      reason: loaded.json.msg || "Failed to load pipeline.",
      get_status: loaded.status,
      pipeline_id: pipeline.uuid,
    };
  }
  pipeline = loaded.json.data.pipeline;

  const config = pipeline.config && typeof pipeline.config === "object" ? pipeline.config : {};
  const ai = config.ai && typeof config.ai === "object" ? config.ai : {};
  const runnerConfigs = ai.runner_config && typeof ai.runner_config === "object" ? ai.runner_config : {};
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
        [runnerId]: runnerConfig,
      },
    },
  };

  const updateResponse = await apiJson(backendUrl, `/api/v1/pipelines/${encodeURIComponent(pipeline.uuid)}`, {
    method: "PUT",
    token,
    body: {
      name: pipelineName,
      description: "Local QA pipeline for real ACP Claude AgentRunner Debug Chat smoke tests.",
      emoji: "QA",
      config: updatedConfig,
    },
  });
  if (isApiFailure(updateResponse)) {
    return {
      status: "fail",
      reason: updateResponse.json.msg || "Failed to update pipeline.",
      update_status: updateResponse.status,
      pipeline_id: pipeline.uuid,
    };
  }

  return {
    status: "pass",
    reason: created ? "ACP AgentRunner pipeline created and configured." : "ACP AgentRunner pipeline updated.",
    pipeline_id: pipeline.uuid,
    pipeline_name: pipelineName,
    created,
    updated: true,
  };
}

function isApiFailure(response) {
  return response.status >= 400 || (response.json && response.json.code !== undefined && response.json.code !== 0);
}

async function upsertEnvLocal(path, values) {
  let text = "";
  try {
    text = await readFile(path, "utf8");
  } catch {
    text = "";
  }
  const lines = text.split(/\r?\n/);
  const keys = new Set(Object.keys(values));
  const output = [];
  for (const line of lines) {
    const match = line.match(/^([A-Z][A-Z0-9_]*)=/);
    if (match && keys.has(match[1])) {
      output.push(`${match[1]}=${values[match[1]]}`);
      keys.delete(match[1]);
    } else if (line !== "" || output.length > 0) {
      output.push(line);
    }
  }
  if (keys.size > 0 && output.length > 0 && output[output.length - 1] !== "") {
    output.push("");
  }
  for (const key of keys) {
    output.push(`${key}=${values[key]}`);
  }
  await writeFile(path, `${output.join("\n").replace(/\n+$/, "")}\n`, "utf8");
}
