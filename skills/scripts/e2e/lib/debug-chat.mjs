import {
  bodyText,
  clickFirstVisible,
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
  const tabByRole = page.getByRole("tab", { name: /Debug Chat|调试聊天|调试对话|Debug|调试/i }).first();
  if (await tabByRole.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await tabByRole.click();
    return true;
  }

  const tabBySelector = page.locator('[role="tab"]').filter({ hasText: /Debug Chat|调试聊天|调试对话|Debug|调试/i }).first();
  if (await tabBySelector.isVisible({ timeout: 2_000 }).catch(() => false)) {
    await tabBySelector.click();
    return true;
  }

  return Boolean(await clickFirstVisible(page, ["Debug Chat", "调试聊天", "调试对话"], 2_000));
}

async function waitForDebugChatReady(page, timeout = 20_000) {
  const input = debugChatInput(page);
  const visible = await input.isVisible({ timeout }).catch(() => false);
  if (!visible) {
    return {
      ready: false,
      reason: "Debug Chat tab was clicked, but the Debug Chat input did not become visible.",
    };
  }

  const enabled = await input.isEnabled({ timeout }).catch(() => false);
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
  prompt,
  latestExpectedLeaf,
  latestFailureLeaf,
  beforeMessages = null,
  afterMessages = null,
  latestAssistantText = "",
  failureSignals = DEBUG_CHAT_FAILURE_SIGNALS,
}) {
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
  const assistantExpectedIncreased = hasMessageEvidence
    ? afterAssistantExpectedCount > beforeAssistantExpectedCount
    : false;

  if (hasMessageEvidence) {
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
      };
    }
    if (assistantExpectedIncreased && String(latestAssistantText).includes(expectedText)) {
      return {
        status: "pass",
        reason: `Expected text appeared in a new assistant message: ${expectedText}`,
        min_expected_count: minExpectedCount,
        final_count: finalCount,
        before_assistant_expected_count: beforeAssistantExpectedCount,
        after_assistant_expected_count: afterAssistantExpectedCount,
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
    return {
      status: "fail",
      reason: `Expected text did not appear in a new assistant message. Expected assistant occurrences to increase above ${beforeAssistantExpectedCount}, saw ${afterAssistantExpectedCount}.`,
      min_expected_count: minExpectedCount,
      final_count: finalCount,
      before_assistant_expected_count: beforeAssistantExpectedCount,
      after_assistant_expected_count: afterAssistantExpectedCount,
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
    await page.goto(pipelineUrl, { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
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

export async function waitForExpectedDebugChatText(page, { expectedText, minExpectedCount, timeoutMs }) {
  await page.waitForFunction(
    ({ expected, min }) => {
      return document.body.innerText.split(expected).length - 1 >= min;
    },
    { expected: expectedText, min: minExpectedCount },
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

export async function runDebugChatPrompt(page, { prompt, expectedText, responseTimeoutMs, imagePath = "", failureSignals = DEBUG_CHAT_FAILURE_SIGNALS }) {
  const beforeText = await bodyText(page);
  const beforeMessages = await visibleDebugChatMessages(page);
  const minExpectedCount = minExpectedOccurrences(beforeText, expectedText, prompt);
  const sent = await sendDebugChatPrompt(page, prompt, imagePath);
  if (sent !== true) {
    if (sent && typeof sent === "object" && typeof sent.reason === "string") return sent;
    return { status: "fail", reason: "Could not find a Debug Chat text input." };
  }

  await waitForExpectedDebugChatText(page, {
    expectedText,
    minExpectedCount,
    prompt,
    timeoutMs: responseTimeoutMs,
  });
  await waitForDebugChatTextStable(page);

  const afterText = await bodyText(page);
  const afterMessages = await visibleDebugChatMessages(page);
  const latestAssistantText = afterMessages.filter((message) => message.role === "assistant").at(-1)?.text || "";
  const latestExpectedLeaf = await latestVisibleLeafText(page, [expectedText]);
  const failureText = findNewFailureSignal(beforeText, afterText, failureSignals);
  const latestFailureLeaf = failureText ? await latestVisibleLeafText(page, [failureText]) : "";

  return classifyDebugChatResult({
    beforeText,
    afterText,
    expectedText,
    prompt,
    latestExpectedLeaf,
    latestFailureLeaf,
    beforeMessages,
    afterMessages,
    latestAssistantText,
    failureSignals,
  });
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
