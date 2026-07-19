#!/usr/bin/env node

import { writeFile } from "node:fs/promises";
import { env } from "node:process";
import {
  DEBUG_CHAT_FAILURE_SIGNALS,
  openPipelineDebugChat,
  setDebugChatStreamOutput,
  visibleDebugChatMessages,
  waitForDebugChatTextStable,
} from "./lib/debug-chat.mjs";
import {
  beginBackendLogCapture,
  createBrowser,
  ensureAuthenticatedBrowser,
  ensureEvidence,
  evidencePaths,
  exitCode,
  finishBackendLogCapture,
  localIsoWithOffset,
  loadEnvFiles,
  pathExists,
  safeScreenshot,
  writeResult,
} from "./lib/langbot-e2e.mjs";

await loadEnvFiles();

const caseId = env.LBS_CASE_ID || "local-agent-steering-debug-chat";
const paths = evidencePaths(caseId);
await ensureEvidence(paths);
const backendLogCapture = await beginBackendLogCapture(paths.evidenceDir);

const backendUrl = (env.LANGBOT_BACKEND_URL || "").replace(/\/$/, "");
const pipelineUrl = env.LANGBOT_E2E_PIPELINE_URL || env.LANGBOT_LOCAL_AGENT_PIPELINE_URL || env.LANGBOT_PIPELINE_URL || "";
const pipelineName = env.LANGBOT_E2E_PIPELINE_NAME || env.LANGBOT_LOCAL_AGENT_PIPELINE_NAME || env.LANGBOT_PIPELINE_NAME || "";
const expectedRunnerId = env.LANGBOT_E2E_EXPECTED_RUNNER_ID || "plugin:langbot-team/LocalAgent/default";
const expectedText = env.LANGBOT_E2E_EXPECTED_TEXT || "qa_steering_sentinel_6194";
const responseTimeoutMs = positiveInt(env.LANGBOT_E2E_RESPONSE_TIMEOUT_MS, 240000);
const followupDelayMs = 1000;
const followupEnabledTimeoutMs = 1500;
const firstPrompt = env.LANGBOT_E2E_PROMPT || [
  "You are running the LangBot steering E2E test.",
  "First call the qa_plugin_sleep tool with seconds=8 and text=steering-e2e-anchor.",
  "Do not answer before the tool result is available.",
  "After the tool returns, answer the latest user follow-up.",
  "If no follow-up was injected, reply only STEERING_NO_FOLLOWUP.",
].join(" ");
const followupPrompt = [
  "This is a steering follow-up sent while the first tool call is still active.",
  `Return only ${expectedText}.`,
].join(" ");

const pipelineConfigDiagnosticPath = `${paths.evidenceDir}/pipeline-config-diagnostic.json`;
const debugChatResetDiagnosticPath = `${paths.evidenceDir}/debug-chat-reset-diagnostic.json`;
const toolDiagnosticPath = `${paths.evidenceDir}/tool-diagnostic.json`;

let browser;
const result = {
  source: "automation",
  case_id: caseId,
  run_id: paths.runId,
  status: "fail",
  reason: "",
  started_at: new Date().toISOString(),
  started_at_local: localIsoWithOffset(new Date()),
  url: "",
  backend_url: backendUrl,
  pipeline_url: pipelineUrl,
  pipeline_name: pipelineName,
  expected_runner_id: expectedRunnerId,
  first_prompt: firstPrompt,
  followup_prompt: followupPrompt,
  expected_text: expectedText,
  followup_delay_ms: followupDelayMs,
  followup_enabled_timeout_ms: followupEnabledTimeoutMs,
  response_timeout_ms: responseTimeoutMs,
  pipeline_config: null,
  debug_chat_reset: null,
  tool_diagnostic: null,
  browser_auth: null,
  steering: null,
  evidence: {
    console_log: paths.consoleLog,
    network_log: paths.networkLog,
    screenshot: paths.screenshot,
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["ui", "console", "network", "screenshot"],
};

try {
  if (!backendUrl) {
    result.status = "env_issue";
    result.reason = "LANGBOT_BACKEND_URL is required.";
    throw new Error(result.reason);
  }

  browser = await createBrowser(paths);
  const { page } = browser;

  const authDiagnostic = await ensureAuthenticatedBrowser(page, {
    frontendUrl: env.LANGBOT_FRONTEND_URL || "",
    backendUrl,
  });
  result.browser_auth = authDiagnostic;
  if (!result.evidence_collected.includes("api_diagnostic")) result.evidence_collected.push("api_diagnostic");
  if (authDiagnostic.status === "env_issue" || authDiagnostic.status === "blocked" || authDiagnostic.status === "fail") {
    result.status = authDiagnostic.status;
    result.reason = authDiagnostic.reason || "Browser authentication failed.";
    throw new Error(result.reason);
  }

  const openResult = await openPipelineDebugChat(page, {
    pipelineUrl,
    pipelineName,
    envHint: "case-specific pipeline env mapped to LANGBOT_E2E_PIPELINE_URL or LANGBOT_E2E_PIPELINE_NAME",
  });
  result.url = page.url();
  if (!openResult.opened) {
    result.status = openResult.status;
    result.reason = openResult.reason;
  } else {
    const pipelineDiagnostic = await inspectPipeline(page, {
      backendUrl,
      pipelineUrl,
      pipelineName,
      expectedRunnerId,
    });
    await writeFile(pipelineConfigDiagnosticPath, `${JSON.stringify(pipelineDiagnostic, null, 2)}\n`, "utf8");
    result.evidence.pipeline_config_diagnostic_json = pipelineConfigDiagnosticPath;
    result.pipeline_config = pipelineDiagnostic;
    if (!result.evidence_collected.includes("api_diagnostic")) result.evidence_collected.push("api_diagnostic");

    const toolDiagnostic = await inspectToolNames(page, { backendUrl });
    await writeFile(toolDiagnosticPath, `${JSON.stringify(toolDiagnostic, null, 2)}\n`, "utf8");
    result.evidence.tool_diagnostic_json = toolDiagnosticPath;
    result.tool_diagnostic = toolDiagnostic;

    if (pipelineDiagnostic.status === "fail" || pipelineDiagnostic.status === "blocked") {
      result.status = pipelineDiagnostic.status;
      result.reason = pipelineDiagnostic.reason || "Pipeline diagnostic failed.";
    } else if (toolDiagnostic.status === "fail" || toolDiagnostic.status === "blocked") {
      result.status = toolDiagnostic.status;
      result.reason = toolDiagnostic.reason || "Tool diagnostic failed.";
    } else if (!toolDiagnostic.tool_names.includes("qa_plugin_sleep")) {
      result.status = "blocked";
      result.reason = "qa_plugin_sleep is not exposed by /api/v1/tools; rebuild/reinstall qa-plugin-smoke before running steering E2E.";
    } else {
      const resetDiagnostic = await resetPipelineDebugChat(page, {
        backendUrl,
        pipelineId: pipelineDiagnostic.pipeline_id,
        sessionType: "person",
      });
      await writeFile(debugChatResetDiagnosticPath, `${JSON.stringify(resetDiagnostic, null, 2)}\n`, "utf8");
      result.evidence.debug_chat_reset_diagnostic_json = debugChatResetDiagnosticPath;
      result.debug_chat_reset = resetDiagnostic;

      if (resetDiagnostic.status === "fail" || resetDiagnostic.status === "blocked") {
        result.status = resetDiagnostic.status;
        result.reason = resetDiagnostic.reason || "Debug Chat reset failed.";
      } else {
        await page.waitForTimeout(1000);
        const reopenResult = await openPipelineDebugChat(page, {
          pipelineUrl,
          pipelineName,
          envHint: "case-specific pipeline env mapped to LANGBOT_E2E_PIPELINE_URL or LANGBOT_E2E_PIPELINE_NAME",
        });
        result.url = page.url();
        if (!reopenResult.opened) {
          result.status = reopenResult.status;
          result.reason = reopenResult.reason;
        } else {
          const streamResult = await setDebugChatStreamOutput(page, true);
          if (streamResult.status === "blocked" || streamResult.status === "fail") {
            result.status = streamResult.status;
            result.reason = streamResult.reason;
          } else {
            result.steering = await runSteeringProbe(page);
            result.status = result.steering.status;
            result.reason = result.steering.reason;
          }
        }
      }
    }
  }
} catch (error) {
  if (!["env_issue", "blocked", "fail", "pass"].includes(result.status) || !result.reason) {
    result.status = /Playwright is not installed|LANGBOT_FRONTEND_URL/.test(error.message) ? "env_issue" : "fail";
  }
  result.reason = result.reason || error.message;
} finally {
  if (browser?.page) await safeScreenshot(browser.page, paths.screenshot);
  if (browser) await browser.close().catch(() => {});
  const backendLog = await finishBackendLogCapture(backendLogCapture);
  if (backendLog) {
    result.evidence.backend_log = backendLog.path;
    result.backend_log = backendLog;
    if (!result.evidence_collected.includes("backend_log")) result.evidence_collected.push("backend_log");
  }
  const finishedAt = new Date();
  result.finished_at = finishedAt.toISOString();
  result.finished_at_local = localIsoWithOffset(finishedAt);
  const existingEvidence = {};
  for (const [key, value] of Object.entries(result.evidence)) {
    if (typeof value !== "string") continue;
    const isResultFile = value === paths.automationResultJson || value === paths.resultJson;
    if (isResultFile || await pathExists(value)) existingEvidence[key] = value;
  }
  result.evidence = existingEvidence;
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(exitCode(result.status));

async function runSteeringProbe(page) {
  const beforeMessages = await visibleDebugChatMessages(page);
  const beforeAssistantCount = countRole(beforeMessages, "assistant");
  const beforeUserCount = countRole(beforeMessages, "user");
  const firstStartedAt = Date.now();
  const firstSend = await sendPrompt(page, firstPrompt, { enabledTimeoutMs: 5000 });
  if (!firstSend.sent) {
    return {
      status: "fail",
      reason: firstSend.reason || "Could not send first Debug Chat prompt.",
      first_send: firstSend,
      before_assistant_count: beforeAssistantCount,
      before_user_count: beforeUserCount,
    };
  }

  await page.waitForTimeout(followupDelayMs);
  const preFollowupMessages = await visibleDebugChatMessages(page);
  const preFollowupAssistantCount = countRole(preFollowupMessages, "assistant");
  const followupStartedAt = Date.now();
  const followupSend = await sendPrompt(page, followupPrompt, { enabledTimeoutMs: followupEnabledTimeoutMs });
  const followupSentAt = Date.now();
  if (!followupSend.sent) {
    return {
      status: "fail",
      reason: followupSend.reason || "Could not send steering follow-up while the first run was active.",
      first_send: firstSend,
      followup_send: followupSend,
      first_to_followup_attempt_ms: followupStartedAt - firstStartedAt,
      followup_send_latency_ms: followupSentAt - followupStartedAt,
      before_assistant_count: beforeAssistantCount,
      pre_followup_assistant_count: preFollowupAssistantCount,
      before_user_count: beforeUserCount,
    };
  }

  const waitResult = await waitForLatestAssistantContaining(page, {
    expectedText,
    beforeAssistantCount,
    timeoutMs: responseTimeoutMs,
  });
  await waitForDebugChatTextStable(page);
  const afterMessages = await visibleDebugChatMessages(page);
  const afterAssistantCount = countRole(afterMessages, "assistant");
  const afterUserCount = countRole(afterMessages, "user");
  const latestAssistantText = latestRoleText(afterMessages, "assistant");
  const failureSignal = findFailureSignal(latestAssistantText) || findFailureSignal(messagesText(afterMessages));
  const newAssistantCount = afterAssistantCount - beforeAssistantCount;
  const newUserCount = afterUserCount - beforeUserCount;

  const base = {
    first_send: firstSend,
    followup_send: followupSend,
    first_to_followup_attempt_ms: followupStartedAt - firstStartedAt,
    followup_send_latency_ms: followupSentAt - followupStartedAt,
    before_assistant_count: beforeAssistantCount,
    pre_followup_assistant_count: preFollowupAssistantCount,
    after_assistant_count: afterAssistantCount,
    new_assistant_count: newAssistantCount,
    before_user_count: beforeUserCount,
    after_user_count: afterUserCount,
    new_user_count: newUserCount,
    latest_assistant_text: latestAssistantText,
    assistant_containing_expected_seen: waitResult.seen,
    failure_signal: failureSignal,
  };

  if (failureSignal) {
    return {
      ...base,
      status: "fail",
      reason: `Debug Chat displayed a known failure signal: ${failureSignal}`,
    };
  }
  if (!waitResult.seen) {
    return {
      ...base,
      status: "fail",
      reason: `No new assistant message contained steering sentinel ${expectedText}.`,
    };
  }
  if (!latestAssistantText.includes(expectedText)) {
    return {
      ...base,
      status: "fail",
      reason: `Latest assistant message did not contain steering sentinel ${expectedText}.`,
    };
  }
  if (newUserCount < 2) {
    return {
      ...base,
      status: "fail",
      reason: `Expected two new user messages, saw ${newUserCount}.`,
    };
  }
  if (newAssistantCount !== 1) {
    return {
      ...base,
      status: "fail",
      reason: `Expected one assistant response for one claimed steering run, saw ${newAssistantCount}. More than one usually means the follow-up became a separate run.`,
    };
  }
  if (latestAssistantText.includes("STEERING_NO_FOLLOWUP")) {
    return {
      ...base,
      status: "fail",
      reason: "Runner answered the no-follow-up branch, so steering was not injected.",
    };
  }

  return {
    ...base,
    status: "pass",
    reason: `Follow-up sentinel ${expectedText} appeared in the only new assistant response after two user messages.`,
  };
}

function debugChatInput(page) {
  return page
    .locator('input[placeholder*="message"], input[placeholder*="消息"], textarea[placeholder*="message"], textarea[placeholder*="消息"]')
    .last();
}

async function sendPrompt(page, prompt, { enabledTimeoutMs }) {
  const input = debugChatInput(page);
  const inputVisible = await input.isVisible({ timeout: 5000 }).catch(() => false);
  if (!inputVisible) return { sent: false, reason: "Debug Chat input is not visible." };
  const inputEnabled = await input.isEnabled({ timeout: enabledTimeoutMs }).catch(() => false);
  if (!inputEnabled) return { sent: false, reason: `Debug Chat input was not enabled within ${enabledTimeoutMs}ms.` };

  await input.fill(prompt).catch(async () => {
    await input.click();
    await input.pressSequentially(prompt);
  });
  await input.press("Enter");
  await page.getByText(prompt, { exact: false }).last().waitFor({ state: "visible", timeout: 10000 }).catch(() => {});
  return {
    sent: true,
    submitted_by: "keyboard_enter",
  };
}

async function waitForLatestAssistantContaining(page, { expectedText, beforeAssistantCount, timeoutMs }) {
  const deadline = Date.now() + timeoutMs;
  let lastMessages = [];
  let latestAssistantText = "";
  while (Date.now() < deadline) {
    const messages = await visibleDebugChatMessages(page);
    lastMessages = messages;
    latestAssistantText = latestRoleText(messages, "assistant");
    if (countRole(messages, "assistant") > beforeAssistantCount && latestAssistantText.includes(expectedText)) {
      return {
        seen: true,
        latest_assistant_text: latestAssistantText,
        messages,
      };
    }
    const failureSignal = findFailureSignal(latestAssistantText);
    if (failureSignal) {
      return {
        seen: false,
        latest_assistant_text: latestAssistantText,
        messages,
        failure_signal: failureSignal,
      };
    }
    await page.waitForTimeout(500);
  }
  return {
    seen: false,
    latest_assistant_text: latestAssistantText,
    messages: lastMessages,
  };
}

async function inspectPipeline(page, { backendUrl, pipelineUrl, pipelineName, expectedRunnerId }) {
  const pipelineIdFromUrl = pipelineIdFromUrlValue(pipelineUrl);
  return await page.evaluate(async ({ backendUrl, pipelineIdFromUrl, pipelineName, expectedRunnerId }) => {
    const token = localStorage.getItem("token");
    if (!token) {
      return {
        status: "blocked",
        authenticated: false,
        reason: "Browser profile has no localStorage token.",
      };
    }
    const getJson = async (path) => {
      const response = await fetch(`${backendUrl}${path}`, {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });
      return {
        status: response.status,
        json: await response.json().catch(() => ({})),
      };
    };

    let pipelineId = pipelineIdFromUrl;
    let matchedBy = pipelineId ? "url" : "";
    if (!pipelineId) {
      if (!pipelineName) {
        return {
          status: "blocked",
          authenticated: true,
          pipeline_resolved: false,
          reason: "Set LANGBOT_LOCAL_AGENT_PIPELINE_URL or LANGBOT_LOCAL_AGENT_PIPELINE_NAME.",
        };
      }
      const list = await getJson("/api/v1/pipelines");
      const pipelines = list.json.data?.pipelines || [];
      const match = pipelines.find((pipeline) => pipeline.name === pipelineName);
      if (!match) {
        return {
          status: "blocked",
          authenticated: true,
          pipeline_resolved: false,
          list_status: list.status,
          reason: `Could not find pipeline named ${pipelineName}.`,
        };
      }
      pipelineId = match.uuid;
      matchedBy = "name";
    }

    const loaded = await getJson(`/api/v1/pipelines/${encodeURIComponent(pipelineId)}`);
    const pipeline = loaded.json.data?.pipeline;
    if (loaded.status >= 400 || !pipeline) {
      return {
        status: "fail",
        authenticated: true,
        pipeline_resolved: false,
        pipeline_id: pipelineId,
        get_status: loaded.status,
        reason: loaded.json.msg || "Could not load pipeline.",
      };
    }
    const config = pipeline.config || {};
    const runner = config.ai?.runner || {};
    const runnerId = runner.id || "";
    if (!runnerId) {
      return {
        status: "blocked",
        authenticated: true,
        pipeline_resolved: true,
        pipeline_id: pipelineId,
        pipeline_name: pipeline.name,
        matched_by: matchedBy,
        reason: "Pipeline has no ai.runner.id.",
      };
    }
    if (expectedRunnerId && runnerId !== expectedRunnerId) {
      return {
        status: "blocked",
        authenticated: true,
        pipeline_resolved: true,
        pipeline_id: pipelineId,
        pipeline_name: pipeline.name,
        matched_by: matchedBy,
        runner_id: runnerId,
        expected_runner_id: expectedRunnerId,
        reason: `Pipeline runner mismatch: expected ${expectedRunnerId}, got ${runnerId}.`,
      };
    }
    return {
      status: "ready",
      authenticated: true,
      pipeline_resolved: true,
      pipeline_id: pipelineId,
      pipeline_name: pipeline.name,
      matched_by: matchedBy,
      runner_id: runnerId,
      expected_runner_id: expectedRunnerId || "",
    };
  }, { backendUrl, pipelineIdFromUrl, pipelineName, expectedRunnerId });
}

async function inspectToolNames(page, { backendUrl }) {
  return await page.evaluate(async ({ backendUrl }) => {
    const token = localStorage.getItem("token");
    if (!token) {
      return {
        status: "blocked",
        authenticated: false,
        tool_names: [],
        reason: "Browser profile has no localStorage token.",
      };
    }
    const response = await fetch(`${backendUrl}/api/v1/tools`, {
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    });
    const json = await response.json().catch(() => ({}));
    const toolNames = (json.data?.tools || [])
      .map((tool) => tool.name || tool.tool_name || tool.function?.name || "")
      .filter(Boolean)
      .sort();
    return {
      status: response.status >= 400 ? "fail" : "ready",
      authenticated: true,
      http_status: response.status,
      code: json.code ?? null,
      tool_names: toolNames,
      reason: response.status >= 400 ? json.msg || "Could not list tools." : "Tool list loaded.",
    };
  }, { backendUrl });
}

async function resetPipelineDebugChat(page, { backendUrl, pipelineId, sessionType }) {
  return await page.evaluate(async ({ backendUrl, pipelineId, sessionType }) => {
    const token = localStorage.getItem("token");
    if (!token) {
      return {
        status: "blocked",
        authenticated: false,
        pipeline_id: pipelineId,
        session_type: sessionType,
        reason: "Browser profile has no localStorage token.",
      };
    }
    const response = await fetch(
      `${backendUrl}/api/v1/pipelines/${encodeURIComponent(pipelineId)}/ws/reset/${encodeURIComponent(sessionType)}`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      },
    );
    const json = await response.json().catch(() => ({}));
    return {
      status: response.status >= 400 ? "fail" : "ready",
      authenticated: true,
      pipeline_id: pipelineId,
      session_type: sessionType,
      reset_status: response.status,
      reset_code: json.code ?? null,
      reason: response.status >= 400 ? json.msg || "Debug Chat reset failed." : "Debug Chat session reset.",
    };
  }, { backendUrl, pipelineId, sessionType });
}

function pipelineIdFromUrlValue(value) {
  const match = String(value || "").match(/\/pipelines?\/([^/?#]+)/i);
  return match ? decodeURIComponent(match[1]) : "";
}

function countRole(messages, role) {
  return messages.filter((message) => message.role === role).length;
}

function latestRoleText(messages, role) {
  return messages.filter((message) => message.role === role).at(-1)?.text || "";
}

function messagesText(messages) {
  return messages.map((message) => message.text).join("\n");
}

function findFailureSignal(text) {
  return DEBUG_CHAT_FAILURE_SIGNALS.find((signal) => String(text || "").includes(signal)) || "";
}

function positiveInt(value, fallback) {
  const parsed = Number.parseInt(String(value || ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}
