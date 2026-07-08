import { existsSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { listValue } from "./fs.ts";
import type { StructuredItem } from "./types.ts";

export type SetupAutomationSpec = {
  entry: string;
  kind: "case" | "node";
  target: string;
  args: string[];
};

export function setupAutomationEntries(item: StructuredItem): string[] {
  return listValue(item.fields, "setup_automation");
}

export function parseSetupAutomationEntry(entry: string): SetupAutomationSpec {
  const trimmed = entry.trim();
  if (trimmed.startsWith("case:")) {
    return {
      entry,
      kind: "case",
      target: trimmed.slice("case:".length).trim(),
      args: [],
    };
  }
  if (trimmed.startsWith("node:")) {
    const words = trimmed.slice("node:".length).trim().split(/\s+/).filter(Boolean);
    return {
      entry,
      kind: "node",
      target: words[0] ?? "",
      args: words.slice(1),
    };
  }
  return {
    entry,
    kind: "case",
    target: "",
    args: [],
  };
}

export function validateSetupAutomationEntry(root: string, entry: string, caseIds: Set<string>): string[] {
  const spec = parseSetupAutomationEntry(entry);
  const errors: string[] = [];
  if (!entry.startsWith("case:") && !entry.startsWith("node:")) {
    return [`setup_automation entry must start with 'case:' or 'node:': ${entry}`];
  }
  if (!spec.target) errors.push(`setup_automation entry is missing a target: ${entry}`);
  if (spec.kind === "case") {
    if (spec.args.length > 0) errors.push(`setup_automation case entries cannot include args: ${entry}`);
    if (spec.target && !/^[a-z0-9][a-z0-9_-]*$/.test(spec.target)) {
      errors.push(`setup_automation case target must be a case id: ${entry}`);
    } else if (spec.target && !caseIds.has(spec.target)) {
      errors.push(`setup_automation references unknown case '${spec.target}'`);
    }
  }
  if (spec.kind === "node") {
    if (spec.target.startsWith("/") || spec.target.includes("..") || !spec.target.startsWith("scripts/")) {
      errors.push(`setup_automation node target must be a repository scripts/ path: ${entry}`);
    }
    if (spec.target && !/\.(mjs|js|ts)$/.test(spec.target)) {
      errors.push(`setup_automation node target must be a Node script: ${entry}`);
    }
    if (spec.target && !existsSync(join(root, spec.target))) {
      errors.push(`setup_automation node script does not exist: ${spec.target}`);
    }
    for (const arg of spec.args) {
      if (!/^--[A-Za-z0-9][A-Za-z0-9_-]*(?:=[A-Za-z0-9_./:@-]+)?$/.test(arg)) {
        errors.push(`setup_automation node arg must be a simple --flag or --key=value: ${entry}`);
      }
    }
  }
  return errors;
}

export function setupAutomationEvidenceName(index: number, spec: SetupAutomationSpec): string {
  const target = spec.kind === "case" ? spec.target : basename(spec.target).replace(/\.[^.]+$/, "");
  return `${String(index + 1).padStart(2, "0")}-${target.replace(/[^A-Za-z0-9_-]+/g, "-")}`;
}

export function setupAutomationScriptPath(root: string, spec: SetupAutomationSpec): string {
  return spec.kind === "node" && spec.target ? resolve(root, spec.target) : "";
}

export function lbsScriptPath(): string {
  return resolve(dirname(fileURLToPath(import.meta.url)), "lbs.ts");
}
