#!/usr/bin/env node

import {
  bodyText,
  createBrowser,
  ensureEvidence,
  evidencePaths,
  exitCode,
  isLoginUrl,
  localIsoWithOffset,
  safeScreenshot,
  writeResult,
} from "./lib/langbot-e2e.mjs";

const caseId = process.env.LBS_CASE_ID || "langrag-kb-retrieve";
const paths = evidencePaths(caseId);
await ensureEvidence(paths);

const startedAt = new Date();
const frontendUrl = process.env.LANGBOT_FRONTEND_URL || "";
const backendUrl = process.env.LANGBOT_BACKEND_URL || "";
const kbUuid = process.env.LANGBOT_LOCAL_AGENT_RAG_KB_UUID || process.env.LANGBOT_RAG_KB_UUID || "";
const query = process.env.LANGBOT_E2E_RETRIEVE_QUERY || "What is the local agent runner retrieval sentinel?";
const expectedText = process.env.LANGBOT_E2E_EXPECTED_TEXT || "azalea-cobalt-7421";

let browser;
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
  kb_uuid: kbUuid,
  query,
  expected_text: expectedText,
  evidence: {
    console_log: paths.consoleLog,
    network_log: paths.networkLog,
    screenshot: paths.screenshot,
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["ui", "screenshot", "console", "network", "api_diagnostic"],
};

try {
  if (!frontendUrl) throw new Error("LANGBOT_FRONTEND_URL is not configured.");
  if (!backendUrl) throw new Error("LANGBOT_BACKEND_URL is not configured.");
  if (!kbUuid) throw new Error("LANGBOT_LOCAL_AGENT_RAG_KB_UUID or LANGBOT_RAG_KB_UUID is required.");

  browser = await createBrowser(paths);
  const { page } = browser;
  await page.goto(`${frontendUrl.replace(/\/$/, "")}/home/knowledge`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
  result.url = page.url();

  const text = await bodyText(page);
  if (isLoginUrl(page.url()) || /登录|Login|Sign in/i.test(text)) {
    result.status = "blocked";
    result.reason = "Browser profile is not authenticated for LANGBOT_FRONTEND_URL.";
  } else if (!/Knowledge|知识库|qa-local-agent-rag/i.test(text)) {
    result.status = "fail";
    result.reason = "Knowledge page opened, but no Knowledge UI signal or QA KB name was visible.";
  } else {
    const retrieve = await page.evaluate(async ({ backendUrl, kbUuid, query }) => {
      const token = localStorage.getItem("token");
      if (!token) {
        return { status: "blocked", authenticated: false, reason: "Browser profile has no localStorage token." };
      }
      const response = await fetch(`${backendUrl}/api/v1/knowledge/bases/${encodeURIComponent(kbUuid)}/retrieve`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query }),
      });
      const json = await response.json().catch(() => ({}));
      return {
        status: response.status >= 400 ? "fail" : "ready",
        authenticated: true,
        http_status: response.status,
        code: json.code ?? null,
        msg: json.msg || "",
        results: json.data?.results || [],
      };
    }, { backendUrl, kbUuid, query });

    result.retrieve = {
      ...retrieve,
      results: Array.isArray(retrieve.results)
        ? retrieve.results.map((item) => ({
            score: item.score ?? item.distance ?? null,
            text: String(item.text || item.content || "").slice(0, 500),
            metadata: item.metadata || {},
          }))
        : [],
    };

    const resultText = JSON.stringify(result.retrieve.results || []);
    if (retrieve.status === "blocked") {
      result.status = "blocked";
      result.reason = retrieve.reason || "Retrieve API blocked.";
    } else if (retrieve.status === "fail") {
      result.status = "fail";
      result.reason = retrieve.msg || "Retrieve API failed.";
    } else if (!resultText.includes(expectedText)) {
      result.status = "fail";
      result.reason = `Retrieve results did not contain expected text: ${expectedText}`;
    } else {
      result.status = "pass";
      result.reason = `Knowledge retrieve returned expected sentinel: ${expectedText}`;
    }
  }

  await safeScreenshot(page, paths.screenshot);
} catch (error) {
  result.status = /Playwright is not installed|not configured|required/.test(error.message) ? "env_issue" : "fail";
  result.reason = error.message;
} finally {
  if (browser) await browser.close().catch(() => {});
  const finishedAt = new Date();
  result.finished_at = finishedAt.toISOString();
  result.finished_at_local = localIsoWithOffset(finishedAt);
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(exitCode(result.status));
