import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { setTimeout as delay } from "node:timers/promises";
import { dirname, join, resolve } from "node:path";
import type { CommandContext } from "../types.ts";
import { optionString, parseOptions, usage } from "../cli.ts";
import { findStructuredItem, loadEnv } from "../fs.ts";
import {
  latestLangBotLogPath,
  logPatternContextFromStructuredItem,
  renderLogFinding,
  renderLogSuccessSignal,
  scanLogSources,
  scanLogText,
  strictLogGuardExitCode,
  type LogFinding,
  type LogGuardPatternContext,
  type LogGuardResult,
  type LogSuccessSignal,
} from "../log-guard.ts";

type LogGuardSession = {
  source: "log-guard-session";
  run_id: string;
  started_at: string;
  started_at_local: string;
  backend_log: string;
  case_id: string;
  case_skill: string;
};

type WatchSummary = {
  mode: "watch";
  status: string;
  path: string;
  started_at_local: string;
  finished_at_local: string;
  bytes_read: number;
  findings: LogFinding[];
  success_signals: LogSuccessSignal[];
};

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

function pad3(value: number): string {
  return String(value).padStart(3, "0");
}

function localIsoWithOffset(date: Date): string {
  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absoluteOffset = Math.abs(offsetMinutes);
  return [
    `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`,
    `T${pad2(date.getHours())}:${pad2(date.getMinutes())}:${pad2(date.getSeconds())}.${pad3(date.getMilliseconds())}`,
    `${sign}${pad2(Math.floor(absoluteOffset / 60))}:${pad2(absoluteOffset % 60)}`,
  ].join("");
}

function timestampSlug(localIso: string): string {
  return localIso
    .replace(/T/, "-")
    .replace(/[.:+]/g, "-")
    .replace(/[^A-Za-z0-9_-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

function writeOrPrint(content: string, output: string | undefined): void {
  if (!output) {
    console.log(content.trimEnd());
    return;
  }
  const path = resolve(output);
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, content, "utf8");
  console.log(path);
}

function positiveIntegerOption(options: Record<string, string | boolean>, key: string, fallback: number): number {
  const raw = optionString(options, key);
  if (!raw) return fallback;
  const parsed = Number.parseInt(raw, 10);
  if (!/^\d+$/.test(raw) || parsed <= 0) return fallback;
  return parsed;
}

function splitPatternList(value: string | undefined): string[] {
  if (!value) return [];
  return value
    .split(/\s*\|\s*|\s*,\s*/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function patternContextFromOptions(root: string, options: Record<string, string | boolean>): LogGuardPatternContext {
  const caseId = optionString(options, "case");
  const base = caseId ? logPatternContextFromStructuredItem(findStructuredItem(root, "cases", caseId)) : {};
  return {
    successPatterns: [
      ...(base.successPatterns ?? []),
      ...splitPatternList(optionString(options, "success-pattern")),
    ],
    failurePatterns: [
      ...(base.failurePatterns ?? []),
      ...splitPatternList(optionString(options, "failure-pattern")),
    ],
    expectedFailures: [
      ...(base.expectedFailures ?? []),
      ...splitPatternList(optionString(options, "expected-failure")),
    ],
    relatedTroubleshootingIds: base.relatedTroubleshootingIds ?? [],
  };
}

function latestOrExplicitBackendLog(root: string, options: Record<string, string | boolean>): string {
  const explicit = optionString(options, "backend-log");
  if (explicit) return resolve(explicit);
  const auto = latestLangBotLogPath(loadEnv(root), root);
  return auto ? resolve(auto) : "";
}

function renderSources(result: LogGuardResult): string[] {
  const lines: string[] = [];
  if (result.sources.length === 0) {
    lines.push("- sources: no log files provided; use --backend-log or configure LANGBOT_REPO.");
    return lines;
  }
  lines.push("- sources:");
  for (const source of result.sources) {
    const origin = source.auto_detected ? ", auto" : "";
    const total = source.total_line_count === undefined ? "" : `/${source.total_line_count}`;
    const range = source.start_line === undefined || source.end_line === undefined
      ? ""
      : `, lines ${source.start_line}-${source.end_line}`;
    const timestamped = source.timestamped_line_count === undefined ? "" : `, ${source.timestamped_line_count} timestamped`;
    lines.push(`  - ${source.source}: ${source.path} (${source.status}${origin}, ${source.line_count}${total} lines${range}${timestamped})`);
  }
  return lines;
}

function renderLogGuardMarkdown(title: string, result: LogGuardResult, extra: string[] = []): string {
  const lines: string[] = [];
  lines.push(`# ${title}`);
  lines.push("");
  lines.push(`Generated: ${new Date().toISOString()}`);
  lines.push(`Status: ${result.status}`);
  lines.push(`Scan mode: ${result.scan.mode}`);
  if (result.scan.since) lines.push(`Since: ${result.scan.since}`);
  if (result.scan.until) lines.push(`Until: ${result.scan.until}`);
  if (result.scan.tail_lines !== undefined) lines.push(`Tail lines: ${result.scan.tail_lines}`);
  if (extra.length > 0) {
    lines.push("");
    lines.push("## Context");
    for (const item of extra) lines.push(`- ${item}`);
  }
  lines.push("");
  lines.push("## Sources");
  lines.push(...renderSources(result));
  if (result.scan.warnings.length > 0) {
    lines.push("");
    lines.push("## Scan Warnings");
    for (const warning of result.scan.warnings) lines.push(`- ${warning}`);
  }
  lines.push("");
  lines.push("## Findings");
  if (result.findings.length === 0) lines.push("- None.");
  else for (const finding of result.findings) lines.push(renderLogFinding(finding));
  lines.push("");
  lines.push("## Success Signals");
  if (result.success_signals.length === 0) lines.push("- None.");
  else for (const signal of result.success_signals) lines.push(renderLogSuccessSignal(signal));
  lines.push("");
  return `${lines.join("\n").trimEnd()}\n`;
}

function statusFromEvents(findings: LogFinding[], successSignals: LogSuccessSignal[]): string {
  if (findings.some((finding) => finding.severity === "fail" || finding.severity === "missing_input")) return "fail";
  if (findings.some((finding) => finding.severity === "matched_troubleshooting" && finding.related_to_case !== false)) return "fail";
  if (findings.some((finding) => finding.severity === "env_issue")) return "env_issue";
  if (findings.some((finding) => finding.severity === "warning")) return "warning";
  if (successSignals.length > 0) return "pass";
  return "no_activity";
}

function strictSummaryExitCode(status: string): number {
  return status === "fail" || status === "env_issue" ? 1 : 0;
}

function sessionDir(options: Record<string, string | boolean>): string {
  return optionString(options, "output-dir") ?? join("reports", "log-guards");
}

function sessionPath(options: Record<string, string | boolean>, runId: string): string {
  return join(sessionDir(options), `${runId}.json`);
}

function readSession(options: Record<string, string | boolean>): LogGuardSession | undefined {
  const runId = optionString(options, "run-id");
  const explicitSession = optionString(options, "session");
  const path = explicitSession ? resolve(explicitSession) : runId ? resolve(sessionPath(options, runId)) : "";
  if (!path || !existsSync(path)) return undefined;
  return JSON.parse(readFileSync(path, "utf8")) as LogGuardSession;
}

export function commandLogScan(ctx: CommandContext): number {
  const { positional, options } = parseOptions(ctx.args.slice(2));
  if (positional.length > 0) usage();

  const result = scanLogSources(ctx.root, options, patternContextFromOptions(ctx.root, options));
  const output = optionString(options, "output");
  const content = options.json === true
    ? `${JSON.stringify(result, null, 2)}\n`
    : renderLogGuardMarkdown("Log Guard Scan", result, [
      optionString(options, "case") ? `case: ${optionString(options, "case")}` : "case: none",
      options.strict === true ? "strict: yes" : "strict: no",
    ]);
  writeOrPrint(content, output);
  return options.strict === true ? strictLogGuardExitCode(result) : 0;
}

export async function commandLogWatch(ctx: CommandContext): Promise<number> {
  const { positional, options } = parseOptions(ctx.args.slice(2));
  if (positional.length > 0) usage();

  const path = latestOrExplicitBackendLog(ctx.root, options);
  if (!path) {
    console.error("ERROR: no backend log found; pass --backend-log or configure LANGBOT_REPO.");
    return 1;
  }
  if (!existsSync(path)) {
    console.error(`ERROR: backend log does not exist: ${path}`);
    return 1;
  }

  const context = patternContextFromOptions(ctx.root, options);
  const intervalMs = positiveIntegerOption(options, "interval-ms", 1000);
  const durationMs = optionString(options, "duration-ms")
    ? positiveIntegerOption(options, "duration-ms", 0)
    : 0;
  const startedAtLocal = localIsoWithOffset(new Date());
  const findings: LogFinding[] = [];
  const successSignals: LogSuccessSignal[] = [];
  let bytesRead = 0;
  let offset = options["from-start"] === true ? 0 : statSync(path).size;
  let baseLineNumber = options["from-start"] === true
    ? 0
    : readFileSync(path).subarray(0, offset).toString("utf8").split(/\r?\n/).length - 1;
  let carry = "";

  if (options.json !== true) {
    console.log(`# Log Guard Watch`);
    console.log(`Path: ${path}`);
    console.log(`Started: ${startedAtLocal}`);
    console.log(`Mode: ${options["from-start"] === true ? "from-start" : "new-lines"}`);
  }

  const startedMs = Date.now();
  let stopRequested = false;
  const stop = (): void => {
    stopRequested = true;
  };
  process.once("SIGINT", stop);
  process.once("SIGTERM", stop);

  const poll = (): void => {
    const buffer = readFileSync(path);
    if (buffer.length < offset) {
      offset = 0;
      baseLineNumber = 0;
      carry = "";
    }
    if (buffer.length === offset) return;

    const chunk = buffer.subarray(offset).toString("utf8");
    offset = buffer.length;
    bytesRead += Buffer.byteLength(chunk);
    const text = `${carry}${chunk}`;
    const hasCompleteLine = /\r?\n$/.test(text);
    const lastNewline = Math.max(text.lastIndexOf("\n"), text.lastIndexOf("\r"));
    if (!hasCompleteLine && lastNewline === -1) {
      carry = text;
      return;
    }

    const complete = hasCompleteLine ? text : text.slice(0, lastNewline + 1);
    carry = hasCompleteLine ? "" : text.slice(lastNewline + 1);
    if (!complete) return;

    const result = scanLogText(ctx.root, "backend", path, complete, {}, context, baseLineNumber, false);
    baseLineNumber += complete.split(/\r?\n/).length - 1;
    findings.push(...result.findings);
    successSignals.push(...result.success_signals);

    if (options.json !== true) {
      for (const finding of result.findings) console.log(renderLogFinding(finding));
      for (const signal of result.success_signals) console.log(renderLogSuccessSignal(signal));
    }
  };

  try {
    do {
      poll();
      if (stopRequested) break;
      if (durationMs > 0 && Date.now() - startedMs >= durationMs) break;
      await delay(Math.min(intervalMs, durationMs > 0 ? Math.max(1, durationMs - (Date.now() - startedMs)) : intervalMs));
    } while (!stopRequested);

    if (carry) {
      const result = scanLogText(ctx.root, "backend", path, carry, {}, context, baseLineNumber, false);
      findings.push(...result.findings);
      successSignals.push(...result.success_signals);
      if (options.json !== true) {
        for (const finding of result.findings) console.log(renderLogFinding(finding));
        for (const signal of result.success_signals) console.log(renderLogSuccessSignal(signal));
      }
    }
  } finally {
    process.off("SIGINT", stop);
    process.off("SIGTERM", stop);
  }

  const summary: WatchSummary = {
    mode: "watch",
    status: statusFromEvents(findings, successSignals),
    path,
    started_at_local: startedAtLocal,
    finished_at_local: localIsoWithOffset(new Date()),
    bytes_read: bytesRead,
    findings,
    success_signals: successSignals,
  };

  if (options.json === true) {
    console.log(JSON.stringify(summary, null, 2));
  } else {
    console.log(`Status: ${summary.status}`);
    console.log(`Bytes read: ${summary.bytes_read}`);
  }
  return options.strict === true ? strictSummaryExitCode(summary.status) : 0;
}

export function commandLogGuard(ctx: CommandContext): number {
  const sub = ctx.args[2];
  if (sub === "start") return commandLogGuardStart(ctx);
  if (sub === "stop") return commandLogGuardStop(ctx);
  usage();
}

function commandLogGuardStart(ctx: CommandContext): number {
  const { positional, options } = parseOptions(ctx.args.slice(3));
  if (positional.length > 0) usage();

  const now = new Date();
  const startedAtLocal = localIsoWithOffset(now);
  const runId = optionString(options, "run-id") ?? `log-guard-${timestampSlug(startedAtLocal)}`;
  const caseId = optionString(options, "case") ?? "";
  const caseItem = caseId ? findStructuredItem(ctx.root, "cases", caseId) : undefined;
  const session: LogGuardSession = {
    source: "log-guard-session",
    run_id: runId,
    started_at: now.toISOString(),
    started_at_local: startedAtLocal,
    backend_log: latestOrExplicitBackendLog(ctx.root, options),
    case_id: caseId,
    case_skill: caseItem?.skill ?? "",
  };
  const path = resolve(sessionPath(options, runId));
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, `${JSON.stringify(session, null, 2)}\n`, "utf8");

  const result = {
    ...session,
    path,
    stop_command: `bin/lbs log guard stop --run-id ${runId} --output-dir ${sessionDir(options)}`,
  };
  if (options.json === true) console.log(JSON.stringify(result, null, 2));
  else {
    console.log(`# Log Guard Session`);
    console.log(`Run: ${runId}`);
    console.log(`Started: ${startedAtLocal}`);
    console.log(`Session: ${path}`);
    if (session.backend_log) console.log(`Backend log: ${session.backend_log}`);
    if (session.case_id) console.log(`Case: ${session.case_id}`);
    console.log(`Stop: ${result.stop_command}`);
  }
  return 0;
}

function commandLogGuardStop(ctx: CommandContext): number {
  const { positional, options } = parseOptions(ctx.args.slice(3));
  if (positional.length > 0) usage();

  const session = readSession(options);
  if (!session) {
    console.error("ERROR: log guard session not found; pass --run-id with --output-dir or --session.");
    return 1;
  }

  const now = new Date();
  const scanOptions: Record<string, string | boolean> = {
    ...options,
    since: optionString(options, "since") ?? session.started_at_local,
    until: optionString(options, "until") ?? localIsoWithOffset(now),
  };
  if (session.backend_log && typeof scanOptions["backend-log"] !== "string") {
    scanOptions["backend-log"] = session.backend_log;
  }

  const caseId = optionString(options, "case") ?? session.case_id;
  const context = caseId
    ? logPatternContextFromStructuredItem(findStructuredItem(ctx.root, "cases", caseId))
    : patternContextFromOptions(ctx.root, options);
  const result = scanLogSources(ctx.root, scanOptions, context);
  const output = optionString(options, "output") ?? join(sessionDir(options), `${session.run_id}.md`);
  const content = options.json === true
    ? `${JSON.stringify({ session, result }, null, 2)}\n`
    : renderLogGuardMarkdown("Log Guard Report", result, [
      `run_id: ${session.run_id}`,
      `started: ${session.started_at_local}`,
      `finished: ${scanOptions.until}`,
      caseId ? `case: ${caseId}` : "case: none",
    ]);
  writeOrPrint(content, options.json === true ? optionString(options, "output") : output);
  return options["no-strict"] === true ? 0 : strictLogGuardExitCode(result);
}
