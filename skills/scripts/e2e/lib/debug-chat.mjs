import {
  bodyText,
  clickFirstVisible,
  clickFirstVisibleLocator,
  countOccurrences,
  gotoFrontend,
  isLoginUrl,
} from "./langbot-e2e.mjs";

export const DEBUG_CHAT_FAILURE_SIGNALS = [
  "Agent runner temporarily unavailable",
  "All models failed during streaming setup",
  "调用超时",
  "超时",
];

export function minExpectedOccurrences(beforeText, expectedText, prompt) {
  const beforeCount = countOccurrences(beforeText, expectedText);
  return beforeCount + (String(prompt).includes(expectedText) ? 2 : 1);
}

export function latestExpectedLeafMatches(latestExpectedLeaf, prompt) {
  return Boolean(latestExpectedLeaf)
    && latestExpectedLeaf !== prompt
    && !String(latestExpectedLeaf).includes(prompt);
}

export function findNewFailureSignal(beforeText, afterText, failureSignals = DEBUG_CHAT_FAILURE_SIGNALS) {
  return failureSignals.find((signal) => countOccurrences(afterText, signal) > countOccurrences(beforeText, signal)) || "";
}

export function hasDebugChatOutcome(text, expectedText, minExpectedCount, failureBaselines = []) {
  if (countOccurrences(text, expectedText) >= minExpectedCount) return true;
  return failureBaselines.some(({ signal, count }) => countOccurrences(text, signal) > count);
}

function findFailureSignalInText(text, failureSignals = DEBUG_CHAT_FAILURE_SIGNALS) {
  return failureSignals.find((signal) => String(text || "").includes(signal)) || "";
}

function countExpectedInMessages(messages, expectedText) {
  return messages
    .filter((message) => message.role === "assistant")
    .reduce((count, message) => count + countOccurrences(message.text, expectedText), 0);
}

function debugChatInput(page) {
  return page
    .locator('input[placeholder*="message"], input[placeholder*="消息"], textarea[placeholder*="message"], textarea[placeholder*="消息"]')
    .last();
}

async function clickDebugChatTab(page) {
  const label = /^(?:Debug Chat|调试聊天|调试对话|对话调试)$/i;
  const configuredTimeout = Number.parseInt(
    process.env.LANGBOT_E2E_UI_READY_TIMEOUT_MS
      || process.env.LANGBOT_E2E_NAVIGATION_TIMEOUT_MS
      || "30000",
    10,
  );
  const timeout = Number.isFinite(configuredTimeout) && configuredTimeout > 0
    ? configuredTimeout
    : 30_000;
  return await clickFirstVisibleLocator(page, [
    page.getByRole("tab", { name: label }),
    page.locator('[data-slot="tabs-trigger"]').filter({ hasText: label }),
    page.getByText(label, { exact: true }),
  ], timeout);
}

export async function waitForDebugChatReady(page, timeout = 20_000) {
  const input = debugChatInput(page);
  const visible = await input.isVisible({ timeout }).catch(() => false);
  if (!visible) {
    return {
      ready: false,
      reason: "Debug Chat tab was clicked, but the Debug Chat input did not become visible.",
    };
  }

  const deadline = Date.now() + timeout;
  let enabled = false;
  while (Date.now() < deadline) {
    enabled = await input.isEnabled().catch(() => false);
    if (enabled) break;
    await page.waitForTimeout(Math.min(250, Math.max(1, deadline - Date.now())));
  }
  if (!enabled) {
    return {
      ready: false,
      reason: "Debug Chat input is visible but disabled; WebSocket may not be connected.",
    };
  }

  return { ready: true, reason: "" };
}

export function classifyDebugChatResult({
  beforeText,
  afterText,
  expectedText,
  expectedTexts = null,
  prompt,
  latestExpectedLeaf,
  latestFailureLeaf,
  beforeMessages = null,
  afterMessages = null,
  latestAssistantText = "",
  latestAssistantIsFinal = null,
  maxNewAssistantMessages = null,
  failureSignals = DEBUG_CHAT_FAILURE_SIGNALS,
}) {
  const requiredExpectedTexts = [...new Set(
    (Array.isArray(expectedTexts) && expectedTexts.length > 0 ? expectedTexts : [expectedText])
      .map(String)
      .filter(Boolean),
  )];
  const minExpectedCount = minExpectedOccurrences(beforeText, expectedText, prompt);
  const finalCount = countOccurrences(afterText, expectedText);
  const failureText = findNewFailureSignal(beforeText, afterText, failureSignals);
  const promptContainsExpected = String(prompt).includes(expectedText);
  const hasMessageEvidence = Array.isArray(beforeMessages) && Array.isArray(afterMessages);
  const beforeAssistantExpectedCount = hasMessageEvidence
    ? countExpectedInMessages(beforeMessages, expectedText)
    : null;
  const afterAssistantExpectedCount = hasMessageEvidence
    ? countExpectedInMessages(afterMessages, expectedText)
    : null;
  const beforeAssistantMessageCount = hasMessageEvidence
    ? beforeMessages.filter((message) => message.role === "assistant").length
    : null;
  const afterAssistantMessageCount = hasMessageEvidence
    ? afterMessages.filter((message) => message.role === "assistant").length
    : null;
  const newAssistantMessageCount = hasMessageEvidence
    ? afterAssistantMessageCount - beforeAssistantMessageCount
    : null;
  const assistantMessageEvidence = {
    before_assistant_message_count: beforeAssistantMessageCount,
    after_assistant_message_count: afterAssistantMessageCount,
    new_assistant_message_count: newAssistantMessageCount,
  };

  if (hasMessageEvidence) {
    const missingExpectedTexts = requiredExpectedTexts.filter(
      (text) => !String(latestAssistantText).includes(text),
    );
    const latestAssistantFailure = findFailureSignalInText(latestAssistantText, failureSignals);
    if (latestAssistantFailure) {
      return {
        status: "fail",
        reason: `Debug Chat displayed a known failure signal in the latest assistant message: ${latestAssistantFailure}`,
        min_expected_count: minExpectedCount,
        final_count: finalCount,
        failure_signal: latestAssistantFailure,
        before_assistant_expected_count: beforeAssistantExpectedCount,
        after_assistant_expected_count: afterAssistantExpectedCount,
        ...assistantMessageEvidence,
      };
    }
    if (latestAssistantIsFinal === false) {
      return {
        status: "fail",
        reason: "The latest assistant message contained the expected text but was not final.",
        min_expected_count: minExpectedCount,
        final_count: finalCount,
        before_assistant_expected_count: beforeAssistantExpectedCount,
        after_assistant_expected_count: afterAssistantExpectedCount,
        ...assistantMessageEvidence,
        latest_assistant_is_final: false,
      };
    }
    if (maxNewAssistantMessages !== null && newAssistantMessageCount > maxNewAssistantMessages) {
      return {
        status: "fail",
        reason: `Debug Chat created ${newAssistantMessageCount} assistant messages; expected at most ${maxNewAssistantMessages}.`,
        min_expected_count: minExpectedCount,
        final_count: finalCount,
        before_assistant_expected_count: beforeAssistantExpectedCount,
        after_assistant_expected_count: afterAssistantExpectedCount,
        ...assistantMessageEvidence,
      };
    }
    if (newAssistantMessageCount > 0 && missingExpectedTexts.length === 0) {
      return {
        status: "pass",
        reason: requiredExpectedTexts.length === 1
          ? `Expected text appeared in a new assistant message: ${expectedText}`
          : `All ${requiredExpectedTexts.length} expected text fragments appeared in a new assistant message.`,
        min_expected_count: minExpectedCount,
        final_count: finalCount,
        before_assistant_expected_count: beforeAssistantExpectedCount,
        after_assistant_expected_count: afterAssistantExpectedCount,
        ...assistantMessageEvidence,
        missing_expected_texts: [],
      };
    }
    if (failureText) {
      return {
        status: "fail",
        reason: `Debug Chat displayed a known failure signal: ${failureText}`,
        min_expected_count: minExpectedCount,
        final_count: finalCount,
        failure_signal: failureText,
        before_assistant_expected_count: beforeAssistantExpectedCount,
        after_assistant_expected_count: afterAssistantExpectedCount,
        ...assistantMessageEvidence,
      };
    }
    return {
      status: "fail",
      reason: missingExpectedTexts.length > 0
        ? `A new assistant message was missing expected text: ${missingExpectedTexts.join(", ")}`
        : `Expected text did not appear in a new assistant message. Expected assistant occurrences to increase above ${beforeAssistantExpectedCount}, saw ${afterAssistantExpectedCount}.`,
      min_expected_count: minExpectedCount,
      final_count: finalCount,
      before_assistant_expected_count: beforeAssistantExpectedCount,
      after_assistant_expected_count: afterAssistantExpectedCount,
      ...assistantMessageEvidence,
      missing_expected_texts: missingExpectedTexts,
    };
  }
  if (failureText) {
    return {
      status: "fail",
      reason: `Debug Chat displayed a known failure signal: ${failureText}`,
      min_expected_count: minExpectedCount,
      final_count: finalCount,
      failure_signal: failureText,
      before_assistant_expected_count: beforeAssistantExpectedCount,
      after_assistant_expected_count: afterAssistantExpectedCount,
    };
  }
  if (latestExpectedLeafMatches(latestExpectedLeaf, prompt) && finalCount >= minExpectedCount) {
    return {
      status: "pass",
      reason: `Expected text appeared in the latest visible response leaf: ${expectedText}`,
      min_expected_count: minExpectedCount,
      final_count: finalCount,
    };
  }
  if (!promptContainsExpected && finalCount >= minExpectedCount) {
    return {
      status: "pass",
      reason: `Expected text appeared enough times for user prompt plus bot response: ${expectedText}`,
      min_expected_count: minExpectedCount,
      final_count: finalCount,
    };
  }
  return {
    status: "fail",
    reason: `Bot response did not appear. Expected ${minExpectedCount} occurrences of ${expectedText}, saw ${finalCount}.`,
    min_expected_count: minExpectedCount,
    final_count: finalCount,
  };
}

export async function openPipelineDebugChat(page, { pipelineUrl, pipelineName, envHint = "LANGBOT_PIPELINE_URL or LANGBOT_PIPELINE_NAME" }) {
  if (pipelineUrl) {
    let alreadyAtPipeline = false;
    try {
      alreadyAtPipeline = new URL(page.url()).href === new URL(pipelineUrl).href;
    } catch {
      // Invalid URLs are handled by page.goto below.
    }
    if (!alreadyAtPipeline) {
      await page.goto(pipelineUrl, { waitUntil: "commit" });
      await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
    }
  } else {
    if (!pipelineName) {
      return {
        opened: false,
        status: "blocked",
        reason: `Set ${envHint} before running pipeline-debug-chat automation.`,
      };
    }
    await gotoFrontend(page);
    if (isLoginUrl(page.url())) {
      return {
        opened: false,
        status: "blocked",
        reason: "Browser profile is not authenticated for LANGBOT_FRONTEND_URL.",
      };
    }
    const clickedPipelines = await clickFirstVisible(page, ["Pipelines", "流水线"], 4_000);
    if (!clickedPipelines) {
      return { opened: false, status: "fail", reason: "Could not find Pipelines navigation." };
    }
    await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
    const clickedPipeline = await clickFirstVisible(page, [pipelineName], 5_000);
    if (!clickedPipeline) {
      return { opened: false, status: "blocked", reason: `Could not find pipeline named ${pipelineName}.` };
    }
  }

  if (isLoginUrl(page.url())) {
    return {
      opened: false,
      status: "blocked",
      reason: "Browser profile is not authenticated for LANGBOT_FRONTEND_URL.",
    };
  }

  const clickedDebug = await clickDebugChatTab(page);
  if (!clickedDebug) {
    return { opened: false, status: "fail", reason: "Could not find the Debug Chat tab." };
  }
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
  const ready = await waitForDebugChatReady(page);
  if (!ready.ready) {
    return { opened: false, status: "fail", reason: ready.reason };
  }
  return { opened: true };
}

export async function latestVisibleLeafText(page, needles) {
  return await page.evaluate((items) => {
    const isVisible = (element) => {
      const style = window.getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.visibility !== "hidden"
        && style.display !== "none"
        && rect.width > 0
        && rect.height > 0;
    };
    const leaves = [];
    for (const element of document.body.querySelectorAll("*")) {
      if (!isVisible(element)) continue;
      const text = element.innerText?.trim();
      if (!text || text.length > 4000) continue;
      const visibleChildHasText = Array.from(element.children).some((child) => (
        isVisible(child) && child.innerText?.trim()
      ));
      if (visibleChildHasText) continue;
      if (!items.some((needle) => text.includes(needle))) continue;
      leaves.push(text);
    }
    return leaves.at(-1) || "";
  }, needles);
}

export async function visibleDebugChatMessages(page) {
  return await page.evaluate(() => {
    const isVisible = (element) => {
      const style = window.getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.visibility !== "hidden"
        && style.display !== "none"
        && rect.width > 0
        && rect.height > 0;
    };
    const classText = (element) => String(element.getAttribute("class") || "");
    return Array.from(document.querySelectorAll("div.max-w-3xl"))
      .filter((element) => isVisible(element))
      .map((element) => {
        const row = element.parentElement;
        const text = element.innerText?.trim() || "";
        const isUser = classText(element).includes("user-message-bubble")
          || classText(row).includes("justify-end");
        return {
          role: isUser ? "user" : "assistant",
          text,
        };
      })
      .filter((message) => message.text);
  });
}

export async function waitForExpectedDebugChatText(page, {
  expectedText,
  expectedTexts = null,
  minExpectedCount,
  minExpectedCounts = null,
  timeoutMs,
  beforeText = "",
  failureSignals = DEBUG_CHAT_FAILURE_SIGNALS,
}) {
  const requiredExpectedTexts = [...new Set(
    (Array.isArray(expectedTexts) && expectedTexts.length > 0 ? expectedTexts : [expectedText])
      .map(String)
      .filter(Boolean),
  )];
  const expectedRequirements = requiredExpectedTexts.map((text, index) => ({
    text,
    min: Array.isArray(minExpectedCounts) && Number.isFinite(minExpectedCounts[index])
      ? minExpectedCounts[index]
      : (text === expectedText ? minExpectedCount : minExpectedOccurrences(beforeText, text, "")),
  }));
  const failureBaselines = failureSignals.map((signal) => ({
    signal,
    count: countOccurrences(beforeText, signal),
  }));
  await page.waitForFunction(
    ({ requirements, failures }) => {
      const text = document.body.innerText;
      if (requirements.every((item) => text.split(item.text).length - 1 >= item.min)) return true;
      return failures.some(({ signal, count }) => text.split(signal).length - 1 > count);
    },
    { requirements: expectedRequirements, failures: failureBaselines },
    { timeout: timeoutMs },
  ).catch(() => {});
}

export async function waitForDebugChatTextStable(page, { timeoutMs = 5_000, quietMs = 750 } = {}) {
  const startedAt = Date.now();
  let lastText = await bodyText(page);
  let stableSince = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    await page.waitForTimeout(250);
    const currentText = await bodyText(page);
    if (currentText !== lastText) {
      lastText = currentText;
      stableSince = Date.now();
      continue;
    }
    if (Date.now() - stableSince >= quietMs) return;
  }
}

async function fetchDebugChatHistory(page, { backendUrl, pipelineId, sessionType }) {
  if (!backendUrl || !pipelineId || !sessionType) {
    return { status: "not_required", messages: [] };
  }
  return await page.evaluate(async ({ backendUrl, pipelineId, sessionType }) => {
    const token = localStorage.getItem("token") || "";
    const response = await fetch(
      `${backendUrl.replace(/\/$/, "")}/api/v1/pipelines/${encodeURIComponent(pipelineId)}/ws/messages/${encodeURIComponent(sessionType)}`,
      { headers: token ? { Authorization: `Bearer ${token}` } : {} },
    );
    const json = await response.json().catch(() => ({}));
    return {
      status: response.ok && json.code === 0 ? "ready" : "fail",
      http_status: response.status,
      code: json.code ?? null,
      messages: json.data?.messages || [],
      reason: response.ok && json.code === 0 ? "" : json.msg || `Debug Chat history returned HTTP ${response.status}.`,
    };
  }, { backendUrl, pipelineId, sessionType });
}

async function waitForFinalDebugChatAssistant(page, {
  backendUrl,
  pipelineId,
  sessionType,
  beforeAssistantCount,
  timeoutMs,
}) {
  if (!backendUrl || !pipelineId || !sessionType) {
    return { status: "not_required", latest_assistant_is_final: null };
  }
  const deadline = Date.now() + Math.max(1, timeoutMs);
  let lastHistory = null;
  while (Date.now() < deadline) {
    lastHistory = await fetchDebugChatHistory(page, { backendUrl, pipelineId, sessionType });
    if (lastHistory.status === "fail") return lastHistory;
    const assistants = lastHistory.messages.filter((message) => message.role === "assistant");
    const latest = assistants.at(-1);
    if (assistants.length > beforeAssistantCount && latest?.is_final === true) {
      return {
        status: "pass",
        latest_assistant_is_final: true,
        assistant_message_count: assistants.length,
      };
    }
    await page.waitForTimeout(Math.min(250, Math.max(1, deadline - Date.now())));
  }
  const assistants = (lastHistory?.messages || []).filter((message) => message.role === "assistant");
  return {
    status: "fail",
    reason: "Timed out waiting for the new assistant message to become final.",
    latest_assistant_is_final: assistants.at(-1)?.is_final === true,
    assistant_message_count: assistants.length,
  };
}

export async function attachDebugChatImage(page, imagePath) {
  if (!imagePath) return { status: "not_required", reason: "" };
  const input = page.locator('input[type="file"][accept*="image"], input[type="file"]').first();
  if (!await input.count()) {
    return { status: "fail", reason: "Could not find a Debug Chat image upload input." };
  }
  await input.setInputFiles(imagePath);
  await page.locator("img").last().waitFor({ state: "visible", timeout: 10_000 }).catch(() => {});
  return { status: "ready", reason: `Attached image fixture: ${imagePath}` };
}

export async function sendDebugChatPrompt(page, prompt, imagePath = "") {
  const imageResult = await attachDebugChatImage(page, imagePath);
  if (imageResult.status === "fail") return imageResult;

  const input = debugChatInput(page);
  const inputVisible = await input.isVisible({ timeout: 5_000 }).catch(() => false);
  const inputEnabled = inputVisible && await input.isEnabled({ timeout: 10_000 }).catch(() => false);
  if (!inputVisible || !inputEnabled) return false;
  await input.fill(prompt).catch(async () => {
    await input.click();
    await input.pressSequentially(prompt);
  });
  const clickedSend = await clickFirstVisible(page, ["Send", "发送", "提交"], 1_500);
  if (!clickedSend) await page.keyboard.press("Enter");
  await page.getByText(prompt, { exact: false }).last().waitFor({ state: "visible", timeout: 10_000 }).catch(() => {});
  return true;
}

export async function runDebugChatPrompt(page, {
  prompt,
  expectedText,
  expectedTexts = null,
  responseTimeoutMs,
  imagePath = "",
  backendUrl = "",
  pipelineId = "",
  sessionType = "person",
  maxNewAssistantMessages = null,
  failureSignals = DEBUG_CHAT_FAILURE_SIGNALS,
}) {
  const beforeText = await bodyText(page);
  const beforeMessages = await visibleDebugChatMessages(page);
  const beforeHistory = await fetchDebugChatHistory(page, { backendUrl, pipelineId, sessionType });
  const beforeHistoryAssistantCount = beforeHistory.messages.filter((message) => message.role === "assistant").length;
  const requiredExpectedTexts = [...new Set(
    (Array.isArray(expectedTexts) && expectedTexts.length > 0 ? expectedTexts : [expectedText])
      .map(String)
      .filter(Boolean),
  )];
  const minExpectedCount = minExpectedOccurrences(beforeText, expectedText, prompt);
  const minExpectedCounts = requiredExpectedTexts.map(
    (text) => minExpectedOccurrences(beforeText, text, prompt),
  );
  const sent = await sendDebugChatPrompt(page, prompt, imagePath);
  if (sent !== true) {
    if (sent && typeof sent === "object" && typeof sent.reason === "string") return sent;
    return { status: "fail", reason: "Could not find a Debug Chat text input." };
  }

  const responseStartedAt = Date.now();
  await waitForExpectedDebugChatText(page, {
    expectedText,
    expectedTexts: requiredExpectedTexts,
    minExpectedCount,
    minExpectedCounts,
    prompt,
    timeoutMs: responseTimeoutMs,
    beforeText,
    failureSignals,
  });
  const finalAssistant = await waitForFinalDebugChatAssistant(page, {
    backendUrl,
    pipelineId,
    sessionType,
    beforeAssistantCount: beforeHistoryAssistantCount,
    timeoutMs: Math.max(1, responseTimeoutMs - (Date.now() - responseStartedAt)),
  });
  await waitForDebugChatTextStable(page);

  const afterText = await bodyText(page);
  const afterMessages = await visibleDebugChatMessages(page);
  const latestAssistantText = afterMessages.filter((message) => message.role === "assistant").at(-1)?.text || "";
  const latestExpectedLeaf = await latestVisibleLeafText(page, [expectedText]);
  const failureText = findNewFailureSignal(beforeText, afterText, failureSignals);
  const latestFailureLeaf = failureText ? await latestVisibleLeafText(page, [failureText]) : "";

  const classified = classifyDebugChatResult({
    beforeText,
    afterText,
    expectedText,
    expectedTexts: requiredExpectedTexts,
    prompt,
    latestExpectedLeaf,
    latestFailureLeaf,
    beforeMessages,
    afterMessages,
    latestAssistantText,
    latestAssistantIsFinal: finalAssistant.latest_assistant_is_final,
    maxNewAssistantMessages,
    failureSignals,
  });
  return {
    ...classified,
    latest_assistant_is_final: finalAssistant.latest_assistant_is_final,
    final_assistant_wait_status: finalAssistant.status,
    final_assistant_wait_reason: finalAssistant.reason || "",
  };
}

export async function setDebugChatStreamOutput(page, desired) {
  if (desired === null || desired === undefined) return { status: "not_required", reason: "" };

  const streamSwitch = page.locator('[role="switch"]').first();
  if (!await streamSwitch.isVisible({ timeout: 5_000 }).catch(() => false)) {
    return { status: "blocked", reason: "Debug Chat stream switch was not visible." };
  }
  if (!await streamSwitch.isEnabled({ timeout: 10_000 }).catch(() => false)) {
    return { status: "blocked", reason: "Debug Chat stream switch was visible but disabled." };
  }

  const checked = (await streamSwitch.getAttribute("aria-checked").catch(() => null)) === "true";
  if (checked !== desired) {
    await streamSwitch.click();
    await page.waitForFunction(
      ({ selector, expected }) => document.querySelector(selector)?.getAttribute("aria-checked") === String(expected),
      { selector: '[role="switch"]', expected: desired },
      { timeout: 5_000 },
    ).catch(() => {});
  }

  const finalChecked = (await streamSwitch.getAttribute("aria-checked").catch(() => null)) === "true";
  if (finalChecked !== desired) {
    return {
      status: "fail",
      reason: `Debug Chat stream switch did not reach requested state: ${desired ? "on" : "off"}.`,
    };
  }
  return { status: "ready", reason: `Debug Chat stream switch is ${desired ? "on" : "off"}.` };
}
