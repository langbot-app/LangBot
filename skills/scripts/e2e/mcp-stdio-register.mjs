#!/usr/bin/env node

import { existsSync, readFileSync } from "node:fs";
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { env } from "node:process";
import {
  createBrowser,
  ensureEvidence,
  evidencePaths,
  exitCode,
  localIsoWithOffset,
  safeScreenshot,
  writeResult,
} from "./lib/langbot-e2e.mjs";

function loadEnvDefaults(path) {
  if (!existsSync(path)) return;
  for (const rawLine of readFileSync(path, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const sep = line.indexOf("=");
    if (sep === -1) continue;
    const key = line.slice(0, sep).trim();
    if (env[key]) continue;
    env[key] = line.slice(sep + 1).trim().replace(/^["']|["']$/g, "");
  }
}

loadEnvDefaults("skills/.env");
loadEnvDefaults("skills/.env.local");

const caseId = env.LBS_CASE_ID || "mcp-stdio-register";
const paths = evidencePaths(caseId);
await ensureEvidence(paths);

const startedAt = new Date();
const serverName = env.LANGBOT_MCP_SERVER_NAME || "qa-local-stdio";
const expectedTool = env.LANGBOT_MCP_EXPECTED_TOOL || "qa_mcp_echo";
const fixturePath = resolve(env.LANGBOT_MCP_FIXTURE_PATH || "skills/langbot-testing/fixtures/mcp/qa_mcp_echo_server.py");
const fixtureCommand = env.LANGBOT_MCP_FIXTURE_COMMAND || "python";
const fixtureArgs = env.LANGBOT_MCP_FIXTURE_ARGS
  ? JSON.parse(env.LANGBOT_MCP_FIXTURE_ARGS)
  : [fixturePath];
const startupTimeoutSec = Number(env.LANGBOT_MCP_STARTUP_TIMEOUT_SEC || "300");
const readyTimeoutMs = Number(env.LANGBOT_MCP_READY_TIMEOUT_MS || "360000");
const backendUrl = env.LANGBOT_BACKEND_URL || "";
const apiDiagnosticPath = resolve(paths.evidenceDir, "api-diagnostic.json");
const envLocalPath = resolve("skills/.env.local");
const serverUuidEnvKey = env.LANGBOT_MCP_SERVER_UUID_ENV_KEY || "LANGBOT_MCP_QA_STDIO_SERVER_UUID";

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
  server_name: serverName,
  fixture_path: fixturePath,
  expected_tool: expectedTool,
  evidence: {
    console_log: paths.consoleLog,
    network_log: paths.networkLog,
    screenshot: paths.screenshot,
    api_diagnostic_json: apiDiagnosticPath,
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["screenshot", "console", "network", "api_diagnostic"],
  wrote_env: false,
};

async function run() {
  if (!backendUrl) {
    result.status = "env_issue";
    result.reason = "LANGBOT_BACKEND_URL is not configured.";
    return;
  }
  if (!existsSync(fixturePath)) {
    result.status = "env_issue";
    result.reason = `MCP fixture not found: ${fixturePath}`;
    return;
  }

  browser = await createBrowser(paths);
  const { page } = browser;
  await page.goto(env.LANGBOT_FRONTEND_URL, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});

  const diagnostic = await page.evaluate(async ({
    backendUrl,
    serverName,
    expectedTool,
    fixturePath,
    fixtureCommand,
    fixtureArgs,
    startupTimeoutSec,
    readyTimeoutMs,
  }) => {
    const token = localStorage.getItem("token");
    if (!token) {
      return {
        authenticated: false,
        save_status: 0,
        save_code: null,
        save_msg: "Browser profile has no localStorage token.",
        tool_names: [],
        has_expected_tool: false,
        runtime_status: null,
        runtime_tool_names: [],
        runtime_error: "",
      };
    }

    const headers = {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    };
    const serverConfig = {
      name: serverName,
      mode: "stdio",
      enable: true,
      extra_args: {
        command: fixtureCommand,
        args: fixtureArgs,
        env: {},
        box: {
          startup_timeout_sec: startupTimeoutSec,
        },
      },
    };
    const getJson = async (path) => {
      const response = await fetch(`${backendUrl}${path}`, { headers });
      return {
        status: response.status,
        json: await response.json().catch(() => ({})),
      };
    };
    const sendJson = async (method, path, body) => {
      const response = await fetch(`${backendUrl}${path}`, {
        method,
        headers,
        body: JSON.stringify(body),
      });
      return {
        status: response.status,
        json: await response.json().catch(() => ({})),
      };
    };

    const serverPath = `/api/v1/mcp/servers/${encodeURIComponent(serverName)}`;
    const beforeServer = await getJson(serverPath);
    const save = beforeServer.status === 404
      ? await sendJson("POST", "/api/v1/mcp/servers", serverConfig)
      : await sendJson("PUT", serverPath, serverConfig);

    const deadline = Date.now() + readyTimeoutMs;
    let lastTools = [];
    let lastRuntime = null;
    let lastServer = null;
    while (Date.now() < deadline) {
      await new Promise((resolveReady) => setTimeout(resolveReady, 500));
      const tools = await getJson("/api/v1/tools");
      const server = await getJson(serverPath);
      lastTools = (tools.json.data?.tools || [])
        .map((tool) => tool.name || tool.tool_name || tool.function?.name || "")
        .filter(Boolean)
        .sort();
      lastServer = server.json.data?.server || null;
      lastRuntime = lastServer?.runtime_info || null;
      if (lastTools.includes(expectedTool)) break;
    }

    return {
      authenticated: true,
      before_status: beforeServer.status,
      save_status: save.status,
      save_code: save.json.code ?? null,
      save_msg: save.json.msg || "",
      server_uuid: lastServer?.uuid || save.json.data?.uuid || "",
      tool_names: lastTools,
      has_expected_tool: lastTools.includes(expectedTool),
      runtime_status: lastRuntime?.status || null,
      runtime_tool_names: (lastRuntime?.tools || [])
        .map((tool) => tool.name || tool.tool_name || "")
        .filter(Boolean)
        .sort(),
      runtime_tool_count: lastRuntime?.tool_count ?? null,
      runtime_error: lastRuntime?.error_message || "",
    };
  }, { backendUrl, serverName, expectedTool, fixturePath, fixtureCommand, fixtureArgs, startupTimeoutSec, readyTimeoutMs });

  await writeFile(apiDiagnosticPath, `${JSON.stringify(diagnostic, null, 2)}\n`, "utf8");
  await safeScreenshot(page, paths.screenshot);

  if (!diagnostic.authenticated) {
    result.status = "blocked";
    result.reason = "Browser profile is not authenticated for LangBot; cannot update MCP server.";
    return;
  }
  if (diagnostic.save_status >= 400 || diagnostic.save_code !== 0) {
    result.status = "fail";
    result.reason = `Failed to save MCP server ${serverName}: ${diagnostic.save_status} ${diagnostic.save_msg}`;
    return;
  }
  if (diagnostic.runtime_status !== "connected") {
    result.status = "fail";
    result.reason = `MCP server ${serverName} is not connected after save: ${diagnostic.runtime_status || "missing runtime"}. ${diagnostic.runtime_error}`;
    return;
  }
  if (!diagnostic.has_expected_tool || !diagnostic.runtime_tool_names.includes(expectedTool)) {
    result.status = "fail";
    result.reason = `MCP server ${serverName} did not expose ${expectedTool}. See ${apiDiagnosticPath}.`;
    return;
  }
  if (!diagnostic.server_uuid) {
    result.status = "fail";
    result.reason = `MCP server ${serverName} exposed ${expectedTool}, but the server UUID was not returned. See ${apiDiagnosticPath}.`;
    return;
  }

  await upsertEnvLocal(envLocalPath, {
    [serverUuidEnvKey]: diagnostic.server_uuid,
  });
  result.wrote_env = true;
  result.server_uuid = diagnostic.server_uuid;
  result.server_uuid_env_key = serverUuidEnvKey;

  result.status = "pass";
  result.reason = `MCP server ${serverName} is connected and exposes ${expectedTool} through LangBot /api/v1/tools.`;
}

async function upsertEnvLocal(path, updates) {
  let text = "";
  try {
    text = await readFile(path, "utf8");
  } catch {
    text = "";
  }

  const lines = text ? text.split(/\r?\n/) : [];
  const seen = new Set();
  const updated = lines.map((line) => {
    const match = line.match(/^([A-Z][A-Z0-9_]*)=/);
    if (!match || !Object.prototype.hasOwnProperty.call(updates, match[1])) return line;
    seen.add(match[1]);
    return `${match[1]}=${updates[match[1]]}`;
  });

  for (const [key, value] of Object.entries(updates)) {
    if (!seen.has(key)) updated.push(`${key}=${value}`);
  }

  await writeFile(path, `${updated.filter((line, index) => line || index < updated.length - 1).join("\n")}\n`, "utf8");
}

try {
  await run();
} catch (error) {
  result.status = /Playwright is not installed|LANGBOT_FRONTEND_URL/.test(error.message) ? "env_issue" : "fail";
  result.reason = error instanceof Error ? error.message : String(error);
} finally {
  if (browser) await browser.close().catch(() => {});
  const finishedAt = new Date();
  result.finished_at = finishedAt.toISOString();
  result.finished_at_local = localIsoWithOffset(finishedAt);
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(exitCode(result.status));
