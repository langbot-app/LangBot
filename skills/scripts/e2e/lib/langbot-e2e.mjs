import { appendFile, mkdir, readFile, stat, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { env } from "node:process";

const secretRe = /(?:authorization|bearer|token|secret|password|api[_-]?key|jwt|oauth)\s*[:=]\s*["']?[^"',\s]+/gi;

export function redact(text) {
  return String(text ?? "")
    .replace(secretRe, (match) => match.replace(/[:=]\s*["']?.*$/, "=[redacted]"))
    .replace(/\bbearer\s+[A-Za-z0-9._~+/=-]{8,}/gi, "Bearer [redacted]")
    .replace(/\bsk-[A-Za-z0-9_-]{6,}\b/g, "[redacted]");
}

export function timestampSlug(date = new Date()) {
  return date.toISOString().replace(/\.\d{3}Z$/, "Z").replace(/[^0-9A-Za-z]+/g, "-").replace(/^-|-$/g, "");
}

export function localIsoWithOffset(date = new Date()) {
  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absolute = Math.abs(offsetMinutes);
  const pad = (value) => String(value).padStart(2, "0");
  const yyyy = date.getFullYear();
  const mm = pad(date.getMonth() + 1);
  const dd = pad(date.getDate());
  const hh = pad(date.getHours());
  const mi = pad(date.getMinutes());
  const ss = pad(date.getSeconds());
  const ms = String(date.getMilliseconds()).padStart(3, "0");
  return `${yyyy}-${mm}-${dd}T${hh}:${mi}:${ss}.${ms}${sign}${pad(Math.floor(absolute / 60))}:${pad(absolute % 60)}`;
}

export function evidencePaths(caseId) {
  const runId = env.LBS_RUN_ID || `${timestampSlug()}-${caseId}`;
  const evidenceDir = resolve(env.LBS_EVIDENCE_DIR || join("reports", "evidence", runId));
  return {
    runId,
    evidenceDir,
    consoleLog: join(evidenceDir, "console.log"),
    networkLog: join(evidenceDir, "network.log"),
    screenshot: join(evidenceDir, "screenshot.png"),
    automationResultJson: join(evidenceDir, "automation-result.json"),
    resultJson: join(evidenceDir, "result.json"),
  };
}

export async function ensureEvidence(paths) {
  await mkdir(paths.evidenceDir, { recursive: true });
  await appendFile(paths.consoleLog, "", "utf8");
  await appendFile(paths.networkLog, "", "utf8");
}

export async function pathExists(path) {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
}

export async function appendLine(path, line) {
  await appendFile(path, `[${localIsoWithOffset()}] ${redact(line)}\n`, "utf8");
}

export async function writeResult(paths, result) {
  const text = `${JSON.stringify(result, null, 2)}\n`;
  if (paths.automationResultJson) await writeFile(paths.automationResultJson, text, "utf8");
  if (paths.resultJson && paths.resultJson !== paths.automationResultJson) {
    await writeFile(paths.resultJson, text, "utf8");
  }
}

export async function loadEnvFiles(paths = ["skills/.env", "skills/.env.local"]) {
  const processEnvKeys = new Set(Object.keys(env));
  for (const path of paths) {
    let text = "";
    try {
      text = await readFile(path, "utf8");
    } catch {
      continue;
    }
    for (const line of text.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const equals = trimmed.indexOf("=");
      if (equals <= 0) continue;
      const key = trimmed.slice(0, equals).trim();
      const value = trimmed.slice(equals + 1).trim().replace(/^["']|["']$/g, "");
      if (!processEnvKeys.has(key)) env[key] = value;
    }
  }
}

export async function readRecoveryKey(repo = env.LANGBOT_REPO || "../LangBot") {
  const configPath = resolve(repo, "data/config.yaml");
  const config = await readFile(configPath, "utf8");
  const match = config.match(/^\s*recovery_key:\s*['"]?([^'"\s#]+)['"]?\s*$/m);
  return match?.[1] || "";
}

export async function apiJson(backendUrl, path, { method = "GET", token = "", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${backendUrl.replace(/\/$/, "")}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return {
    status: response.status,
    json: await response.json().catch(() => ({})),
  };
}

export async function checkBackendToken(backendUrl, token) {
  if (!token) {
    return { authenticated: false, http_status: 0, code: null, reason: "No token." };
  }
  const response = await apiJson(backendUrl, "/api/v1/user/check-token", { token });
  const code = response.json.code ?? null;
  const authenticated = response.status < 400 && code === 0;
  return {
    authenticated,
    http_status: response.status,
    code,
    reason: authenticated ? "Token accepted by backend." : response.json.msg || "Backend rejected token.",
  };
}

export async function resetAndAuthLocalUser({ backendUrl, user, password, recoveryKey = "" }) {
  const key = recoveryKey || await readRecoveryKey();
  if (!key) throw new Error("Could not read recovery_key from LangBot config.");

  const reset = await apiJson(backendUrl, "/api/v1/user/reset-password", {
    method: "POST",
    body: {
      user,
      recovery_key: key,
      new_password: password,
    },
  });
  if (reset.status >= 400 || reset.json.code !== 0) {
    throw new Error(reset.json.msg || `Password reset failed with HTTP ${reset.status}.`);
  }

  const auth = await apiJson(backendUrl, "/api/v1/user/auth", {
    method: "POST",
    body: { user, password },
  });
  const token = auth.json.data?.token || "";
  if (auth.status >= 400 || auth.json.code !== 0 || !token) {
    throw new Error(auth.json.msg || `Auth failed with HTTP ${auth.status}.`);
  }

  const check = await checkBackendToken(backendUrl, token);
  if (!check.authenticated) {
    throw new Error(check.reason || "Authenticated token failed backend token check.");
  }

  return { token, check };
}

export async function setBrowserToken(page, frontendUrl, token) {
  await page.addInitScript((value) => {
    localStorage.setItem("token", value);
  }, token);
  await page.goto(frontendUrl, { waitUntil: "domcontentloaded" });
  await page.evaluate((value) => localStorage.setItem("token", value), token);
}

export async function verifyBrowserToken(page, backendUrl) {
  return await page.evaluate(async (baseUrl) => {
    const token = localStorage.getItem("token");
    if (!token) {
      return { authenticated: false, http_status: 0, code: null, reason: "No localStorage token." };
    }
    try {
      const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/user/check-token`, {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });
      const json = await response.json().catch(() => ({}));
      const code = json.code ?? null;
      const authenticated = response.status < 400 && code === 0;
      return {
        authenticated,
        http_status: response.status,
        code,
        reason: authenticated ? "Token accepted by backend." : json.msg || "Backend rejected token.",
      };
    } catch (error) {
      return {
        authenticated: false,
        http_status: 0,
        code: null,
        reason: error.message,
      };
    }
  }, backendUrl);
}

export function exitCode(status) {
  if (status === "pass") return 0;
  if (status === "blocked" || status === "env_issue") return 2;
  return 1;
}

export async function loadPlaywright() {
  try {
    return await import("playwright");
  } catch {
    throw new Error(
      "Playwright is not installed. Install it in this repo with `npm install --save-dev playwright`, then run `npx playwright install chromium`.",
    );
  }
}

export async function createBrowser(paths) {
  const { chromium } = await loadPlaywright();
  const headed = env.LBS_HEADED === "1";
  const launchOptions = {
    headless: !headed,
  };
  if (env.LANGBOT_CHROMIUM_EXECUTABLE && await pathExists(env.LANGBOT_CHROMIUM_EXECUTABLE)) {
    launchOptions.executablePath = env.LANGBOT_CHROMIUM_EXECUTABLE;
  }

  let browser;
  let context;
  if (env.LANGBOT_BROWSER_PROFILE) {
    context = await chromium.launchPersistentContext(resolve(env.LANGBOT_BROWSER_PROFILE), {
      ...launchOptions,
      viewport: { width: 1440, height: 960 },
    });
  } else {
    browser = await chromium.launch(launchOptions);
    context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
  }
  const page = context.pages()[0] || await context.newPage();

  page.on("console", (message) => {
    appendLine(paths.consoleLog, `[${message.type()}] ${message.text()}`).catch(() => {});
  });
  page.on("pageerror", (error) => {
    appendLine(paths.consoleLog, `[pageerror] ${error.message}`).catch(() => {});
  });
  page.on("requestfailed", (request) => {
    appendLine(paths.networkLog, `[requestfailed] ${request.method()} ${request.url()} ${request.failure()?.errorText ?? ""}`).catch(() => {});
  });
  page.on("response", (response) => {
    if (response.status() < 400) return;
    appendLine(paths.networkLog, `[response] ${response.status()} ${response.url()}`).catch(() => {});
  });

  return {
    page,
    context,
    async close() {
      await context.close();
      if (browser) await browser.close();
    },
  };
}

export async function safeScreenshot(page, path) {
  try {
    await page.screenshot({ path, fullPage: true });
  } catch {
    // Screenshot evidence is useful, but a screenshot failure should not hide the real test result.
  }
}

export async function gotoFrontend(page) {
  const frontendUrl = env.LANGBOT_FRONTEND_URL;
  if (!frontendUrl) {
    throw new Error("LANGBOT_FRONTEND_URL is not configured.");
  }
  await page.goto(frontendUrl, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
}

export function isLoginUrl(url) {
  return /\/login(?:[/?#]|$)/.test(url);
}

export async function bodyText(page) {
  return await page.locator("body").innerText({ timeout: 5_000 }).catch(() => "");
}

export function countOccurrences(haystack, needle) {
  if (!needle) return 0;
  return String(haystack).split(needle).length - 1;
}

export async function clickFirstVisible(page, labels, timeout = 2_000) {
  for (const label of labels) {
    const roleButton = page.getByRole("button", { name: label }).first();
    if (await roleButton.isVisible({ timeout }).catch(() => false)) {
      await roleButton.click();
      return label;
    }

    const roleLink = page.getByRole("link", { name: label }).first();
    if (await roleLink.isVisible({ timeout }).catch(() => false)) {
      await roleLink.click();
      return label;
    }

    const text = page.getByText(label, { exact: false }).first();
    if (await text.isVisible({ timeout }).catch(() => false)) {
      await text.click();
      return label;
    }
  }
  return null;
}

export async function fillFirstTextInput(page, value) {
  const candidates = [
    page.getByRole("textbox").last(),
    page.locator("textarea").last(),
    page.locator("[contenteditable=true]").last(),
    page.locator("input[type=text]").last(),
  ];

  for (const locator of candidates) {
    if (!await locator.isVisible({ timeout: 2_000 }).catch(() => false)) continue;
    await locator.fill(value).catch(async () => {
      await locator.click();
      await locator.pressSequentially(value);
    });
    return true;
  }
  return false;
}

export async function waitForVisibleText(page, text, timeout = 20_000) {
  await page.getByText(text, { exact: false }).last().waitFor({ state: "visible", timeout });
}
