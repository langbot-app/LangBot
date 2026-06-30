import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { execPath } from "node:process";
import type { CommandContext, StructuredItem } from "../types.ts";
import { fail, optionString, parseOptions, usage } from "../cli.ts";
import { findStructuredItem, getSkill, listValue, loadStructuredItems, scalar, yamlList, yamlQuote } from "../fs.ts";
import { caseAutomationReadiness, caseEnvReadiness, caseFixtureReadiness, caseManualReadiness, runtimeEnv } from "../readiness.ts";
import { lbsScriptPath, setupAutomationEntries } from "../setup-automation.ts";

function suitePath(root: string, skillName: string, id: string): string {
  const skill = getSkill(root, skillName);
  const dir = join(skill.path, "suites");
  mkdirSync(dir, { recursive: true });
  return join(dir, `${id}.yaml`);
}

function caseItemById(root: string, id: string): StructuredItem {
  return findStructuredItem(root, "cases", id);
}

function suiteCaseSummary(root: string, id: string): Record<string, unknown> {
  const item = caseItemById(root, id);
  const env = runtimeEnv(root);
  const caseId = scalar(item.fields, "id");
  return {
    skill: item.skill,
    id: caseId,
    title: scalar(item.fields, "title"),
    mode: scalar(item.fields, "mode"),
    area: scalar(item.fields, "area"),
    type: scalar(item.fields, "type"),
    priority: scalar(item.fields, "priority"),
    risk: scalar(item.fields, "risk"),
    tags: listValue(item.fields, "tags"),
    preconditions: listValue(item.fields, "preconditions"),
    setup: listValue(item.fields, "setup"),
    setup_automation: setupAutomationEntries(item),
    setup_provides_env: listValue(item.fields, "setup_provides_env"),
    automation: scalar(item.fields, "automation"),
    evidence_required: listValue(item.fields, "evidence_required"),
    env_readiness: caseEnvReadiness(item, env),
    automation_readiness: caseAutomationReadiness(item, env),
    fixture_readiness: caseFixtureReadiness(root, caseId),
    manual_readiness: caseManualReadiness(item),
  };
}

function suiteSummary(item: StructuredItem): Record<string, string | string[]> {
  return {
    skill: item.skill,
    id: scalar(item.fields, "id"),
    title: scalar(item.fields, "title"),
    description: scalar(item.fields, "description"),
    type: scalar(item.fields, "type"),
    priority: scalar(item.fields, "priority"),
    tags: listValue(item.fields, "tags"),
    cases: listValue(item.fields, "cases"),
  };
}

function findSuite(root: string, args: string[]): StructuredItem {
  if (args.length < 1 || args.length > 2) usage();
  return args.length === 1
    ? findStructuredItem(root, "suites", args[0])
    : findStructuredItem(root, "suites", args[0], args[1]);
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

function suiteCases(root: string, item: StructuredItem): Record<string, unknown>[] {
  return listValue(item.fields, "cases").map((id) => suiteCaseSummary(root, id));
}

function statusOf(caseItem: Record<string, unknown>, key: string): string {
  const value = caseItem[key] as Record<string, unknown> | undefined;
  return typeof value?.status === "string" ? value.status : "not_required";
}

function readinessSummary(cases: Array<Record<string, unknown>>): Record<string, unknown> {
  const missingEnv = cases.filter((item) => statusOf(item, "env_readiness") === "missing").map((item) => item.id);
  const missingAutomation = cases.filter((item) => statusOf(item, "automation_readiness") === "missing").map((item) => item.id);
  const missingFixture = cases.filter((item) => statusOf(item, "fixture_readiness") === "missing").map((item) => item.id);
  const manualCheck = cases.filter((item) => statusOf(item, "manual_readiness") === "manual_check").map((item) => item.id);
  const missingCount = missingEnv.length + missingAutomation.length + missingFixture.length;
  return {
    status: missingCount > 0 ? "missing" : manualCheck.length > 0 ? "manual_check" : "ready",
    missing_env_cases: missingEnv,
    missing_automation_env_cases: missingAutomation,
    missing_fixture_cases: missingFixture,
    manual_check_cases: manualCheck,
  };
}

function hasProbeCases(cases: Array<Record<string, unknown>>): boolean {
  return cases.some((caseItem) => caseItem.mode === "probe");
}

function suiteReportGuidance(cases: Array<Record<string, unknown>>): string {
  return hasProbeCases(cases)
    ? "Run each case according to its mode; probe cases may collect non-UI evidence, while agent-browser cases still require browser/UI execution."
    : "Run each case through browser/UI first; use test report with the evidence directory and backend log window after execution.";
}

function suiteResultPolicy(cases: Array<Record<string, unknown>>): string[] {
  if (hasProbeCases(cases)) {
    return [
      "A suite is not pass unless every case has a result and required evidence for the same run window.",
      "agent-browser cases require UI/browser results; probe cases are judged by their declared checks and required evidence.",
      "blocked and env_issue are not product pass; report them separately.",
    ];
  }

  return [
    "A suite is not pass unless every case has a UI/browser result and required evidence for the same run window.",
    "blocked and env_issue are not product pass; report them separately.",
  ];
}

function suiteEvidencePolicy(cases: Array<Record<string, unknown>>): string[] {
  if (hasProbeCases(cases)) {
    return [
      "Run each case according to its mode. Agent-browser cases use browser/UI; probe cases use their declared probe steps or automation.",
      "Use each case evidence_dir for screenshots, console.log, network.log, automation-result.json, result.json, and any probe artifacts.",
      "After case execution and report review, run each result_command_template with the final status and collected evidence.",
      "After per-case result.json files exist, run the suite report command to aggregate them.",
      "blocked and env_issue are not product pass; they must be reported separately from pass.",
    ];
  }

  return [
    "Run each case through browser/UI. API/curl/log diagnostics cannot make a UI case pass by themselves.",
    "Use each case evidence_dir for screenshots, console.log, network.log, automation-result.json, and final result.json.",
    "After case execution and report review, run each result_command_template with the final status and collected evidence.",
    "After per-case result.json files exist, run the suite report command to aggregate them.",
    "blocked and env_issue are not product pass; they must be reported separately from pass.",
  ];
}

function buildSuitePlan(root: string, item: StructuredItem): Record<string, unknown> {
  const suite = suiteSummary(item);
  const cases = suiteCases(root, item);
  return {
    ...suite,
    cases,
    readiness: readinessSummary(cases),
    commands: cases.map((caseItem) => ({
      id: caseItem.id,
      plan: `bin/lbs test plan ${caseItem.id}`,
      start: `bin/lbs test start ${caseItem.id}`,
      automation: caseItem.automation ? `bin/lbs test run ${caseItem.id} --dry-run` : "",
    })),
    report_guidance: suiteReportGuidance(cases),
  };
}

export function commandSuiteNew(ctx: CommandContext): number {
  const { positional, options } = parseOptions(ctx.args.slice(2));
  const id = positional[0];
  const title = optionString(options, "title");
  if (!id || !title) usage();

  const skill = optionString(options, "skill") ?? "langbot-testing";
  const path = suitePath(ctx.root, skill, id);
  if (existsSync(path)) fail(`suite already exists: ${path}`);

  const text =
    `id: ${id}\n` +
    `title: ${yamlQuote(title)}\n` +
    `description: ${yamlQuote(optionString(options, "description") ?? "Describe when to run this suite.")}\n` +
    `type: ${optionString(options, "type") ?? "smoke"}\n` +
    `priority: ${optionString(options, "priority") ?? "p2"}\n` +
    "tags:\n" +
    yamlList([optionString(options, "type") ?? "smoke"]) +
    "\ncases:\n" +
    yamlList(["webui-login-state"]) +
    "\n";

  writeFileSync(path, text, "utf8");
  console.log(path);
  return 0;
}

export function commandSuiteList(ctx: CommandContext): number {
  const { positional, options } = parseOptions(ctx.args.slice(2));
  const skill = positional[0];
  const rows = loadStructuredItems(ctx.root, "suites", skill)
    .map(suiteSummary)
    .filter((row) => !optionString(options, "type") || row.type === optionString(options, "type"))
    .filter((row) => !optionString(options, "priority") || row.priority === optionString(options, "priority"));

  if (options.json === true) {
    console.log(JSON.stringify(rows, null, 2));
    return 0;
  }

  for (const row of rows) {
    console.log([
      row.skill,
      row.id,
      row.type,
      row.priority,
      Array.isArray(row.cases) ? row.cases.length : 0,
      row.title,
    ].join("\t"));
  }
  return 0;
}

export function commandSuiteShow(ctx: CommandContext): number {
  const item = findSuite(ctx.root, ctx.args.slice(2));
  console.log(item.raw.trimEnd());
  return 0;
}

export function commandSuitePlan(ctx: CommandContext): number {
  const { positional: args, options } = parseOptions(ctx.args.slice(2));
  const item = findSuite(ctx.root, args);
  const plan = buildSuitePlan(ctx.root, item);
  const suite = suiteSummary(item);
  const cases = suiteCases(ctx.root, item);

  if (options.json === true) {
    console.log(JSON.stringify(plan, null, 2));
    return 0;
  }

  console.log(`# Suite Plan: ${suite.id}`);
  console.log("");
  console.log(`Title: ${suite.title}`);
  console.log(`Type: ${suite.type}`);
  console.log(`Priority: ${suite.priority}`);
  console.log(`Description: ${suite.description}`);
  console.log("");
  const readiness = readinessSummary(cases);
  console.log("## Readiness");
  console.log(`Status: ${readiness.status}`);
  for (const [key, value] of Object.entries(readiness)) {
    if (key === "status" || !Array.isArray(value) || value.length === 0) continue;
    console.log(`- ${key}: ${value.join(", ")}`);
  }
  console.log("");
  console.log("## Cases");
  for (const [index, caseItem] of cases.entries()) {
    console.log(`${index + 1}. ${caseItem.id} [${caseItem.priority}/${caseItem.risk}] ${caseItem.title}`);
    console.log(`   - plan: bin/lbs test plan ${caseItem.id}`);
    console.log(`   - start: bin/lbs test start ${caseItem.id}`);
    if (caseItem.automation) console.log(`   - automation dry-run: bin/lbs test run ${caseItem.id} --dry-run`);
    console.log(`   - evidence: ${Array.isArray(caseItem.evidence_required) ? caseItem.evidence_required.join(", ") : ""}`);
    const envReadiness = caseItem.env_readiness as Record<string, unknown>;
    const automationReadiness = caseItem.automation_readiness as Record<string, unknown>;
    const fixtureReadiness = caseItem.fixture_readiness as Record<string, unknown>;
    const manualReadiness = caseItem.manual_readiness as Record<string, unknown>;
    const missing: string[] = [];
    if (Array.isArray(envReadiness.missing) && envReadiness.missing.length > 0) missing.push(`env=${envReadiness.missing.join(",")}`);
    if (Array.isArray(automationReadiness.missing) && automationReadiness.missing.length > 0) missing.push(`automation_env=${automationReadiness.missing.join(",")}`);
    if (Array.isArray(fixtureReadiness.missing) && fixtureReadiness.missing.length > 0) missing.push(`fixture=${fixtureReadiness.missing.join(",")}`);
    const manualLabel = manualReadiness.status === "manual_check" ? " manual_check" : "";
    console.log(`   - readiness: ${missing.length === 0 ? `ready${manualLabel}` : `missing ${missing.join(" ")}`}`);
    const preconditions = caseItem.preconditions;
    if (Array.isArray(preconditions) && preconditions.length > 0) console.log(`   - preconditions: ${preconditions.length}`);
    const setupAutomation = caseItem.setup_automation;
    if (Array.isArray(setupAutomation) && setupAutomation.length > 0) console.log(`   - setup automation: ${setupAutomation.length}`);
  }
  console.log("");
  console.log("## Result Policy");
  for (const policy of suiteResultPolicy(cases)) console.log(`- ${policy}`);
  return 0;
}

function suiteStartPath(root: string, path: string): string {
  return resolve(root, path);
}

function ensureDirectory(root: string, path: string, label: string): void {
  const resolvedPath = suiteStartPath(root, path);
  if (existsSync(resolvedPath) && !statSync(resolvedPath).isDirectory()) {
    fail(`${label} exists and is not a directory: ${resolvedPath}`);
  }
  mkdirSync(resolvedPath, { recursive: true });
}

function buildSuiteStart(
  root: string,
  item: StructuredItem,
  args: string[],
  options: Record<string, string | boolean>,
): Record<string, unknown> {
  const now = new Date();
  const startedAtLocal = localIsoWithOffset(now);
  const suite = suiteSummary(item);
  const suiteId = String(suite.id);
  const runId = optionString(options, "run-id") ?? `${timestampSlug(startedAtLocal)}-${suiteId}`;
  const evidenceRoot = optionString(options, "evidence-dir") ?? join("reports", "evidence", runId);
  const reportPath = join("reports", `${runId}.md`);
  const manifestPath = join(evidenceRoot, "suite-start.json");
  const handoffPath = join(evidenceRoot, "suite-start.md");
  const cases = suiteCases(root, item).map((caseItem) => {
    const caseId = String(caseItem.id);
    const caseRunId = `${runId}-${caseId}`;
    const evidenceDir = join(evidenceRoot, caseId);
    const consoleLog = join(evidenceDir, "console.log");
    const caseReportPath = join("reports", `${caseRunId}.md`);
    return {
      ...caseItem,
      run_id: caseRunId,
      evidence_dir: evidenceDir,
      plan_command: `bin/lbs test plan ${caseId}`,
      start_command: `bin/lbs test start ${caseId}`,
      automation_command: caseItem.automation
        ? `bin/lbs test run ${caseId} --run-id ${caseRunId} --output ${evidenceDir}`
        : "",
      report_command: caseItem.automation
        ? `bin/lbs test report ${caseId} --since "${startedAtLocal}" --console-log ${consoleLog} --evidence-dir ${evidenceDir} --output ${caseReportPath}`
        : `bin/lbs test report ${caseId} --since "${startedAtLocal}" --evidence-dir ${evidenceDir} --output ${caseReportPath}`,
      result_command_template: `bin/lbs test result ${caseId} --result <status> --reason "<short reason>" --evidence-dir ${evidenceDir} --run-id ${caseRunId} --started-at "${startedAtLocal}" --evidence ${Array.isArray(caseItem.evidence_required) ? caseItem.evidence_required.join(",") : ""}`,
    };
  });

  const locator = args.join(" ");
  return {
    run_id: runId,
    started_at: now.toISOString(),
    started_at_local: startedAtLocal,
    suite,
    evidence_root: evidenceRoot,
    manifest_path: manifestPath,
    handoff_path: handoffPath,
    cases,
    suite_report_path: reportPath,
    plan_command: `bin/lbs suite plan ${locator}`,
    report_command: `bin/lbs suite report ${locator} --run-id ${runId} --evidence-dir ${evidenceRoot} --output ${reportPath}`,
    evidence_policy: suiteEvidencePolicy(cases),
  };
}

function writeSuiteStartArtifacts(root: string, start: Record<string, unknown>, rendered: string): void {
  const evidenceRoot = String(start.evidence_root || "");
  if (!evidenceRoot) return;

  ensureDirectory(root, evidenceRoot, "suite evidence directory");
  for (const caseItem of start.cases as Array<Record<string, unknown>>) {
    const evidenceDir = String(caseItem.evidence_dir || "");
    if (evidenceDir) ensureDirectory(root, evidenceDir, "case evidence directory");
  }

  const manifestPath = String(start.manifest_path || "");
  if (manifestPath) {
    const path = suiteStartPath(root, manifestPath);
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, `${JSON.stringify(start, null, 2)}\n`, "utf8");
  }

  const handoffPath = String(start.handoff_path || "");
  if (handoffPath) {
    const path = suiteStartPath(root, handoffPath);
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, rendered, "utf8");
  }
}

function renderSuiteStart(start: Record<string, unknown>): string {
  const suite = start.suite as Record<string, unknown>;
  const cases = start.cases as Array<Record<string, unknown>>;
  const lines: string[] = [];
  lines.push(`# Suite Start: ${suite.id}`);
  lines.push("");
  lines.push(`Run: ${start.run_id}`);
  lines.push(`Started: ${start.started_at_local}`);
  lines.push(`Title: ${suite.title}`);
  lines.push(`Evidence root: ${start.evidence_root}`);
  lines.push("");
  lines.push("## Commands");
  lines.push(`- plan: ${start.plan_command}`);
  lines.push(`- report: ${start.report_command}`);
  lines.push("");
  lines.push("## Cases");
  for (const [index, caseItem] of cases.entries()) {
    lines.push(`${index + 1}. ${caseItem.id} [${caseItem.priority}/${caseItem.risk}] ${caseItem.title}`);
    lines.push(`   - evidence_dir: ${caseItem.evidence_dir}`);
    lines.push(`   - plan: ${caseItem.plan_command}`);
    if (caseItem.automation_command) lines.push(`   - automation: ${caseItem.automation_command}`);
    else lines.push(`   - manual start: ${caseItem.start_command}`);
    lines.push(`   - report: ${caseItem.report_command}`);
    lines.push(`   - result template: ${caseItem.result_command_template}`);
  }
  lines.push("");
  lines.push("## Evidence Policy");
  for (const item of start.evidence_policy as string[]) lines.push(`- ${item}`);
  return `${lines.join("\n").trimEnd()}\n`;
}

export function commandSuiteStart(ctx: CommandContext): number {
  const { positional: args, options } = parseOptions(ctx.args.slice(2));
  const item = findSuite(ctx.root, args);
  const start = buildSuiteStart(ctx.root, item, args, options);
  const rendered = renderSuiteStart(start);
  writeSuiteStartArtifacts(ctx.root, start, rendered);
  const content = options.json === true ? `${JSON.stringify(start, null, 2)}\n` : rendered;
  writeOrPrint(content, optionString(options, "output"));
  return 0;
}

function suiteRunCaseArgs(root: string, caseItem: Record<string, unknown>, headed: boolean): string[] {
  const args = [
    lbsScriptPath(),
    "--root",
    root,
    "test",
    "run",
    String(caseItem.id),
    "--run-id",
    String(caseItem.run_id),
    "--output",
    String(caseItem.evidence_dir),
  ];
  if (headed) args.push("--headed");
  return args;
}

function suiteReportExitCode(status: string): number {
  if (status === "pass") return 0;
  if (status === "blocked" || status === "env_issue" || status === "flaky") return 2;
  return 1;
}

function outputTail(value: string | Buffer | null | undefined): string {
  return String(value ?? "").trim().slice(-4000);
}

function exitStatusFromResultStatus(status: string): number {
  if (status === "pass") return 0;
  if (status === "blocked" || status === "env_issue" || status === "flaky") return 2;
  return 1;
}

function executionStatusFromExitStatus(status: number): string {
  if (status === 0) return "ok";
  if (status === 2) return "classified";
  return "nonzero";
}

function executionFromCaseResultFile(caseItem: Record<string, unknown>): Record<string, unknown> | null {
  const resultPath = join(String(caseItem.evidence_dir), "result.json");
  if (!existsSync(resultPath)) return null;
  try {
    const parsed = JSON.parse(readFileSync(resultPath, "utf8")) as Record<string, unknown>;
    if (
      parsed.case_id !== caseItem.id ||
      parsed.run_id !== caseItem.run_id ||
      typeof parsed.status !== "string"
    ) return null;
    const exitStatus = exitStatusFromResultStatus(parsed.status);
    return {
      status: executionStatusFromExitStatus(exitStatus),
      exit_status: exitStatus,
      reason: typeof parsed.reason === "string" ? parsed.reason : "result.json completed",
      result_status: parsed.status,
      result_json: resultPath,
    };
  } catch {
    return null;
  }
}

function executionProblemStatus(executions: Array<Record<string, unknown>>): string {
  const statuses = executions.map((item) => String(item.status));
  if (statuses.includes("nonzero")) return "fail";
  if (statuses.includes("skipped")) return "incomplete";
  return "";
}

function missingReadinessReason(caseItem: Record<string, unknown>): string {
  const labels: Array<[string, string]> = [
    ["env", "env_readiness"],
    ["automation_env", "automation_readiness"],
    ["fixture", "fixture_readiness"],
  ];
  const missing = labels.flatMap(([label, key]) => {
    const value = caseItem[key] as Record<string, unknown> | undefined;
    if (value?.status !== "missing") return [];
    const names = Array.isArray(value.missing) ? value.missing.filter((item): item is string => typeof item === "string") : [];
    return [`${label}=${names.length > 0 ? names.join(",") : "missing"}`];
  });
  return missing.length > 0
    ? `case readiness missing (${missing.join(" ")}); rerun with --include-not-ready after fixing or intentionally accepting readiness gaps`
    : "";
}

export function commandSuiteRun(ctx: CommandContext): number {
  const { positional: args, options } = parseOptions(ctx.args.slice(2));
  const item = findSuite(ctx.root, args);
  const start = buildSuiteStart(ctx.root, item, args, options);
  const renderedStart = renderSuiteStart(start);
  const dryRun = options["dry-run"] === true;
  if (!dryRun) writeSuiteStartArtifacts(ctx.root, start, renderedStart);

  const executions = [];
  for (const caseItem of start.cases as Array<Record<string, unknown>>) {
    if (statusOf(caseItem, "manual_readiness") === "manual_check" && options["include-manual-check"] !== true) {
      executions.push({ id: caseItem.id, status: "skipped", reason: "case requires manual_check; rerun with --include-manual-check after confirming preconditions" });
      continue;
    }
    const missingReadiness = missingReadinessReason(caseItem);
    if (missingReadiness && options["include-not-ready"] !== true) {
      executions.push({ id: caseItem.id, status: "skipped", reason: missingReadiness });
      continue;
    }
    if (!caseItem.automation) {
      executions.push({ id: caseItem.id, status: "skipped", reason: "case has no automation" });
      continue;
    }
    const runArgs = suiteRunCaseArgs(ctx.root, caseItem, options.headed === true);
    if (dryRun) {
      executions.push({ id: caseItem.id, status: "planned", reason: "dry-run; case automation not executed", command: [execPath, ...runArgs].join(" ") });
      continue;
    }
    if (options.json !== true) console.log(`Suite case: ${caseItem.id}`);
    const result = spawnSync(execPath, runArgs, {
      cwd: ctx.root,
      encoding: "utf8",
      stdio: options.json === true ? "pipe" : "inherit",
    });
    const fileExecution = result.error ? executionFromCaseResultFile(caseItem) : null;
    const status = typeof fileExecution?.exit_status === "number"
      ? fileExecution.exit_status
      : result.error ? 1 : result.status ?? 1;
    executions.push({
      id: caseItem.id,
      status: fileExecution?.status ?? executionStatusFromExitStatus(status),
      exit_status: status,
      reason: fileExecution?.reason ?? result.error?.message ?? "",
      result_status: fileExecution?.result_status,
      result_json: fileExecution?.result_json,
      spawn_error: fileExecution && result.error ? result.error.message : undefined,
      stdout: outputTail(result.stdout),
      stderr: outputTail(result.stderr),
    });
  }

  const report = buildSuiteReport(ctx.root, item, {
    ...options,
    "run-id": String(start.run_id),
    "evidence-dir": String(start.evidence_root),
  }, executions);
  const payload = {
    run_id: start.run_id,
    evidence_root: start.evidence_root,
    executions,
    report,
  };
  const content = options.json === true
    ? `${JSON.stringify(payload, null, 2)}\n`
    : renderSuiteReport(report);
  writeOrPrint(content, optionString(options, "output") ?? (options.json === true || dryRun ? undefined : String(start.suite_report_path || "")));
  return dryRun ? 0 : suiteReportExitCode(String(report.status));
}

function arrayField(data: Record<string, unknown>, key: string): string[] {
  const value = data[key];
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function readCaseResult(evidenceDir: string, caseId: string, expectedRunId: string, requiredEvidence: string[]): Record<string, unknown> {
  const resultPath = join(evidenceDir, "result.json");
  if (!existsSync(resultPath)) {
    return { status: "missing", path: resultPath, reason: "result.json not found" };
  }
  try {
    const parsed = JSON.parse(readFileSync(resultPath, "utf8")) as Record<string, unknown>;
    if (parsed.case_id !== caseId) {
      return {
        status: "invalid",
        path: resultPath,
        reason: `result.json case_id mismatch: expected ${caseId}, got ${String(parsed.case_id ?? "missing")}`,
      };
    }
    if (expectedRunId && parsed.run_id !== expectedRunId) {
      return {
        status: "invalid",
        path: resultPath,
        reason: `result.json run_id mismatch: expected ${expectedRunId}, got ${String(parsed.run_id ?? "missing")}`,
      };
    }
    const collected = arrayField(parsed, "evidence_collected");
    const missing = requiredEvidence.filter((item) => !collected.includes(item));
    return {
      status: typeof parsed.status === "string" ? parsed.status : "invalid",
      path: resultPath,
      reason: typeof parsed.reason === "string" ? parsed.reason : "",
      started_at_local: typeof parsed.started_at_local === "string" ? parsed.started_at_local : "",
      finished_at_local: typeof parsed.finished_at_local === "string" ? parsed.finished_at_local : "",
      url: typeof parsed.url === "string" ? parsed.url : "",
      evidence_collected: collected,
      evidence_required: requiredEvidence,
      evidence_missing: missing,
      evidence_status: missing.length === 0 ? "complete" : "incomplete",
    };
  } catch (error) {
    return { status: "invalid", path: resultPath, reason: String(error) };
  }
}

function suiteStatus(caseResults: Array<Record<string, unknown>>): string {
  const statuses = caseResults.map((item) => String(item.status));
  if (statuses.length === 0) return "not_run";
  if (statuses.includes("fail") || statuses.includes("invalid")) return "fail";
  if (statuses.includes("missing")) return "incomplete";
  if (caseResults.some((item) => item.status === "pass" && item.evidence_status !== "complete")) return "incomplete";
  if (statuses.every((status) => status === "pass")) return "pass";
  if (statuses.includes("blocked")) return "blocked";
  if (statuses.includes("env_issue")) return "env_issue";
  if (statuses.includes("flaky")) return "flaky";
  return "unknown";
}

function buildSuiteReport(
  root: string,
  item: StructuredItem,
  options: Record<string, string | boolean>,
  executions: Array<Record<string, unknown>> = [],
): Record<string, unknown> {
  const suite = suiteSummary(item);
  const runId = optionString(options, "run-id") ?? "";
  const evidenceRoot = optionString(options, "evidence-dir") ?? (runId ? join("reports", "evidence", runId) : "");
  const cases = suiteCases(root, item).map((caseItem) => {
    const caseId = String(caseItem.id);
    const expectedCaseRunId = runId ? `${runId}-${caseId}` : "";
    const evidenceDir = evidenceRoot ? join(evidenceRoot, caseId) : "";
    const requiredEvidence = Array.isArray(caseItem.evidence_required) ? caseItem.evidence_required : [];
    const result = evidenceDir
      ? readCaseResult(evidenceDir, caseId, expectedCaseRunId, requiredEvidence)
      : { status: "missing", path: "", reason: "Set --evidence-dir or --run-id to locate case result.json files" };
    return {
      ...caseItem,
      evidence_dir: evidenceDir,
      result,
    };
  });
  const counts: Record<string, number> = {};
  for (const item of cases) {
    const status = String((item.result as Record<string, unknown>).status);
    counts[status] = (counts[status] ?? 0) + 1;
  }

  const resultStatus = suiteStatus(cases.map((item) => item.result as Record<string, unknown>));
  const executionStatus = executionProblemStatus(executions);
  return {
    generated_at: new Date().toISOString(),
    run_id: runId,
    suite,
    evidence_root: evidenceRoot,
    status: executionStatus || resultStatus,
    counts,
    cases,
    execution_status: executionStatus || "ok",
    decision_policy: [
      "pass requires every case result to be pass.",
      "suite run pass also requires every attempted execution to finish ok.",
      "blocked and env_issue are not product pass.",
      "pass results missing required evidence keep the suite incomplete.",
      "result.json must match the expected case_id and suite case run_id.",
      "missing or invalid result.json means the suite is incomplete or failed to collect evidence.",
    ],
  };
}

function renderSuiteReport(report: Record<string, unknown>): string {
  const suite = report.suite as Record<string, unknown>;
  const cases = report.cases as Array<Record<string, unknown>>;
  const counts = report.counts as Record<string, number>;
  const lines: string[] = [];
  lines.push(`# Suite Report: ${suite.id}`);
  lines.push("");
  lines.push(`Generated: ${report.generated_at}`);
  if (report.run_id) lines.push(`Run: ${report.run_id}`);
  lines.push(`Title: ${suite.title}`);
  lines.push(`Status: ${report.status}`);
  lines.push(`Evidence root: ${report.evidence_root || "not provided"}`);
  lines.push("");
  lines.push("## Counts");
  for (const key of Object.keys(counts).sort()) lines.push(`- ${key}: ${counts[key]}`);
  if (Object.keys(counts).length === 0) lines.push("- None.");
  lines.push("");
  lines.push("## Cases");
  for (const caseItem of cases) {
    const result = caseItem.result as Record<string, unknown>;
    lines.push(`- ${caseItem.id}: ${result.status} - ${result.reason || "no reason"}`);
    if (Array.isArray(result.evidence_missing) && result.evidence_missing.length > 0) {
      lines.push(`  evidence_missing: ${result.evidence_missing.join(", ")}`);
    }
    if (caseItem.evidence_dir) lines.push(`  evidence_dir: ${caseItem.evidence_dir}`);
    if (result.path) lines.push(`  result_json: ${result.path}`);
  }
  lines.push("");
  lines.push("## Decision Policy");
  for (const item of report.decision_policy as string[]) lines.push(`- ${item}`);
  return `${lines.join("\n").trimEnd()}\n`;
}

export function commandSuiteReport(ctx: CommandContext): number {
  const { positional: args, options } = parseOptions(ctx.args.slice(2));
  const item = findSuite(ctx.root, args);
  const report = buildSuiteReport(ctx.root, item, options);
  const content = options.json === true ? `${JSON.stringify(report, null, 2)}\n` : renderSuiteReport(report);
  writeOrPrint(content, optionString(options, "output"));
  return 0;
}
