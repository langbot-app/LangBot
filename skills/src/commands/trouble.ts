import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { CommandContext } from "../types.ts";
import { fail, optionString, parseOptions, usage } from "../cli.ts";
import { findStructuredItem, getSkill, loadStructuredItems, scalar, slugify, todayIso, yamlList, yamlQuote } from "../fs.ts";

function troubleshootingYamlPath(root: string, skillName: string, id: string): string {
  const skill = getSkill(root, skillName);
  const dir = join(skill.path, "troubleshooting");
  mkdirSync(dir, { recursive: true });
  return join(dir, `${id}.yaml`);
}

function legacyTroubleshootingPath(root: string, skillName: string): string {
  const skill = getSkill(root, skillName);
  const refsDir = join(skill.path, "references");
  mkdirSync(refsDir, { recursive: true });
  const path = join(refsDir, "troubleshooting.md");
  if (!existsSync(path)) writeFileSync(path, "# Troubleshooting\n\n", "utf8");
  return path;
}

export function commandTroubleList(ctx: CommandContext): number {
  const skill = ctx.args[2];
  const yamlItems = loadStructuredItems(ctx.root, "troubleshooting", skill);
  for (const item of yamlItems) {
    console.log(`${item.skill}\t${scalar(item.fields, "id")}\t${scalar(item.fields, "title")}`);
  }

  if (skill && yamlItems.length === 0) {
    const legacyPath = legacyTroubleshootingPath(ctx.root, skill);
    const text = readFileSync(legacyPath, "utf8");
    const headings = Array.from(text.matchAll(/^##\s+(.+)$/gm)).map((match) => match[1]);
    for (const heading of headings) console.log(`${skill}\tlegacy\t${heading}`);
  }
  return 0;
}

export function commandTroubleShow(ctx: CommandContext): number {
  const positional = ctx.args.slice(2);
  if (positional.length < 1 || positional.length > 2) usage();
  const item = positional.length === 1
    ? findStructuredItem(ctx.root, "troubleshooting", positional[0])
    : findStructuredItem(ctx.root, "troubleshooting", positional[0], positional[1]);
  console.log(item.raw.trimEnd());
  return 0;
}

export function commandTroubleSearch(ctx: CommandContext): number {
  const query = ctx.args[2]?.toLowerCase();
  if (!query) usage();
  const items = loadStructuredItems(ctx.root, "troubleshooting").filter((item) => item.raw.toLowerCase().includes(query));
  for (const item of items) {
    console.log(`${item.skill}\t${scalar(item.fields, "id")}\t${scalar(item.fields, "title")}`);
  }
  return 0;
}

export function commandTroubleAdd(ctx: CommandContext): number {
  const skill = ctx.args[2];
  if (!skill) usage();
  const { options } = parseOptions(ctx.args.slice(3));
  for (const key of ["title", "symptom", "cause", "fix"]) {
    if (!optionString(options, key)) fail(`--${key} is required`);
  }

  const title = optionString(options, "title") ?? "";
  const symptom = optionString(options, "symptom") ?? "";
  const id = optionString(options, "id") ?? slugify(title);
  const path = troubleshootingYamlPath(ctx.root, skill, id);
  if (existsSync(path)) fail(`troubleshooting entry already exists: ${path}`);

  const text =
    `id: ${id}\n` +
    `title: ${yamlQuote(title)}\n` +
    `date: ${todayIso()}\n` +
    "symptoms:\n" +
    yamlList([symptom]) +
    "\npatterns:\n" +
    yamlList([symptom]) +
    "\nlikely_causes:\n" +
    yamlList([optionString(options, "cause") ?? ""]) +
    "\nfix_steps:\n" +
    yamlList([optionString(options, "fix") ?? ""]) +
    "\nverification: " +
    yamlQuote(optionString(options, "verify") ?? "Add the command, UI signal, or log line that proves the fix worked.") +
    "\nrelated_cases:\n" +
    yamlList([]) +
    "\n";

  writeFileSync(path, text, "utf8");
  appendFileSync(legacyTroubleshootingPath(ctx.root, skill), `\n## ${id}: ${title}\n\nSee \`../troubleshooting/${id}.yaml\`.\n`, "utf8");
  console.log(path);
  return 0;
}
