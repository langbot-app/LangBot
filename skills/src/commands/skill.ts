import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { CommandContext } from "../types.ts";
import { fail, optionString, parseOptions, usage } from "../cli.ts";
import { loadFixtureItems } from "../fixtures.ts";
import { boolValue, getSkill, globMarkdownRefs, listValue, loadSkills, loadStructuredItems, scalar, skillsRoot } from "../fs.ts";

export function commandList(ctx: CommandContext): number {
  for (const skill of loadSkills(ctx.root)) {
    console.log(`${skill.directory}\t${skill.name}\t${skill.description}`);
  }
  return 0;
}

function buildIndexData(root: string): Record<string, unknown> {
  const caseSummary = (item: ReturnType<typeof loadStructuredItems>[number]) => ({
    id: scalar(item.fields, "id"),
    title: scalar(item.fields, "title"),
    mode: scalar(item.fields, "mode"),
    area: scalar(item.fields, "area"),
    type: scalar(item.fields, "type"),
    priority: scalar(item.fields, "priority"),
    risk: scalar(item.fields, "risk"),
    ci_eligible: boolValue(item.fields, "ci_eligible") ?? false,
    tags: listValue(item.fields, "tags"),
    automation: scalar(item.fields, "automation"),
    setup_automation: listValue(item.fields, "setup_automation"),
    setup_provides_env: listValue(item.fields, "setup_provides_env"),
    evidence_required: listValue(item.fields, "evidence_required"),
  });
  const troubleshootingSummary = (item: ReturnType<typeof loadStructuredItems>[number]) => ({
    id: scalar(item.fields, "id"),
    title: scalar(item.fields, "title"),
    category: scalar(item.fields, "category") || "product",
    related_cases: listValue(item.fields, "related_cases"),
  });
  const suiteSummary = (item: ReturnType<typeof loadStructuredItems>[number]) => ({
    id: scalar(item.fields, "id"),
    title: scalar(item.fields, "title"),
    description: scalar(item.fields, "description"),
    type: scalar(item.fields, "type"),
    priority: scalar(item.fields, "priority"),
    tags: listValue(item.fields, "tags"),
    cases: listValue(item.fields, "cases"),
  });
  return {
    generated_by: "lbs",
    skills: loadSkills(root).map((skill) => ({
      directory: skill.directory,
      name: skill.name,
      description: skill.description,
      references: globMarkdownRefs(skill.path),
      cases: loadStructuredItems(root, "cases", skill.directory).map((item) => scalar(item.fields, "id")),
      case_summaries: loadStructuredItems(root, "cases", skill.directory).map(caseSummary),
      suites: loadStructuredItems(root, "suites", skill.directory).map((item) => scalar(item.fields, "id")),
      suite_summaries: loadStructuredItems(root, "suites", skill.directory).map(suiteSummary),
      fixtures: loadFixtureItems(root, skill.directory).items.map((item) => ({
        id: item.id,
        title: item.title,
        kind: item.kind,
        path: item.path,
        related_cases: item.related_cases,
      })),
      troubleshooting: loadStructuredItems(root, "troubleshooting", skill.directory).map((item) => scalar(item.fields, "id")),
      troubleshooting_summaries: loadStructuredItems(root, "troubleshooting", skill.directory).map(troubleshootingSummary),
    })),
  };
}

export function commandIndex(ctx: CommandContext): number {
  const { options } = parseOptions(ctx.args.slice(1));
  const data = buildIndexData(ctx.root);
  const out = join(ctx.root, "skills.index.json");
  const content = `${JSON.stringify(data, null, 2)}\n`;
  if (options.check === true) {
    if (!existsSync(out)) {
      console.error(`ERROR: missing index: ${out}`);
      return 1;
    }
    if (readFileSync(out, "utf8") !== content) {
      console.error(`ERROR: index is stale: ${out}`);
      return 1;
    }
    console.log(`OK ${out}`);
    return 0;
  }
  writeFileSync(out, content, "utf8");
  console.log(out);
  return 0;
}

export function commandNewSkill(ctx: CommandContext): number {
  const { positional, options } = parseOptions(ctx.args.slice(1));
  const name = positional[0];
  if (!name) usage();

  const skillDir = join(skillsRoot(ctx.root), name);
  const skillMd = join(skillDir, "SKILL.md");
  if (existsSync(skillMd)) fail(`skill already exists: ${skillDir}`);

  mkdirSync(skillDir, { recursive: true });
  const description = optionString(options, "description") ?? `Use when working with ${name}.`;
  const text =
    `---\nname: ${name}\ndescription: ${description}\n---\n\n` +
    `# ${name}\n\n` +
    "Add concise routing and workflow instructions here.\n";
  writeFileSync(skillMd, text, "utf8");
  console.log(skillMd);
  return 0;
}

export function commandNewRef(ctx: CommandContext): number {
  const skill = ctx.args[1];
  const rawName = ctx.args[2];
  if (!skill || !rawName) usage();

  const skillDir = getSkill(ctx.root, skill).path;
  const refsDir = join(skillDir, "references");
  mkdirSync(refsDir, { recursive: true });
  const name = rawName.endsWith(".md") ? rawName : `${rawName}.md`;
  const refPath = join(refsDir, name);
  if (existsSync(refPath)) fail(`reference already exists: ${refPath}`);

  const title = name.replace(/\.md$/, "").replace(/-/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
  writeFileSync(refPath, `# ${title}\n\nAdd concise reusable instructions here.\n`, "utf8");
  console.log(refPath);
  return 0;
}
