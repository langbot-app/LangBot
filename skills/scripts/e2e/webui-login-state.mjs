#!/usr/bin/env node

import {
  bodyText,
  createBrowser,
  ensureEvidence,
  evidencePaths,
  exitCode,
  gotoFrontend,
  isLoginUrl,
  loadEnvFiles,
  localIsoWithOffset,
  safeScreenshot,
  verifyBrowserToken,
  writeResult,
} from "./lib/langbot-e2e.mjs";

const caseId = "webui-login-state";
await loadEnvFiles();
const paths = evidencePaths(caseId);
await ensureEvidence(paths);

const startedAt = new Date();
let browser;
let result = {
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
  auth: null,
  evidence: {
    console_log: paths.consoleLog,
    network_log: paths.networkLog,
    screenshot: paths.screenshot,
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["ui", "screenshot", "console"],
};

try {
  browser = await createBrowser(paths);
  const { page } = browser;
  await gotoFrontend(page);
  result.url = page.url();

  const backendUrl = process.env.LANGBOT_BACKEND_URL || "";
  if (!backendUrl) {
    result.status = "env_issue";
    result.reason = "LANGBOT_BACKEND_URL is not configured.";
    await safeScreenshot(page, paths.screenshot);
    throw new Error(result.reason);
  }

  const auth = await verifyBrowserToken(page, backendUrl);
  result.auth = auth;
  const text = await bodyText(page);
  const navigationSignals = [
    "Dashboard",
    "Bots",
    "Pipelines",
    "Knowledge",
    "Plugins",
    "首页",
    "机器人",
    "流水线",
    "知识库",
    "插件",
  ];
  const matchedSignal = navigationSignals.find((signal) => text.includes(signal));

  if (!auth.authenticated) {
    result.status = "blocked";
    result.reason = auth.reason || "Browser profile token was not accepted by backend.";
  } else if (isLoginUrl(page.url()) || /登录|Login|Sign in/i.test(text)) {
    result.status = "fail";
    result.reason = "Backend accepted the token, but the WebUI still showed the login page.";
  } else if (!matchedSignal) {
    result.status = "fail";
    result.reason = "Opened WebUI, but no known LangBot navigation signal was visible.";
  } else {
    result.status = "pass";
    result.reason = `Authenticated navigation signal visible: ${matchedSignal}`;
  }

  await safeScreenshot(page, paths.screenshot);
} catch (error) {
  if (!["env_issue", "blocked", "fail", "pass"].includes(result.status) || !result.reason) {
    result.status = /Playwright is not installed|LANGBOT_FRONTEND_URL/.test(error.message) ? "env_issue" : "fail";
    result.reason = error.message;
  }
} finally {
  if (browser) await browser.close().catch(() => {});
  const finishedAt = new Date();
  result.finished_at = finishedAt.toISOString();
  result.finished_at_local = localIsoWithOffset(finishedAt);
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(exitCode(result.status));
