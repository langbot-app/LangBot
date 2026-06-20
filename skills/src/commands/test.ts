import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { env as processEnv, execPath } from "node:process";
import type { CommandContext, StructuredItem } from "../types.ts";
import { parseOptions, usage } from "../cli.ts";
import { caseEvidenceValues, testResultStatusValues } from "../constants.ts";
import { boolValue, findStructuredItem, listValue, loadEnv, loadStructuredItems, scalar } from "../fs.ts";
import { splitEnvAnyGroup } from "../env-groups.ts";
import {
  readAutomationResultEvidence,
  renderLogFinding,
  renderLogSuccessSignal,
  scanStructuredLogSources,
  type AutomationResultEvidence,
  type LogFinding,
  type LogGuardResult,
  type LogSuccessSignal,
} from "../log-guard.ts";
import {
  automationEnvDefaults,
  caseAutomationReadiness,
  caseEnvReadiness,
  caseFixtureReadiness,
  caseManualReadiness,
  redactEnvValue,
  resolvedAutomationEnvOverrides,
  runtimeEnv,
  type AutomationReadiness,
  type EnvReadiness,
  type FixtureReadiness,
  type ManualReadiness,
} from "../readiness.ts";
import {
  lbsScriptPath,
  parseSetupAutomationEntry,
  setupAutomationEntries,
  setupAutomationEvidenceName,
  setupAutomationScriptPath,
} from "../setup-automation.ts";

type TroubleshootingSummary = {
  id: string;
  title: string;
  patterns: string[];
  verification: string;
};

type TestPlan = {
  id: string;
  title: string;
  mode: string;
  principle: string;
  env: Record<string, string>;
  env_readiness: EnvReadiness;
  automation_readiness: AutomationReadiness;
  fixture_readiness: FixtureReadiness;
  manual_readiness: ManualReadiness;
  required_skills: string[];
  preconditions: string[];
  setup: string[];
  setup_automation: string[];
  setup_provides_env: string[];
  cleanup: string[];
  steps: string[];
  checks: string[];
  diagnostics: string[];
  visual_checks: string[];
  evidence_required: string[];
  success_patterns: string[];
  failure_patterns: string[];
  troubleshooting: TroubleshootingSummary[];
  report_template: Record<string, string>;
};

type TestStart = {
  run_id: string;
  started_at: string;
  started_at_local: string;
  case: Record<string, string | boolean | string[]>;
  environment: Record<string, string>;
  required_skills: string[];
  preconditions: string[];
  setup: string[];
  setup_automation: string[];
  setup_provides_env: string[];
  cleanup: string[];
  steps: string[];
  checks: string[];
  success_patterns: string[];
  failure_patterns: string[];
  evidence_required: string[];
  automation?: {
    script: string;
    command: string;
    evidence_dir: string;
  };
  recommended_report_path: string;
  plan_command: string;
  report_command: string;
  result_command_template: string;
  evidence_checklist: string[];
};

type TestAutomationRun = {
  run_id: string;
  started_at: string;
  started_at_local: string;
  case: Record<string, string | boolean | string[]>;
  setup_automation: SetupAutomation[];
  automation: {
    script: string;
    script_path: string;
    exists: boolean;
    required_env: string[];
    evidence_dir: string;
    console_log: string;
    network_log: string;
    screenshot: string;
    automation_result_json: string;
    result_json: string;
    command: string;
    report_command: string;
    env_defaults: Record<string, string>;
    env_aliases: Array<{
      target: string;
      source: string;
      configured: boolean;
    }>;
    pipeline_env_required: boolean;
  };
};

type SetupAutomation = {
  entry: string;
  kind: "case" | "node";
  target: string;
  args: string[];
  command: string;
  dry_run_command: string;
  evidence_dir: string;
  exists: boolean;
};

type TestResultRecord = {
  source: "final";
  case_id: string;
  run_id: string;
  written_at: string;
  written_at_local: string;
  started_at: string;
  started_at_local: string;
  finished_at: string;
  finished_at_local: string;
  status: string;
  reason: string;
  url: string;
  browser_path: string;
  evidence_dir: string;
  evidence_collected: string[];
  evidence_required: string[];
  evidence_missing: string[];
  evidence_status: "complete" | "incomplete";
  report_path: string;
  notes: string;
};

type ManualEvidenceTemplate = {
  result: string;
  [key: string]: string;
};

type TestReport = {
  generated_at: string;
  case: Record<string, string | boolean | string[]>;
  result_options: string[];
  automation_result: AutomationResultEvidence;
  manual_evidence: ManualEvidenceTemplate;
  environment: Record<string, string>;
  required_skills: string[];
  steps: string[];
  checks: string[];
  diagnostics: string[];
  evidence_required: string[];
  success_patterns: string[];
  failure_patterns: string[];
  expected_failures: string[];
  troubleshooting: TroubleshootingSummary[];
  log_guard: LogGuardResult;
};

type TestRecommendation = {
  id: string;
  reason: string;
};

type TestRecommendReport = {
  generated_at: string;
  changed_files: string[];
  recommendations: TestRecommendation[];
  commands: string[];
  notes: string[];
};

function relatedTroubleshooting(root: string, item: StructuredItem): StructuredItem[] {
  return listValue(item.fields, "troubleshooting")
    .map((id) => {
      try {
        return findStructuredItem(root, "troubleshooting", id);
      } catch {
        return null;
      }
    })
    .filter((entry): entry is StructuredItem => entry !== null);
}

function findCase(root: string, args: string[]): StructuredItem {
  if (args.length < 1 || args.length > 2) usage();

  return args.length === 1
    ? findStructuredItem(root, "cases", args[0])
    : findStructuredItem(root, "cases", args[0], args[1]);
}

function caseSummary(item: StructuredItem): Record<string, string | boolean | string[]> {
  return {
    skill: item.skill,
    id: scalar(item.fields, "id"),
    title: scalar(item.fields, "title"),
    mode: scalar(item.fields, "mode"),
    area: scalar(item.fields, "area"),
    type: scalar(item.fields, "type"),
    priority: scalar(item.fields, "priority"),
    risk: scalar(item.fields, "risk"),
    ci_eligible: boolValue(item.fields, "ci_eligible") ?? false,
    tags: listValue(item.fields, "tags"),
  };
}

function caseMode(item: StructuredItem): string {
  return scalar(item.fields, "mode") || "agent-browser";
}

function isProbeMode(mode: string): boolean {
  return mode === "probe";
}

function modePrinciple(mode: string): string {
  return isProbeMode(mode)
    ? "Run the declared probe steps and collect the required evidence. Browser/UI interaction is not required unless the case steps explicitly call for it."
    : "Use browser/UI interaction as the primary QA path. API/curl/log checks are diagnostic only and cannot make a UI case pass by themselves.";
}

function stepHeading(mode: string): string {
  return isProbeMode(mode) ? "Probe Steps" : "Browser Steps";
}

function visualChecks(mode: string): string[] {
  if (isProbeMode(mode)) return [];
  return [
    "If the active agent has screenshot/vision capability, capture before/after screenshots.",
    "Look for blank pages, overlapping text, hidden primary actions, error toasts, or broken layout.",
    "If no visual model is available, use DOM/accessibility snapshots and console output instead.",
  ];
}

function reportTemplate(mode: string): Record<string, string> {
  if (isProbeMode(mode)) {
    return {
      result: "pass | fail | blocked | env_issue | flaky",
      target_tested: "Probe target, endpoint, file, command, or service actually checked",
      execution_path: "automation script | shell command | direct API | other",
      probe_result: "What the probe observed",
      logs_or_artifacts: "Log, filesystem, API, or other artifact paths collected",
      diagnostics: "Extra diagnostics used, if any",
      matched_troubleshooting: "Troubleshooting ids matched, if any",
      assets_to_update: "New case/reference/troubleshooting entries to add",
    };
  }

  return {
    result: "pass | fail | blocked | env_issue | flaky",
    url_tested: "LANGBOT_FRONTEND_URL actually opened",
    browser_path: "Computer Use | Playwright MCP | other",
    ui_result: "What the user-visible UI showed",
    console_errors: "Unexpected browser console errors, if any",
    backend_logs: "Relevant backend log lines, if checked",
    screenshots: "Screenshot paths or skipped reason",
    diagnostics: "API/curl/log diagnostics used, if any",
    matched_troubleshooting: "Troubleshooting ids matched, if any",
    assets_to_update: "New case/reference/troubleshooting entries to add",
  };
}

function evidenceChecklist(mode: string): string[] {
  if (isProbeMode(mode)) {
    return [
      "Execute the declared probe steps or automation script.",
      "Store required logs, API diagnostics, filesystem artifacts, or other evidence in the evidence directory.",
      "After execution, run the report command to scan logs from the start timestamp.",
      "Write a final result.json with the result command only after required evidence has been collected.",
      "Mark the final result as pass, fail, blocked, env_issue, or flaky in the generated report.",
    ];
  }

  return [
    "Open the configured LangBot WebUI and execute the browser steps.",
    "Capture screenshot paths when screenshot/vision tooling is available.",
    "Record unexpected console errors and failed network requests without pasting secrets.",
    "After browser execution, run the report command to scan logs from the start timestamp.",
    "Write a final result.json with the result command only after required evidence has been collected.",
    "Mark the final result as pass, fail, blocked, env_issue, or flaky in the generated report.",
  ];
}

function manualEvidenceTemplate(mode: string): ManualEvidenceTemplate {
  if (isProbeMode(mode)) {
    return {
      result: "pass | fail | blocked | env_issue | flaky",
      target_tested: "TODO: probe target, endpoint, file, command, or service actually checked",
      execution_path: "TODO: automation script | shell command | direct API | other",
      probe_result: "TODO: observed probe result",
      logs_or_artifacts: "TODO: evidence paths or skipped reason",
      diagnostics: "TODO: additional diagnostics used, if any",
      matched_troubleshooting: "TODO: troubleshooting ids matched, if any",
      assets_to_update: "TODO: case/reference/troubleshooting updates to make",
    };
  }

  return {
    result: "pass | fail | blocked | env_issue | flaky",
    url_tested: "LANGBOT_FRONTEND_URL actually opened",
    browser_path: "Computer Use | Playwright MCP | direct Playwright | other",
    ui_result: "TODO: user-visible result",
    console_errors: "TODO: unexpected browser console errors or none",
    network_symptoms: "TODO: failed requests, websocket issues, or none",
    backend_logs: "TODO: relevant backend log lines or skipped reason",
    frontend_logs: "TODO: relevant frontend dev-server log lines or skipped reason",
    screenshots: "TODO: screenshot paths or skipped reason",
    diagnostics: "TODO: API/curl/log diagnostics used, if any",
    matched_troubleshooting: "TODO: troubleshooting ids matched, if any",
    assets_to_update: "TODO: case/reference/troubleshooting updates to make",
  };
}

function envSummary(item: StructuredItem, env: Record<string, string>): Record<string, string> {
  const keys = [
    ...listValue(item.fields, "env"),
    ...listValue(item.fields, "env_any").flatMap(splitEnvAnyGroup),
  ];
  return Object.fromEntries(Array.from(new Set(keys)).map((key) => [key, redactEnvValue(key, env[key] ?? "")]));
}

function buildPlan(root: string, item: StructuredItem): TestPlan {
  const env = runtimeEnv(root);
  const troubles = relatedTroubleshooting(root, item);
  const id = scalar(item.fields, "id");
  const mode = caseMode(item);
  return {
    id,
    title: scalar(item.fields, "title"),
    mode,
    principle: modePrinciple(mode),
    env: envSummary(item, env),
    env_readiness: caseEnvReadiness(item, env),
    automation_readiness: caseAutomationReadiness(item, env),
    fixture_readiness: caseFixtureReadiness(root, id),
    manual_readiness: caseManualReadiness(item),
    required_skills: listValue(item.fields, "skills"),
    preconditions: listValue(item.fields, "preconditions"),
    setup: listValue(item.fields, "setup"),
    setup_automation: setupAutomationEntries(item),
    setup_provides_env: listValue(item.fields, "setup_provides_env"),
    cleanup: listValue(item.fields, "cleanup"),
    steps: listValue(item.fields, "steps"),
    checks: listValue(item.fields, "checks"),
    diagnostics: listValue(item.fields, "diagnostics"),
    visual_checks: visualChecks(mode),
    evidence_required: listValue(item.fields, "evidence_required"),
    success_patterns: listValue(item.fields, "success_patterns"),
    failure_patterns: listValue(item.fields, "failure_patterns"),
    troubleshooting: troubles.map((entry) => ({
      id: scalar(entry.fields, "id"),
      title: scalar(entry.fields, "title"),
      patterns: listValue(entry.fields, "patterns"),
      verification: scalar(entry.fields, "verification"),
    })),
    report_template: reportTemplate(mode),
  };
}

export function commandTestPlan(ctx: CommandContext): number {
  const { positional: args, options } = parseOptions(ctx.args.slice(2));
  const item = findCase(ctx.root, args);
  const plan = buildPlan(ctx.root, item);

  if (options.json === true) {
    console.log(JSON.stringify(plan, null, 2));
    return 0;
  }

  console.log(`# Test Plan: ${plan.id}`);
  console.log("");
  console.log(`Title: ${plan.title}`);
  console.log(`Mode: ${plan.mode}`);
  console.log("");
  console.log("## Principle");
  console.log(plan.principle);
  console.log("");
  console.log("## Environment");
  for (const [key, value] of Object.entries(plan.env)) console.log(`- ${key}=${value}`);
  if (plan.env_readiness.missing.length > 0) console.log(`- missing: ${plan.env_readiness.missing.join(", ")}`);
  console.log("");
  console.log("## Automation Readiness");
  console.log(`- status: ${plan.automation_readiness.status}`);
  if (plan.automation_readiness.script) console.log(`- script: ${plan.automation_readiness.script}`);
  if (plan.automation_readiness.pipeline_env_required) console.log("- pipeline env: case-specific required");
  if (plan.automation_readiness.missing.length > 0) console.log(`- missing: ${plan.automation_readiness.missing.join(", ")}`);
  if (plan.automation_readiness.defaulted.length > 0) console.log(`- case defaults: ${plan.automation_readiness.defaulted.join(", ")}`);
  for (const alias of plan.automation_readiness.env_aliases) {
    console.log(`- alias: ${alias.target} <- ${alias.source} (${alias.configured ? "configured" : "missing"})`);
  }
  console.log("");
  console.log("## Fixture Readiness");
  console.log(`- status: ${plan.fixture_readiness.status}`);
  for (const fixture of plan.fixture_readiness.required) {
    console.log(`- ${fixture.id}: ${fixture.exists ? "present" : "missing"} (${fixture.path})`);
  }
  console.log("");
  console.log("## Manual Readiness");
  console.log(`- status: ${plan.manual_readiness.status}`);
  if (plan.preconditions.length === 0) console.log("- preconditions: none declared");
  for (const precondition of plan.preconditions) console.log(`- precondition: ${precondition}`);
  if (plan.setup.length > 0) for (const item of plan.setup) console.log(`- setup: ${item}`);
  if (plan.setup_automation.length > 0) {
    for (const item of plan.setup_automation) console.log(`- setup automation: ${item}`);
  }
  if (plan.setup_provides_env.length > 0) console.log(`- setup provides env: ${plan.setup_provides_env.join(", ")}`);
  if (plan.cleanup.length > 0) for (const item of plan.cleanup) console.log(`- cleanup: ${item}`);
  console.log("");
  console.log("## Required Skills");
  for (const skill of plan.required_skills) console.log(`- ${skill}`);
  console.log("");
  console.log(`## ${stepHeading(plan.mode)}`);
  for (const [index, step] of plan.steps.entries()) console.log(`${index + 1}. ${step}`);
  console.log("");
  console.log("## Checks");
  for (const check of plan.checks) console.log(`- ${check}`);
  console.log("");
  console.log("## Diagnostics");
  if (plan.diagnostics.length === 0) console.log("- Optional: use API/curl/logs only to diagnose failures.");
  for (const diagnostic of plan.diagnostics) console.log(`- ${diagnostic}`);
  console.log("");
  if (plan.visual_checks.length > 0) {
    console.log("## Visual Checks");
    for (const check of plan.visual_checks) console.log(`- ${check}`);
    console.log("");
  }
  console.log("## Required Evidence");
  if (plan.evidence_required.length === 0) console.log("- None declared.");
  for (const evidence of plan.evidence_required) console.log(`- ${evidence}`);
  console.log("");
  console.log("## Success Signals");
  if (plan.success_patterns.length === 0) console.log("- None declared.");
  for (const pattern of plan.success_patterns) console.log(`- ${pattern}`);
  console.log("");
  console.log("## Failure Signals");
  if (plan.failure_patterns.length === 0) console.log("- None declared.");
  for (const pattern of plan.failure_patterns) console.log(`- ${pattern}`);
  console.log("");
  console.log("## Troubleshooting");
  for (const entry of plan.troubleshooting) {
    console.log(`- ${entry.id}: ${entry.title}`);
    for (const pattern of entry.patterns) console.log(`  pattern: ${pattern}`);
  }
  console.log("");
  console.log("## Report Template");
  for (const [key, value] of Object.entries(plan.report_template)) console.log(`- ${key}: ${value}`);
  return 0;
}

function normalizeChangedPath(path: string): string {
  return path.replace(/\\/g, "/").replace(/^\.\//, "");
}

function isChangedFilePath(path: string): boolean {
  return Boolean(path) && !path.endsWith("/") && !path.startsWith("--- ") && !path.startsWith("+++ ");
}

function existingCaseIds(root: string): Set<string> {
  return new Set(loadStructuredItems(root, "cases").map((item) => scalar(item.fields, "id")));
}

function addRecommendation(
  output: TestRecommendation[],
  existing: Set<string>,
  id: string,
  reason: string,
): void {
  if (!existing.has(id) || output.some((item) => item.id === id)) return;
  output.push({ id, reason });
}

function changedFilesFromGit(repo: string, prefix: string): string[] {
  if (!existsSync(repo)) return [];
  const argsList = [
    ["diff", "--name-only", "HEAD"],
    ["status", "--short"],
  ];
  const files: string[] = [];
  for (const args of argsList) {
    const result = spawnSync("git", args, {
      cwd: repo,
      encoding: "utf8",
    });
    if (result.status !== 0) continue;
    for (const raw of result.stdout.split(/\r?\n/)) {
      if (!raw.trim()) continue;
      const file = args[0] === "status"
        ? raw.slice(3).trim().split(/\s+->\s+/).pop() ?? ""
        : raw.trim();
      if (isChangedFilePath(file)) files.push(`${prefix}/${normalizeChangedPath(file)}`);
    }
  }
  return files;
}

function repoCandidates(root: string, env: Record<string, string>): Array<{ path: string; prefix: string }> {
  return [
    { path: env.LANGBOT_REPO || resolve(root, "../LangBot"), prefix: "LangBot" },
    { path: env.LANGBOT_PLUGIN_SDK_REPO || resolve(root, "../langbot-plugin-sdk"), prefix: "langbot-plugin-sdk" },
    { path: env.LANGBOT_AGENT_RUNNER_REPO || resolve(root, "../langbot-agent-runner"), prefix: "langbot-agent-runner" },
    { path: env.LANGBOT_LOCAL_AGENT_REPO || resolve(root, "../langbot-local-agent"), prefix: "langbot-local-agent" },
  ];
}

function repeatedOptionValues(args: string[], key: string): string[] {
  const values: string[] = [];
  for (let i = 0; i < args.length; i += 1) {
    if (args[i] !== `--${key}`) continue;
    const value = args[i + 1];
    if (value && !value.startsWith("--")) values.push(value);
  }
  return values;
}

function changedFiles(root: string, explicitFiles: string[]): string[] {
  const explicit = explicitFiles.map(normalizeChangedPath);
  if (explicit.length > 0) return Array.from(new Set(explicit));

  const env = runtimeEnv(root);
  const files = repoCandidates(root, env).flatMap((repo) => changedFilesFromGit(repo.path, repo.prefix));
  return Array.from(new Set(files)).sort();
}

function buildRecommendations(root: string, files: string[]): TestRecommendation[] {
  const existing = existingCaseIds(root);
  const recommendations: TestRecommendation[] = [];
  const text = files.map(normalizeChangedPath);
  const has = (pattern: RegExp) => text.some((file) => pattern.test(file));

  if (has(/(^|\/)(result_normalizer|orchestrator|descriptor|errors)\.py$/) || has(/agent_runner\/result\.py$/)) {
    addRecommendation(recommendations, existing, "agent-runner-fixture-contract", "Deterministic AgentRunner fixture contract should still execute.");
    addRecommendation(recommendations, existing, "agent-runner-behavior-matrix", "AgentRunner result/orchestration contract changed.");
  }
  if (has(/fixtures\/plugins\/qa-agent-runner|components\/agent_runner|manifest\.ya?ml$/)) {
    addRecommendation(recommendations, existing, "agent-runner-fixture-contract", "AgentRunner fixture or runner manifest changed.");
    addRecommendation(recommendations, existing, "agent-runner-live-install", "AgentRunner plugin package should still install and register.");
    addRecommendation(recommendations, existing, "agent-runner-qa-debug-chat", "Installed QA AgentRunner should still execute through Debug Chat.");
  }
  if (has(/fixtures\/plugins\/qa-plugin-smoke|qa_plugin_|qa-plugin-smoke/i)) {
    addRecommendation(recommendations, existing, "qa-plugin-smoke-live-install", "QA plugin smoke fixture should install and expose tools.");
  }
  if (has(/(run_ledger|agent_run\.py|run_ledger\.py|alembic.*agent_run|test_run_ledger)/i)) {
    addRecommendation(recommendations, existing, "agent-runner-ledger-invariants", "Run ledger schema/status code changed.");
    addRecommendation(recommendations, existing, "agent-runner-ledger-stress", "Run ledger queue/claim behavior changed.");
    addRecommendation(recommendations, existing, "agent-runner-ledger-contention", "Run ledger claim behavior changed; check local write contention.");
    addRecommendation(recommendations, existing, "agent-runner-async-db-readiness", "Async DB readiness gates ledger concurrency probes.");
    addRecommendation(recommendations, existing, "agent-runner-ledger-concurrency", "Run ledger concurrency/auth tests are relevant.");
  }
  if (has(/(plugin\/handler|agent_run_api|history_event_api|state_api|pull_api|runtime\/plugin|test_mgr_agent_runner|test_pull_api_handlers)/)) {
    addRecommendation(recommendations, existing, "agent-runner-runtime-chaos", "SDK/runtime or Host action handling changed.");
  }
  if (has(/(LangBot\/web\/|^web\/|control-plane|frontend|\/page|\/pages)/)) {
    addRecommendation(recommendations, existing, "agent-runner-release-preflight", "UI/control-plane surface changed; preflight catches wrong live target.");
    addRecommendation(recommendations, existing, "webui-login-state", "Browser session must still reach LangBot WebUI.");
  }
  if (has(/(local-agent|context|compaction|rag|tool|mcp|multimodal)/i)) {
    addRecommendation(recommendations, existing, "qa-plugin-smoke-live-install", "Tool-loop checks depend on the QA plugin smoke fixture.");
    addRecommendation(recommendations, existing, "local-agent-basic-debug-chat", "Local-agent user path may be affected.");
    addRecommendation(recommendations, existing, "local-agent-plugin-tool-call-debug-chat", "Tool-loop changes need browser evidence.");
  }
  if (has(/(^|\/)(acp|claude|codex)(\/|-)|langbot-agent-runner\//i)) {
    addRecommendation(recommendations, existing, "acp-agent-runner-debug-chat", "External AgentRunner path may be affected.");
  }
  if (recommendations.length === 0) {
    addRecommendation(recommendations, existing, "agent-runner-release-preflight", "No narrow AgentRunner rule matched; start with preflight if this branch touches runner behavior.");
  }
  return recommendations;
}

function buildRecommendReport(root: string, explicitFiles: string[]): TestRecommendReport {
  const files = changedFiles(root, explicitFiles);
  const recommendations = buildRecommendations(root, files);
  return {
    generated_at: new Date().toISOString(),
    changed_files: files,
    recommendations,
    commands: recommendations.flatMap((item) => [
      `bin/lbs test plan ${item.id}`,
      `bin/lbs test run ${item.id} --dry-run`,
    ]),
    notes: [
      "Run probe cases before browser cases.",
      "Remove --dry-run only after readiness and manual_check preconditions are confirmed.",
      "Treat blocked/env_issue separately from product fail.",
      "Browser cases still need required UI evidence before pass.",
    ],
  };
}

function renderRecommendReport(report: TestRecommendReport): string {
  const lines: string[] = [];
  lines.push("# Test Recommendations");
  lines.push("");
  lines.push(`Generated: ${report.generated_at}`);
  lines.push("");
  lines.push("## Changed Files");
  if (report.changed_files.length === 0) lines.push("- None detected. Pass --file <path> to recommend from explicit paths.");
  else for (const file of report.changed_files) lines.push(`- ${file}`);
  lines.push("");
  lines.push("## Recommended Cases");
  if (report.recommendations.length === 0) lines.push("- None.");
  for (const item of report.recommendations) {
    lines.push(`- ${item.id}: ${item.reason}`);
  }
  lines.push("");
  lines.push("## Commands");
  for (const command of report.commands) lines.push(`- ${command}`);
  lines.push("");
  lines.push("## Notes");
  for (const note of report.notes) lines.push(`- ${note}`);
  return `${lines.join("\n").trimEnd()}\n`;
}

export function commandTestRecommend(ctx: CommandContext): number {
  const { options } = parseOptions(ctx.args.slice(2));
  const report = buildRecommendReport(ctx.root, repeatedOptionValues(ctx.args.slice(2), "file"));
  if (options.json === true) console.log(JSON.stringify(report, null, 2));
  else console.log(renderRecommendReport(report).trimEnd());
  return 0;
}

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

function caseLocator(args: string[]): string {
  return args.join(" ");
}

function automationScript(item: StructuredItem): string {
  return scalar(item.fields, "automation");
}

function setupCaseExists(root: string, target: string): boolean {
  return loadStructuredItems(root, "cases").some((item) => scalar(item.fields, "id") === target);
}

function setupAutomation(root: string, item: StructuredItem, runId: string, evidenceRoot: string): SetupAutomation[] {
  return setupAutomationEntries(item).map((entry, index) => {
    const spec = parseSetupAutomationEntry(entry);
    const evidenceDir = join("setup", setupAutomationEvidenceName(index, spec));
    const fullEvidenceDir = join(evidenceRoot, evidenceDir);
    const command = spec.kind === "case"
      ? `bin/lbs test run ${spec.target} --run-id ${runId}-${spec.target} --output ${fullEvidenceDir}`
      : `node ${spec.target}${spec.args.length > 0 ? ` ${spec.args.join(" ")}` : ""}`;
    const dryRunCommand = spec.kind === "case" ? `${command} --dry-run` : "";
    return {
      entry,
      kind: spec.kind,
      target: spec.target,
      args: spec.args,
      command,
      dry_run_command: dryRunCommand,
      evidence_dir: fullEvidenceDir,
      exists: spec.kind === "case" ? setupCaseExists(root, spec.target) : existsSync(setupAutomationScriptPath(root, spec)),
    };
  });
}

function isoFromDateInput(input: string): string {
  const parsed = Date.parse(input);
  return Number.isNaN(parsed) ? "" : new Date(parsed).toISOString();
}

function commaList(value: string | undefined): string[] {
  if (!value) return [];
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildTestResult(
  root: string,
  item: StructuredItem,
  options: Record<string, string | boolean>,
): { result?: TestResultRecord; errors: string[] } {
  const errors: string[] = [];
  const status = typeof options.result === "string" ? options.result : "";
  const reason = typeof options.reason === "string" ? options.reason : "";
  const evidenceDir = typeof options["evidence-dir"] === "string" ? options["evidence-dir"] : "";
  const now = new Date();
  const writtenAtLocal = localIsoWithOffset(now);
  const startedAtLocal = typeof options["started-at"] === "string" ? options["started-at"] : writtenAtLocal;
  const finishedAtLocal = typeof options["finished-at"] === "string" ? options["finished-at"] : writtenAtLocal;
  const startedAt = isoFromDateInput(startedAtLocal);
  const finishedAt = isoFromDateInput(finishedAtLocal);
  const evidenceCollected = commaList(typeof options.evidence === "string" ? options.evidence : undefined);
  const evidenceRequired = listValue(item.fields, "evidence_required");
  const evidenceMissing = evidenceRequired.filter((value) => !evidenceCollected.includes(value));

  if (!status) errors.push("--result is required");
  else if (!testResultStatusValues.includes(status)) {
    errors.push(`--result must be one of ${testResultStatusValues.join(", ")}`);
  }
  if (!reason) errors.push("--reason is required");
  if (!evidenceDir) errors.push("--evidence-dir is required");
  if (!startedAt) errors.push(`--started-at is not a valid date/time: ${startedAtLocal}`);
  if (!finishedAt) errors.push(`--finished-at is not a valid date/time: ${finishedAtLocal}`);

  const allowedEvidence = new Set(caseEvidenceValues);
  for (const value of evidenceCollected) {
    if (!allowedEvidence.has(value)) errors.push(`--evidence contains unsupported value '${value}'`);
  }
  if (status === "pass" && evidenceMissing.length > 0) {
    errors.push(`pass result is missing required evidence: ${evidenceMissing.join(", ")}`);
  }

  if (errors.length > 0) return { errors };

  const resolvedEvidenceDir = resolve(evidenceDir);
  return {
    errors,
    result: {
      source: "final",
      case_id: scalar(item.fields, "id"),
      run_id: typeof options["run-id"] === "string" ? options["run-id"] : resolvedEvidenceDir.split(/[\\/]/).pop() ?? "",
      written_at: now.toISOString(),
      written_at_local: writtenAtLocal,
      started_at: startedAt,
      started_at_local: startedAtLocal,
      finished_at: finishedAt,
      finished_at_local: finishedAtLocal,
      status,
      reason,
      url: typeof options.url === "string" ? options.url : "",
      browser_path: typeof options["browser-path"] === "string" ? options["browser-path"] : "",
      evidence_dir: evidenceDir,
      evidence_collected: evidenceCollected,
      evidence_required: evidenceRequired,
      evidence_missing: evidenceMissing,
      evidence_status: evidenceMissing.length === 0 ? "complete" : "incomplete",
      report_path: typeof options.report === "string" ? options.report : "",
      notes: typeof options.notes === "string" ? options.notes : "",
    },
  };
}

function renderTestResult(result: TestResultRecord): string {
  const lines: string[] = [];
  lines.push(`# Test Result: ${result.case_id}`);
  lines.push("");
  lines.push(`Run: ${result.run_id}`);
  lines.push(`Status: ${result.status}`);
  lines.push(`Reason: ${result.reason}`);
  lines.push(`Evidence dir: ${result.evidence_dir}`);
  lines.push(`Evidence status: ${result.evidence_status}`);
  if (result.evidence_missing.length > 0) lines.push(`Evidence missing: ${result.evidence_missing.join(", ")}`);
  if (result.url) lines.push(`URL: ${result.url}`);
  if (result.browser_path) lines.push(`Browser path: ${result.browser_path}`);
  if (result.report_path) lines.push(`Report: ${result.report_path}`);
  lines.push("");
  lines.push("## Evidence Collected");
  if (result.evidence_collected.length === 0) lines.push("- None declared.");
  else for (const value of result.evidence_collected) lines.push(`- ${value}`);
  return `${lines.join("\n").trimEnd()}\n`;
}

function buildStart(root: string, item: StructuredItem, args: string[]): TestStart {
  const now = new Date();
  const startedAtLocal = localIsoWithOffset(now);
  const id = scalar(item.fields, "id");
  const mode = caseMode(item);
  const runId = `${timestampSlug(startedAtLocal)}-${id}`;
  const recommendedReportPath = join("reports", `${runId}.md`);
  const evidenceDir = join("reports", "evidence", runId);
  const locator = caseLocator(args);
  const script = automationScript(item);
  const automationCommand = script
    ? `bin/lbs test run ${locator} --run-id ${runId} --output ${evidenceDir}`
    : undefined;
  const consoleLog = join(evidenceDir, "console.log");
  const reportCommand = script
    ? `bin/lbs test report ${locator} --since "${startedAtLocal}" --console-log ${consoleLog} --evidence-dir ${evidenceDir} --output ${recommendedReportPath}`
    : `bin/lbs test report ${locator} --since "${startedAtLocal}" --evidence-dir ${evidenceDir} --output ${recommendedReportPath}`;
  const resultCommandTemplate = `bin/lbs test result ${locator} --result <status> --reason "<short reason>" --evidence-dir ${evidenceDir} --started-at "${startedAtLocal}" --evidence ${listValue(item.fields, "evidence_required").join(",")}`;

  return {
    run_id: runId,
    started_at: now.toISOString(),
    started_at_local: startedAtLocal,
    case: caseSummary(item),
    environment: envSummary(item, { ...loadEnv(root), ...processEnv }),
    required_skills: listValue(item.fields, "skills"),
    preconditions: listValue(item.fields, "preconditions"),
    setup: listValue(item.fields, "setup"),
    setup_automation: setupAutomationEntries(item),
    setup_provides_env: listValue(item.fields, "setup_provides_env"),
    cleanup: listValue(item.fields, "cleanup"),
    steps: listValue(item.fields, "steps"),
    checks: listValue(item.fields, "checks"),
    evidence_required: listValue(item.fields, "evidence_required"),
    success_patterns: listValue(item.fields, "success_patterns"),
    failure_patterns: listValue(item.fields, "failure_patterns"),
    automation: script
      ? {
        script,
        command: automationCommand ?? "",
        evidence_dir: evidenceDir,
      }
      : undefined,
    recommended_report_path: recommendedReportPath,
    plan_command: `bin/lbs test plan ${locator}`,
    report_command: reportCommand,
    result_command_template: resultCommandTemplate,
    evidence_checklist: evidenceChecklist(mode),
  };
}

function renderMarkdownStart(start: TestStart): string {
  const lines: string[] = [];
  const reportCase = start.case;

  lines.push(`# Test Start: ${reportCase.id}`);
  lines.push("");
  lines.push(`Run: ${start.run_id}`);
  lines.push(`Started: ${start.started_at_local}`);
  lines.push(`Title: ${reportCase.title}`);
  lines.push(`Skill: ${reportCase.skill}`);
  lines.push("");
  lines.push("## Commands");
  lines.push(`- plan: ${start.plan_command}`);
  if (start.automation) lines.push(`- automation: ${start.automation.command}`);
  lines.push(`- report: ${start.report_command}`);
  lines.push(`- result template: ${start.result_command_template}`);
  lines.push("");
  lines.push("## Evidence Checklist");
  for (const item of start.evidence_checklist) lines.push(`- ${item}`);
  lines.push("");
  lines.push(...renderLines("Required Evidence", start.evidence_required));
  lines.push("");
  lines.push(...renderLines("Preconditions", start.preconditions));
  lines.push(...renderLines("Setup", start.setup));
  lines.push(...renderLines("Setup Automation", start.setup_automation));
  lines.push(...renderLines("Setup Provides Env", start.setup_provides_env));
  lines.push(...renderLines("Cleanup", start.cleanup));
  lines.push(`## ${stepHeading(String(reportCase.mode || "agent-browser"))}`);
  for (const [index, step] of start.steps.entries()) lines.push(`${index + 1}. ${step}`);
  lines.push("");
  lines.push(...renderLines("Checks", start.checks));
  lines.push(...renderLines("Success Signals", start.success_patterns));
  lines.push(...renderLines("Failure Signals", start.failure_patterns));
  lines.push("## Environment");
  for (const [key, value] of Object.entries(start.environment)) lines.push(`- ${key}=${value}`);
  lines.push("");

  return `${lines.join("\n").trimEnd()}\n`;
}

export function commandTestStart(ctx: CommandContext): number {
  const { positional: args, options } = parseOptions(ctx.args.slice(2));
  const item = findCase(ctx.root, args);
  const start = buildStart(ctx.root, item, args);
  const output = typeof options.output === "string" ? options.output : undefined;
  const content = options.json === true ? `${JSON.stringify(start, null, 2)}\n` : renderMarkdownStart(start);

  writeOrPrint(content, output);
  return 0;
}

export function commandTestResult(ctx: CommandContext): number {
  const { positional: args, options } = parseOptions(ctx.args.slice(2));
  const item = findCase(ctx.root, args);
  const { result, errors } = buildTestResult(ctx.root, item, options);
  if (!result) {
    for (const error of errors) console.error(`ERROR: ${error}`);
    return 1;
  }

  const resultPath = join(result.evidence_dir, "result.json");
  mkdirSync(dirname(resultPath), { recursive: true });
  writeFileSync(resultPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");

  if (options.json === true) console.log(JSON.stringify(result, null, 2));
  else console.log(renderTestResult(result).trimEnd());
  return 0;
}

function buildAutomationRun(
  root: string,
  item: StructuredItem,
  args: string[],
  options: Record<string, string | boolean>,
): TestAutomationRun {
  const now = new Date();
  const startedAtLocal = localIsoWithOffset(now);
  const id = scalar(item.fields, "id");
  const sourceEnv = runtimeEnv(root);
  const runId = typeof options["run-id"] === "string" ? options["run-id"] : `${timestampSlug(startedAtLocal)}-${id}`;
  const script = automationScript(item);
  const scriptPath = script ? resolve(root, script) : "";
  const evidenceDir = typeof options.output === "string"
    ? options.output
    : join("reports", "evidence", runId);
  const locator = caseLocator(args);
  const consoleLog = join(evidenceDir, "console.log");
  const reportPath = join("reports", `${runId}.md`);
  const reportCommand = `bin/lbs test report ${locator} --since "${startedAtLocal}" --console-log ${consoleLog} --evidence-dir ${evidenceDir} --output ${reportPath}`;
  const runCommand = [
    "bin/lbs",
    "test",
    "run",
    locator,
    "--run-id",
    runId,
    "--output",
    evidenceDir,
  ].join(" ");

  return {
    run_id: runId,
    started_at: now.toISOString(),
    started_at_local: startedAtLocal,
    case: caseSummary(item),
    setup_automation: setupAutomation(root, item, runId, evidenceDir),
    automation: {
      script,
      script_path: scriptPath,
      exists: scriptPath ? existsSync(scriptPath) : false,
      required_env: [...listValue(item.fields, "automation_env"), ...listValue(item.fields, "automation_env_any")],
      evidence_dir: evidenceDir,
      console_log: consoleLog,
      network_log: join(evidenceDir, "network.log"),
      screenshot: join(evidenceDir, "screenshot.png"),
      automation_result_json: join(evidenceDir, "automation-result.json"),
      result_json: join(evidenceDir, "result.json"),
      command: runCommand,
      report_command: reportCommand,
      env_defaults: automationEnvDefaults(item, sourceEnv),
      env_aliases: caseAutomationReadiness(item, sourceEnv).env_aliases,
      pipeline_env_required: caseAutomationReadiness(item, sourceEnv).pipeline_env_required,
    },
  };
}

function renderAutomationRun(run: TestAutomationRun): string {
  const lines: string[] = [];
  lines.push(`# Test Automation: ${run.case.id}`);
  lines.push("");
  lines.push(`Run: ${run.run_id}`);
  lines.push(`Started: ${run.started_at_local}`);
  lines.push(`Script: ${run.automation.script || "None declared."}`);
  lines.push(`Script path: ${run.automation.script_path || "None declared."}`);
  lines.push(`Script exists: ${run.automation.exists ? "yes" : "no"}`);
  lines.push("");
  lines.push("## Setup Automation");
  if (run.setup_automation.length === 0) lines.push("- None declared.");
  for (const setup of run.setup_automation) {
    lines.push(`- ${setup.entry}`);
    lines.push(`  command: ${setup.command}`);
    if (setup.dry_run_command) lines.push(`  dry_run_command: ${setup.dry_run_command}`);
    lines.push(`  evidence_dir: ${setup.evidence_dir}`);
    lines.push(`  exists: ${setup.exists ? "yes" : "no"}`);
  }
  lines.push("");
  lines.push("## Commands");
  lines.push(`- run: ${run.automation.command}`);
  lines.push(`- report: ${run.automation.report_command}`);
  lines.push("");
  lines.push("## Evidence Files");
  lines.push(`- console_log: ${run.automation.console_log}`);
  lines.push(`- network_log: ${run.automation.network_log}`);
  lines.push(`- screenshot: ${run.automation.screenshot}`);
  lines.push(`- automation_result_json: ${run.automation.automation_result_json}`);
  lines.push(`- result_json: ${run.automation.result_json}`);
  lines.push("");
  lines.push(...renderLines("Required Env", run.automation.required_env));
  lines.push("## Automation Env Defaults");
  const defaults = Object.entries(run.automation.env_defaults);
  if (defaults.length === 0) lines.push("- None declared.");
  for (const [key, value] of defaults) lines.push(`- ${key}=${redactEnvValue(key, value)}`);
  lines.push("## Automation Env Aliases");
  if (run.automation.env_aliases.length === 0) lines.push("- None declared.");
  for (const alias of run.automation.env_aliases) {
    lines.push(`- ${alias.target} <- ${alias.source} (${alias.configured ? "configured" : "missing"})`);
  }
  if (run.automation.pipeline_env_required) lines.push("- Pipeline env is case-specific; global LANGBOT_PIPELINE_URL fallback is disabled.");
  return `${lines.join("\n").trimEnd()}\n`;
}

function automationEnv(
  root: string,
  item: StructuredItem,
  run: TestAutomationRun,
  evidenceDir: string,
  options: Record<string, string | boolean>,
): Record<string, string | undefined> {
  const baseEnv = runtimeEnv(root);
  const envDefaults = automationEnvDefaults(item, baseEnv);
  return {
    ...processEnv,
    ...envDefaults,
    ...baseEnv,
    ...resolvedAutomationEnvOverrides(item, baseEnv),
    ...Object.fromEntries(
      Object.keys(envDefaults)
        .filter((key) => baseEnv[key] !== undefined)
        .map((key) => [key, baseEnv[key]]),
    ),
    LBS_ROOT: root,
    LBS_CASE_ID: String(run.case.id),
    LBS_RUN_ID: run.run_id,
    LBS_STARTED_AT: run.started_at,
    LBS_STARTED_AT_LOCAL: run.started_at_local,
    LBS_EVIDENCE_DIR: resolve(evidenceDir),
    LBS_HEADED: options.headed === true ? "1" : processEnv.LBS_HEADED,
  };
}

function readSetupResult(setup: SetupAutomation): { status?: string; reason?: string } {
  try {
    return JSON.parse(readFileSync(join(setup.evidence_dir, "automation-result.json"), "utf8"));
  } catch {
    return {};
  }
}

function writeSetupFailureResult(run: TestAutomationRun, setup: SetupAutomation, exitStatus: number | null): void {
  const now = new Date();
  const setupResult = readSetupResult(setup);
  const status = setupResult.status && setupResult.status !== "pass"
    ? setupResult.status
    : exitStatus === 2 ? "env_issue" : "fail";
  const result = {
    source: "setup_automation",
    case_id: run.case.id,
    run_id: run.run_id,
    status,
    reason: setupResult.reason || `Setup automation failed: ${setup.entry}`,
    failed_setup: setup,
    exit_status: exitStatus,
    started_at: run.started_at,
    started_at_local: run.started_at_local,
    finished_at: now.toISOString(),
    finished_at_local: localIsoWithOffset(now),
    evidence_collected: ["api_diagnostic"],
  };
  writeFileSync(join(run.automation.evidence_dir, "automation-result.json"), `${JSON.stringify(result, null, 2)}\n`, "utf8");
  writeFileSync(join(run.automation.evidence_dir, "result.json"), `${JSON.stringify(result, null, 2)}\n`, "utf8");
}

function executionTail(value: string | Buffer | null | undefined): string {
  return String(value ?? "").trim().slice(-4000);
}

function runSetupAutomation(
  ctx: CommandContext,
  item: StructuredItem,
  run: TestAutomationRun,
  setup: SetupAutomation,
  options: Record<string, string | boolean>,
): { status: number; execution: Record<string, unknown> } {
  if (!setup.exists) {
    if (options.json !== true) console.error(`ERROR: setup automation target not found: ${setup.entry}`);
    writeSetupFailureResult(run, setup, 1);
    return {
      status: 1,
      execution: { entry: setup.entry, status: "nonzero", exit_status: 1, reason: "setup automation target not found" },
    };
  }
  mkdirSync(setup.evidence_dir, { recursive: true });
  if (options.json !== true) {
    console.log(`Setup: ${setup.entry}`);
    console.log(`Setup evidence: ${setup.evidence_dir}`);
  }
  const env = automationEnv(ctx.root, item, run, setup.evidence_dir, options);
  const args = setup.kind === "case"
    ? [
      lbsScriptPath(),
      "--root",
      ctx.root,
      "test",
      "run",
      setup.target,
      "--run-id",
      `${run.run_id}-${setup.target}`,
      "--output",
      setup.evidence_dir,
      ...(options.headed === true ? ["--headed"] : []),
    ]
    : [setupAutomationScriptPath(ctx.root, parseSetupAutomationEntry(setup.entry)), ...setup.args];
  const result = spawnSync(execPath, args, {
    cwd: ctx.root,
    env,
    encoding: "utf8",
    stdio: options.json === true ? "pipe" : "inherit",
  });
  if (result.error) {
    if (options.json !== true) console.error(`ERROR: failed to run setup automation: ${result.error.message}`);
    writeSetupFailureResult(run, setup, 1);
    return {
      status: 1,
      execution: {
        entry: setup.entry,
        status: "nonzero",
        exit_status: 1,
        reason: result.error.message,
        stdout: executionTail(result.stdout),
        stderr: executionTail(result.stderr),
      },
    };
  }
  const status = result.status ?? 1;
  if (status !== 0) writeSetupFailureResult(run, setup, status);
  return {
    status,
    execution: {
      entry: setup.entry,
      status: status === 0 ? "ok" : "nonzero",
      exit_status: status,
      stdout: executionTail(result.stdout),
      stderr: executionTail(result.stderr),
    },
  };
}

export function commandTestRun(ctx: CommandContext): number {
  const { positional: args, options } = parseOptions(ctx.args.slice(2));
  const item = findCase(ctx.root, args);
  const run = buildAutomationRun(ctx.root, item, args, options);
  const output = typeof options.plan_output === "string" ? options.plan_output : undefined;

  if (options["dry-run"] === true) {
    const content = options.json === true ? `${JSON.stringify(run, null, 2)}\n` : renderAutomationRun(run);
    writeOrPrint(content, output);
    return 0;
  }

  if (!run.automation.script) {
    console.error(`ERROR: case has no automation script: ${run.case.id}`);
    return 1;
  }
  if (!run.automation.exists) {
    console.error(`ERROR: automation script not found: ${run.automation.script_path}`);
    return 1;
  }

  mkdirSync(run.automation.evidence_dir, { recursive: true });
  if (options.json !== true) {
    console.log(`Run: ${run.run_id}`);
    console.log(`Evidence: ${run.automation.evidence_dir}`);
    console.log(`Report command: ${run.automation.report_command}`);
  }

  const setupExecutions: Array<Record<string, unknown>> = [];
  for (const setup of run.setup_automation) {
    const { status, execution } = runSetupAutomation(ctx, item, run, setup, options);
    setupExecutions.push(execution);
    if (status !== 0) {
      if (options.json === true) {
        console.log(JSON.stringify({
          run,
          setup_executions: setupExecutions,
          automation_execution: null,
          exit_status: status,
        }, null, 2));
      }
      return status;
    }
  }

  const env = automationEnv(ctx.root, item, run, run.automation.evidence_dir, options);
  const result = spawnSync(execPath, [run.automation.script_path], {
    cwd: ctx.root,
    env,
    encoding: "utf8",
    stdio: options.json === true ? "pipe" : "inherit",
  });

  if (result.error) {
    if (options.json !== true) console.error(`ERROR: failed to run automation: ${result.error.message}`);
    if (options.json === true) {
      console.log(JSON.stringify({
        run,
        setup_executions: setupExecutions,
        automation_execution: {
          status: "nonzero",
          exit_status: 1,
          reason: result.error.message,
          stdout: executionTail(result.stdout),
          stderr: executionTail(result.stderr),
        },
        exit_status: 1,
      }, null, 2));
    }
    return 1;
  }
  const status = result.status ?? 1;
  if (options.json === true) {
    console.log(JSON.stringify({
      run,
      setup_executions: setupExecutions,
      automation_execution: {
        status: status === 0 ? "ok" : "nonzero",
        exit_status: status,
        stdout: executionTail(result.stdout),
        stderr: executionTail(result.stderr),
      },
      exit_status: status,
    }, null, 2));
  }
  return status;
}


function buildReport(root: string, item: StructuredItem, options: Record<string, string | boolean>): TestReport {
  const env = loadEnv(root);
  const mode = caseMode(item);
  const related = relatedTroubleshooting(root, item).map((entry) => ({
    id: scalar(entry.fields, "id"),
    title: scalar(entry.fields, "title"),
    patterns: listValue(entry.fields, "patterns"),
    verification: scalar(entry.fields, "verification"),
  }));

  return {
    generated_at: new Date().toISOString(),
    case: caseSummary(item),
    result_options: ["pass", "fail", "blocked", "env_issue", "flaky"],
    automation_result: readAutomationResultEvidence(options),
    manual_evidence: manualEvidenceTemplate(mode),
    environment: envSummary(item, env),
    required_skills: listValue(item.fields, "skills"),
    steps: listValue(item.fields, "steps"),
    checks: listValue(item.fields, "checks"),
    diagnostics: listValue(item.fields, "diagnostics"),
    evidence_required: listValue(item.fields, "evidence_required"),
    success_patterns: listValue(item.fields, "success_patterns"),
    failure_patterns: listValue(item.fields, "failure_patterns"),
    expected_failures: listValue(item.fields, "expected_failures"),
    troubleshooting: related,
    log_guard: scanStructuredLogSources(root, item, options),
  };
}

function renderLines(title: string, values: string[]): string[] {
  const lines = [`## ${title}`];
  if (values.length === 0) lines.push("- None declared.");
  else for (const value of values) lines.push(`- ${value}`);
  lines.push("");
  return lines;
}

function renderFinding(finding: LogFinding): string {
  return renderLogFinding(finding);
}

function renderSuccessSignal(signal: LogSuccessSignal): string {
  return renderLogSuccessSignal(signal);
}

function renderMarkdownReport(report: TestReport): string {
  const reportCase = report.case;
  const evidence = report.manual_evidence;
  const environment = report.environment;
  const logGuard = report.log_guard;
  const troubleshooting = report.troubleshooting;
  const lines: string[] = [];

  lines.push(`# Test Report: ${reportCase.id}`);
  lines.push("");
  lines.push(`Generated: ${report.generated_at}`);
  lines.push(`Title: ${reportCase.title}`);
  lines.push(`Skill: ${reportCase.skill}`);
  lines.push(`Mode: ${reportCase.mode}`);
  lines.push(`Area: ${reportCase.area}`);
  lines.push(`Type: ${reportCase.type}`);
  lines.push("");
  lines.push("## Result");
  lines.push(`- result: ${evidence.result}`);
  for (const [key, value] of Object.entries(evidence)) {
    if (key !== "result") lines.push(`- ${key}: ${value}`);
  }
  lines.push("");
  lines.push("## Automation Result");
  lines.push(`- status: ${report.automation_result.status}`);
  if (report.automation_result.path) lines.push(`- path: ${report.automation_result.path}`);
  if (report.automation_result.result) lines.push(`- result: ${report.automation_result.result}`);
  if (report.automation_result.reason) lines.push(`- reason: ${report.automation_result.reason}`);
  if (report.automation_result.started_at_local) lines.push(`- started_at_local: ${report.automation_result.started_at_local}`);
  if (report.automation_result.finished_at_local) lines.push(`- finished_at_local: ${report.automation_result.finished_at_local}`);
  if (report.automation_result.url) lines.push(`- url: ${report.automation_result.url}`);
  if (report.automation_result.expected_text) lines.push(`- expected_text: ${report.automation_result.expected_text}`);
  lines.push("");
  lines.push("## Environment");
  for (const [key, value] of Object.entries(environment)) lines.push(`- ${key}=${value}`);
  lines.push("");
  lines.push(`## ${stepHeading(String(reportCase.mode || "agent-browser"))}`);
  for (const [index, step] of report.steps.entries()) lines.push(`${index + 1}. ${step}`);
  lines.push("");
  lines.push(...renderLines("Checks", report.checks));
  lines.push(...renderLines("Diagnostics", report.diagnostics));
  lines.push(...renderLines("Required Evidence", report.evidence_required));
  lines.push(...renderLines("Success Signals", report.success_patterns));
  lines.push(...renderLines("Failure Signals", report.failure_patterns));
  lines.push(...renderLines("Expected Failures", report.expected_failures));
  lines.push("## Log Guard");
  lines.push(`- status: ${logGuard.status}`);
  lines.push(`- scan_mode: ${logGuard.scan.mode}`);
  if (logGuard.scan.since) lines.push(`- since: ${logGuard.scan.since}`);
  if (logGuard.scan.until) lines.push(`- until: ${logGuard.scan.until}`);
  if (logGuard.scan.tail_lines !== undefined) lines.push(`- tail_lines: ${logGuard.scan.tail_lines}`);
  if (logGuard.scan.warnings.length > 0) {
    lines.push("- scan_warnings:");
    for (const warning of logGuard.scan.warnings) lines.push(`  - ${warning}`);
  }
  if (logGuard.sources.length === 0) {
    lines.push("- sources: no log files provided; run with --backend-log, --frontend-log, or --console-log to scan logs.");
  } else {
    lines.push("- sources:");
    for (const source of logGuard.sources) {
      const origin = source.auto_detected ? ", auto" : "";
      const total = source.total_line_count === undefined ? "" : `/${source.total_line_count}`;
      const range = source.start_line === undefined || source.end_line === undefined
        ? ""
        : `, lines ${source.start_line}-${source.end_line}`;
      const timestamped = source.timestamped_line_count === undefined ? "" : `, ${source.timestamped_line_count} timestamped`;
      lines.push(`  - ${source.source}: ${source.path} (${source.status}${origin}, ${source.line_count}${total} lines${range}${timestamped})`);
    }
  }
  lines.push("- findings:");
  if (logGuard.findings.length === 0) lines.push("  - None.");
  else for (const finding of logGuard.findings) lines.push(`  ${renderFinding(finding)}`);
  lines.push("- success_signals:");
  if (logGuard.success_signals.length === 0) lines.push("  - None.");
  else for (const signal of logGuard.success_signals) lines.push(`  ${renderSuccessSignal(signal)}`);
  lines.push("");
  lines.push("## Related Troubleshooting");
  if (troubleshooting.length === 0) lines.push("- None declared.");
  for (const entry of troubleshooting) {
    lines.push(`- ${entry.id}: ${entry.title}`);
    if (entry.patterns.length > 0) lines.push(`  patterns: ${entry.patterns.join(" | ")}`);
    if (entry.verification) lines.push(`  verification: ${entry.verification}`);
  }
  lines.push("");
  lines.push("## Decision Notes");
  if (isProbeMode(String(reportCase.mode))) {
    lines.push("- Probe results should be judged from the declared checks and required evidence for the same run.");
  } else {
    lines.push("- API/curl diagnostics can explain the run, but cannot make this UI case pass by themselves.");
  }
  lines.push("- Do not paste API keys, OAuth secrets, tokens, or localStorage token values into this report.");
  lines.push("");

  return `${lines.join("\n").trimEnd()}\n`;
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

export function commandTestReport(ctx: CommandContext): number {
  const { positional: args, options } = parseOptions(ctx.args.slice(2));
  const item = findCase(ctx.root, args);
  const report = buildReport(ctx.root, item, options);
  const output = typeof options.output === "string" ? options.output : undefined;
  const content = options.json === true ? `${JSON.stringify(report, null, 2)}\n` : renderMarkdownReport(report);

  writeOrPrint(content, output);
  return 0;
}
