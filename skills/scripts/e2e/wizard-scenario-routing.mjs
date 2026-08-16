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

const caseId = "wizard-scenario-routing";
await loadEnvFiles();
const paths = evidencePaths(caseId);
await ensureEvidence(paths);
const messageScreenshot = paths.screenshot.replace(
  /\.png$/,
  "-message-scenario.png",
);
const mobileScreenshot = paths.screenshot.replace(/\.png$/, "-mobile.png");

const startedAt = new Date();
const frontendUrl = process.env.LANGBOT_FRONTEND_URL || "";
const backendUrl = process.env.LANGBOT_BACKEND_URL || "";

let browser;
let token = "";
let botId = "";
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
    message_scenario_screenshot: messageScreenshot,
    mobile_screenshot: mobileScreenshot,
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

  const adapters = await apiJson(backendUrl, "/api/v1/platform/adapters", {
    token,
  });
  const catalog = adapters.json.data?.adapters || [];
  const httpBot = catalog.find((adapter) => adapter.name === "http_bot");
  const welcomeAdapters = catalog.filter((adapter) =>
    (adapter.spec?.supported_events || []).includes("group.member_joined"),
  );
  result.api.adapters = {
    http_status: adapters.status,
    code: adapters.json.code ?? null,
    http_bot_supports_message:
      !httpBot?.spec?.supported_events?.length ||
      httpBot.spec.supported_events.includes("message.received"),
    http_bot_supports_member_joined:
      httpBot?.spec?.supported_events?.includes("group.member_joined") || false,
    welcome_adapter_count: welcomeAdapters.length,
  };
  if (adapters.status >= 400 || adapters.json.code !== 0) {
    throw new Error(adapters.json.msg || "Adapter discovery failed.");
  }
  if (!httpBot || welcomeAdapters.length === 0) {
    throw new Error(
      "The adapter catalog does not contain the fixtures required by this case.",
    );
  }
  if (result.api.adapters.http_bot_supports_member_joined) {
    throw new Error(
      "HTTP Bot unexpectedly declares group.member_joined support; update the case expectation.",
    );
  }

  const progressUrl = `${backendUrl.replace(/\/$/, "")}/api/v1/system/wizard/progress`;
  await page.route(progressUrl, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 0, msg: "ok", data: {} }),
    });
  });

  await page.goto(`${frontendUrl.replace(/\/$/, "")}/wizard`, {
    waitUntil: "domcontentloaded",
  });
  result.url = page.url();
  await page
    .getByText(
      /What should this bot do\?|这个机器人要完成什么？|このボットで何を実現しますか？/,
    )
    .waitFor({ timeout: 15_000 });

  await page
    .getByRole("button", {
      name: /Reply to messages|回复收到的消息|受信メッセージに返信/,
    })
    .click();
  await page
    .getByText(/HTTP Bot|HTTP 通用接入|HTTP ボット/, { exact: true })
    .waitFor();
  result.visible_signals.push("scenario-first", "message-http-compatible");
  await safeScreenshot(page, messageScreenshot);

  await page
    .getByRole("button", {
      name: /Welcome new members|欢迎新成员|新しいメンバーを歓迎/,
    })
    .click();
  await page
    .getByText(/Discord/, { exact: true })
    .first()
    .waitFor();
  const httpBotCount = await page
    .getByText(/HTTP Bot|HTTP 通用接入|HTTP ボット/, { exact: true })
    .count();
  if (httpBotCount !== 0) {
    throw new Error("HTTP Bot remained visible for group.member_joined.");
  }
  const selectedScenario = page.getByRole("button", {
    name: /Welcome new members|欢迎新成员|新しいメンバーを歓迎/,
  });
  if (
    !(await selectedScenario.getByText("Agent", { exact: true }).isVisible())
  ) {
    throw new Error(
      "The non-message scenario is not visibly labeled as Agent.",
    );
  }
  result.visible_signals.push(
    "welcome-compatible-channel",
    "http-filtered",
    "agent-behavior-label",
  );

  await safeScreenshot(page, paths.screenshot);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(250);
  const horizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  if (horizontalOverflow > 1) {
    throw new Error(
      `The mobile wizard overflows horizontally by ${horizontalOverflow}px.`,
    );
  }
  await selectedScenario.scrollIntoViewIfNeeded();
  await page
    .getByText(/Discord/, { exact: true })
    .first()
    .waitFor();
  await safeScreenshot(page, mobileScreenshot);
  result.visible_signals.push("mobile-layout");

  const fixtureSuffix = paths.runId.slice(-48);
  const agent = await apiJson(backendUrl, "/api/v1/agents", {
    method: "POST",
    token,
    body: {
      kind: "agent",
      name: `Wizard Scenario Agent ${fixtureSuffix}`,
      description: "Temporary wizard scenario routing fixture",
      emoji: "W",
      enabled: true,
      supported_event_patterns: ["group.member_joined"],
    },
  });
  agentId = agent.json.data?.uuid || "";
  result.api.create_agent = {
    http_status: agent.status,
    code: agent.json.code ?? null,
  };
  if (agent.status >= 400 || agent.json.code !== 0 || !agentId) {
    throw new Error(agent.json.msg || "Failed to create the temporary Agent.");
  }

  const bot = await apiJson(backendUrl, "/api/v1/platform/bots", {
    method: "POST",
    token,
    body: {
      name: `Wizard Scenario Bot ${fixtureSuffix}`,
      description: "Temporary disabled wizard scenario routing fixture",
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
  result.api.create_bot = {
    http_status: bot.status,
    code: bot.json.code ?? null,
  };
  if (bot.status >= 400 || bot.json.code !== 0 || !botId) {
    throw new Error(bot.json.msg || "Failed to create the temporary Bot.");
  }

  const update = await apiJson(
    backendUrl,
    `/api/v1/platform/bots/${encodeURIComponent(botId)}`,
    {
      method: "PUT",
      token,
      body: {
        event_bindings: [
          {
            event_pattern: "group.member_joined",
            target_type: "agent",
            target_uuid: agentId,
            filters: [],
            priority: 0,
            enabled: true,
            description: "Welcome new members",
          },
        ],
      },
    },
  );
  result.api.bind_route = {
    http_status: update.status,
    code: update.json.code ?? null,
  };
  if (update.status >= 400 || update.json.code !== 0) {
    throw new Error(update.json.msg || "Failed to bind the temporary route.");
  }

  const savedBot = await apiJson(
    backendUrl,
    `/api/v1/platform/bots/${encodeURIComponent(botId)}`,
    { token },
  );
  const savedRoute = savedBot.json.data?.bot?.event_bindings?.[0];
  result.api.read_route = {
    http_status: savedBot.status,
    code: savedBot.json.code ?? null,
    event_pattern: savedRoute?.event_pattern || null,
    target_type: savedRoute?.target_type || null,
    target_matches: savedRoute?.target_uuid === agentId,
  };
  if (
    savedBot.status >= 400 ||
    savedBot.json.code !== 0 ||
    savedRoute?.event_pattern !== "group.member_joined" ||
    savedRoute?.target_type !== "agent" ||
    savedRoute?.target_uuid !== agentId
  ) {
    throw new Error("The saved Bot did not return the expected Agent route.");
  }
  result.visible_signals.push("agent-route-persisted");

  result.diagnostics = await scanBrowserDiagnostics(paths);
  if (result.diagnostics.status !== "pass") {
    throw new Error(result.diagnostics.reason);
  }
  result.status = "pass";
  result.reason =
    "Quick Start visibly filtered channels by scenario at desktop and mobile widths.";
} catch (error) {
  if (!["blocked", "env_issue"].includes(result.status)) result.status = "fail";
  result.reason = result.reason || error.message;
  if (browser?.page) await safeScreenshot(browser.page, paths.screenshot);
} finally {
  const cleanup = {};
  if (botId && token && backendUrl) {
    const deletedBot = await apiJson(
      backendUrl,
      `/api/v1/platform/bots/${encodeURIComponent(botId)}`,
      { method: "DELETE", token },
    ).catch((error) => ({
      status: 0,
      json: { code: null, msg: error.message },
    }));
    cleanup.bot_deleted = deletedBot.status < 400 && deletedBot.json.code === 0;
    cleanup.bot_http_status = deletedBot.status;
  }
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
  const cleanupFailed =
    (botId && !cleanup.bot_deleted) || (agentId && !cleanup.agent_deleted);
  if (cleanupFailed && result.status === "pass") {
    result.status = "fail";
    result.reason = "The temporary wizard routing fixtures were not deleted.";
  }
  if (browser) await browser.close().catch(() => {});
  const finishedAt = new Date();
  result.finished_at = finishedAt.toISOString();
  result.finished_at_local = localIsoWithOffset(finishedAt);
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(exitCode(result.status));
