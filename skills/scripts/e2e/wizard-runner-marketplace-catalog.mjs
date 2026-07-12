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

const caseId = "wizard-runner-marketplace-catalog";
await loadEnvFiles();
const paths = evidencePaths(caseId);
await ensureEvidence(paths);
const mobileScreenshot = paths.screenshot.replace(/\.png$/, "-mobile.png");

const startedAt = new Date();
const frontendUrl = process.env.LANGBOT_FRONTEND_URL || "";
const backendUrl = process.env.LANGBOT_BACKEND_URL || "";
let browser;
let token = "";
let botId = "";

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
  marketplace_request: null,
  diagnostics: null,
  cleanup: {},
  evidence: {
    screenshot: paths.screenshot,
    mobile_screenshot: mobileScreenshot,
    console_log: paths.consoleLog,
    network_log: paths.networkLog,
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["ui", "screenshot", "console", "api_diagnostic"],
};

try {
  if (!frontendUrl) throw new Error("LANGBOT_FRONTEND_URL is not configured.");
  if (!backendUrl) throw new Error("LANGBOT_BACKEND_URL is not configured.");

  browser = await createBrowser(paths);
  const { page } = browser;
  page.on("request", (request) => {
    if (
      !/\/api\/v1\/marketplace\/(extensions|plugins)\/search$/.test(
        new URL(request.url()).pathname,
      )
    ) {
      return;
    }
    try {
      const payload = request.postDataJSON();
      if (payload?.component_filter === "AgentRunner") {
        result.marketplace_request = {
          endpoint: new URL(request.url()).pathname,
          component_filter: payload.component_filter,
          type_filter: payload.type_filter || null,
          page_size: payload.page_size || null,
        };
      }
    } catch {
      // The assertion below reports a missing or malformed catalog request.
    }
  });

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
    throw new Error("Authenticated browser token is unavailable.");
  }

  const [plugins, metadata, system] = await Promise.all([
    apiJson(backendUrl, "/api/v1/plugins", { token }),
    apiJson(backendUrl, "/api/v1/pipelines/_/metadata", { token }),
    apiJson(backendUrl, "/api/v1/system/info", { token }),
  ]);
  const runnerStage = metadata.json.data?.configs
    ?.find((config) => config.name === "ai")
    ?.stages?.find((stage) => stage.name === "runner");
  const runnerOptions =
    runnerStage?.config?.find((item) => item.name === "id")?.options || [];
  const installedPlugins = plugins.json.data?.plugins || [];
  result.api.clean_state = {
    plugin_count: installedPlugins.length,
    runner_count: runnerOptions.length,
    wizard_status: system.json.data?.wizard_status || null,
  };
  if (installedPlugins.length !== 0 || runnerOptions.length !== 0) {
    result.status = "blocked";
    throw new Error(
      `This case requires zero plugins and zero runners; found ${installedPlugins.length} plugins and ${runnerOptions.length} runners.`,
    );
  }
  if (system.json.data?.wizard_status !== "none") {
    result.status = "blocked";
    throw new Error(
      `This case requires a first-run instance; wizard status is ${system.json.data?.wizard_status}.`,
    );
  }

  const suffix = paths.runId.slice(-40);
  const bot = await apiJson(backendUrl, "/api/v1/platform/bots", {
    method: "POST",
    token,
    body: {
      name: `Runner Catalog Wizard ${suffix}`,
      description: "Temporary clean-runner catalog fixture",
      adapter: "aiocqhttp",
      adapter_config: {
        host: "127.0.0.1",
        port: 2280,
        "access-token": "",
      },
      enable: false,
      event_bindings: [],
    },
  });
  botId = bot.json.data?.uuid || "";
  if (bot.status >= 400 || bot.json.code !== 0 || !botId) {
    throw new Error(bot.json.msg || "Failed to create the temporary Bot.");
  }

  const progress = await apiJson(backendUrl, "/api/v1/system/wizard/progress", {
    method: "PUT",
    token,
    body: {
      step: 2,
      selected_scenario: "message_reply",
      selected_adapter: "aiocqhttp",
      created_bot_uuid: botId,
      bot_saved: true,
      selected_runner: null,
    },
  });
  if (progress.status >= 400 || progress.json.code !== 0) {
    throw new Error(progress.json.msg || "Failed to prepare Wizard progress.");
  }

  await page.goto(`${frontendUrl.replace(/\/$/, "")}/wizard`, {
    waitUntil: "domcontentloaded",
  });
  result.url = page.url();
  await page
    .getByText(/Select an AI Engine|选择 AI 引擎|AIエンジンを選択/, {
      exact: true,
    })
    .waitFor({ timeout: 15_000 });
  await page
    .getByText(
      /No AgentRunner extensions are published yet|市场暂未发布 AgentRunner 扩展|AgentRunner 拡張機能はまだ公開されていません/,
      { exact: true },
    )
    .waitFor({ timeout: 15_000 });
  const browseLink = page.getByRole("link", {
    name: /Browse Runner Extensions|浏览运行器扩展|Runner 拡張機能を見る/,
  });
  await browseLink.waitFor();
  const href = await browseLink.getAttribute("href");
  if (href !== "/home/extensions?type=plugin&component=AgentRunner") {
    throw new Error(`Unexpected Runner marketplace URL: ${href}`);
  }
  const nextButton = page.getByRole("button", {
    name: /Create & Deploy|创建并部署|作成＆デプロイ/,
  });
  if (!(await nextButton.isDisabled())) {
    throw new Error("Wizard allowed continuing without an installed Runner.");
  }
  if (!result.marketplace_request) {
    throw new Error(
      "Wizard did not request the AgentRunner Marketplace catalog.",
    );
  }

  result.visible_signals.push(
    "first-run-ai-engine-step",
    "empty-runner-catalog-state",
    "runner-marketplace-link",
    "next-disabled-without-runner",
  );
  await safeScreenshot(page, paths.screenshot);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(250);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  if (overflow > 1) {
    throw new Error(`Runner catalog Wizard overflows mobile by ${overflow}px.`);
  }
  await browseLink.scrollIntoViewIfNeeded();
  await safeScreenshot(page, mobileScreenshot);
  result.visible_signals.push("mobile-layout");

  result.diagnostics = await scanBrowserDiagnostics(paths);
  if (result.diagnostics.status !== "pass") {
    throw new Error(result.diagnostics.reason);
  }
  result.status = "pass";
  result.reason =
    "A clean first-run instance requested the AgentRunner catalog, showed a safe empty state, and prevented continuing without a Runner.";
} catch (error) {
  if (!["blocked", "env_issue"].includes(result.status)) result.status = "fail";
  result.reason = result.reason || error.message;
  if (browser?.page) await safeScreenshot(browser.page, paths.screenshot);
} finally {
  const cleanup = {};
  if (token && backendUrl) {
    const resetProgress = await apiJson(
      backendUrl,
      "/api/v1/system/wizard/progress",
      {
        method: "PUT",
        token,
        body: {
          step: 0,
          selected_scenario: null,
          selected_adapter: null,
          created_bot_uuid: null,
          bot_saved: false,
          selected_runner: null,
        },
      },
    ).catch(() => ({ status: 0, json: {} }));
    cleanup.progress_reset =
      resetProgress.status < 400 && resetProgress.json.code === 0;
  }
  if (botId && token && backendUrl) {
    const deletedBot = await apiJson(
      backendUrl,
      `/api/v1/platform/bots/${encodeURIComponent(botId)}`,
      { method: "DELETE", token },
    ).catch(() => ({ status: 0, json: {} }));
    cleanup.bot_deleted = deletedBot.status < 400 && deletedBot.json.code === 0;
  }
  result.cleanup = cleanup;
  if (
    result.status === "pass" &&
    (!cleanup.progress_reset || (botId && !cleanup.bot_deleted))
  ) {
    result.status = "fail";
    result.reason = "The clean Wizard fixtures were not fully reset.";
  }
  if (browser) await browser.close().catch(() => {});
  const finishedAt = new Date();
  result.finished_at = finishedAt.toISOString();
  result.finished_at_local = localIsoWithOffset(finishedAt);
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(exitCode(result.status));
