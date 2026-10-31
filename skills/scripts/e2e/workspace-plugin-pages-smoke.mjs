#!/usr/bin/env node

import { join } from "node:path";
import { env } from "node:process";
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

await loadEnvFiles();
const caseId = env.LBS_CASE_ID || "workspace-plugin-pages-smoke";
const paths = evidencePaths(caseId);
await ensureEvidence(paths);
const startedAt = new Date();
const frontendUrl = env.LANGBOT_FRONTEND_URL || "";
const backendUrl = env.LANGBOT_BACKEND_URL || "";

const targets = [
  {
    id: "control-plane",
    author: "langbot",
    plugin: "agent-control-plane",
    page: "control-plane",
    signal: "Agent Control Plane",
    endpoint: "/health",
    method: "GET",
  },
  {
    id: "memory-console",
    author: "langbot-team",
    plugin: "LongTermMemory",
    page: "memory_console",
    signal: "Memory Console",
    endpoint: "/summary",
    method: "GET",
  },
  {
    id: "langrag-observability",
    author: "langbot-team",
    plugin: "LangRAG",
    page: "observability",
    signal: "LangRAG Observability",
    endpoint: "/snapshot",
    method: "GET",
  },
  {
    id: "skill-authoring",
    author: "huanghuoguoguo",
    plugin: "skill-authoring",
    page: "authoring",
    signal: "Skill Authoring",
    endpoint: "/health",
    method: "GET",
  },
];

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
  frontend_url: frontendUrl,
  backend_url: backendUrl,
  pages: [],
  browser_diagnostics: null,
  evidence: {
    console_log: paths.consoleLog,
    network_log: paths.networkLog,
    screenshot: paths.screenshot,
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["ui", "screenshot", "console", "network", "api_diagnostic"],
};

let browser;
try {
  if (!frontendUrl || !backendUrl) throw new Error("LANGBOT_FRONTEND_URL and LANGBOT_BACKEND_URL must be configured.");
  browser = await createBrowser(paths);
  const { page } = browser;
  await page.goto(frontendUrl, { waitUntil: "domcontentloaded" });
  const auth = await ensureAuthenticatedBrowser(page, { frontendUrl, backendUrl });
  if (auth.status !== "pass") {
    result.status = auth.status;
    throw new Error(auth.reason);
  }
  const token = await page.evaluate(() => localStorage.getItem("token") || "");
  const pluginsResponse = await apiJson(backendUrl, "/api/v1/plugins", { token });
  if (pluginsResponse.status >= 400 || pluginsResponse.json.code !== 0) {
    throw new Error(pluginsResponse.json.msg || "Failed to list installed plugins.");
  }
  const installed = new Map((pluginsResponse.json.data?.plugins || []).map((item) => {
    const metadata = item.manifest?.manifest?.metadata || item.manifest?.metadata || {};
    return [`${metadata.author || ""}/${metadata.name || ""}`, item];
  }));
  const missing = targets.filter((target) => {
    const plugin = installed.get(`${target.author}/${target.plugin}`);
    if (!plugin) return true;
    const pages = plugin.manifest?.manifest?.spec?.pages || plugin.manifest?.spec?.pages || [];
    return !pages.some((pageSpec) => pageSpec.id === target.page);
  });
  if (missing.length) {
    result.status = "blocked";
    throw new Error(`Required plugin page fixture(s) are not installed or do not register the expected Page ID: ${missing.map((item) => item.id).join(", ")}`);
  }

  for (const target of targets) {
    const routeId = `${target.author}/${target.plugin}/${target.page}`;
    const route = `${frontendUrl.replace(/\/$/, "")}/home/plugin-pages?id=${encodeURIComponent(routeId)}`;
    const pageResult = {
      id: target.id,
      route,
      visible_signal: target.signal,
      ui_status: "fail",
      api_status: "fail",
      screenshot: join(paths.evidenceDir, `${target.id}.png`),
      page_api: null,
    };
    result.pages.push(pageResult);

    await page.goto(route, { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => {});
    const frame = page.frameLocator("iframe").first();
    await frame.getByText(target.signal, { exact: true }).first().waitFor({ state: "visible", timeout: 30_000 });
    pageResult.ui_status = "pass";
    await safeScreenshot(page, pageResult.screenshot);

    const apiResponse = await apiJson(
      backendUrl,
      `/api/v1/plugins/${encodeURIComponent(target.author)}/${encodeURIComponent(target.plugin)}/page-api`,
      {
        method: "POST",
        token,
        body: { page_id: target.page, endpoint: target.endpoint, method: target.method, body: null },
      },
    );
    pageResult.page_api = {
      endpoint: target.endpoint,
      method: target.method,
      http_status: apiResponse.status,
      code: apiResponse.json.code ?? null,
      has_data: apiResponse.json.data !== undefined && apiResponse.json.data !== null,
    };
    if (apiResponse.status >= 400 || apiResponse.json.code !== 0 || apiResponse.json.data == null) {
      throw new Error(`${target.id} Page API ${target.method} ${target.endpoint} failed.`);
    }
    pageResult.api_status = "pass";
  }

  await safeScreenshot(page, paths.screenshot);
  result.browser_diagnostics = await scanBrowserDiagnostics(paths);
  if (result.browser_diagnostics.status !== "pass") {
    throw new Error(result.browser_diagnostics.reason);
  }
  result.status = "pass";
  result.reason = "All workspace plugin pages rendered in the LangBot WebUI and their read-only Page APIs passed.";
} catch (error) {
  if (result.status === "fail" && /configured|Playwright is not installed|ECONNREFUSED|ERR_CONNECTION/i.test(error.message)) {
    result.status = "env_issue";
  }
  result.reason = error.message;
} finally {
  if (browser?.page) await safeScreenshot(browser.page, paths.screenshot);
  if (browser) await browser.close().catch(() => {});
  const finishedAt = new Date();
  result.finished_at = finishedAt.toISOString();
  result.finished_at_local = localIsoWithOffset(finishedAt);
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(exitCode(result.status));
