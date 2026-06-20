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
import importlib.util
import sys
from pathlib import Path

from langbot_plugin.api.entities.builtin.agent_runner.context import AgentRunContext
from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext
from langbot_plugin.api.entities.builtin.agent_runner.event import AgentEventContext
from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput
from langbot_plugin.api.entities.builtin.agent_runner.resources import AgentResources
from langbot_plugin.api.entities.builtin.agent_runner.runtime import AgentRuntimeContext
from langbot_plugin.api.entities.builtin.agent_runner.trigger import AgentTrigger

fixture = Path(sys.argv[1])
runner_py = fixture / "components" / "agent_runner" / "default.py"
manifest = fixture / "manifest.yaml"
runner_yaml = fixture / "components" / "agent_runner" / "default.yaml"
assert manifest.exists(), manifest
assert runner_yaml.exists(), runner_yaml
spec = importlib.util.spec_from_file_location("qa_agent_runner_fixture", runner_py)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

def context(run_id, text):
    return AgentRunContext(
        run_id=run_id,
        trigger=AgentTrigger(type="message.received", source="webui"),
        event=AgentEventContext(event_id=f"evt-{run_id}", event_type="message.received", source="webui"),
        input=AgentInput(text=text),
        delivery=DeliveryContext(surface="debug_chat"),
        resources=AgentResources(),
        runtime=AgentRuntimeContext(langbot_version="qa"),
    )

async def collect(text):
    runner = module.DefaultAgentRunner()
    results = []
    async for result in runner.run(context(f"run-{len(text)}", text)):
        results.append(result)
    return results

async def main():
    normal = await collect("hello")
    assert len(normal) == 1, normal
    assert normal[0].type.value == "run.completed"
    assert normal[0].data["message"]["content"] == "QA_AGENT_RUNNER_OK:hello"

    stream = await collect("stream hello")
    assert [item.type.value for item in stream] == ["message.delta", "message.delta", "message.delta", "run.completed"]
    assert "".join(item.data["chunk"]["content"] for item in stream[:3]) == "QA_AGENT_RUNNER_OK:stream hello"

    failed = await collect("please fail")
    assert len(failed) == 1
    assert failed[0].type.value == "run.failed"
    assert failed[0].data["error"] == "QA_AGENT_RUNNER_CONTROLLED_FAILURE"
    print("QA_AGENT_RUNNER_FIXTURE_CONTRACT_OK")

asyncio.run(main())
`;

async function main() {
  const root = resolve(env.LBS_ROOT || process.cwd());
  const caseId = "agent-runner-fixture-contract";
  const runId = env.LBS_RUN_ID || `${timestampSlug()}-${caseId}`;
  const evidenceDir = resolve(env.LBS_EVIDENCE_DIR || join(root, "reports", "evidence", runId));
  await mkdir(evidenceDir, { recursive: true });
  const startedAt = new Date();
  const sdkRepo = resolve(root, env.LANGBOT_PLUGIN_SDK_REPO || "../langbot-plugin-sdk");
  const sdkSrc = resolve(sdkRepo, "src");
  const fixturePath = resolve(root, "skills/langbot-testing/fixtures/plugins/qa-agent-runner");
  const stdoutLog = join(evidenceDir, "probe-stdout.log");
  const stderrLog = join(evidenceDir, "probe-stderr.log");
  const automationResultJson = join(evidenceDir, "automation-result.json");
  const resultJson = join(evidenceDir, "result.json");
  const timeoutMs = Number(env.LANGBOT_AGENT_RUNNER_PROBE_TIMEOUT_MS || "30000");
  const command = { executable: "rtk", args: ["uv", "run", "python", "-c", script, fixturePath], cwd: sdkRepo };
  const result = {
    source: "automation",
    probe: "agent-runner-fixture-contract",
    case_id: caseId,
    run_id: runId,
    started_at: startedAt.toISOString(),
    started_at_local: localIsoWithOffset(startedAt),
    finished_at: "",
    finished_at_local: "",
    duration_ms: 0,
    status: "fail",
    reason: "",
    repo_path: sdkRepo,
    fixture_path: fixturePath,
    command,
    timeout_ms: timeoutMs,
    exit_status: null,
    signal: null,
    evidence: { stdout_log: stdoutLog, stderr_log: stderrLog, automation_result_json: automationResultJson, result_json: resultJson },
    evidence_collected: ["filesystem"],
  };
  try {
    if (!existsSync(sdkRepo) || !existsSync(fixturePath)) {
      result.status = "env_issue";
      result.reason = `SDK repo or fixture path missing: ${sdkRepo} ${fixturePath}`;
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
        result.reason = `fixture contract probe timed out after ${timeoutMs}ms`;
      } else if (proc.status === 0 && proc.stdout.includes("QA_AGENT_RUNNER_FIXTURE_CONTRACT_OK")) {
        result.status = "pass";
        result.reason = "QA AgentRunner fixture contract passed";
      } else {
        result.status = "fail";
        result.reason = `fixture contract exited with status ${proc.status}`;
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
