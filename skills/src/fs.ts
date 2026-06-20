import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import type { ParsedYaml, Skill, StructuredItem, StructuredItemKind } from "./types.ts";
import { fail } from "./cli.ts";

const frontmatterRe = /^---\n([\s\S]*?)\n---\n/;

export function statIsDirectory(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

export function skillsRoot(root: string): string {
  const nested = join(root, "skills");
  return existsSync(nested) && statIsDirectory(nested) ? nested : root;
}

export function envPath(root: string): string {
  return join(skillsRoot(root), ".env");
}

export function envLocalPath(root: string): string {
  return join(skillsRoot(root), ".env.local");
}

export function envExamplePath(root: string): string {
  return join(skillsRoot(root), ".env.example");
}

export function loadEnv(root: string): Record<string, string> {
  return {
    ...parseEnvFile(envPath(root)),
    ...parseEnvFile(envLocalPath(root)),
  };
}

export function listDirectories(root: string): string[] {
  return readdirSync(root)
    .filter((name) => !name.startsWith("."))
    .filter((name) => statIsDirectory(join(root, name)))
    .sort();
}

export function parseFrontmatter(text: string): { meta: Record<string, string>; body: string } {
  const match = text.match(frontmatterRe);
  if (!match) return { meta: {}, body: text };

  const meta: Record<string, string> = {};
  for (const line of match[1].split("\n")) {
    const sep = line.indexOf(":");
    if (sep === -1) continue;
    const key = line.slice(0, sep).trim();
    const value = line.slice(sep + 1).trim().replace(/^["']|["']$/g, "");
    meta[key] = value;
  }

  return { meta, body: text.slice(match[0].length) };
}

export function loadSkills(root: string): Skill[] {
  const skills: Skill[] = [];
  const base = skillsRoot(root);
  for (const directory of listDirectories(base)) {
    const skillPath = join(base, directory);
    const skillMd = join(skillPath, "SKILL.md");
    if (!existsSync(skillMd)) continue;
    const text = readFileSync(skillMd, "utf8");
    const { meta, body } = parseFrontmatter(text);
    skills.push({
      path: skillPath,
      directory,
      name: meta.name ?? "",
      description: meta.description ?? "",
      body,
    });
  }
  return skills;
}

export function getSkill(root: string, skillName: string): Skill {
  const skill = loadSkills(root).find((item) => item.directory === skillName || item.name === skillName);
  if (!skill) fail(`unknown skill: ${skillName}`);
  return skill;
}

export function parseEnvFile(path: string): Record<string, string> {
  if (!existsSync(path)) return {};
  const env: Record<string, string> = {};
  for (const rawLine of readFileSync(path, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const sep = line.indexOf("=");
    if (sep === -1) continue;
    const key = line.slice(0, sep).trim();
    const value = line.slice(sep + 1).trim().replace(/^["']|["']$/g, "");
    env[key] = value;
  }
  return env;
}

export function globMarkdownRefs(skillPath: string): string[] {
  const refsDir = join(skillPath, "references");
  if (!existsSync(refsDir)) return [];
  return readdirSync(refsDir)
    .filter((name) => name.endsWith(".md"))
    .sort()
    .map((name) => join("references", name));
}

export function globYamlFiles(dir: string): string[] {
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((name) => name.endsWith(".yaml") || name.endsWith(".yml"))
    .sort()
    .map((name) => join(dir, name));
}

function unquote(value: string): string {
  return value.trim().replace(/^["']|["']$/g, "");
}

function parseScalarValue(value: string): string | boolean {
  const trimmed = value.trim();
  if (/^["'].*["']$/.test(trimmed)) return unquote(trimmed);
  if (trimmed === "true") return true;
  if (trimmed === "false") return false;
  return trimmed;
}

export function parseYamlLite(text: string): ParsedYaml {
  const fields: ParsedYaml = {};
  let currentList: string | null = null;

  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.replace(/\s+$/, "");
    if (!line.trim() || line.trim().startsWith("#")) continue;

    const pair = line.match(/^([A-Za-z0-9_]+):\s*(.*)$/);
    if (pair) {
      const key = pair[1];
      const value = pair[2];
      if (value === "") {
        fields[key] = [];
        currentList = key;
      } else {
        fields[key] = parseScalarValue(value);
        currentList = null;
      }
      continue;
    }

    const item = line.match(/^\s*-\s*(.*)$/);
    if (item && currentList) {
      const existing = fields[currentList];
      if (Array.isArray(existing)) existing.push(unquote(item[1]));
    }
  }

  return fields;
}

export function scalar(fields: ParsedYaml, key: string): string {
  const value = fields[key];
  return typeof value === "string" ? value : "";
}

export function boolValue(fields: ParsedYaml, key: string): boolean | undefined {
  const value = fields[key];
  return typeof value === "boolean" ? value : undefined;
}

export function listValue(fields: ParsedYaml, key: string): string[] {
  const value = fields[key];
  return Array.isArray(value) ? value : [];
}

export function yamlQuote(value: string): string {
  return JSON.stringify(value);
}

export function yamlList(values: string[]): string {
  return values.map((value) => `  - ${yamlQuote(value)}`).join("\n");
}

export function loadStructuredItems(root: string, kind: StructuredItemKind, skillFilter?: string): StructuredItem[] {
  const skills = skillFilter ? [getSkill(root, skillFilter)] : loadSkills(root);
  const items: StructuredItem[] = [];
  for (const skill of skills) {
    for (const path of globYamlFiles(join(skill.path, kind))) {
      const raw = readFileSync(path, "utf8");
      items.push({ path, skill: skill.directory, fields: parseYamlLite(raw), raw });
    }
  }
  return items.sort((a, b) => `${a.skill}:${scalar(a.fields, "id")}`.localeCompare(`${b.skill}:${scalar(b.fields, "id")}`));
}

export function findStructuredItem(
  root: string,
  kind: StructuredItemKind,
  skillOrId: string,
  maybeId?: string,
): StructuredItem {
  const skillFilter = maybeId ? skillOrId : undefined;
  const id = maybeId ?? skillOrId;
  const matches = loadStructuredItems(root, kind, skillFilter).filter((item) => scalar(item.fields, "id") === id);
  if (matches.length === 0) fail(`unknown ${kind.slice(0, -1)}: ${id}`);
  if (matches.length > 1) {
    fail(`ambiguous ${kind.slice(0, -1)} '${id}', specify skill: ${matches.map((item) => item.skill).join(", ")}`);
  }
  return matches[0];
}

export function slugify(input: string): string {
  return input
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}
