import { execFile } from "node:child_process";
import { closeSync, openSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { spawn } from "node:child_process";
import { pathExists, resolveLangBotRepo } from "./langbot-e2e.mjs";

const execFileAsync = promisify(execFile);
const proxyKeys = [
  "ALL_PROXY",
  "all_proxy",
  "HTTP_PROXY",
  "http_proxy",
  "HTTPS_PROXY",
  "https_proxy",
];

function withoutProxy(source = process.env) {
  const next = { ...source };
  for (const key of proxyKeys) delete next[key];
  next.NO_PROXY = "127.0.0.1,localhost";
  next.no_proxy = "127.0.0.1,localhost";
  return next;
}

async function getFreePort() {
  const server = createServer();
  await new Promise((resolvePromise, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolvePromise);
  });
  const address = server.address();
  const port = typeof address === "object" && address ? address.port : 0;
  await new Promise((resolvePromise) => server.close(resolvePromise));
  if (!port) throw new Error("Could not allocate an isolated LangBot port.");
  return port;
}

async function waitForHttp(url, child, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) {
      throw new Error(`${label} exited before becoming ready (code ${child.exitCode}).`);
    }
    try {
      const response = await fetch(url, { redirect: "manual" });
      if (response.status < 500) return response;
    } catch {
      // The service is still starting.
    }
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 500));
  }
  throw new Error(`${label} did not become ready within ${timeoutMs}ms.`);
}

function spawnLogged(command, args, { cwd, env, logPath }) {
  const logFd = openSync(logPath, "a");
  try {
    return spawn(command, args, {
      cwd,
      env,
      detached: true,
      stdio: ["ignore", logFd, logFd],
    });
  } finally {
    closeSync(logFd);
  }
}

async function stopProcess(child) {
  if (!child || child.exitCode !== null) return;
  const closed = new Promise((resolvePromise) => child.once("close", resolvePromise));
  try {
    process.kill(-child.pid, "SIGTERM");
  } catch {
    child.kill("SIGTERM");
  }
  const graceful = await Promise.race([
    closed.then(() => true),
    new Promise((resolvePromise) => setTimeout(() => resolvePromise(false), 5_000)),
  ]);
  if (graceful) return;
  try {
    process.kill(-child.pid, "SIGKILL");
  } catch {
    child.kill("SIGKILL");
  }
  await closed.catch(() => {});
}

async function initializeUser(backendUrl, user, password) {
  const response = await fetch(`${backendUrl}/api/v1/user/init`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user, password }),
  });
  const payload = await response.json().catch(() => ({}));
  if (response.status >= 400 || ![0, 1].includes(payload.code)) {
    throw new Error(payload.msg || `Could not initialize isolated user (HTTP ${response.status}).`);
  }
}

export async function startIsolatedLangBotInstance({ evidenceDir }) {
  const repo = await resolveLangBotRepo();
  const webRepo = process.env.LANGBOT_WEB_REPO || join(repo, "web");
  const python = join(repo, ".venv", "bin", "python");
  const configScript = resolve(
    dirname(fileURLToPath(import.meta.url)),
    "../prepare-isolated-langbot-config.py",
  );
  if (!(await pathExists(python))) throw new Error(`LangBot virtualenv Python is missing: ${python}`);
  if (!(await pathExists(join(webRepo, "node_modules")))) {
    throw new Error(`LangBot frontend dependencies are missing: ${join(webRepo, "node_modules")}`);
  }

  const [backendPort, frontendPort, pluginDebugPort] = await Promise.all([
    getFreePort(),
    getFreePort(),
    getFreePort(),
  ]);
  const instanceRoot = await mkdtemp(join(tmpdir(), "langbot-clean-catalog-"));
  const backendUrl = `http://127.0.0.1:${backendPort}`;
  const frontendUrl = `http://127.0.0.1:${frontendPort}`;
  const backendLog = join(evidenceDir, "isolated-backend.log");
  const frontendLog = join(evidenceDir, "isolated-frontend.log");
  const user = "langbot-e2e@example.invalid";
  const password = "LangBotIsolatedE2E!2026";
  let backend;
  let frontend;

  const stop = async () => {
    await stopProcess(frontend);
    await stopProcess(backend);
    await rm(instanceRoot, { recursive: true, force: true });
  };

  try {
    await execFileAsync(
      python,
      [
        configScript,
        "--instance-root",
        instanceRoot,
        "--port",
        String(backendPort),
        "--plugin-debug-port",
        String(pluginDebugPort),
      ],
      { cwd: repo, env: withoutProxy(), timeout: 30_000 },
    );

    backend = spawnLogged(python, ["-m", "langbot"], {
      cwd: instanceRoot,
      env: {
        ...withoutProxy(),
        PYTHONPATH: join(repo, "src"),
        LANGBOT_DATA_ROOT: join(instanceRoot, "data"),
        API__PORT: String(backendPort),
        API__WEBHOOK_PREFIX: backendUrl,
        SPACE__DISABLE_TELEMETRY: "true",
        SPACE__DISABLE_MODELS_SERVICE: "true",
      },
      logPath: backendLog,
    });
    await waitForHttp(`${backendUrl}/api/v1/system/info`, backend, 180_000, "Isolated LangBot backend");

    const configText = await readFile(join(instanceRoot, "data", "config.yaml"), "utf8");
    const recoveryKey = configText.match(/^\s*recovery_key:\s*['"]?([^'"\s#]+)['"]?\s*$/m)?.[1] || "";
    if (!recoveryKey) throw new Error("Isolated LangBot did not generate a recovery key.");
    await initializeUser(backendUrl, user, password);

    frontend = spawnLogged(
      "pnpm",
      ["exec", "vite", "--host", "127.0.0.1", "--port", String(frontendPort), "--strictPort"],
      {
        cwd: webRepo,
        env: { ...withoutProxy(), VITE_API_BASE_URL: backendUrl },
        logPath: frontendLog,
      },
    );
    await waitForHttp(frontendUrl, frontend, 60_000, "Isolated LangBot frontend");

    return {
      backendUrl,
      frontendUrl,
      recoveryKey,
      user,
      password,
      logs: { backend: backendLog, frontend: frontendLog },
      stop,
    };
  } catch (error) {
    await stop();
    throw error;
  }
}
