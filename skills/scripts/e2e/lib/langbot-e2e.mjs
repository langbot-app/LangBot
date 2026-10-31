import { appendFile, mkdir, readFile, stat, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { basename, join, resolve } from "node:path";
import { env } from "node:process";

const secretRe = /(?:authorization|bearer|token|secret|password|api[_-]?key|jwt|oauth)\s*[:=]\s*["']?[^"',\s]+/gi;
const ACTIVE_WORKSPACE_STORAGE_KEY = "langbot_active_workspace_uuid";
const workspaceUuidCache = new Map();

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

export function boxWorkspaceNamespace(instanceUuid, workspaceUuid) {
  const instance = String(instanceUuid || "").trim();
  const workspace = String(workspaceUuid || "").trim();
  if (!instance || !workspace) {
    throw new Error("Box Workspace namespace requires instance and Workspace UUIDs.");
  }
  const digest = createHash("sha256")
    .update(`${instance}\0${workspace}`, "utf8")
    .digest("hex")
    .slice(0, 24);
  return `ws-${digest}`;
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

export async function beginBackendLogCapture(evidenceDir, sourcePath = env.LANGBOT_BACKEND_LOG || "") {
  if (!sourcePath) return null;
  const source = resolve(sourcePath);
  try {
    const info = await stat(source);
    return {
      source,
      start_offset: info.size,
      target: resolve(evidenceDir, "backend.log"),
    };
  } catch {
    return null;
  }
}

export async function finishBackendLogCapture(capture) {
  if (!capture) return null;
  try {
    const content = await readFile(capture.source);
    const start = content.length >= capture.start_offset ? capture.start_offset : 0;
    const window = content.subarray(start);
    if (window.length === 0) return null;
    await writeFile(capture.target, window);
    return {
      path: capture.target,
      bytes: window.length,
    };
  } catch {
    return null;
  }
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

export function isTaskFailed(task) {
  const status = String(task?.status || task?.state || "").toLowerCase();
  const runtimeStatus = String(task?.runtime?.status || task?.runtime?.state || "").toLowerCase();
  return ["failed", "error", "cancelled", "canceled"].includes(status)
    || ["failed", "error", "cancelled", "canceled"].includes(runtimeStatus)
    || task?.failed === true
    || Boolean(task?.error)
    || Boolean(task?.runtime?.exception);
}

export function isTaskComplete(task) {
  if (isTaskFailed(task)) return false;
  const status = String(task?.status || task?.state || "").toLowerCase();
  const runtimeStatus = String(task?.runtime?.status || task?.runtime?.state || "").toLowerCase();
  return ["done", "completed", "success", "succeeded", "finished"].includes(status)
    || ["done", "completed", "success", "succeeded", "finished"].includes(runtimeStatus)
    || task?.done === true
    || task?.completed === true
    || task?.runtime?.done === true;
}

function browserDiagnosticFindings(source, text) {
  const findings = [];
  const lines = String(text || "").split(/\r?\n/);
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (!line) continue;
    const lineNumber = index + 1;

    if (source === "console") {
      const checks = [
        ["pageerror", /\[pageerror\]/i],
        ["frontend_uncaught_error", /\[error\].*(?:\bUncaught\b|Unhandled(?: promise rejection|Rejection)|TypeError|ReferenceError)/i],
        ["http_5xx", /Failed to load resource: the server responded with a status of 5\d\d/i],
        ["api_server_error", /\[error\].*Server error:/i],
        ["plugin_runtime_timeout", /\[error\].*Action [A-Za-z0-9_]+ call timed out/i],
      ];
      for (const [kind, regex] of checks) {
        if (!regex.test(line)) continue;
        findings.push({
          source,
          severity: "fail",
          kind,
          line: lineNumber,
          excerpt: redact(line.trim()),
        });
        break;
      }
      continue;
    }

    if (source === "network") {
      if (/\[response\]\s+5\d\d\b/i.test(line)) {
        findings.push({
          source,
          severity: "fail",
          kind: "http_5xx",
          line: lineNumber,
          excerpt: redact(line.trim()),
        });
        continue;
      }
      if (/\[requestfailed\]/i.test(line) && !/net::ERR_ABORTED/i.test(line)) {
        findings.push({
          source,
          severity: "warning",
          kind: "request_failed",
          line: lineNumber,
          excerpt: redact(line.trim()),
        });
      }
    }
  }
  return findings;
}

export async function scanBrowserDiagnostics(paths) {
  const sources = [
    ["console", paths.consoleLog],
    ["network", paths.networkLog],
  ];
  const findings = [];
  for (const [source, path] of sources) {
    let text = "";
    try {
      text = await readFile(path, "utf8");
    } catch {
      continue;
    }
    findings.push(...browserDiagnosticFindings(source, text));
  }
  const hasFailure = findings.some((finding) => finding.severity === "fail");
  return {
    status: hasFailure ? "fail" : "pass",
    findings,
    reason: hasFailure
      ? `Browser diagnostics found ${findings.filter((finding) => finding.severity === "fail").length} failing signal(s).`
      : "No failing browser diagnostics found.",
  };
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

export async function resolveLangBotRepo(repo = env.LANGBOT_REPO || "", cwd = process.cwd()) {
  if (repo) return resolve(repo);

  const candidates = [
    resolve(cwd),
    basename(cwd) === "skills" ? resolve(cwd, "..") : "",
    resolve(cwd, "../LangBot"),
    resolve(cwd, "LangBot"),
  ].filter(Boolean);

  const seen = new Set();
  for (const candidate of candidates) {
    if (seen.has(candidate)) continue;
    seen.add(candidate);
    if (await pathExists(resolve(candidate, "data/config.yaml"))) return candidate;
  }

  return resolve(cwd, "../LangBot");
}

export async function readRecoveryKey(repo = env.LANGBOT_REPO || "") {
  const configPath = resolve(await resolveLangBotRepo(repo), "data/config.yaml");
  const config = await readFile(configPath, "utf8");
  const match = config.match(/^\s*recovery_key:\s*['"]?([^'"\s#]+)['"]?\s*$/m);
  return match?.[1] || "";
}

function workspaceCacheKey(backendUrl, token) {
  return `${backendUrl.replace(/\/$/, "")}\0${token}`;
}

function isAccountScopedApi(path, method) {
  const pathname = path.split("?", 1)[0];
  if (pathname === "/api/v1/workspaces/bootstrap") return true;
  if (pathname === "/api/v1/workspaces" && method === "GET") return true;
  return [
    "/api/v1/user/check-token",
    "/api/v1/user/info",
    "/api/v1/user/account-info",
    "/api/v1/user/change-password",
  ].includes(pathname);
}

export async function resolveWorkspaceUuid(
  backendUrl,
  token,
  preferredWorkspaceUuid = env.LANGBOT_WORKSPACE_UUID || "",
) {
  if (!token) throw new Error("A user token is required to resolve the active Workspace.");

  const normalizedBackendUrl = backendUrl.replace(/\/$/, "");
  const normalizedPreferred = preferredWorkspaceUuid.trim();
  const cacheKey = workspaceCacheKey(normalizedBackendUrl, token);
  const cached = workspaceUuidCache.get(cacheKey);
  if (cached && (!normalizedPreferred || cached === normalizedPreferred)) return cached;

  const response = await fetch(`${normalizedBackendUrl}/api/v1/workspaces/bootstrap`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });
  const json = await response.json().catch(() => ({}));
  if (response.status >= 400 || json.code !== 0) {
    throw new Error(json.msg || `Workspace bootstrap failed with HTTP ${response.status}.`);
  }

  const workspaces = json.data?.workspaces || [];
  const workspaceUuids = workspaces
    .map((entry) => entry.workspace?.uuid || entry.uuid || "")
    .filter(Boolean);
  let workspaceUuid = normalizedPreferred;
  if (workspaceUuid && !workspaceUuids.includes(workspaceUuid)) {
    throw new Error(`Configured Workspace ${workspaceUuid} is not available to the authenticated Account.`);
  }
  if (!workspaceUuid && workspaceUuids.length === 1) {
    [workspaceUuid] = workspaceUuids;
  }
  if (!workspaceUuid && workspaceUuids.length === 0) {
    throw new Error("The authenticated Account has no available Workspace.");
  }
  if (!workspaceUuid) {
    throw new Error(
      "The authenticated Account has multiple Workspaces; set LANGBOT_WORKSPACE_UUID for this QA run.",
    );
  }

  workspaceUuidCache.set(cacheKey, workspaceUuid);
  return workspaceUuid;
}

export async function authenticatedApiHeaders(
  backendUrl,
  token,
  { contentType = "application/json", workspaceUuid = "" } = {},
) {
  const resolvedWorkspaceUuid = await resolveWorkspaceUuid(backendUrl, token, workspaceUuid);
  return {
    Authorization: `Bearer ${token}`,
    ...(contentType ? { "Content-Type": contentType } : {}),
    "X-Workspace-Id": resolvedWorkspaceUuid,
  };
}

export async function apiJson(
  backendUrl,
  path,
  { method = "GET", token = "", body, skipWorkspace = false, workspaceUuid = "" } = {},
) {
  const normalizedMethod = method.toUpperCase();
  const headers = { "Content-Type": "application/json" };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
    if (!skipWorkspace && !isAccountScopedApi(path, normalizedMethod)) {
      headers["X-Workspace-Id"] = await resolveWorkspaceUuid(backendUrl, token, workspaceUuid);
    }
  }
  const response = await fetch(`${backendUrl.replace(/\/$/, "")}${path}`, {
    method: normalizedMethod,
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

export async function ensureBrowserWorkspace(
  page,
  backendUrl,
  preferredWorkspaceUuid = env.LANGBOT_WORKSPACE_UUID || "",
) {
  const browserContext = await page.evaluate((storageKey) => ({
    token: localStorage.getItem("token") || "",
    workspaceUuid: localStorage.getItem(storageKey) || "",
  }), ACTIVE_WORKSPACE_STORAGE_KEY);
  if (!browserContext.token) {
    return { status: "blocked", reason: "Browser profile has no localStorage token.", workspace_uuid: "" };
  }

  try {
    const workspaceUuid = await resolveWorkspaceUuid(
      backendUrl,
      browserContext.token,
      preferredWorkspaceUuid || browserContext.workspaceUuid,
    );
    await page.evaluate(({ storageKey, workspaceUuid: value }) => {
      localStorage.setItem(storageKey, value);
    }, { storageKey: ACTIVE_WORKSPACE_STORAGE_KEY, workspaceUuid });
    return {
      status: "pass",
      reason: "Browser Workspace selection is initialized.",
      workspace_uuid: workspaceUuid,
    };
  } catch (error) {
    return { status: "blocked", reason: error.message, workspace_uuid: "" };
  }
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

export async function ensureAuthenticatedBrowser(page, {
  frontendUrl = env.LANGBOT_FRONTEND_URL || "",
  backendUrl = env.LANGBOT_BACKEND_URL || "",
  user = env.LANGBOT_E2E_LOGIN_USER || "",
  password = env.LANGBOT_E2E_LOGIN_PASSWORD || "LangBotE2ELocalPass!2026",
  recoveryKey = "",
} = {}) {
  if (!frontendUrl) return { status: "env_issue", reason: "LANGBOT_FRONTEND_URL is not configured." };
  if (!backendUrl) return { status: "env_issue", reason: "LANGBOT_BACKEND_URL is not configured." };

  const current = await verifyBrowserToken(page, backendUrl).catch((error) => ({
    authenticated: false,
    reason: error.message,
  }));
  if (current.authenticated) {
    const workspace = await ensureBrowserWorkspace(page, backendUrl);
    if (workspace.status !== "pass") {
      return {
        status: workspace.status,
        reason: workspace.reason,
        backend_token_check: null,
        browser_token_check: current,
        workspace,
        injected: false,
      };
    }
    return {
      status: "pass",
      reason: "Existing browser token is valid.",
      backend_token_check: null,
      browser_token_check: current,
      workspace,
      injected: false,
    };
  }

  if (!user) {
    return {
      status: "blocked",
      reason: "Browser profile is not authenticated for LANGBOT_FRONTEND_URL, and LANGBOT_E2E_LOGIN_USER is not configured for automatic local login.",
      backend_token_check: null,
      browser_token_check: current,
      injected: false,
    };
  }

  const auth = await resetAndAuthLocalUser({ backendUrl, user, password, recoveryKey });
  await setBrowserToken(page, frontendUrl, auth.token);
  const browserCheck = await verifyBrowserToken(page, backendUrl);
  if (!browserCheck.authenticated) {
    return {
      status: "blocked",
      reason: browserCheck.reason || "Browser token check failed after automatic local login.",
      backend_token_check: auth.check,
      browser_token_check: browserCheck,
      injected: true,
    };
  }

  const workspace = await ensureBrowserWorkspace(page, backendUrl);
  if (workspace.status !== "pass") {
    return {
      status: workspace.status,
      reason: workspace.reason,
      backend_token_check: auth.check,
      browser_token_check: browserCheck,
      workspace,
      injected: true,
    };
  }

  return {
    status: "pass",
    reason: "Browser token injected from local recovery login.",
    backend_token_check: auth.check,
    browser_token_check: browserCheck,
    workspace,
    injected: true,
  };
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
  const navigationTimeoutMs = Number.parseInt(env.LANGBOT_E2E_NAVIGATION_TIMEOUT_MS || "30000", 10);
  if (Number.isFinite(navigationTimeoutMs) && navigationTimeoutMs > 0) {
    page.setDefaultNavigationTimeout(navigationTimeoutMs);
  }

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

async function clickVisibleCandidate(page, candidates, timeout) {
  const deadline = Date.now() + Math.max(1, timeout);
  do {
    for (const candidate of candidates) {
      const count = await candidate.locator.count().catch(() => 0);
      for (let index = 0; index < count; index += 1) {
        const element = candidate.locator.nth(index);
        if (!await element.isVisible().catch(() => false)) continue;
        const remaining = Math.max(1, deadline - Date.now());
        const clicked = await element.click({ timeout: Math.min(1_000, remaining) })
          .then(() => true)
          .catch(() => false);
        if (clicked) return candidate.value;
      }
    }
    const remaining = deadline - Date.now();
    if (remaining <= 0) break;
    await page.waitForTimeout(Math.min(100, remaining));
  } while (Date.now() < deadline);
  return null;
}

export async function clickFirstVisibleLocator(page, locators, timeout = 2_000) {
  const candidates = locators.map((locator) => ({ locator, value: true }));
  return Boolean(await clickVisibleCandidate(page, candidates, timeout));
}

export async function clickFirstVisible(page, labels, timeout = 2_000) {
  const candidates = labels.flatMap((label) => [
    { locator: page.getByRole("button", { name: label }), value: label },
    { locator: page.getByRole("link", { name: label }), value: label },
    { locator: page.getByText(label, { exact: false }), value: label },
  ]);
  return await clickVisibleCandidate(page, candidates, timeout);
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
