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

function resolveFromRoot(root, value) {
  return resolve(root, value);
}

function runProcess(command, timeoutMs, childEnv) {
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

const probeScript = String.raw`
import sqlite3
from sqlalchemy import create_engine, inspect

from langbot.pkg.agent.runner.run_ledger_store import TERMINAL_STATUSES
from langbot.pkg.entity.persistence.agent_run import AgentRun, AgentRunEvent, AgentRuntime

expected_statuses = {'created', 'queued', 'claimed', 'running', 'completed', 'failed', 'cancelled', 'timeout'}
expected_terminal = {'completed', 'failed', 'cancelled', 'timeout'}
assert TERMINAL_STATUSES == expected_terminal, TERMINAL_STATUSES

engine = create_engine('sqlite:///:memory:')
for table in (AgentRun.__table__, AgentRunEvent.__table__, AgentRuntime.__table__):
    table.create(engine)

inspector = inspect(engine)
assert set(inspector.get_table_names()) == {'agent_run', 'agent_run_event', 'agent_runtime'}
agent_run_indexes = {index['name']: tuple(index['column_names']) for index in inspector.get_indexes('agent_run')}
for name in (
    'ix_agent_run_scope_status',
    'ix_agent_run_runner_status',
    'ix_agent_run_queue_claim',
    'ix_agent_run_run_id',
    'ix_agent_run_claim_token',
):
    assert name in agent_run_indexes, agent_run_indexes

event_uniques = {
    unique['name']: tuple(unique['column_names'])
    for unique in inspector.get_unique_constraints('agent_run_event')
}
assert event_uniques['uq_agent_run_event_run_sequence'] == ('run_id', 'sequence')

with engine.begin() as conn:
    conn.execute(AgentRun.__table__.insert().values(
        run_id='run-sync',
        event_id='evt-sync',
        binding_id='binding-sync',
        runner_id='plugin:test/runner/default',
        status='queued',
        queue_name='default',
        priority=10,
    ))
    row = conn.execute(AgentRun.__table__.select().where(AgentRun.__table__.c.run_id == 'run-sync')).mappings().one()
    assert row['status'] == 'queued'
    conn.execute(AgentRunEvent.__table__.insert().values(
        run_id='run-sync',
        sequence=1,
        type='message.completed',
        data_json='{}',
        source='runner',
    ))

print('LEDGER_INVARIANTS_OK tables=3 statuses=8')
`;

async function main() {
  const root = resolve(env.LBS_ROOT || process.cwd());
  const caseId = "agent-runner-ledger-invariants";
  const runId = env.LBS_RUN_ID || `${timestampSlug()}-${caseId}`;
  const evidenceDir = resolve(env.LBS_EVIDENCE_DIR || join(root, "reports", "evidence", runId));
  await mkdir(evidenceDir, { recursive: true });
  const startedAt = new Date();
  const langbotRepo = resolveFromRoot(root, env.LANGBOT_REPO || "..");
  const sdkRepo = resolveFromRoot(root, env.LANGBOT_PLUGIN_SDK_REPO || "../../langbot-plugin-sdk");
  const sdkSrc = resolve(sdkRepo, "src");
  const stdoutLog = join(evidenceDir, "probe-stdout.log");
  const stderrLog = join(evidenceDir, "probe-stderr.log");
  const automationResultJson = join(evidenceDir, "automation-result.json");
  const resultJson = join(evidenceDir, "result.json");
  const command = {
    executable: "rtk",
    args: [resolve(langbotRepo, ".venv/bin/python"), "-c", probeScript],
    cwd: langbotRepo,
  };
  const timeoutMs = Number(env.LANGBOT_AGENT_RUNNER_PROBE_TIMEOUT_MS || "30000");
  const result = {
    source: "automation",
    probe: "python-sync",
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
    command,
    timeout_ms: timeoutMs,
    exit_status: null,
    signal: null,
    evidence: {
      stdout_log: stdoutLog,
      stderr_log: stderrLog,
      automation_result_json: automationResultJson,
      result_json: resultJson,
    },
    evidence_collected: ["filesystem"],
  };

  try {
    if (!existsSync(langbotRepo)) {
      result.status = "env_issue";
      result.reason = `LANGBOT_REPO/default ../LangBot did not resolve: ${langbotRepo}`;
    } else {
      const childEnv = {
        ...process.env,
        PYTHONPATH: [sdkSrc, process.env.PYTHONPATH].filter(Boolean).join(delimiter),
        UV_CACHE_DIR: env.UV_CACHE_DIR || join(evidenceDir, ".uv-cache"),
      };
      await mkdir(childEnv.UV_CACHE_DIR, { recursive: true });
      const proc = await runProcess(command, timeoutMs, childEnv);
      result.exit_status = proc.status;
      result.signal = proc.signal;
      await writeFile(stdoutLog, proc.stdout, "utf8");
      await writeFile(stderrLog, proc.stderr, "utf8");
      if (proc.error) {
        result.status = "env_issue";
        result.reason = proc.error.message;
      } else if (proc.timedOut) {
        result.status = "fail";
        result.reason = `ledger invariant probe timed out after ${timeoutMs}ms`;
      } else if (proc.status === 0) {
        result.status = "pass";
        result.reason = "ledger invariant probe passed";
      } else {
        result.status = "fail";
        result.reason = `ledger invariant probe exited with status ${proc.status}`;
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
