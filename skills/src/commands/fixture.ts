import type { CommandContext } from "../types.ts";
import { parseOptions } from "../cli.ts";
import { loadFixtureItems } from "../fixtures.ts";
import { dirname, join } from "node:path";
import { existsSync, readFileSync } from "node:fs";

function fixtureRows(root: string, skill: string | undefined): ReturnType<typeof loadFixtureItems> {
  return loadFixtureItems(root, skill);
}

function qaAgentRunnerSourceFindings(item: ReturnType<typeof loadFixtureItems>["items"][number]) {
  if (!item.checks.includes("qa_agent_runner_source") || !item.exists) return [];
  const root = dirname(item.absolute_path);
  const required = [
    "main.py",
    "components/agent_runner/default.yaml",
    "components/agent_runner/default.py",
    "assets/icon.svg",
  ];
  const missing = required
    .filter((path) => !existsSync(join(root, path)))
    .map((path) => ({
      severity: "fail",
      kind: "fixture_check_missing_file",
      id: item.id,
      path: `${item.path.replace(/\/[^/]+$/, "")}/${path}`,
    }));
  if (missing.length > 0) return missing;

  const manifest = readFileSync(item.absolute_path, "utf8");
  const runnerYaml = readFileSync(join(root, "components/agent_runner/default.yaml"), "utf8");
  const runnerPy = readFileSync(join(root, "components/agent_runner/default.py"), "utf8");
  const requiredText = [
    [manifest, "AgentRunner", "manifest.yaml"],
    [manifest, "QAAgentRunnerPlugin", "manifest.yaml"],
    [runnerYaml, "kind: AgentRunner", "components/agent_runner/default.yaml"],
    [runnerYaml, "DefaultAgentRunner", "components/agent_runner/default.yaml"],
    [runnerPy, "QA_AGENT_RUNNER_OK", "components/agent_runner/default.py"],
    [runnerPy, "QA_AGENT_RUNNER_CONTROLLED_FAILURE", "components/agent_runner/default.py"],
  ];
  return requiredText
    .filter(([text, needle]) => !text.includes(needle))
    .map(([, needle, relativePath]) => ({
      severity: "fail",
      kind: "fixture_check_missing_text",
      id: item.id,
      path: `${item.path.replace(/\/[^/]+$/, "")}/${relativePath}`,
      detail: `missing ${needle}`,
    }));
}

function zipPackageFindings(item: ReturnType<typeof loadFixtureItems>["items"][number]) {
  if (!item.checks.includes("zip_package") || !item.exists) return [];
  const header = readFileSync(item.absolute_path).subarray(0, 4).toString("binary");
  if (header === "PK\u0003\u0004" || header === "PK\u0005\u0006") return [];
  return [{
    severity: "fail",
    kind: "fixture_check_invalid_zip",
    id: item.id,
    path: item.path,
  }];
}

export function commandFixtureList(ctx: CommandContext): number {
  const { positional, options } = parseOptions(ctx.args.slice(2));
  const skill = positional[0];
  const result = fixtureRows(ctx.root, skill);

  if (options.json === true) {
    console.log(JSON.stringify(result.items, null, 2));
    return result.errors.length > 0 ? 1 : 0;
  }

  for (const item of result.items) {
    console.log([
      item.skill,
      item.id,
      item.kind,
      item.exists ? "present" : "missing",
      item.path,
      item.title,
    ].join("\t"));
  }
  for (const error of result.errors) console.error(`ERROR: ${error}`);
  return result.errors.length > 0 ? 1 : 0;
}

export function commandFixtureCheck(ctx: CommandContext): number {
  const { positional, options } = parseOptions(ctx.args.slice(2));
  const skill = positional[0];
  const result = fixtureRows(ctx.root, skill);
  const findings = [
    ...result.errors.map((error) => ({ severity: "fail", kind: "invalid_manifest", detail: error })),
    ...result.items
      .filter((item) => !item.exists)
      .map((item) => ({
        severity: "fail",
        kind: "missing_fixture",
        id: item.id,
        path: item.path,
        absolute_path: item.absolute_path,
      })),
    ...result.items.flatMap(qaAgentRunnerSourceFindings),
    ...result.items.flatMap(zipPackageFindings),
  ];
  const report = {
    status: findings.some((finding) => finding.severity === "fail") ? "fail" : "pass",
    fixture_count: result.items.length,
    findings,
    fixtures: result.items,
  };

  if (options.json === true) {
    console.log(JSON.stringify(report, null, 2));
  } else {
    console.log(`# Fixture Check`);
    console.log("");
    console.log(`status: ${report.status}`);
    console.log(`fixture_count: ${report.fixture_count}`);
    console.log("");
    console.log("## Fixtures");
    for (const item of result.items) {
      console.log(`- ${item.id}: ${item.exists ? "present" : "missing"} (${item.path})`);
    }
    console.log("");
    console.log("## Findings");
    if (findings.length === 0) console.log("- None.");
    else for (const finding of findings) console.log(`- [${finding.severity}] ${finding.kind}: ${"detail" in finding ? finding.detail : finding.id}`);
  }

  return report.status === "pass" ? 0 : 1;
}
