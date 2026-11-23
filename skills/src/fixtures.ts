import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { loadSkills } from "./fs.ts";

export type FixtureItem = {
  skill: string;
  manifest_path: string;
  id: string;
  title: string;
  path: string;
  kind: string;
  related_cases: string[];
  checks: string[];
  absolute_path: string;
  exists: boolean;
};

export type FixtureLoadResult = {
  items: FixtureItem[];
  errors: string[];
};

function stringField(data: Record<string, unknown>, key: string): string {
  const value = data[key];
  return typeof value === "string" ? value : "";
}

function stringList(data: Record<string, unknown>, key: string): string[] {
  const value = data[key];
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

export function loadFixtureItems(root: string, skillFilter?: string): FixtureLoadResult {
  const items: FixtureItem[] = [];
  const errors: string[] = [];
  const skills = loadSkills(root).filter((skill) => !skillFilter || skill.directory === skillFilter || skill.name === skillFilter);

  for (const skill of skills) {
    const manifestPath = join(skill.path, "fixtures", "fixtures.json");
    if (!existsSync(manifestPath)) continue;

    let parsed: unknown;
    try {
      parsed = JSON.parse(readFileSync(manifestPath, "utf8"));
    } catch (error) {
      errors.push(`${manifestPath}: invalid fixture manifest JSON (${String(error)})`);
      continue;
    }

    if (!Array.isArray(parsed)) {
      errors.push(`${manifestPath}: fixture manifest must be a JSON array`);
      continue;
    }

    for (const [index, entry] of parsed.entries()) {
      if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
        errors.push(`${manifestPath}: fixture entry ${index} must be an object`);
        continue;
      }
      const data = entry as Record<string, unknown>;
      const id = stringField(data, "id");
      const title = stringField(data, "title");
      const path = stringField(data, "path");
      const kind = stringField(data, "kind") || "file";
      if (!id || !title || !path) {
        errors.push(`${manifestPath}: fixture entry ${index} must include id, title, and path`);
        continue;
      }
      const absolutePath = join(skill.path, path);
      items.push({
        skill: skill.directory,
        manifest_path: manifestPath,
        id,
        title,
        path,
        kind,
        related_cases: stringList(data, "related_cases"),
        checks: stringList(data, "checks"),
        absolute_path: absolutePath,
        exists: existsSync(absolutePath),
      });
    }
  }

  return { items, errors };
}
