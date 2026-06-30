#!/usr/bin/env node

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { delimiter, join, resolve } from "node:path";
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

const script = String.raw`
import concurrent.futures
import sqlite3
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine

from langbot.pkg.entity.persistence.agent_run import AgentRun, AgentRunEvent, AgentRuntime

db_path = Path(sys.argv[1])
run_count = 120
worker_count = 8
engine = create_engine(f"sqlite:///{db_path}")
for table in (AgentRun.__table__, AgentRunEvent.__table__, AgentRuntime.__table__):
    table.create(engine)

with engine.begin() as conn:
    conn.execute(AgentRun.__table__.insert(), [
        {
            "run_id": f"run-{i:03d}",
            "event_id": f"evt-{i:03d}",
            "binding_id": "binding-contention",
            "runner_id": "plugin:qa/agent-runner/default",
            "status": "queued",
            "queue_name": "default",
            "priority": run_count - i,
        }
        for i in range(run_count)
    ])

def worker(worker_id):
    claimed = []
    conn = sqlite3.connect(db_path, timeout=10, isolation_level=None)
    conn.execute("pragma busy_timeout=10000")
    try:
        while True:
            try:
                conn.execute("begin immediate")
                row = conn.execute(
                    "select run_id from agent_run where status = 'queued' "
                    "order by priority desc, id asc limit 1"
                ).fetchone()
                if row is None:
                    conn.execute("commit")
                    return claimed
                run_id = row[0]
                updated = conn.execute(
                    "update agent_run "
                    "set status = 'completed', claimed_by_runtime_id = ?, dispatch_attempts = coalesce(dispatch_attempts, 0) + 1 "
                    "where run_id = ? and status = 'queued'",
                    (f"worker-{worker_id}", run_id),
                ).rowcount
                conn.execute("commit")
                if updated == 1:
                    claimed.append(run_id)
            except sqlite3.OperationalError as exc:
                try:
                    conn.execute("rollback")
                except sqlite3.OperationalError:
                    pass
                if "locked" not in str(exc).lower():
                    raise
                time.sleep(0.01)
    finally:
        conn.close()

with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as pool:
    claims = [run_id for worker_claims in pool.map(worker, range(worker_count)) for run_id in worker_claims]

conn = sqlite3.connect(db_path)
rows = conn.execute(
    "select run_id, status, dispatch_attempts, claimed_by_runtime_id from agent_run"
).fetchall()
conn.close()

assert len(claims) == run_count, len(claims)
assert len(set(claims)) == run_count, "duplicate claims detected"
assert all(row[1] == "completed" for row in rows), rows[:5]
assert all(row[2] == 1 for row in rows), rows[:5]
assert all(row[3] for row in rows), rows[:5]
print(f"LEDGER_CONTENTION_OK runs={run_count} workers={worker_count}")
`;

async function main() {
  const root = resolve(env.LBS_ROOT || process.cwd());
  const caseId = "agent-runner-ledger-contention";
  const runId = env.LBS_RUN_ID || `${timestampSlug()}-${caseId}`;
  const evidenceDir = resolve(env.LBS_EVIDENCE_DIR || join(root, "reports", "evidence", runId));
  await mkdir(evidenceDir, { recursive: true });
  const startedAt = new Date();
  const langbotRepo = resolve(root, env.LANGBOT_REPO || "../LangBot");
  const sdkSrc = resolve(root, env.LANGBOT_PLUGIN_SDK_REPO || "../langbot-plugin-sdk/src");
  const dbPath = join(evidenceDir, "ledger-contention.sqlite3");
  const stdoutLog = join(evidenceDir, "probe-stdout.log");
  const stderrLog = join(evidenceDir, "probe-stderr.log");
  const automationResultJson = join(evidenceDir, "automation-result.json");
  const resultJson = join(evidenceDir, "result.json");
  const timeoutMs = Number(env.LANGBOT_AGENT_RUNNER_PROBE_TIMEOUT_MS || "30000");
  const command = { executable: "rtk", args: ["uv", "run", "python", "-c", script, dbPath], cwd: langbotRepo };
  const result = {
    source: "automation",
    probe: "agent-runner-ledger-contention",
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
    python_paths: [sdkSrc],
    database_path: dbPath,
    command,
    timeout_ms: timeoutMs,
    exit_status: null,
    signal: null,
    evidence: { stdout_log: stdoutLog, stderr_log: stderrLog, database: dbPath, automation_result_json: automationResultJson, result_json: resultJson },
    evidence_collected: ["filesystem"],
  };
  try {
    if (!existsSync(langbotRepo)) {
      result.status = "env_issue";
      result.reason = `LANGBOT_REPO/default ../LangBot did not resolve: ${langbotRepo}`;
    } else {
      const proc = await run(command, timeoutMs, {
        ...process.env,
        PYTHONPATH: [sdkSrc, process.env.PYTHONPATH].filter(Boolean).join(delimiter),
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
        result.status = "fail";
        result.reason = `ledger contention timed out after ${timeoutMs}ms`;
      } else if (proc.status === 0 && proc.stdout.includes("LEDGER_CONTENTION_OK")) {
        result.status = "pass";
        result.reason = "ledger contention probe passed";
      } else {
        result.status = "fail";
        result.reason = `ledger contention exited with status ${proc.status}`;
      }
    }
  } catch (error) {
    result.status = "fail";
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
