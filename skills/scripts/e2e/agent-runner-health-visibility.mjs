#!/usr/bin/env node

import {
  apiJson,
  createBrowser,
  ensureAuthenticatedBrowser,
  ensureEvidence,
  evidencePaths,
  exitCode,
  loadEnvFiles,
  localIsoWithOffset,
  safeScreenshot,
  scanBrowserDiagnostics,
  writeResult,
} from "./lib/langbot-e2e.mjs";

const caseId = "agent-runner-health-visibility";
await loadEnvFiles();
const paths = evidencePaths(caseId);
await ensureEvidence(paths);
const readyScreenshot = paths.screenshot.replace(/\.png$/, "-ready.png");
const unavailableScreenshot = paths.screenshot.replace(
  /\.png$/,
  "-unavailable.png",
);

const startedAt = new Date();
const frontendUrl = process.env.LANGBOT_FRONTEND_URL || "";
const backendUrl = process.env.LANGBOT_BACKEND_URL || "";
const missingRunnerId = "plugin:qa/missing-runner/default";

let browser;
let token = "";
let agentId = "";
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
  url: "",
  visible_signals: [],
  api: {},
  diagnostics: null,
  cleanup: null,
  evidence: {
    console_log: paths.consoleLog,
    network_log: paths.networkLog,
    screenshot: paths.screenshot,
    ready_screenshot: readyScreenshot,
    unavailable_screenshot: unavailableScreenshot,
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["ui", "screenshot", "console", "api_diagnostic"],
};

function schemaDefaults(items = []) {
  return Object.fromEntries(
    items
      .filter((item) => item.name && Object.hasOwn(item, "default"))
      .map((item) => [item.name, item.default]),
  );
}

async function openRunnerSettings(page, agentUrl) {
  await page.goto(agentUrl, { waitUntil: "domcontentloaded" });
  await page
    .getByRole("button", { name: /Runner|运行器|ランナー/ })
    .first()
    .waitFor({ timeout: 15_000 });
  await page
    .getByRole("button", { name: /Runner|运行器|ランナー/ })
    .first()
    .click();
}

try {
  if (!frontendUrl) throw new Error("LANGBOT_FRONTEND_URL is not configured.");
  if (!backendUrl) throw new Error("LANGBOT_BACKEND_URL is not configured.");

  browser = await createBrowser(paths);
  const { page } = browser;
  await page.goto(frontendUrl, { waitUntil: "domcontentloaded" });
  const auth = await ensureAuthenticatedBrowser(page, {
    frontendUrl,
    backendUrl,
  });
  if (auth.status !== "pass") {
    result.status = auth.status;
    throw new Error(auth.reason);
  }

  token = await page.evaluate(() => localStorage.getItem("token") || "");
  if (!token) {
    result.status = "blocked";
    throw new Error("Authenticated browser has no reusable local token.");
  }

  const pluginStatus = await apiJson(
    backendUrl,
    "/api/v1/system/status/plugin-system",
    { token },
  );
  const pluginData = pluginStatus.json.data || {};
  result.api.plugin_status = {
    http_status: pluginStatus.status,
    code: pluginStatus.json.code ?? null,
    is_enable: pluginData.is_enable ?? null,
    is_connected: pluginData.is_connected ?? null,
  };
  if (pluginStatus.status >= 400 || pluginStatus.json.code !== 0) {
    result.status = "env_issue";
    throw new Error(pluginStatus.json.msg || "Plugin status request failed.");
  }
  if (!pluginData.is_enable || !pluginData.is_connected) {
    result.status = "env_issue";
    throw new Error("The plugin runtime is not enabled and connected.");
  }

  const metadata = await apiJson(backendUrl, "/api/v1/agents/_/metadata", {
    token,
  });
  const runnerTab = metadata.json.data?.runner_config;
  const runnerStage = runnerTab?.stages?.find(
    (stage) => stage.name === "runner",
  );
  const runnerOptions =
    runnerStage?.config?.find((item) => item.name === "id")?.options || [];
  const runner = runnerOptions[0];
  result.api.agent_metadata = {
    http_status: metadata.status,
    code: metadata.json.code ?? null,
    runner_count: runnerOptions.length,
    selected_runner: runner?.name || null,
  };
  if (metadata.status >= 400 || metadata.json.code !== 0) {
    throw new Error(metadata.json.msg || "Agent metadata request failed.");
  }
  if (!runner?.name) {
    result.status = "blocked";
    throw new Error("No registered AgentRunner is available for the UI check.");
  }

  const runnerConfigStage = runnerTab.stages.find(
    (stage) => stage.name === runner.name,
  );
  const create = await apiJson(backendUrl, "/api/v1/agents", {
    method: "POST",
    token,
    body: {
      kind: "agent",
      name: `Runner Health ${paths.runId.slice(-40)}`,
      description: "Temporary AgentRunner health visibility fixture",
      emoji: "H",
      component_ref: runner.name,
      config: {
        runner: { id: runner.name, "expire-time": 0 },
        runner_config: {
          [runner.name]: schemaDefaults(runnerConfigStage?.config),
        },
      },
      enabled: true,
      supported_event_patterns: ["message.*"],
    },
  });
  agentId = create.json.data?.uuid || "";
  result.api.create_agent = {
    http_status: create.status,
    code: create.json.code ?? null,
  };
  if (create.status >= 400 || create.json.code !== 0 || !agentId) {
    throw new Error(create.json.msg || "Failed to create the temporary Agent.");
  }

  const agentUrl = `${frontendUrl.replace(/\/$/, "")}/home/agents?id=${encodeURIComponent(agentId)}`;
  result.url = agentUrl;
  await openRunnerSettings(page, agentUrl);
  await page
    .getByText(/Runner ready|运行器已就绪|Runner の準備完了/, { exact: true })
    .waitFor({ timeout: 15_000 });
  result.visible_signals.push("registered-runner-ready");
  await safeScreenshot(page, readyScreenshot);

  const staleUpdate = await apiJson(
    backendUrl,
    `/api/v1/agents/${encodeURIComponent(agentId)}`,
    {
      method: "PUT",
      token,
      body: {
        component_ref: missingRunnerId,
        config: {
          runner: { id: missingRunnerId, "expire-time": 0 },
          runner_config: { [missingRunnerId]: {} },
        },
      },
    },
  );
  result.api.set_stale_runner = {
    http_status: staleUpdate.status,
    code: staleUpdate.json.code ?? null,
  };
  if (staleUpdate.status >= 400 || staleUpdate.json.code !== 0) {
    throw new Error(
      staleUpdate.json.msg || "Failed to set the stale runner fixture.",
    );
  }

  await openRunnerSettings(page, agentUrl);
  await page
    .getByText(
      /Selected runner is unavailable|所选运行器不可用|選択した Runner は利用できません/,
      { exact: true },
    )
    .waitFor({ timeout: 15_000 });
  await page.getByRole("link", { name: /Extensions|扩展|拡張機能/ }).waitFor();
  result.visible_signals.push("stale-runner-unavailable", "recovery-action");
  await safeScreenshot(page, unavailableScreenshot);
  await safeScreenshot(page, paths.screenshot);

  result.diagnostics = await scanBrowserDiagnostics(paths);
  if (result.diagnostics.status !== "pass") {
    throw new Error(result.diagnostics.reason);
  }
  result.status = "pass";
  result.reason =
    "Agent Runner settings visibly distinguished a registered runner from a stale binding.";
} catch (error) {
  if (!["blocked", "env_issue"].includes(result.status)) result.status = "fail";
  result.reason = result.reason || error.message;
  if (browser?.page) await safeScreenshot(browser.page, paths.screenshot);
} finally {
  const cleanup = {};
  if (agentId && token && backendUrl) {
    const deletedAgent = await apiJson(
      backendUrl,
      `/api/v1/agents/${encodeURIComponent(agentId)}`,
      { method: "DELETE", token },
    ).catch((error) => ({
      status: 0,
      json: { code: null, msg: error.message },
    }));
    cleanup.agent_deleted =
      deletedAgent.status < 400 && deletedAgent.json.code === 0;
    cleanup.agent_http_status = deletedAgent.status;
  }
  result.cleanup = cleanup;
  if (agentId && !cleanup.agent_deleted && result.status === "pass") {
    result.status = "fail";
    result.reason = "The temporary runner health Agent was not deleted.";
  }
  if (browser) await browser.close().catch(() => {});
  const finishedAt = new Date();
  result.finished_at = finishedAt.toISOString();
  result.finished_at_local = localIsoWithOffset(finishedAt);
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(exitCode(result.status));
