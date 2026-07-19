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
import asyncio
import json
import sys
from pathlib import Path

from langbot.pkg.agent.runner.descriptor import AgentRunnerDescriptor
from langbot.pkg.agent.runner.errors import RunnerExecutionError, RunnerProtocolError
from langbot.pkg.agent.runner.result_normalizer import AgentResultNormalizer

class Logger:
    def debug(self, *_args, **_kwargs): pass
    def info(self, *_args, **_kwargs): pass
    def warning(self, *_args, **_kwargs): pass
    def error(self, *_args, **_kwargs): pass

class App:
    logger = Logger()

def descriptor():
    return AgentRunnerDescriptor(
        id='plugin:qa/agent-runner/default',
        source='plugin',
        label={'en_US': 'QA AgentRunner'},
        plugin_author='qa',
        plugin_name='agent-runner',
        runner_name='default',
        capabilities={'streaming': True},
    )

async def consume_behavior(normalizer, desc, behavior):
    messages = []
    chunks = []
    failures = []
    protocol_errors = []
    for result in behavior['results']:
        try:
            normalized = await normalizer.normalize(result, desc)
        except RunnerExecutionError as exc:
            failures.append(str(exc))
            continue
        except RunnerProtocolError as exc:
            protocol_errors.append(str(exc))
            continue
        if normalized is None:
            continue
        content = getattr(normalized, 'content', '')
        if normalized.__class__.__name__ == 'MessageChunk':
            chunks.append(content)
        else:
            messages.append(content)
    return {
        'name': behavior['name'],
        'messages': messages,
        'chunks': chunks,
        'failures': failures,
        'protocol_errors': protocol_errors,
    }

async def main(path):
    data = json.loads(Path(path).read_text())
    normalizer = AgentResultNormalizer(App())
    desc = descriptor()
    observed = [await consume_behavior(normalizer, desc, item) for item in data['behaviors']]
    by_name = {item['name']: item for item in observed}
    assert by_name['ok']['messages'] == ['QA_RUNNER_OK'], by_name['ok']
    assert ''.join(by_name['stream_ok']['chunks']) == 'QA_RUNNER_STREAM_OK', by_name['stream_ok']
    assert by_name['empty_output']['messages'] == [] and by_name['empty_output']['chunks'] == [], by_name['empty_output']
    assert by_name['malformed_result']['messages'] == [] and by_name['malformed_result']['chunks'] == [], by_name['malformed_result']
    assert by_name['controlled_failure']['failures'], by_name['controlled_failure']
    print('QA_RUNNER_BEHAVIOR_MATRIX_OK behaviors=%d' % len(observed))

asyncio.run(main(sys.argv[1]))
`;

async function main() {
  const root = resolve(env.LBS_ROOT || process.cwd());
  const caseId = "agent-runner-behavior-matrix";
  const runId = env.LBS_RUN_ID || `${timestampSlug()}-${caseId}`;
  const evidenceDir = resolve(env.LBS_EVIDENCE_DIR || join(root, "reports", "evidence", runId));
  await mkdir(evidenceDir, { recursive: true });
  const startedAt = new Date();
  const langbotRepo = resolve(root, env.LANGBOT_REPO || "..");
  const sdkRepo = resolve(root, env.LANGBOT_PLUGIN_SDK_REPO || "../../langbot-plugin-sdk");
  const sdkSrc = resolve(sdkRepo, "src");
  const fixturePath = resolve(root, "skills/langbot-testing/fixtures/agent-runner/qa-runner-behaviors.json");
  const stdoutLog = join(evidenceDir, "probe-stdout.log");
  const stderrLog = join(evidenceDir, "probe-stderr.log");
  const automationResultJson = join(evidenceDir, "automation-result.json");
  const resultJson = join(evidenceDir, "result.json");
  const timeoutMs = Number(env.LANGBOT_AGENT_RUNNER_PROBE_TIMEOUT_MS || "30000");
  const command = {
    executable: "rtk",
    args: [resolve(langbotRepo, ".venv/bin/python"), "-c", script, fixturePath],
    cwd: langbotRepo,
  };
  const result = {
    source: "automation",
    probe: "agent-runner-behavior-matrix",
    case_id: caseId,
    run_id: runId,
    started_at: startedAt.toISOString(),
    started_at_local: localIsoWithOffset(startedAt),
    finished_at: "",
    finished_at_local: "",
    duration_ms: 0,
    status: "fail",
    reason: "",
    fixture_path: fixturePath,
    repo_path: langbotRepo,
    python_paths: [sdkSrc],
    command,
    timeout_ms: timeoutMs,
    exit_status: null,
    signal: null,
    evidence: { stdout_log: stdoutLog, stderr_log: stderrLog, automation_result_json: automationResultJson, result_json: resultJson },
    evidence_collected: ["filesystem"],
  };
  try {
    if (!existsSync(langbotRepo) || !existsSync(fixturePath)) {
      result.status = "env_issue";
      result.reason = `missing repo or fixture: ${langbotRepo} ${fixturePath}`;
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
        result.reason = `behavior matrix timed out after ${timeoutMs}ms`;
      } else if (proc.status === 0 && proc.stdout.includes("QA_RUNNER_BEHAVIOR_MATRIX_OK")) {
        result.status = "pass";
        result.reason = "behavior matrix passed";
      } else {
        result.status = "fail";
        result.reason = `behavior matrix exited with status ${proc.status}`;
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
