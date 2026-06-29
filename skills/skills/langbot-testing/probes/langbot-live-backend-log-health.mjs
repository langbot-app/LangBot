#!/usr/bin/env node

import { existsSync, readdirSync, statSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { env, exit } from "node:process";

function pad(value, size = 2) {
  return String(value).padStart(size, "0");
}

function localIsoWithOffset(date = new Date()) {
  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absolute = Math.abs(offsetMinutes);
  return [
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}.${pad(date.getMilliseconds(), 3)}`,
    `${sign}${pad(Math.floor(absolute / 60))}:${pad(absolute % 60)}`,
  ].join("");
}

function timestampSlug(date = new Date()) {
  return date.toISOString().replace(/\.\d{3}Z$/, "Z").replace(/[^0-9A-Za-z]+/g, "-").replace(/^-|-$/g, "");
}

function repoRootFromEnv(root) {
  return env.LANGBOT_REPO ? resolve(env.LANGBOT_REPO) : resolve(root, "..");
}

function latestBackendLog(root) {
  const explicit = env.LANGBOT_BACKEND_LOG;
  if (explicit) return resolve(explicit);

  const logsDir = join(repoRootFromEnv(root), "data", "logs");
  if (!existsSync(logsDir)) return "";
  const candidates = readdirSync(logsDir)
    .filter((name) => /^langbot-.*\.log$/.test(name))
    .map((name) => join(logsDir, name))
    .filter((path) => {
      try {
        return statSync(path).isFile();
      } catch {
        return false;
      }
    })
    .sort((left, right) => statSync(right).mtimeMs - statSync(left).mtimeMs);
  return candidates[0] || "";
}

function parseSince(startedAt) {
  if (env.LANGBOT_BACKEND_LOG_SINCE) return new Date(env.LANGBOT_BACKEND_LOG_SINCE);
  const lookbackSeconds = Number(env.LANGBOT_BACKEND_LOG_LOOKBACK_SECONDS || "300");
  return new Date(startedAt.getTime() - lookbackSeconds * 1000);
}

function parseTimestamp(line, year) {
  const localMatch = line.match(/^\[(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{3})\]/);
  if (localMatch) {
    const [, month, day, hour, minute, second, millisecond] = localMatch;
    return new Date(`${year}-${month}-${day}T${hour}:${minute}:${second}.${millisecond}+08:00`);
  }

  const accessMatch = line.match(/^\[(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2}) ([+-]\d{4})\]/);
  if (accessMatch) {
    const [, fullYear, month, day, hour, minute, second, offset] = accessMatch;
    const normalizedOffset = `${offset.slice(0, 3)}:${offset.slice(3)}`;
    return new Date(`${fullYear}-${month}-${day}T${hour}:${minute}:${second}${normalizedOffset}`);
  }

  return null;
}

function findingForLine(line, number) {
  const rules = [
    { severity: "fail", kind: "python_traceback", pattern: /\bTraceback(?: \(most recent call last\))?/i },
    { severity: "fail", kind: "unretrieved_task_exception", pattern: /Task exception was never retrieved/i },
    { severity: "fail", kind: "unawaited_coroutine", pattern: /RuntimeWarning:\s+coroutine .* was never awaited/i },
    { severity: "fail", kind: "unclosed_client_session", pattern: /Unclosed client session/i },
    { severity: "fail", kind: "unclosed_connector", pattern: /Unclosed connector/i },
    { severity: "fail", kind: "import_error", pattern: /\bImportError\b/i },
    { severity: "fail", kind: "error_log", pattern: /\b(?:ERROR|CRITICAL)\b/ },
    { severity: "warning", kind: "warning_log", pattern: /\bWARNING\b/ },
  ];

  for (const rule of rules) {
    if (rule.pattern.test(line)) {
      return {
        severity: rule.severity,
        kind: rule.kind,
        line: number,
        excerpt: line,
      };
    }
  }
  return null;
}

function scanLines(text, since, year) {
  const findings = [];
  const scanned = [];
  let includeContinuation = false;
  const lines = text.split(/\r?\n/);
  for (const [index, line] of lines.entries()) {
    const number = index + 1;
    const timestamp = parseTimestamp(line, year);
    if (timestamp) includeContinuation = timestamp >= since;
    if (!includeContinuation) continue;
    scanned.push({ number, text: line });
    const finding = findingForLine(line, number);
    if (finding) findings.push(finding);
  }
  return { findings, scanned, total_lines: lines.length };
}

async function main() {
  const root = resolve(env.LBS_ROOT || process.cwd());
  const caseId = "langbot-live-backend-log-health";
  const runId = env.LBS_RUN_ID || `${timestampSlug()}-${caseId}`;
  const evidenceDir = resolve(env.LBS_EVIDENCE_DIR || join(root, "reports", "evidence", runId));
  await mkdir(evidenceDir, { recursive: true });

  const startedAt = new Date();
  const since = parseSince(startedAt);
  const logPath = latestBackendLog(root);
  const metricsPath = join(evidenceDir, "metrics.json");
  const findingsPath = join(evidenceDir, "findings.json");
  const scannedLogPath = join(evidenceDir, "scanned-backend.log");
  const automationResultPath = join(evidenceDir, "automation-result.json");
  const resultPath = join(evidenceDir, "result.json");

  let status = "fail";
  let reason = "";
  let scan = { findings: [], scanned: [], total_lines: 0 };
  if (!logPath || !existsSync(logPath)) {
    status = "env_issue";
    reason = "No LangBot backend log file was found. Set LANGBOT_BACKEND_LOG or LANGBOT_REPO.";
  } else {
    const text = await readFile(logPath, "utf8");
    scan = scanLines(text, since, startedAt.getFullYear());
    const failCount = scan.findings.filter((item) => item.severity === "fail").length;
    status = failCount === 0 ? "pass" : "fail";
    reason = status === "pass"
      ? "Live backend log health passed; no fail-severity findings in the scanned window."
      : "Live backend log health found fail-severity backend log findings.";
  }

  const warningCount = scan.findings.filter((item) => item.severity === "warning").length;
  const failCount = scan.findings.filter((item) => item.severity === "fail").length;
  const metrics = {
    probe: caseId,
    backend_log: logPath,
    since: since.toISOString(),
    scanned_line_count: scan.scanned.length,
    total_line_count: scan.total_lines,
    fail_count: failCount,
    warning_count: warningCount,
    finding_count: scan.findings.length,
  };
  const thresholds = {
    fail_count: { actual: failCount, max: 0, pass: failCount === 0 },
  };

  await writeFile(metricsPath, `${JSON.stringify(metrics, null, 2)}\n`, "utf8");
  await writeFile(findingsPath, `${JSON.stringify(scan.findings, null, 2)}\n`, "utf8");
  await writeFile(scannedLogPath, scan.scanned.map((item) => `${item.number}: ${item.text}`).join("\n") + (scan.scanned.length > 0 ? "\n" : ""), "utf8");

  const finishedAt = new Date();
  const result = {
    source: "automation",
    case_id: caseId,
    run_id: runId,
    status,
    reason,
    started_at: startedAt.toISOString(),
    started_at_local: localIsoWithOffset(startedAt),
    finished_at: finishedAt.toISOString(),
    finished_at_local: localIsoWithOffset(finishedAt),
    duration_ms: finishedAt.getTime() - startedAt.getTime(),
    url: logPath,
    metrics_summary: {
      scanned_line_count: metrics.scanned_line_count,
      fail_count: metrics.fail_count,
      warning_count: metrics.warning_count,
      finding_count: metrics.finding_count,
    },
    thresholds_summary: thresholds,
    artifacts: {
      metrics_json: metricsPath,
      findings_json: findingsPath,
      scanned_backend_log: scannedLogPath,
      automation_result_json: automationResultPath,
      result_json: resultPath,
    },
    evidence_collected: ["metrics", "backend_log", "filesystem"],
  };

  const resultText = `${JSON.stringify(result, null, 2)}\n`;
  await writeFile(automationResultPath, resultText, "utf8");
  await writeFile(resultPath, resultText, "utf8");
  console.log(JSON.stringify(result, null, 2));
  exit(status === "pass" ? 0 : status === "env_issue" ? 2 : 1);
}

await main();
