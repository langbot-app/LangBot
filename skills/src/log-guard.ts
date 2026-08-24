import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import type { StructuredItem } from "./types.ts";
import { listValue, loadEnv, loadStructuredItems, scalar } from "./fs.ts";

export type LogSourceName = "backend" | "frontend" | "console";
export type FindingSeverity =
  | "fail"
  | "warning"
  | "matched_troubleshooting"
  | "env_issue"
  | "ignored_expected_issue"
  | "missing_input";

export type LogFinding = {
  source: LogSourceName;
  path: string;
  severity: FindingSeverity;
  kind: string;
  pattern: string;
  line?: number;
  excerpt?: string;
  troubleshooting_id?: string;
  troubleshooting_title?: string;
  related_to_case?: boolean;
};

export type LogLine = {
  number: number;
  text: string;
};

export type LogSuccessSignal = {
  source: LogSourceName;
  path: string;
  kind: "case_success_pattern";
  pattern: string;
  line?: number;
  excerpt?: string;
};

export type LogScanMode =
  | "whole-file"
  | "since"
  | "until"
  | "since+until"
  | "tail-lines"
  | "since+tail-lines"
  | "until+tail-lines"
  | "since+until+tail-lines";

export type LogScanConfig = {
  mode: LogScanMode;
  since?: string;
  since_epoch_ms?: number;
  until?: string;
  until_epoch_ms?: number;
  tail_lines?: number;
  warnings: string[];
};

export type LogSourceSummary = {
  source: LogSourceName;
  path: string;
  status: "scanned" | "missing" | "auto_not_found";
  line_count: number;
  total_line_count?: number;
  start_line?: number;
  end_line?: number;
  timestamped_line_count?: number;
  auto_detected?: boolean;
};

export type LogGuardPatternContext = {
  successPatterns?: string[];
  failurePatterns?: string[];
  expectedFailures?: string[];
  relatedTroubleshootingIds?: string[];
};

export type LogGuardResult = {
  status: string;
  scan: LogScanConfig;
  sources: LogSourceSummary[];
  success_signals: LogSuccessSignal[];
  findings: LogFinding[];
};

export type AutomationResultEvidence = {
  status: "not_provided" | "missing" | "invalid" | "loaded";
  path?: string;
  result?: string;
  reason?: string;
  duration_ms?: number;
  started_at?: string;
  started_at_local?: string;
  finished_at?: string;
  finished_at_local?: string;
  url?: string;
  prompt?: string;
  expected_text?: string;
  stream_output?: string;
  prompt_count?: number;
  image_fixture?: string;
  evidence?: Record<string, string>;
  evidence_collected?: string[];
  browser_diagnostics?: {
    status?: string;
    reason?: string;
    finding_count?: number;
  };
  chat_results?: Array<{
    index?: number;
    expected_text?: string;
    status?: string;
    reason?: string;
  }>;
  metrics_summary?: Record<string, unknown>;
  thresholds_summary?: Record<string, unknown>;
  artifacts?: Record<string, unknown>;
};

type MutableScanState = {
  findings: LogFinding[];
  successSignals: LogSuccessSignal[];
  seenFindings: Set<string>;
  seenSuccessSignals: Set<string>;
};

const secretAssignmentRe = /\b(api[_-]?key|authorization|credential|jwt|oauth|password|secret|token)\s*[:=]\s*["']?([^"',\s]+)/gi;
const bearerSecretRe = /\bbearer\s+[A-Za-z0-9._~+/=-]{8,}/i;
const openAiStyleSecretRe = /\bsk-[A-Za-z0-9_-]{6,}\b/i;

const unexpectedPatterns: Array<{
  kind: string;
  pattern: string;
  regex: RegExp;
  severity: FindingSeverity;
  sources?: LogSourceName[];
}> = [
  { kind: "python_traceback", pattern: "Traceback", regex: /\bTraceback(?: \(most recent call last\))?/i, severity: "fail" },
  {
    kind: "unretrieved_task_exception",
    pattern: "Task exception was never retrieved",
    regex: /Task exception was never retrieved/i,
    severity: "fail",
  },
  {
    kind: "unawaited_coroutine",
    pattern: "RuntimeWarning: coroutine .* was never awaited",
    regex: /RuntimeWarning:\s+coroutine .* was never awaited/i,
    severity: "fail",
  },
  {
    kind: "unclosed_client_session",
    pattern: "Unclosed client session",
    regex: /Unclosed client session/i,
    severity: "fail",
  },
  { kind: "unclosed_connector", pattern: "Unclosed connector", regex: /Unclosed connector/i, severity: "fail" },
  { kind: "key_error", pattern: "KeyError", regex: /(^|[^A-Za-z])KeyError(?:\b|:)/, severity: "fail" },
  { kind: "type_error", pattern: "TypeError", regex: /(^|[^A-Za-z])TypeError(?:\b|:)/, severity: "fail" },
  {
    kind: "attribute_error",
    pattern: "AttributeError",
    regex: /(^|[^A-Za-z])AttributeError(?:\b|:)/,
    severity: "fail",
  },
  {
    kind: "frontend_uncaught_error",
    pattern: "Uncaught frontend error",
    regex: /\bUncaught (?:[A-Za-z]*Error|Exception)|Unhandled(?: promise rejection|Rejection)/i,
    severity: "fail",
    sources: ["console", "frontend"],
  },
  {
    kind: "http_5xx",
    pattern: "HTTP 5xx resource failure",
    regex: /Failed to load resource: the server responded with a status of 5\d\d|HTTP\/\d(?:\.\d)?\s+5\d\d/i,
    severity: "fail",
  },
  { kind: "error_log", pattern: "ERROR or CRITICAL log line", regex: /\b(?:ERROR|CRITICAL)\b/, severity: "warning" },
];

export function logPatternContextFromStructuredItem(item: StructuredItem): LogGuardPatternContext {
  return {
    successPatterns: listValue(item.fields, "success_patterns"),
    failurePatterns: listValue(item.fields, "failure_patterns"),
    expectedFailures: listValue(item.fields, "expected_failures"),
    relatedTroubleshootingIds: listValue(item.fields, "troubleshooting"),
  };
}

export function scanStructuredLogSources(
  root: string,
  item: StructuredItem,
  options: Record<string, string | boolean>,
): LogGuardResult {
  return scanLogSources(root, options, logPatternContextFromStructuredItem(item));
}

export function scanLogSources(
  root: string,
  options: Record<string, string | boolean>,
  context: LogGuardPatternContext = {},
): LogGuardResult {
  const env = loadEnv(root);
  const scan = parseScanConfig(optionsWithEvidenceWindow(options));
  const configuredSources: Array<{ source: LogSourceName; option: string }> = [
    { source: "backend", option: "backend-log" },
    { source: "frontend", option: "frontend-log" },
    { source: "console", option: "console-log" },
  ];
  const sources: LogSourceSummary[] = [];
  const state: MutableScanState = {
    findings: [],
    successSignals: [],
    seenFindings: new Set(),
    seenSuccessSignals: new Set(),
  };

  for (const warning of scan.warnings) {
    addFinding(state, {
      source: "backend",
      path: "log-scan-options",
      severity: "missing_input",
      kind: "invalid_log_scan_option",
      pattern: warning,
    });
  }

  for (const configured of configuredSources) {
    const explicitPath = options[configured.option];
    const autoPath = configured.source === "backend" && options["no-auto-log"] !== true
      ? latestLangBotLogPath(env, root)
      : null;
    const rawPath = typeof explicitPath === "string" ? explicitPath : autoPath;
    const autoDetected = typeof explicitPath !== "string" && rawPath === autoPath;
    if (!rawPath) {
      if (configured.source === "backend" && options["no-auto-log"] !== true) {
        const logsDir = langBotLogsDir(env, root) ?? "LANGBOT_REPO/data/logs";
        sources.push({ source: "backend", path: join(logsDir, "langbot-*.log"), status: "auto_not_found", line_count: 0, auto_detected: true });
      }
      continue;
    }

    const path = resolve(rawPath);
    if (!existsSync(path)) {
      sources.push({ source: configured.source, path, status: "missing", line_count: 0 });
      if (!autoDetected) {
        addFinding(state, {
          source: configured.source,
          path,
          severity: "missing_input",
          kind: "missing_log_file",
          pattern: `${configured.option} path does not exist`,
        });
      }
      continue;
    }

    const text = readFileSync(path, "utf8");
    scanLogTextIntoState(root, configured.source, path, text, scan, context, sources, state);
  }

  finalizeMissingSuccessSignal(context, sources, state);
  return buildLogGuardResult(scan, sources, state);
}

export function scanLogText(
  root: string,
  source: LogSourceName,
  path: string,
  text: string,
  options: Record<string, string | boolean> = {},
  context: LogGuardPatternContext = {},
  baseLineNumber = 0,
  includeMissingSuccessSignal = true,
): LogGuardResult {
  const scan = parseScanConfig(options);
  const sources: LogSourceSummary[] = [];
  const state: MutableScanState = {
    findings: [],
    successSignals: [],
    seenFindings: new Set(),
    seenSuccessSignals: new Set(),
  };

  scanLogTextIntoState(root, source, resolve(path), text, scan, context, sources, state, baseLineNumber);
  if (includeMissingSuccessSignal) finalizeMissingSuccessSignal(context, sources, state);
  return buildLogGuardResult(scan, sources, state);
}

function scanLogTextIntoState(
  root: string,
  source: LogSourceName,
  path: string,
  text: string,
  scan: LogScanConfig,
  context: LogGuardPatternContext,
  sources: LogSourceSummary[],
  state: MutableScanState,
  baseLineNumber = 0,
): void {
  const allLines = text.split(/\r?\n/).map((line, index) => ({ number: baseLineNumber + index + 1, text: line }));
  const selected = selectLinesForScan(allLines, scan);
  sources.push({
    source,
    path,
    status: "scanned",
    line_count: selected.lines.length,
    total_line_count: allLines.length,
    start_line: selected.lines[0]?.number,
    end_line: selected.lines[selected.lines.length - 1]?.number,
    timestamped_line_count: selected.timestampedLineCount,
  });

  scanUnexpectedPatterns(state, source, path, selected.lines, context.expectedFailures ?? []);
  scanCaseDeclaredPatterns(
    state,
    source,
    path,
    selected.lines,
    context.successPatterns ?? [],
    context.failurePatterns ?? [],
    context.expectedFailures ?? [],
  );
  scanTroubleshootingPatterns(
    state,
    source,
    path,
    selected.lines,
    loadStructuredItems(root, "troubleshooting"),
    new Set(context.relatedTroubleshootingIds ?? []),
    context.expectedFailures ?? [],
  );
}

function buildLogGuardResult(scan: LogScanConfig, sources: LogSourceSummary[], state: MutableScanState): LogGuardResult {
  const scannedCount = sources.filter((source) => source.status === "scanned").length;
  const hardFailures = state.findings.filter(
    (finding) => finding.severity === "fail" || finding.severity === "missing_input",
  );
  const relatedEnvIssues = state.findings.filter(
    (finding) => finding.severity === "env_issue" && finding.related_to_case !== false,
  );
  const hardFailuresAreExplainedProviderTracebacks = hardFailures.length > 0
    && relatedEnvIssues.length > 0
    && hardFailures.every((failure) =>
      failure.kind === "python_traceback"
      && relatedEnvIssues.some((envIssue) =>
        envIssue.source === failure.source
        && envIssue.path === failure.path
        && typeof envIssue.line === "number"
        && typeof failure.line === "number"
        && Math.abs(envIssue.line - failure.line) <= 100,
      ),
    );
  const status = scannedCount === 0 && state.findings.length === 0
    ? "not_run"
    : hardFailures.length > 0 && !hardFailuresAreExplainedProviderTracebacks
      ? "fail"
      : state.findings.some((finding) => finding.severity === "matched_troubleshooting" && finding.related_to_case !== false)
        ? "fail"
        : state.findings.some((finding) => finding.severity === "env_issue")
          ? "env_issue"
          : state.findings.some((finding) => finding.severity === "warning")
            ? "warning"
            : "pass";

  return { status, scan, sources, success_signals: state.successSignals, findings: state.findings };
}

function finalizeMissingSuccessSignal(
  context: LogGuardPatternContext,
  sources: LogSourceSummary[],
  state: MutableScanState,
): void {
  const scannedCount = sources.filter((source) => source.status === "scanned").length;
  const successPatterns = context.successPatterns ?? [];
  if (scannedCount > 0 && successPatterns.length > 0 && state.successSignals.length === 0) {
    addFinding(state, {
      source: "backend",
      path: "case-success-patterns",
      severity: "warning",
      kind: "missing_success_signal",
      pattern: successPatterns.join(" | "),
      excerpt: "No declared success_patterns matched the scanned log window.",
    });
  }
}

function shouldTreatAssignmentValueAsSecret(value: string): boolean {
  const normalized = value.trim().replace(/^["']|["']$/g, "");
  const lower = normalized.toLowerCase();
  if (!normalized) return false;
  if (["error", "invalid", "missing", "none", "null", "undefined", "redacted", "[redacted]"].includes(lower)) {
    return false;
  }
  if (/^(error|invalid|missing|none|null|undefined)\b/i.test(normalized)) return false;
  if (/^(your-|<|\$\{|example-|placeholder)/i.test(normalized)) return false;
  if (openAiStyleSecretRe.test(normalized)) return true;
  return normalized.length >= 8 && /[A-Za-z0-9]/.test(normalized);
}

function redactSecretAssignments(text: string): string {
  return text.replace(secretAssignmentRe, (match, key: string, value: string) => {
    if (!shouldTreatAssignmentValueAsSecret(value)) return match;
    return match.replace(value, "[redacted]");
  });
}

export function redactSecrets(text: string): string {
  return redactSecretAssignments(text
    .replace(/(\bauthorization\s*[:=]\s*bearer\s+)[A-Za-z0-9._~+/=-]+/gi, "$1[redacted]")
    .replace(/\bbearer\s+[A-Za-z0-9._~+/=-]{8,}/gi, "Bearer [redacted]")
    .replace(/\bsk-[A-Za-z0-9_-]{6,}\b/g, "[redacted]"));
}

function hasSecretLeak(line: string): boolean {
  secretAssignmentRe.lastIndex = 0;
  const hasSecretAssignment = Array.from(line.matchAll(secretAssignmentRe))
    .some((match) => shouldTreatAssignmentValueAsSecret(match[2] ?? ""));
  return hasSecretAssignment || bearerSecretRe.test(line) || openAiStyleSecretRe.test(line);
}

function findingKey(finding: LogFinding): string {
  return [
    finding.source,
    finding.path,
    finding.kind,
    finding.pattern,
    finding.line ?? "",
    finding.troubleshooting_id ?? "",
  ].join("\0");
}

function addFinding(state: MutableScanState, finding: LogFinding): void {
  const key = findingKey(finding);
  if (state.seenFindings.has(key)) return;
  state.seenFindings.add(key);
  state.findings.push(finding);
}

function successSignalKey(signal: LogSuccessSignal): string {
  return [signal.source, signal.path, signal.pattern, signal.line ?? ""].join("\0");
}

function addSuccessSignal(state: MutableScanState, signal: LogSuccessSignal): void {
  const key = successSignalKey(signal);
  if (state.seenSuccessSignals.has(key)) return;
  state.seenSuccessSignals.add(key);
  state.successSignals.push(signal);
}

function isExpectedFinding(finding: LogFinding, expectedFailures: string[]): boolean {
  if (finding.kind === "secret_leak" || finding.severity === "missing_input") return false;
  const haystack = [
    finding.kind,
    finding.pattern,
    finding.troubleshooting_id ?? "",
    finding.troubleshooting_title ?? "",
    finding.excerpt ?? "",
  ].join("\n").toLowerCase();
  return expectedFailures.some((item) => item && haystack.includes(item.toLowerCase()));
}

function withExpectedSeverity(finding: LogFinding, expectedFailures: string[]): LogFinding {
  if (!isExpectedFinding(finding, expectedFailures)) return finding;
  return { ...finding, severity: "ignored_expected_issue" };
}

function scanUnexpectedPatterns(
  state: MutableScanState,
  source: LogSourceName,
  path: string,
  lines: LogLine[],
  expectedFailures: string[],
): void {
  for (const line of lines) {
    for (const pattern of unexpectedPatterns) {
      if (pattern.sources && !pattern.sources.includes(source)) continue;
      if (!pattern.regex.test(line.text)) continue;
      addFinding(state, withExpectedSeverity({
        source,
        path,
        severity: pattern.severity,
        kind: pattern.kind,
        pattern: pattern.pattern,
        line: line.number,
        excerpt: redactSecrets(line.text.trim()),
      }, expectedFailures));
    }

    if (hasSecretLeak(line.text)) {
      addFinding(state, {
        source,
        path,
        severity: "fail",
        kind: "secret_leak",
        pattern: "secret-like value in logs",
        line: line.number,
        excerpt: redactSecrets(line.text.trim()),
      });
    }
  }
}

function scanTroubleshootingPatterns(
  state: MutableScanState,
  source: LogSourceName,
  path: string,
  lines: LogLine[],
  troubles: StructuredItem[],
  relatedIds: Set<string>,
  expectedFailures: string[],
): void {
  for (const entry of troubles) {
    const id = scalar(entry.fields, "id");
    const title = scalar(entry.fields, "title");
    const category = scalar(entry.fields, "category");
    for (const pattern of listValue(entry.fields, "patterns")) {
      const needle = pattern.toLowerCase();
      if (!needle) continue;
      let matchesForPattern = 0;
      for (const line of lines) {
        if (!line.text.toLowerCase().includes(needle)) continue;
        if (id === "plugin-runtime-timeout" && isModelRouteUnavailableText(line.text)) continue;
        addFinding(state, withExpectedSeverity({
          source,
          path,
          severity: category === "env_issue" ? "env_issue" : "matched_troubleshooting",
          kind: "troubleshooting_pattern",
          pattern,
          line: line.number,
          excerpt: redactSecrets(line.text.trim()),
          troubleshooting_id: id,
          troubleshooting_title: title,
          related_to_case: relatedIds.has(id),
        }, expectedFailures));
        matchesForPattern += 1;
        if (matchesForPattern >= 3) break;
      }
    }
  }
}

function isModelRouteUnavailableText(text: string): boolean {
  return /model_not_found|no available channel for model|invalid api key|insufficient user quota|insufficient_quota|quota exceeded|余额不足|当前分组上游负载已饱和/i.test(text);
}

function scanCaseDeclaredPatterns(
  state: MutableScanState,
  source: LogSourceName,
  path: string,
  lines: LogLine[],
  successPatterns: string[],
  failurePatterns: string[],
  expectedFailures: string[],
): void {
  for (const pattern of successPatterns) {
    const needle = pattern.toLowerCase();
    if (!needle) continue;
    let matchesForPattern = 0;
    for (const line of lines) {
      if (!line.text.toLowerCase().includes(needle)) continue;
      addSuccessSignal(state, {
        source,
        path,
        kind: "case_success_pattern",
        pattern,
        line: line.number,
        excerpt: redactSecrets(line.text.trim()),
      });
      matchesForPattern += 1;
      if (matchesForPattern >= 3) break;
    }
  }

  for (const pattern of failurePatterns) {
    const needle = pattern.toLowerCase();
    if (!needle) continue;
    let matchesForPattern = 0;
    for (const line of lines) {
      if (!line.text.toLowerCase().includes(needle)) continue;
      addFinding(state, withExpectedSeverity({
        source,
        path,
        severity: "fail",
        kind: "case_failure_pattern",
        pattern,
        line: line.number,
        excerpt: redactSecrets(line.text.trim()),
      }, expectedFailures));
      matchesForPattern += 1;
      if (matchesForPattern >= 3) break;
    }
  }
}

function optionsWithEvidenceWindow(options: Record<string, string | boolean>): Record<string, string | boolean> {
  if (typeof options.since === "string" && typeof options.until === "string") {
    return options;
  }

  const evidenceDir = evidenceDirFromOptions(options);
  if (!evidenceDir) return options;

  const resultPath = automationResultPath(evidenceDir);
  if (!existsSync(resultPath)) return options;

  try {
    const result = JSON.parse(readFileSync(resultPath, "utf8")) as Record<string, unknown>;
    const enriched = { ...options };
    const startedAt = stringField(result, "started_at_local") ?? stringField(result, "started_at");
    const finishedAt = stringField(result, "finished_at_local") ?? stringField(result, "finished_at");

    if (typeof enriched.since !== "string" && startedAt) {
      enriched.since = startedAt;
    }
    if (typeof enriched.until !== "string" && finishedAt) {
      enriched.until = finishedAt;
    }
    return enriched;
  } catch {
    return options;
  }
}

function stringField(data: Record<string, unknown>, key: string): string | undefined {
  const value = data[key];
  return typeof value === "string" && value.trim() ? value : undefined;
}

function numberField(data: Record<string, unknown>, key: string): number | undefined {
  const value = data[key];
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function objectField(data: Record<string, unknown>, key: string): Record<string, unknown> | undefined {
  const value = data[key];
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : undefined;
}

function stringMapField(data: Record<string, unknown>, key: string): Record<string, string> | undefined {
  const value = data[key];
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const entries = Object.entries(value as Record<string, unknown>)
    .filter((entry): entry is [string, string] => typeof entry[1] === "string" && entry[1].trim().length > 0);
  return entries.length ? Object.fromEntries(entries) : undefined;
}

function stringListField(data: Record<string, unknown>, key: string): string[] | undefined {
  const value = data[key];
  if (!Array.isArray(value)) return undefined;
  const items = value.map((item) => typeof item === "string" ? item : "").filter(Boolean);
  return items.length ? items : undefined;
}

function chatResultsField(data: Record<string, unknown>): AutomationResultEvidence["chat_results"] {
  const value = data.chat_results;
  if (!Array.isArray(value)) return undefined;
  const results = value
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item))
    .map((item) => ({
      index: numberField(item, "index"),
      expected_text: stringField(item, "expected_text"),
      status: stringField(item, "status"),
      reason: stringField(item, "reason"),
    }));
  return results.length ? results : undefined;
}

function browserDiagnosticsField(data: Record<string, unknown>): AutomationResultEvidence["browser_diagnostics"] {
  const value = data.browser_diagnostics;
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const diagnostics = value as Record<string, unknown>;
  const findings = Array.isArray(diagnostics.findings) ? diagnostics.findings.length : undefined;
  return {
    status: stringField(diagnostics, "status"),
    reason: stringField(diagnostics, "reason"),
    finding_count: findings,
  };
}

function evidenceDirFromOptions(options: Record<string, string | boolean>): string | undefined {
  const explicit = typeof options["evidence-dir"] === "string" ? options["evidence-dir"] : undefined;
  if (explicit) return resolve(explicit);
  const consoleLog = typeof options["console-log"] === "string" ? options["console-log"] : undefined;
  return consoleLog ? dirname(resolve(consoleLog)) : undefined;
}

function automationResultPath(evidenceDir: string): string {
  const primary = join(evidenceDir, "automation-result.json");
  if (existsSync(primary)) return primary;
  return join(evidenceDir, "result.json");
}

export function readAutomationResultEvidence(options: Record<string, string | boolean>): AutomationResultEvidence {
  const evidenceDir = evidenceDirFromOptions(options);
  if (!evidenceDir) return { status: "not_provided" };

  const resultPath = automationResultPath(evidenceDir);
  if (!existsSync(resultPath)) return { status: "missing", path: resultPath };

  try {
    const result = JSON.parse(readFileSync(resultPath, "utf8")) as Record<string, unknown>;
    if (result.source === "final") {
      return {
        status: "not_provided",
        path: resultPath,
        reason: "only final result.json is present; automation-result.json was not found",
      };
    }
    return {
      status: "loaded",
      path: resultPath,
      result: stringField(result, "status"),
      reason: stringField(result, "reason"),
      duration_ms: numberField(result, "duration_ms"),
      started_at: stringField(result, "started_at"),
      started_at_local: stringField(result, "started_at_local"),
      finished_at: stringField(result, "finished_at"),
      finished_at_local: stringField(result, "finished_at_local"),
      url: stringField(result, "url"),
      prompt: redactSecrets(stringField(result, "prompt") ?? ""),
      expected_text: stringField(result, "expected_text"),
      stream_output: typeof result.stream_output === "boolean" ? String(result.stream_output) : stringField(result, "stream_output"),
      prompt_count: numberField(result, "prompt_count"),
      image_fixture: stringField(result, "image_fixture"),
      evidence: stringMapField(result, "evidence"),
      evidence_collected: stringListField(result, "evidence_collected"),
      browser_diagnostics: browserDiagnosticsField(result),
      chat_results: chatResultsField(result),
      metrics_summary: objectField(result, "metrics_summary"),
      thresholds_summary: objectField(result, "thresholds_summary"),
      artifacts: objectField(result, "artifacts"),
    };
  } catch (error) {
    return { status: "invalid", path: resultPath, reason: String(error) };
  }
}

function langBotRepoFromRoot(root: string): string | null {
  const candidates = [
    resolve(root),
    basename(resolve(root)) === "skills" ? resolve(root, "..") : "",
    resolve(root, "../LangBot"),
    resolve(root, "LangBot"),
  ].filter(Boolean);

  const seen = new Set<string>();
  for (const candidate of candidates) {
    if (seen.has(candidate)) continue;
    seen.add(candidate);
    if (existsSync(join(candidate, "data", "config.yaml"))) return candidate;
  }
  return null;
}

function langBotLogsDir(env: Record<string, string>, root: string): string | null {
  const repo = env.LANGBOT_REPO ? resolve(env.LANGBOT_REPO) : langBotRepoFromRoot(root);
  return repo ? join(repo, "data", "logs") : null;
}

export function latestLangBotLogPath(env: Record<string, string>, root = process.cwd()): string | null {
  const logsDir = langBotLogsDir(env, root);
  if (!logsDir) return null;
  if (!existsSync(logsDir)) return null;

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
    .sort((a, b) => statSync(b).mtimeMs - statSync(a).mtimeMs);

  return candidates[0] ?? null;
}

export function parseScanConfig(options: Record<string, string | boolean>): LogScanConfig {
  const warnings: string[] = [];
  const sinceInput = typeof options.since === "string" ? options.since : undefined;
  const sinceMs = sinceInput ? Date.parse(sinceInput) : undefined;
  const untilInput = typeof options.until === "string" ? options.until : undefined;
  const untilMs = untilInput ? Date.parse(untilInput) : undefined;
  const tailInput = typeof options["tail-lines"] === "string" ? options["tail-lines"] : undefined;
  let tailLines: number | undefined;

  if (sinceInput && Number.isNaN(sinceMs)) {
    warnings.push(`--since is not a valid date/time: ${sinceInput}`);
  }
  if (untilInput && Number.isNaN(untilMs)) {
    warnings.push(`--until is not a valid date/time: ${untilInput}`);
  }

  if (tailInput) {
    const parsed = Number.parseInt(tailInput, 10);
    if (!/^\d+$/.test(tailInput) || parsed <= 0) {
      warnings.push(`--tail-lines must be a positive integer: ${tailInput}`);
    } else {
      tailLines = parsed;
    }
  }

  const hasSince = sinceInput !== undefined && sinceMs !== undefined && !Number.isNaN(sinceMs);
  const hasUntil = untilInput !== undefined && untilMs !== undefined && !Number.isNaN(untilMs);
  const hasTail = tailLines !== undefined;
  let mode: LogScanMode = "whole-file";
  if (hasSince && hasUntil && hasTail) {
    mode = "since+until+tail-lines";
  } else if (hasSince && hasUntil) {
    mode = "since+until";
  } else if (hasSince && hasTail) {
    mode = "since+tail-lines";
  } else if (hasUntil && hasTail) {
    mode = "until+tail-lines";
  } else if (hasSince) {
    mode = "since";
  } else if (hasUntil) {
    mode = "until";
  } else if (hasTail) {
    mode = "tail-lines";
  }

  return {
    mode,
    since: hasSince ? sinceInput : undefined,
    since_epoch_ms: hasSince ? sinceMs : undefined,
    until: hasUntil ? untilInput : undefined,
    until_epoch_ms: hasUntil ? untilMs : undefined,
    tail_lines: tailLines,
    warnings,
  };
}

function selectLinesForScan(lines: LogLine[], scan: LogScanConfig): { lines: LogLine[]; timestampedLineCount: number } {
  let selected = lines;
  let timestampedLineCount = 0;

  if (scan.since_epoch_ms !== undefined || scan.until_epoch_ms !== undefined) {
    const offsetMinutes =
      timezoneOffsetMinutes(scan.since)
      ?? timezoneOffsetMinutes(scan.until)
      ?? -new Date(scan.since_epoch_ms ?? scan.until_epoch_ms ?? Date.now()).getTimezoneOffset();
    const yearHint = new Date(scan.since_epoch_ms ?? scan.until_epoch_ms ?? Date.now()).getUTCFullYear();
    let includeCurrentBlock = false;
    const filtered = lines.filter((line) => {
      const timestamp = parseLogLineTimestampMs(line.text, yearHint, offsetMinutes);
      if (timestamp !== null) {
        timestampedLineCount += 1;
        includeCurrentBlock =
          (scan.since_epoch_ms === undefined || timestamp >= scan.since_epoch_ms)
          && (scan.until_epoch_ms === undefined || timestamp <= scan.until_epoch_ms);
        return includeCurrentBlock;
      }
      return includeCurrentBlock;
    });
    selected = timestampedLineCount === 0 ? lines : filtered;
  } else {
    timestampedLineCount = lines.reduce((count, line) => (
      parseLogLineTimestampMs(line.text, new Date().getFullYear(), -new Date().getTimezoneOffset()) === null
        ? count
        : count + 1
    ), 0);
  }

  if (scan.tail_lines !== undefined && selected.length > scan.tail_lines) {
    selected = selected.slice(-scan.tail_lines);
  }

  return { lines: selected, timestampedLineCount };
}

function timezoneOffsetMinutes(input: string | undefined): number | null {
  if (!input) return null;
  if (/[zZ]$/.test(input)) return 0;
  const match = input.match(/([+-])(\d{2}):?(\d{2})$/);
  if (!match) return null;
  const sign = match[1] === "-" ? -1 : 1;
  return sign * (Number.parseInt(match[2], 10) * 60 + Number.parseInt(match[3], 10));
}

function parseLogLineTimestampMs(line: string, yearHint: number, offsetMinutes: number): number | null {
  const fullIso = line.match(/^\[?(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:?\d{2})?)\]?/);
  if (fullIso) {
    const timestamp = Date.parse(fullIso[1].replace(" ", "T"));
    return Number.isNaN(timestamp) ? null : timestamp;
  }

  const langBot = line.match(/^\[(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{3})\]/);
  if (!langBot) return null;
  const [, month, day, hour, minute, second, millisecond] = langBot;
  return Date.UTC(
    yearHint,
    Number.parseInt(month, 10) - 1,
    Number.parseInt(day, 10),
    Number.parseInt(hour, 10),
    Number.parseInt(minute, 10),
    Number.parseInt(second, 10),
    Number.parseInt(millisecond, 10),
  ) - offsetMinutes * 60 * 1000;
}

export function renderLogFinding(finding: LogFinding): string {
  const location = finding.line ? `${finding.source}:${finding.line}` : finding.source;
  const trouble = finding.troubleshooting_id ? ` (${finding.troubleshooting_id})` : "";
  const related = finding.related_to_case === true ? ", related" : "";
  const excerpt = finding.excerpt ? ` - ${finding.excerpt}` : "";
  return `- [${finding.severity}] ${location}: ${finding.kind}${trouble}${related}; pattern: ${finding.pattern}${excerpt}`;
}

export function renderLogSuccessSignal(signal: LogSuccessSignal): string {
  const location = signal.line ? `${signal.source}:${signal.line}` : signal.source;
  const excerpt = signal.excerpt ? ` - ${signal.excerpt}` : "";
  return `- ${location}: ${signal.pattern}${excerpt}`;
}

export function strictLogGuardExitCode(result: LogGuardResult): number {
  return result.status === "fail" || result.status === "env_issue" ? 1 : 0;
}
