import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { Socket } from "node:net";
import { join } from "node:path";
import type { CommandContext } from "../types.ts";
import { parseOptions } from "../cli.ts";
import { loadEnv } from "../fs.ts";
import { requiredEnvKeys } from "../constants.ts";
import { redactEnvValue } from "../readiness.ts";

export function commandEnvShow(ctx: CommandContext): number {
  const { options } = parseOptions(ctx.args.slice(2));
  const env = loadEnv(ctx.root);
  const outputEnv = Object.fromEntries(
    Object.entries(env).map(([key, value]) => [key, redactEnvValue(key, value)]),
  );
  if (options.json === true) {
    console.log(JSON.stringify(outputEnv, null, 2));
    return 0;
  }
  for (const key of Object.keys(outputEnv).sort()) {
    console.log(`${key}=${outputEnv[key]}`);
  }
  return 0;
}

async function checkUrl(label: string, url: string): Promise<{ ok: boolean; message: string }> {
  if (!url) return { ok: false, message: `${label}: missing` };
  const displayUrl = redactEnvValue(label, url);
  try {
    const response = await fetch(url, { method: "HEAD", signal: AbortSignal.timeout(2500) });
    return { ok: response.ok || response.status < 500, message: `${label}: ${displayUrl} -> HTTP ${response.status}` };
  } catch (error) {
    return { ok: false, message: `${label}: ${displayUrl} -> ${String(error).replace(/\s+/g, " ")}` };
  }
}

function endpoint(url: string): { host: string; port: number } | null {
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
    const port = parsed.port ? Number(parsed.port) : parsed.protocol === "https:" ? 443 : 80;
    return { host: parsed.hostname, port };
  } catch {
    return null;
  }
}

async function checkTcpListener(url: string): Promise<{ ok: boolean; message: string } | null> {
  const target = endpoint(url);
  if (!target) return null;

  return await new Promise((resolve) => {
    const socket = new Socket();
    let settled = false;
    const finish = (ok: boolean, detail: string) => {
      if (settled) return;
      settled = true;
      socket.destroy();
      resolve({
        ok,
        message: `${target.host}:${target.port} ${detail}`,
      });
    };

    socket.setTimeout(1500);
    socket.once("connect", () => finish(true, "is listening"));
    socket.once("timeout", () => finish(false, "did not accept TCP connection before timeout"));
    socket.once("error", (error) => finish(false, `is not listening (${error.message})`));
    socket.connect(target.port, target.host);
  });
}

function startupHint(label: string, env: Record<string, string>): string | null {
  if (label === "LANGBOT_BACKEND_URL" && env.LANGBOT_REPO) {
    return `start backend: cd ${env.LANGBOT_REPO} && uv run main.py`;
  }
  if (label === "LANGBOT_FRONTEND_URL" && env.LANGBOT_WEB_REPO) {
    return `start frontend: cd ${env.LANGBOT_WEB_REPO} && pnpm dev`;
  }
  return null;
}

function compareProxyPair(env: Record<string, string>, upper: string, lower: string): string | null {
  const upperValue = process.env[upper] ?? env[upper] ?? "";
  const lowerValue = process.env[lower] ?? env[lower] ?? "";
  if (upperValue && lowerValue && upperValue !== lowerValue) {
    return `${upper}/${lower}: mismatch (${redactEnvValue(upper, upperValue)} vs ${redactEnvValue(lower, lowerValue)})`;
  }
  return null;
}

function envValue(env: Record<string, string>, key: string): string {
  return process.env[key] ?? env[key] ?? "";
}

function activeSocksProxy(env: Record<string, string>): { key: string; value: string } | null {
  for (const key of ["ALL_PROXY", "all_proxy", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"]) {
    const value = envValue(env, key);
    if (/^socks/i.test(value)) return { key, value };
  }
  return null;
}

function checkSocksio(env: Record<string, string>): string | null {
  const proxy = activeSocksProxy(env);
  if (!proxy) return null;

  const repo = env.LANGBOT_REPO;
  const python = repo ? join(repo, ".venv", "bin", "python") : "";
  if (!python || !existsSync(python)) {
    return `SOCKS proxy ${proxy.key} is configured (${redactEnvValue(proxy.key, proxy.value)}), but LangBot venv python was not found; after creating the venv, verify it can import socksio.`;
  }

  const result = spawnSync(python, ["-c", "import socksio"], {
    encoding: "utf8",
    timeout: 5000,
  });
  if (result.status === 0) return null;

  return `SOCKS proxy ${proxy.key} is configured (${redactEnvValue(proxy.key, proxy.value)}), but ${python} cannot import socksio; run \`${python} -m pip install socksio\` or start LangBot without SOCKS proxy env.`;
}

export async function commandEnvDoctor(ctx: CommandContext): Promise<number> {
  const env = loadEnv(ctx.root);
  const failures: string[] = [];
  const warnings: string[] = [];

  for (const key of requiredEnvKeys) {
    if (!env[key]) failures.push(`missing ${key}`);
  }

  for (const [label, path] of [
    ["LANGBOT_REPO", env.LANGBOT_REPO],
    ["LANGBOT_WEB_REPO", env.LANGBOT_WEB_REPO],
    ["LANGBOT_CHROMIUM_EXECUTABLE", env.LANGBOT_CHROMIUM_EXECUTABLE],
  ]) {
    if (!path || !existsSync(path)) failures.push(`${label}: path does not exist (${path || "missing"})`);
  }

  if (env.LANGBOT_BROWSER_PROFILE && !existsSync(env.LANGBOT_BROWSER_PROFILE)) {
    warnings.push(`LANGBOT_BROWSER_PROFILE: path does not exist yet (${env.LANGBOT_BROWSER_PROFILE})`);
  }

  for (const mismatch of [
    compareProxyPair(env, "HTTP_PROXY", "http_proxy"),
    compareProxyPair(env, "HTTPS_PROXY", "https_proxy"),
    compareProxyPair(env, "ALL_PROXY", "all_proxy"),
    compareProxyPair(env, "NO_PROXY", "no_proxy"),
  ]) {
    if (mismatch) failures.push(mismatch);
  }
  const socksioFailure = checkSocksio(env);
  if (socksioFailure) failures.push(socksioFailure);

  for (const [label, result] of await Promise.all([
    checkUrl("LANGBOT_BACKEND_URL", env.LANGBOT_BACKEND_URL).then((result) => ["LANGBOT_BACKEND_URL", result] as const),
    checkUrl("LANGBOT_FRONTEND_URL", env.LANGBOT_FRONTEND_URL).then((result) => ["LANGBOT_FRONTEND_URL", result] as const),
  ])) {
    if (result.ok) console.log(`OK: ${result.message}`);
    else {
      failures.push(result.message);
      const tcp = await checkTcpListener(env[label]);
      if (tcp && !tcp.ok) failures.push(`${label}: no HTTP service reachable because ${tcp.message}`);
      const hint = startupHint(label, env);
      if (hint) warnings.push(`${label}: ${hint}`);
    }
  }

  for (const warning of warnings) console.log(`WARN: ${warning}`);
  for (const failure of failures) console.log(`FAIL: ${failure}`);
  if (failures.length > 0) return 1;
  console.log("OK: environment looks usable");
  return 0;
}
