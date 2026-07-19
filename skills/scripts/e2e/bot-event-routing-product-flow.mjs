#!/usr/bin/env node

import {
  apiJson,
  bodyText,
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

const caseId = "bot-event-routing-product-flow";
await loadEnvFiles();
const paths = evidencePaths(caseId);
await ensureEvidence(paths);
const mobileScreenshot = paths.screenshot.replace(/\.png$/, "-mobile.png");
const scenarioMenuScreenshot = paths.screenshot.replace(
  /\.png$/,
  "-scenario-menu.png",
);

const startedAt = new Date();
const frontendUrl = process.env.LANGBOT_FRONTEND_URL || "";
const backendUrl = process.env.LANGBOT_BACKEND_URL || "";
const fixtureName = `EBA Product Flow ${paths.runId}`;

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
  bot_id: "",
  visible_signals: [],
  api: {},
  diagnostics: null,
  cleanup: null,
  evidence: {
    console_log: paths.consoleLog,
    network_log: paths.networkLog,
    screenshot: paths.screenshot,
    mobile_screenshot: mobileScreenshot,
    scenario_menu_screenshot: scenarioMenuScreenshot,
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

  await page.goto(`${frontendUrl.replace(/\/$/, "")}/home/bots?id=new`, {
    waitUntil: "domcontentloaded",
  });
  await page
    .getByText(/Create Bot|创建机器人|ボットを作成/)
    .first()
    .waitFor({ timeout: 15_000 });
  await page.getByRole("combobox").first().click();
  await page
    .getByRole("option", { name: /HTTP Bot|HTTP 通用接入|HTTP ボット/ })
    .click();
  await page
    .getByText(/Event Routing|事件路由|イベントルーティング/)
    .first()
    .waitFor();
  const addBehavior = page.getByRole("button", {
    name: /Add behavior|添加行为|動作を追加/,
  });
  await addBehavior.waitFor();
  await addBehavior.click();
  const messageBehavior = page.getByRole("menuitem", {
    name: /Reply to messages|回复收到的消息|受信メッセージに返信/,
  });
  const noEventRoutes = page.getByText(
    /No event routes|暂无事件路由|イベントルートはありません/,
    { exact: true },
  );
  await noEventRoutes.waitFor();
  await messageBehavior.waitFor();
  await page.waitForTimeout(250);
  await safeScreenshot(page, scenarioMenuScreenshot);
  await messageBehavior.click();
  await noEventRoutes.waitFor({ state: "hidden" });
  result.visible_signals.push("create-mode-routing", "scenario-route-added");

  const create = await apiJson(backendUrl, "/api/v1/platform/bots", {
    method: "POST",
    token,
    body: {
      name: fixtureName,
      description: "Temporary EBA product-flow fixture",
      adapter: "http_bot",
      adapter_config: {
        inbound_secret: "eba-product-flow-local-only",
        callback_url: "http://127.0.0.1:9/langbot-e2e-unused",
        outbound_secret: "",
        default_session_type: "person",
        signature_required: false,
        callback_timeout: 1,
        callback_max_retries: 0,
      },
      enable: true,
      event_bindings: [
        {
          id: "qa-message-discard",
          event_pattern: "message.received",
          target_type: "discard",
          target_uuid: "",
          filters: [],
          priority: 0,
          enabled: true,
          description: "Discard the deterministic QA event",
          order: 0,
        },
        {
          id: "qa-message-discard-shadowed",
          event_pattern: "message.received",
          target_type: "discard",
          target_uuid: "",
          filters: [],
          priority: 0,
          enabled: true,
          description: "Verify visible route conflict guidance",
          order: 1,
        },
      ],
    },
  });
  botId = create.json.data?.uuid || "";
  result.api.create_bot = {
    http_status: create.status,
    code: create.json.code ?? null,
  };
  result.bot_id = botId;
  if (create.status >= 400 || create.json.code !== 0 || !botId) {
    throw new Error(create.json.msg || "Failed to create the temporary Bot.");
  }

  const botUrl = `${frontendUrl.replace(/\/$/, "")}/home/bots?id=${encodeURIComponent(botId)}`;
  await page.goto(botUrl, { waitUntil: "domcontentloaded" });
  await page
    .waitForLoadState("networkidle", { timeout: 10_000 })
    .catch(() => {});
  result.url = page.url();

  await page
    .getByText(/Event Routing|事件路由|イベントルーティング/)
    .first()
    .waitFor({ timeout: 15_000 });
  await page
    .getByText(
      /Events this adapter can receive|此适配器可接收的事件|このアダプターが受信できるイベント/,
    )
    .waitFor();
  await page
    .getByText(/Message received|收到消息|メッセージを受信/)
    .first()
    .waitFor();
  await page
    .getByText(
      /Some routes overlap|部分路由存在覆盖冲突|一部のルートが重複しています/,
    )
    .waitFor();
  await page
    .getByText(
      /Events that match no route are ignored|未命中任何路由的事件会被忽略|どのルートにも一致しないイベントは無視されます/,
    )
    .waitFor();
  result.visible_signals.push(
    "event-routing",
    "adapter-capabilities",
    "friendly-event-name",
    "route-conflict-guidance",
    "fallback-guidance",
  );

  await page
    .getByRole("button", { name: /Test route|测试路由|ルートをテスト/ })
    .click();
  await page.getByRole("dialog").waitFor();
  await page
    .getByRole("button", { name: /Preview route|预览路由|ルートをプレビュー/ })
    .click();
  await page
    .getByText(/Route matched|已命中路由|ルートに一致しました/)
    .waitFor({ timeout: 15_000 });
  await page
    .getByText(/Discard|丢弃|破棄/)
    .first()
    .waitFor();
  result.visible_signals.push("dry-run-matched", "discard-target");

  await page
    .getByRole("button", {
      name: /Run saved route|运行已保存路由|保存済みルートを実行/,
    })
    .click();
  await page
    .getByText(
      /saved route ran successfully|已保存路由运行成功|保存済みルートを実行しました/,
    )
    .waitFor({ timeout: 20_000 });
  result.visible_signals.push("test-event-dispatched");

  await page
    .getByRole("button", { name: /Close|关闭|閉じる/ })
    .first()
    .click();
  await page.getByRole("dialog").waitFor({ state: "hidden" });
  await page
    .getByText(/Discarded|已丢弃|破棄済み/)
    .first()
    .waitFor({ timeout: 10_000 });
  result.visible_signals.push("route-status-discarded");

  const text = await bodyText(page);
  if (/\bEBA event\b/.test(text)) {
    throw new Error(
      "The primary route surface exposes an internal EBA runtime message.",
    );
  }

  const status = await apiJson(
    backendUrl,
    `/api/v1/platform/bots/${encodeURIComponent(botId)}/event-routes/status`,
    { token },
  );
  const latest = status.json.data?.routes?.find(
    (route) => route.binding_id === "qa-message-discard",
  );
  result.api.route_status = {
    http_status: status.status,
    code: status.json.code ?? null,
    last_status: latest?.last_status || null,
  };
  if (
    status.status >= 400 ||
    status.json.code !== 0 ||
    latest?.last_status !== "discarded"
  ) {
    throw new Error(
      "Route status API did not confirm the discarded synthetic event.",
    );
  }

  await safeScreenshot(page, paths.screenshot);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(250);
  const horizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  if (horizontalOverflow > 1) {
    throw new Error(
      `The mobile route editor overflows horizontally by ${horizontalOverflow}px.`,
    );
  }
  await page
    .getByText(
      /Some routes overlap|部分路由存在覆盖冲突|一部のルートが重複しています/,
    )
    .waitFor();
  await safeScreenshot(page, mobileScreenshot);
  result.visible_signals.push("mobile-layout");
  result.diagnostics = await scanBrowserDiagnostics(paths);
  if (result.diagnostics.status !== "pass") {
    throw new Error(result.diagnostics.reason);
  }
  result.status = "pass";
  result.reason =
    "Bot event routing, dry-run, synthetic dispatch, and visible route status passed in the WebUI.";
} catch (error) {
  if (!["blocked", "env_issue"].includes(result.status)) result.status = "fail";
  result.reason = result.reason || error.message;
  if (browser?.page) await safeScreenshot(browser.page, paths.screenshot);
} finally {
  if (botId && token && backendUrl) {
    const cleanup = await apiJson(
      backendUrl,
      `/api/v1/platform/bots/${encodeURIComponent(botId)}`,
      { method: "DELETE", token },
    ).catch((error) => ({
      status: 0,
      json: { code: null, msg: error.message },
    }));
    result.cleanup = {
      http_status: cleanup.status,
      code: cleanup.json.code ?? null,
      deleted: cleanup.status < 400 && cleanup.json.code === 0,
    };
    if (!result.cleanup.deleted && result.status === "pass") {
      result.status = "fail";
      result.reason =
        cleanup.json.msg || "The temporary Bot could not be deleted.";
    }
  }
  if (browser) await browser.close().catch(() => {});
  const finishedAt = new Date();
  result.finished_at = finishedAt.toISOString();
  result.finished_at_local = localIsoWithOffset(finishedAt);
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(exitCode(result.status));
