import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { basename, delimiter, join, resolve } from "node:path";
import { env } from "node:process";

function loadEnvDefaults(root) {
  for (const path of [join(root, "skills/.env"), join(root, "skills/.env.local")]) {
    if (!existsSync(path)) continue;
    for (const rawLine of readFileSync(path, "utf8").split(/\r?\n/)) {
      const line = rawLine.trim();
      if (!line || line.startsWith("#")) continue;
      const sep = line.indexOf("=");
      if (sep === -1) continue;
      const key = line.slice(0, sep).trim();
      if (env[key]) continue;
      env[key] = line.slice(sep + 1).trim().replace(/^["']|["']$/g, "");
    }
  }
}

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
  if (!value) return "";
  return resolve(root, value);
}

function truncate(text, maxLength = 12000) {
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength)}\n...[truncated ${text.length - maxLength} chars]`;
}

function exitCode(status) {
  if (status === "pass") return 0;
  if (status === "blocked" || status === "env_issue") return 2;
  return 1;
}

async function runProcess(command, timeoutMs, childEnv) {
  return await new Promise((resolveDone) => {
    const child = spawn(command.executable, command.args, {
      cwd: command.cwd,
      env: childEnv,
      detached: true,
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
      setTimeout(() => {
        try {
          process.kill(-child.pid, "SIGKILL");
        } catch {
          child.kill("SIGKILL");
        }
      }, 5000).unref();
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

export async function runPytestProbe({
  caseId,
  repoEnvKey,
  defaultRepo,
  pythonPathEnvKeys = [],
  defaultPythonPaths = [],
  testTargets,
  description,
  timeoutMs,
}) {
  const root = resolve(env.LBS_ROOT || process.cwd());
  loadEnvDefaults(root);
  const resolvedTimeoutMs = Number(timeoutMs || env.LANGBOT_AGENT_RUNNER_PROBE_TIMEOUT_MS || "180000");

  const runId = env.LBS_RUN_ID || `${timestampSlug()}-${caseId}`;
  const evidenceDir = resolve(env.LBS_EVIDENCE_DIR || join(root, "reports", "evidence", runId));
  await mkdir(evidenceDir, { recursive: true });
  const uvCacheDir = env.UV_CACHE_DIR || join(evidenceDir, ".uv-cache");
  await mkdir(uvCacheDir, { recursive: true });

  const startedAt = new Date();
  const repoPath = resolveFromRoot(root, env[repoEnvKey] || defaultRepo);
  const pythonPaths = [
    ...pythonPathEnvKeys.map((key) => env[key]).filter(Boolean),
    ...defaultPythonPaths,
  ].map((value) => resolveFromRoot(root, value));
  const automationResultJson = join(evidenceDir, "automation-result.json");
  const stdoutLog = join(evidenceDir, "pytest-stdout.log");
  const stderrLog = join(evidenceDir, "pytest-stderr.log");
  const resultJson = join(evidenceDir, "result.json");
  const command = {
    executable: "rtk",
    args: ["uv", "run", "pytest", "-q", ...testTargets],
    cwd: repoPath,
  };
  const result = {
    source: "automation",
    probe: "pytest",
    case_id: caseId,
    run_id: runId,
    description,
    started_at: startedAt.toISOString(),
    started_at_local: localIsoWithOffset(startedAt),
    finished_at: "",
    finished_at_local: "",
    duration_ms: 0,
    status: "fail",
    reason: "",
    repo_env_key: repoEnvKey,
    repo_path: repoPath,
    python_paths: pythonPaths,
    test_targets: testTargets,
    command,
    timeout_ms: resolvedTimeoutMs,
    uv_cache_dir: uvCacheDir,
    exit_status: null,
    signal: null,
    evidence: {
      pytest_stdout_log: stdoutLog,
      pytest_stderr_log: stderrLog,
      automation_result_json: automationResultJson,
      result_json: resultJson,
    },
    evidence_collected: ["filesystem"],
  };

  await writeFile(stdoutLog, "", "utf8");
  await writeFile(stderrLog, "", "utf8");

  try {
    if (!existsSync(repoPath)) {
      result.status = "env_issue";
      result.reason = `${repoEnvKey || "repo"} did not resolve to an existing directory: ${repoPath}`;
    } else {
      const missingTargets = testTargets.filter((target) => !existsSync(join(repoPath, target.split("::")[0])));
      if (missingTargets.length > 0) {
        result.status = "env_issue";
        result.reason = `pytest target file(s) not found in ${basename(repoPath)}: ${missingTargets.join(", ")}`;
      } else {
        const childEnv = { ...process.env, UV_CACHE_DIR: uvCacheDir };
        if (pythonPaths.length > 0) {
          childEnv.PYTHONPATH = [pythonPaths.join(delimiter), childEnv.PYTHONPATH].filter(Boolean).join(delimiter);
        }
        const proc = await runProcess(command, resolvedTimeoutMs, childEnv);
        result.exit_status = proc.status;
        result.signal = proc.signal;
        await writeFile(stdoutLog, truncate(proc.stdout), "utf8");
        await writeFile(stderrLog, truncate(proc.stderr), "utf8");

        if (proc.error) {
          result.status = "env_issue";
          result.reason = `Failed to start pytest command '${command.executable}': ${proc.error.message}`;
        } else if (proc.timedOut) {
          result.status = "fail";
          result.reason = `pytest timed out after ${resolvedTimeoutMs}ms. See ${stdoutLog} and ${stderrLog}.`;
        } else if (proc.status === 0) {
          result.status = "pass";
          result.reason = `pytest passed for ${testTargets.join(", ")}.`;
        } else if (/command not found|no such file or directory|executable file not found/i.test(`${proc.stdout}\n${proc.stderr}`)) {
          result.status = "env_issue";
          result.reason = `pytest command could not run in ${repoPath}. See ${stdoutLog} and ${stderrLog}.`;
        } else {
          result.status = "fail";
          result.reason = `pytest exited with status ${proc.status}. See ${stdoutLog} and ${stderrLog}.`;
        }
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

  process.exit(exitCode(result.status));
}
