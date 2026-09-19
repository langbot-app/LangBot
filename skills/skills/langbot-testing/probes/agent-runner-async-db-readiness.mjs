#!/usr/bin/env node

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { env } from "node:process";

function timestampSlug(date = new Date()) {
  return date.toISOString().replace(/\.\d{3}Z$/, "Z").replace(/[^0-9A-Za-z]+/g, "-").replace(/^-|-$/g, "");
}

function localIsoWithOffset(date = new Date()) {
  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absolute = Math.abs(offsetMinutes);
  const pad = (value) => String(value).padStart(2, "0");
  return [
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}.${String(date.getMilliseconds()).padStart(3, "0")}`,
    `${sign}${pad(Math.floor(absolute / 60))}:${pad(absolute % 60)}`,
  ].join("");
}

function run(command, timeoutMs, childEnv) {
  return new Promise((resolveDone) => {
    const child = spawn(command.executable, command.args, {
      cwd: command.cwd,
      detached: true,
      env: childEnv,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    let timedOut = false;
    const timeout = setTimeout(() => {
      timedOut = true;
      try {
        process.kill(-child.pid, "SIGTERM");
      } catch {
        child.kill("SIGTERM");
      }
    }, timeoutMs);
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
    });
    child.on("error", (error) => {
      clearTimeout(timeout);
      resolveDone({ stdout, stderr, error, timedOut, status: null, signal: null });
    });
    child.on("close", (status, signal) => {
      clearTimeout(timeout);
      resolveDone({ stdout, stderr, error: null, timedOut, status, signal });
    });
  });
}

const script = `
import asyncio
import aiosqlite

async def main():
    async with aiosqlite.connect(':memory:') as db:
        await db.execute('create table t(id integer primary key)')
        await db.commit()
    print('AIOSQLITE_READY')

asyncio.run(main())
`;

async function main() {
  const root = resolve(env.LBS_ROOT || process.cwd());
  const caseId = "agent-runner-async-db-readiness";
  const runId = env.LBS_RUN_ID || `${timestampSlug()}-${caseId}`;
  const evidenceDir = resolve(env.LBS_EVIDENCE_DIR || join(root, "reports", "evidence", runId));
  await mkdir(evidenceDir, { recursive: true });
  const startedAt = new Date();
  const langbotRepo = resolve(root, env.LANGBOT_REPO || "..");
  const stdoutLog = join(evidenceDir, "probe-stdout.log");
  const stderrLog = join(evidenceDir, "probe-stderr.log");
  const automationResultJson = join(evidenceDir, "automation-result.json");
  const resultJson = join(evidenceDir, "result.json");
  const timeoutMs = Number(env.LANGBOT_ASYNC_DB_READINESS_TIMEOUT_MS || "5000");
  const command = {
    executable: "rtk",
    args: [resolve(langbotRepo, ".venv/bin/python"), "-c", script],
    cwd: langbotRepo,
  };
  const result = {
    source: "automation",
    probe: "aiosqlite-readiness",
    case_id: caseId,
    run_id: runId,
    started_at: startedAt.toISOString(),
    started_at_local: localIsoWithOffset(startedAt),
    finished_at: "",
    finished_at_local: "",
    duration_ms: 0,
    status: "fail",
    reason: "",
    repo_path: langbotRepo,
    command,
    timeout_ms: timeoutMs,
    exit_status: null,
    signal: null,
    evidence: { stdout_log: stdoutLog, stderr_log: stderrLog, automation_result_json: automationResultJson, result_json: resultJson },
    evidence_collected: ["filesystem"],
  };
  try {
    if (!existsSync(langbotRepo)) {
      result.status = "env_issue";
      result.reason = `LANGBOT_REPO/default ../LangBot did not resolve: ${langbotRepo}`;
    } else {
      const proc = await run(command, timeoutMs, {
        ...process.env,
        UV_CACHE_DIR: env.UV_CACHE_DIR || join(evidenceDir, ".uv-cache"),
      });
      await writeFile(stdoutLog, proc.stdout, "utf8");
      await writeFile(stderrLog, proc.stderr, "utf8");
      result.exit_status = proc.status;
      result.signal = proc.signal;
      if (proc.error) {
        result.status = "env_issue";
        result.reason = proc.error.message;
      } else if (proc.timedOut) {
        result.status = "env_issue";
        result.reason = `aiosqlite readiness timed out after ${timeoutMs}ms`;
      } else if (proc.status === 0 && proc.stdout.includes("AIOSQLITE_READY")) {
        result.status = "pass";
        result.reason = "aiosqlite readiness passed";
      } else {
        result.status = "env_issue";
        result.reason = `aiosqlite readiness exited with status ${proc.status}`;
      }
    }
  } catch (error) {
    result.status = "env_issue";
    result.reason = error instanceof Error ? error.message : String(error);
  } finally {
    const finishedAt = new Date();
    result.finished_at = finishedAt.toISOString();
    result.finished_at_local = localIsoWithOffset(finishedAt);
    result.duration_ms = finishedAt.getTime() - startedAt.getTime();
    const resultText = `${JSON.stringify(result, null, 2)}\n`;
    await writeFile(automationResultJson, resultText, "utf8");
    await writeFile(resultJson, resultText, "utf8");
    console.log(JSON.stringify(result, null, 2));
  }
  process.exit(result.status === "pass" ? 0 : result.status === "env_issue" ? 2 : 1);
}

await main();
