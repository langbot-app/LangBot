import { dirname, resolve } from "node:path";
import { cwd, exit } from "node:process";
import { existsSync } from "node:fs";
import type { CommandContext } from "./types.ts";

export function usage(): never {
  console.log(`Usage:
  bin/lbs [--root <path>] list
  bin/lbs [--root <path>] validate
  bin/lbs [--root <path>] index [--check]
  bin/lbs [--root <path>] new-skill <name> [--description <text>]
  bin/lbs [--root <path>] new-ref <skill> <name>

  bin/lbs [--root <path>] env show [--json]
  bin/lbs [--root <path>] env doctor

  bin/lbs [--root <path>] fixture list [skill] [--json]
  bin/lbs [--root <path>] fixture check [skill] [--json]

  bin/lbs [--root <path>] log scan [--json] [--output <path>] [--backend-log <path>] [--frontend-log <path>] [--console-log <path>] [--case <case-id>] [--success-pattern <text>] [--failure-pattern <text>] [--expected-failure <text>] [--since <datetime>] [--until <datetime>] [--tail-lines <n>] [--no-auto-log] [--strict]
  bin/lbs [--root <path>] log watch [--json] [--backend-log <path>] [--case <case-id>] [--success-pattern <text>] [--failure-pattern <text>] [--expected-failure <text>] [--interval-ms <n>] [--duration-ms <n>] [--from-start] [--strict]
  bin/lbs [--root <path>] log guard start [--run-id <id>] [--output-dir <dir>] [--backend-log <path>] [--case <case-id>] [--json]
  bin/lbs [--root <path>] log guard stop --run-id <id> [--output-dir <dir>] [--session <path>] [--output <path>] [--case <case-id>] [--backend-log <path>] [--since <datetime>] [--until <datetime>] [--json] [--no-strict]

  bin/lbs [--root <path>] case new <id> --title <text> [--skill langbot-testing] [--mode agent-browser|probe] [--area <area>] [--type smoke]
  bin/lbs [--root <path>] case list [skill] [--json] [--type <type>] [--area <area>] [--tag <tag>] [--priority p0|p1|p2] [--risk low|medium|high] [--automation] [--ci] [--ready] [--machine-ready]
  bin/lbs [--root <path>] case show [skill] <id>

  bin/lbs [--root <path>] suite new <id> --title <text> [--skill langbot-testing] [--description <text>] [--type smoke] [--priority p2]
  bin/lbs [--root <path>] suite list [skill] [--json] [--type <type>] [--priority p0|p1|p2]
  bin/lbs [--root <path>] suite show [skill] <id>
  bin/lbs [--root <path>] suite plan [skill] <id> [--json]
  bin/lbs [--root <path>] suite start [skill] <id> [--run-id <id>] [--evidence-dir <dir>] [--output <path>] [--json]
  bin/lbs [--root <path>] suite run [skill] <id> [--run-id <id>] [--evidence-dir <dir>] [--output <path>] [--headed] [--dry-run] [--include-manual-check] [--include-not-ready] [--json]
  bin/lbs [--root <path>] suite report [skill] <id> [--run-id <id>] [--evidence-dir <dir>] [--output <path>] [--json]

  bin/lbs [--root <path>] test plan [skill] <case-id> [--json]
  bin/lbs [--root <path>] test recommend [--file <path>] [--json]
  bin/lbs [--root <path>] test start [skill] <case-id> [--output <path>] [--json]
  bin/lbs [--root <path>] test run [skill] <case-id> [--output <dir>] [--run-id <id>] [--headed] [--dry-run] [--json]
  bin/lbs [--root <path>] test report [skill] <case-id> [--output <path>] [--json] [--backend-log <path>] [--frontend-log <path>] [--console-log <path>] [--evidence-dir <dir>] [--since <datetime>] [--until <datetime>] [--tail-lines <n>] [--no-auto-log]
  bin/lbs [--root <path>] test result [skill] <case-id> --result <pass|fail|blocked|env_issue|flaky> --reason <text> --evidence-dir <dir> [--evidence ui,console,backend_log] [--started-at <datetime>] [--finished-at <datetime>] [--run-id <id>] [--url <url>] [--browser-path <text>] [--report <path>] [--notes <text>] [--json]

  bin/lbs [--root <path>] trouble list [skill]
  bin/lbs [--root <path>] trouble show [skill] <id>
  bin/lbs [--root <path>] trouble search <query>
  bin/lbs [--root <path>] trouble add <skill> --title <text> --symptom <text> --cause <text> --fix <text> [--id <id>] [--verify <text>]
`);
  exit(2);
}

export function fail(message: string): never {
  console.error(`ERROR: ${message}`);
  exit(1);
}

export function repoRoot(start: string): string {
  let current = resolve(start);
  while (true) {
    // The skills assets root is identified by skills.index.json (present at the
    // root of this assets tree). Check it first so that when the tree lives
    // inside a larger repo (e.g. LangBot/skills/), we stop at the assets root
    // and not at the outer repo's .git/README.md.
    if (existsSync(`${current}/skills.index.json`) && existsSync(`${current}/schemas/case.schema.json`)) {
      return current;
    }
    if (existsSync(`${current}/.git`) && existsSync(`${current}/README.md`)) {
      return current;
    }
    const parent = dirname(current);
    if (parent === current) return resolve(start);
    current = parent;
  }
}

export function parseGlobalArgs(rawArgs: string[]): CommandContext {
  let root = repoRoot(cwd());
  const args = [...rawArgs];

  for (let i = 0; i < args.length; ) {
    if (args[i] === "--root") {
      const value = args[i + 1];
      if (!value) fail("--root requires a path");
      root = resolve(value);
      args.splice(i, 2);
      continue;
    }
    i += 1;
  }

  return { root, args };
}

export function parseOptions(args: string[]): { positional: string[]; options: Record<string, string | boolean> } {
  const positional: string[] = [];
  const options: Record<string, string | boolean> = {};

  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg.startsWith("--")) {
      const key = arg.slice(2);
      const value = args[i + 1];
      if (!value || value.startsWith("--")) {
        options[key] = true;
      } else {
        options[key] = value;
        i += 1;
      }
    } else {
      positional.push(arg);
    }
  }

  return { positional, options };
}

export function optionString(options: Record<string, string | boolean>, key: string): string | undefined {
  const value = options[key];
  return typeof value === "string" ? value : undefined;
}
