#!/usr/bin/env node

import { env } from "node:process";
import {
  bodyText,
  createBrowser,
  ensureEvidence,
  evidencePaths,
  loadEnvFiles,
  resetAndAuthLocalUser,
  safeScreenshot,
  setBrowserToken,
  verifyBrowserToken,
  writeResult,
} from "./lib/langbot-e2e.mjs";

const caseId = "refresh-local-login";
const paths = evidencePaths(caseId);
await loadEnvFiles();
await ensureEvidence(paths);

const result = {
  source: "automation",
  case_id: caseId,
  status: "fail",
  reason: "",
  user: env.LANGBOT_E2E_LOGIN_USER || "",
  frontend_url: env.LANGBOT_FRONTEND_URL || "",
  backend_url: env.LANGBOT_BACKEND_URL || "",
  backend_token_check: null,
  browser_token_check: null,
  evidence: {
    console_log: paths.consoleLog,
    network_log: paths.networkLog,
    screenshot: paths.screenshot,
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["ui", "screenshot", "console", "api_diagnostic"],
};

let browser;

try {
  const backendUrl = env.LANGBOT_BACKEND_URL;
  const frontendUrl = env.LANGBOT_FRONTEND_URL;
  const user = env.LANGBOT_E2E_LOGIN_USER;
  const password = env.LANGBOT_E2E_LOGIN_PASSWORD || "LangBotE2ELocalPass!2026";
  if (!backendUrl) throw new Error("LANGBOT_BACKEND_URL is not configured.");
  if (!frontendUrl) throw new Error("LANGBOT_FRONTEND_URL is not configured.");
  if (!user) throw new Error("LANGBOT_E2E_LOGIN_USER is required.");

  const auth = await resetAndAuthLocalUser({ backendUrl, user, password });
  result.backend_token_check = auth.check;

  browser = await createBrowser(paths);
  const { page } = browser;
  await setBrowserToken(page, frontendUrl, auth.token);
  const browserCheck = await verifyBrowserToken(page, backendUrl);
  result.browser_token_check = browserCheck;
  if (!browserCheck.authenticated) {
    throw new Error(browserCheck.reason || "Browser token check failed.");
  }

  await page.goto(`${frontendUrl.replace(/\/$/, "")}/home/monitoring`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
  const text = await bodyText(page);
  if (!text.includes("Dashboard") && !text.includes("Pipelines") && !text.includes("流水线")) {
    throw new Error("Token was written, but authenticated navigation was not visible.");
  }

  result.status = "pass";
  result.reason = "Browser profile localStorage token refreshed.";
} catch (error) {
  result.status = "fail";
  result.reason = error.message;
} finally {
  if (browser?.page) await safeScreenshot(browser.page, paths.screenshot);
  if (browser) await browser.close().catch(() => {});
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(result.status === "pass" ? 0 : 1);
