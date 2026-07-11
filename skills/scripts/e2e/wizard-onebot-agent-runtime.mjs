#!/usr/bin/env node

import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  createBrowser,
  ensureAuthenticatedBrowser,
  ensureEvidence,
  evidencePaths,
  exitCode,
  loadEnvFiles,
  localIsoWithOffset,
  pathExists,
  resolveLangBotRepo,
  safeScreenshot,
  scanBrowserDiagnostics,
  writeResult,
} from "./lib/langbot-e2e.mjs";

const caseId = "wizard-onebot-agent-runtime";
await loadEnvFiles();
const paths = evidencePaths(caseId);
await ensureEvidence(paths);

const startedAt = new Date();
const frontendUrl = process.env.LANGBOT_FRONTEND_URL || "";
const backendUrl = process.env.LANGBOT_BACKEND_URL || "";
let browser;
let botId = "";
let agentId = "";
let token = "";

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
  agent_id: "",
  visible_signals: [],
  api: {},
  runtime: {},
  cleanup: {},
  diagnostics: null,
  evidence: {
    screenshot: paths.screenshot,
    console_log: paths.consoleLog,
    network_log: paths.networkLog,
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["ui", "screenshot", "console", "api_diagnostic"],
};

async function getFreePort() {
  const server = createServer();
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();
  const port = typeof address === "object" && address ? address.port : 0;
  await new Promise((resolve) => server.close(resolve));
  if (!port) throw new Error("Could not allocate a temporary OneBot port.");
  return port;
}

async function api(page, path, options = {}) {
  return await page.evaluate(
    async ({ baseUrl, path, options, token }) => {
      const response = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
        method: options.method || "GET",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body:
          options.body === undefined ? undefined : JSON.stringify(options.body),
      });
      return {
        status: response.status,
        json: await response.json().catch(() => ({})),
      };
    },
    { baseUrl: backendUrl, path, options, token },
  );
}

async function runProbe(port) {
  const repo = await resolveLangBotRepo();
  const python = join(repo, ".venv", "bin", "python");
  const script = join(
    dirname(fileURLToPath(import.meta.url)),
    "onebot-runtime-probe.py",
  );
  if (!(await pathExists(python))) {
    throw new Error(`LangBot virtualenv Python is missing: ${python}`);
  }
  return await new Promise((resolve, reject) => {
    const child = spawn(python, [script, "--port", String(port)], {
      cwd: repo,
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => (stdout += chunk));
    child.stderr.on("data", (chunk) => (stderr += chunk));
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) {
        resolve(JSON.parse(stdout.trim().split("\n").at(-1)));
      } else {
        reject(
          new Error(
            stderr.trim() || stdout.trim() || `OneBot probe exited ${code}`,
          ),
        );
      }
    });
  });
}

try {
  if (!frontendUrl) throw new Error("LANGBOT_FRONTEND_URL is not configured.");
  if (!backendUrl) throw new Error("LANGBOT_BACKEND_URL is not configured.");
  const port = await getFreePort();

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
    throw new Error("Authenticated browser token is unavailable.");
  }

  // Keep this case isolated from the instance's real onboarding state.
  await page.route("**/api/v1/system/wizard/progress", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 0, msg: "ok", data: {} }),
    });
  });

  await page.goto(`${frontendUrl.replace(/\/$/, "")}/wizard`, {
    waitUntil: "domcontentloaded",
  });
  await page
    .getByRole("button", {
      name: /Welcome new members|欢迎新成员|新しいメンバーを歓迎/,
    })
    .click();
  await page.getByText("OneBot v11", { exact: true }).last().click();

  const botResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v1\/platform\/bots$/.test(new URL(response.url()).pathname),
  );
  await page
    .getByRole("button", {
      name: /Confirm, Create Bot|确定，创建机器人|確定、ボットを作成/,
    })
    .click();
  const botPayload = await (await botResponse).json();
  botId = botPayload.data?.uuid || "";
  if (!botId) throw new Error("Wizard did not create a Bot.");
  result.bot_id = botId;
  result.api.create_bot = { code: botPayload.code ?? null };

  await page
    .getByText(/Configure Your Bot|配置机器人|ボットを設定/)
    .first()
    .waitFor({ timeout: 15_000 });
  const portInput = page.getByRole("spinbutton").first();
  await portInput.fill(String(port));
  await portInput.press("Tab");
  await page
    .getByRole("button", {
      name: /Save & Enable Bot|保存并启用|保存して有効化/,
    })
    .click();
  await page
    .getByText(
      /Bot configuration saved and enabled|机器人配置已保存并启用|ボット設定が保存され、有効になりました/,
    )
    .waitFor({ timeout: 15_000 });
  result.visible_signals.push("bot-created", "adapter-enabled");

  await page.getByRole("button", { name: /Next|下一步|次へ/ }).click();
  await page
    .getByText(/Local Agent|本地 Agent/)
    .first()
    .click();
  await page.waitForFunction(
    () =>
      Array.from(document.querySelectorAll("textarea")).some((element) => {
        const value = element.value || "";
        return [
          "Welcome new group members",
          "欢迎新群成员",
          "新しいグループメンバー",
        ].some((expected) => value.includes(expected));
      }),
    null,
    { timeout: 15_000 },
  );
  result.visible_signals.push("scenario-prompt-visible");

  await page
    .getByText(/QA Deterministic Runner|QA 确定性 Runner/)
    .first()
    .click();

  const agentResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v1\/agents$/.test(new URL(response.url()).pathname),
  );
  await page
    .getByRole("button", {
      name: /Create & Deploy|创建并部署|作成＆デプロイ/,
    })
    .click();
  const agentPayload = await (await agentResponse).json();
  agentId = agentPayload.data?.uuid || "";
  if (!agentId) throw new Error("Wizard did not create an Agent.");
  result.agent_id = agentId;
  result.api.create_agent = { code: agentPayload.code ?? null };
  await page.getByText(/All Set!|一切就绪！/).waitFor({ timeout: 15_000 });
  result.visible_signals.push("agent-created", "wizard-complete");

  const savedBot = await api(page, `/api/v1/platform/bots/${botId}`);
  const route = savedBot.json.data?.bot?.event_bindings?.[0];
  result.api.saved_route = {
    http_status: savedBot.status,
    event_pattern: route?.event_pattern || null,
    target_type: route?.target_type || null,
    target_matches: route?.target_uuid === agentId,
  };
  if (
    route?.event_pattern !== "group.member_joined" ||
    route?.target_type !== "agent" ||
    route?.target_uuid !== agentId
  ) {
    throw new Error("Wizard did not persist the expected Agent route.");
  }
  result.visible_signals.push("route-persisted");

  result.runtime.onebot = await runProbe(port);
  let routeStatus;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    routeStatus = await api(
      page,
      `/api/v1/platform/bots/${botId}/event-routes/status`,
    );
    if (routeStatus.json.data?.routes?.[0]?.last_status === "delivered") break;
    await page.waitForTimeout(250);
  }
  const latest = routeStatus?.json?.data?.routes?.[0];
  result.runtime.route_status = latest || null;
  if (latest?.last_status !== "delivered") {
    throw new Error(
      `Runtime route did not reach delivered status: ${latest?.last_status || "none"}`,
    );
  }
  result.visible_signals.push(
    "platform-event-converted",
    "agent-ran",
    "reply-delivered",
  );

  const botUrl = `${frontendUrl.replace(/\/$/, "")}/home/bots?id=${encodeURIComponent(botId)}`;
  await page.goto(botUrl, { waitUntil: "domcontentloaded" });
  result.url = page.url();
  const deliveredStatus = page
    .getByText(/Delivered|已投递|配信済み/, { exact: true })
    .first();
  await deliveredStatus.waitFor({ timeout: 15_000 });
  await deliveredStatus.scrollIntoViewIfNeeded();
  await page.waitForTimeout(250);
  result.visible_signals.push("delivered-status-visible");
  await safeScreenshot(page, paths.screenshot);

  result.diagnostics = await scanBrowserDiagnostics(paths);
  if (result.diagnostics.status !== "pass") {
    throw new Error(result.diagnostics.reason);
  }
  result.status = "pass";
  result.reason =
    "Quick Start created an enabled OneBot scenario that converted a platform event, ran an Agent, delivered its reply, and showed the final status.";
} catch (error) {
  if (!["blocked", "env_issue"].includes(result.status)) result.status = "fail";
  result.reason = result.reason || error.message;
  if (browser?.page) await safeScreenshot(browser.page, paths.screenshot);
} finally {
  if (browser?.page && token) {
    if (botId) {
      const deleted = await api(
        browser.page,
        `/api/v1/platform/bots/${encodeURIComponent(botId)}`,
        { method: "DELETE" },
      ).catch(() => ({ status: 0, json: {} }));
      result.cleanup.bot_deleted =
        deleted.status < 400 && deleted.json.code === 0;
    }
    if (agentId) {
      const deleted = await api(
        browser.page,
        `/api/v1/agents/${encodeURIComponent(agentId)}`,
        { method: "DELETE" },
      ).catch(() => ({ status: 0, json: {} }));
      result.cleanup.agent_deleted =
        deleted.status < 400 && deleted.json.code === 0;
    }
  }
  const cleanupFailed =
    (botId && !result.cleanup.bot_deleted) ||
    (agentId && !result.cleanup.agent_deleted);
  if (cleanupFailed && result.status === "pass") {
    result.status = "fail";
    result.reason = "The temporary OneBot wizard resources were not deleted.";
  }
  if (browser) await browser.close().catch(() => {});
  const finishedAt = new Date();
  result.finished_at = finishedAt.toISOString();
  result.finished_at_local = localIsoWithOffset(finishedAt);
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(exitCode(result.status));
