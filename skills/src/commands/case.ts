import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import type { CommandContext } from "../types.ts";
import { parseOptions, optionString, usage, fail } from "../cli.ts";
import { caseModeValues } from "../constants.ts";
import { boolValue, findStructuredItem, getSkill, listValue, loadStructuredItems, scalar, yamlList, yamlQuote } from "../fs.ts";
import { caseAutomationReadiness, caseEnvReadiness, caseFixtureReadiness, caseManualReadiness, runtimeEnv } from "../readiness.ts";
import { setupAutomationEntries } from "../setup-automation.ts";

function casePath(root: string, skillName: string, id: string): string {
  const skill = getSkill(root, skillName);
  const dir = join(skill.path, "cases");
  mkdirSync(dir, { recursive: true });
  return join(dir, `${id}.yaml`);
}

export function commandCaseNew(ctx: CommandContext): number {
  const { positional, options } = parseOptions(ctx.args.slice(2));
  const id = positional[0];
  const title = optionString(options, "title");
  if (!id || !title) usage();

  const skill = optionString(options, "skill") ?? "langbot-testing";
  const path = casePath(ctx.root, skill, id);
  if (existsSync(path)) fail(`case already exists: ${path}`);

  const area = optionString(options, "area") ?? "general";
  const type = optionString(options, "type") ?? "smoke";
  const mode = optionString(options, "mode") ?? "agent-browser";
  if (!caseModeValues.includes(mode)) fail(`--mode must be one of ${caseModeValues.join(", ")}`);
  const isProbe = mode === "probe";

  const text =
    `id: ${id}\n` +
    `title: ${yamlQuote(title)}\n` +
    `mode: ${mode}\n` +
    `area: ${area}\n` +
    `type: ${type}\n` +
    "priority: p2\n" +
    "risk: medium\n" +
    "ci_eligible: false\n" +
    "tags:\n" +
    yamlList([type]) +
    "\nskills:\n" +
    yamlList(["langbot-env-setup", skill]) +
    "\nenv:\n" +
    yamlList(isProbe ? [] : ["LANGBOT_FRONTEND_URL", "LANGBOT_BACKEND_URL"]) +
    "\nsteps:\n" +
    yamlList([isProbe ? "Describe the probe command, script, or diagnostic to run." : "Describe the user-visible action to perform."]) +
    "\nchecks:\n" +
    yamlList(isProbe
      ? [
        "Probe: Describe the expected success signal.",
        "Evidence: Required logs, API diagnostics, or filesystem artifacts are written.",
      ]
      : [
        "UI: Describe the user-visible success signal.",
        "Console: No unexpected frontend errors.",
        "Logs: Relevant backend processing completed when applicable.",
      ]) +
    "\nevidence_required:\n" +
    yamlList(isProbe ? ["api_diagnostic"] : ["ui", "console"]) +
    "\ndiagnostics:\n" +
    yamlList([isProbe
      ? "Use logs, API, or filesystem diagnostics to explain probe failures."
      : "Use API/curl/logs only to distinguish frontend failure from backend/runtime failure."]) +
    "\ntroubleshooting:\n" +
    yamlList([]) +
    "\n";

  writeFileSync(path, text, "utf8");
  console.log(path);
  return 0;
}

function caseRow(item: ReturnType<typeof loadStructuredItems>[number], root: string): Record<string, unknown> {
  const automation = scalar(item.fields, "automation");
  const env = runtimeEnv(root);
  const id = scalar(item.fields, "id");
  const row = {
    skill: item.skill,
    id,
    title: scalar(item.fields, "title"),
    mode: scalar(item.fields, "mode"),
    area: scalar(item.fields, "area"),
    type: scalar(item.fields, "type"),
    priority: scalar(item.fields, "priority"),
    risk: scalar(item.fields, "risk"),
    ci_eligible: boolValue(item.fields, "ci_eligible") ?? false,
    tags: listValue(item.fields, "tags"),
    env: listValue(item.fields, "env"),
    env_any: listValue(item.fields, "env_any"),
    preconditions: listValue(item.fields, "preconditions"),
    setup: listValue(item.fields, "setup"),
    setup_automation: setupAutomationEntries(item),
    setup_provides_env: listValue(item.fields, "setup_provides_env"),
    cleanup: listValue(item.fields, "cleanup"),
    evidence_required: listValue(item.fields, "evidence_required"),
    automation,
    automation_exists: automation ? existsSync(resolve(root, automation)) : false,
    env_readiness: caseEnvReadiness(item, env),
    automation_readiness: caseAutomationReadiness(item, env),
    fixture_readiness: caseFixtureReadiness(root, id),
    manual_readiness: caseManualReadiness(item),
  };
  return {
    ...row,
    readiness: readinessLabel(row),
  };
}

function hasTag(row: Record<string, unknown>, tag: string): boolean {
  const tags = row.tags;
  return Array.isArray(tags) && tags.includes(tag);
}

function hasMissingReadiness(row: Record<string, unknown>): boolean {
  for (const key of ["env_readiness", "automation_readiness", "fixture_readiness"]) {
    const value = row[key] as Record<string, unknown> | undefined;
    if (value?.status === "missing") return true;
  }
  return false;
}

function hasManualCheck(row: Record<string, unknown>): boolean {
  const manual = row.manual_readiness as Record<string, unknown> | undefined;
  return manual?.status === "manual_check";
}

function readinessLabel(row: Record<string, unknown>): string {
  if (hasMissingReadiness(row)) return "not-ready";
  return hasManualCheck(row) ? "manual-check" : "ready";
}

export function commandCaseList(ctx: CommandContext): number {
  const { positional, options } = parseOptions(ctx.args.slice(2));
  const skill = positional[0];
  const rows = loadStructuredItems(ctx.root, "cases", skill)
    .map((item) => caseRow(item, ctx.root))
    .filter((row) => !optionString(options, "type") || row.type === optionString(options, "type"))
    .filter((row) => !optionString(options, "area") || row.area === optionString(options, "area"))
    .filter((row) => !optionString(options, "priority") || row.priority === optionString(options, "priority"))
    .filter((row) => !optionString(options, "risk") || row.risk === optionString(options, "risk"))
    .filter((row) => !optionString(options, "tag") || hasTag(row, optionString(options, "tag") ?? ""))
    .filter((row) => options.automation !== true || Boolean(row.automation))
    .filter((row) => options.ci !== true || row.ci_eligible === true)
    .filter((row) => options["machine-ready"] !== true || !hasMissingReadiness(row))
    .filter((row) => options.ready !== true || (!hasMissingReadiness(row) && !hasManualCheck(row)));

  if (options.json === true) {
    console.log(JSON.stringify(rows, null, 2));
    return 0;
  }

  for (const row of rows) {
    console.log([
      row.skill,
      row.id,
      row.type,
      row.area,
      row.priority,
      row.risk,
      row.ci_eligible ? "ci" : "manual",
      row.automation ? "automated" : "manual-path",
      row.readiness,
      row.title,
    ].join("\t"));
  }
  return 0;
}

export function commandCaseShow(ctx: CommandContext): number {
  const positional = ctx.args.slice(2);
  if (positional.length < 1 || positional.length > 2) usage();
  const item = positional.length === 1
    ? findStructuredItem(ctx.root, "cases", positional[0])
    : findStructuredItem(ctx.root, "cases", positional[0], positional[1]);
  console.log(item.raw.trimEnd());
  return 0;
}
