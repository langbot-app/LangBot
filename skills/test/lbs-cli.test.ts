import assert from "node:assert/strict";
import { test } from "node:test";
import {
  appendFileSync,
  chmodSync,
  existsSync,
  mkdtempSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { spawn, spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { CommandContext } from "../src/types.ts";
import {
  commandCaseList,
  commandCaseNew,
  commandCaseShow,
} from "../src/commands/case.ts";
import { commandEnvDoctor, commandEnvShow } from "../src/commands/env.ts";
import {
  commandFixtureCheck,
  commandFixtureList,
} from "../src/commands/fixture.ts";
import {
  commandLogGuard,
  commandLogScan,
  commandLogWatch,
} from "../src/commands/log.ts";
import {
  commandSuiteList,
  commandSuiteNew,
  commandSuitePlan,
  commandSuiteReport,
  commandSuiteRun,
  commandSuiteShow,
  commandSuiteStart,
} from "../src/commands/suite.ts";
import {
  commandTestPlan,
  commandTestRecommend,
  commandTestReport,
  commandTestResult,
  commandTestRun,
  commandTestStart,
} from "../src/commands/test.ts";
import { commandTroubleSearch } from "../src/commands/trouble.ts";
import { commandValidate } from "../src/commands/validate.ts";
import { commandIndex } from "../src/commands/skill.ts";
import { loadEnv } from "../src/fs.ts";
import { repoRoot } from "../src/cli.ts";
import {
  classifyDebugChatResult,
  findNewFailureSignal,
  minExpectedOccurrences,
} from "../scripts/e2e/lib/debug-chat.mjs";
import {
  ensureAuthenticatedBrowser,
  resolveLangBotRepo,
  scanBrowserDiagnostics,
} from "../scripts/e2e/lib/langbot-e2e.mjs";

const root = process.cwd();

test("repo root detects the skills tree before generated bin exists", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-root-no-bin-"));
  try {
    mkdirSync(join(tmp, "schemas"), { recursive: true });
    mkdirSync(join(tmp, "skills", "langbot-testing"), { recursive: true });
    writeFileSync(join(tmp, "skills.index.json"), "{}");
    writeFileSync(join(tmp, "schemas", "case.schema.json"), "{}");
    assert.equal(repoRoot(join(tmp, "skills", "langbot-testing")), tmp);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("e2e helpers resolve embedded LangBot repo from skills cwd", async () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-langbot-repo-detect-"));
  try {
    const repo = join(tmp, "LangBot");
    const skills = join(repo, "skills");
    mkdirSync(join(repo, "data"), { recursive: true });
    mkdirSync(skills, { recursive: true });
    writeFileSync(
      join(repo, "data", "config.yaml"),
      "system:\n  recovery_key: test\n",
    );

    assert.equal(await resolveLangBotRepo("", skills), repo);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("e2e browser diagnostics fail on console server errors", async () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-browser-diagnostics-"));
  try {
    const consoleLog = join(tmp, "console.log");
    const networkLog = join(tmp, "network.log");
    writeFileSync(
      consoleLog,
      [
        "[2026-06-30T03:02:49.702+08:00] [error] Failed to load resource: the server responded with a status of 500 ()",
        "[2026-06-30T03:02:49.703+08:00] [error] Server error: Action list_plugins call timed out",
      ].join("\n"),
    );
    writeFileSync(
      networkLog,
      "[2026-06-30T03:02:49.701+08:00] [response] 500 http://127.0.0.1:5300/api/v1/plugins\n",
    );

    const result = await scanBrowserDiagnostics({ consoleLog, networkLog });

    assert.equal(result.status, "fail");
    assert.match(result.reason, /Browser diagnostics found/);
    assert.ok(
      result.findings.some(
        (finding: { kind: string }) => finding.kind === "api_server_error",
      ),
    );
    assert.ok(
      result.findings.some(
        (finding: { kind: string }) => finding.kind === "http_5xx",
      ),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("e2e helper can inject a local login token into a fresh browser context", async () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-auth-helper-"));
  const previousFetch = globalThis.fetch;
  const previousRepo = process.env.LANGBOT_REPO;
  try {
    const repo = join(tmp, "LangBot");
    mkdirSync(join(repo, "data"), { recursive: true });
    writeFileSync(
      join(repo, "data", "config.yaml"),
      "system:\n  recovery_key: recovery-test\n",
    );
    process.env.LANGBOT_REPO = repo;

    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      if (url.endsWith("/api/v1/user/reset-password")) {
        return new Response(JSON.stringify({ code: 0 }), { status: 200 });
      }
      if (url.endsWith("/api/v1/user/auth")) {
        return new Response(
          JSON.stringify({ code: 0, data: { token: "fresh-token" } }),
          { status: 200 },
        );
      }
      if (url.endsWith("/api/v1/user/check-token")) {
        const auth = init?.headers && typeof init.headers === "object"
          ? (init.headers as Record<string, string>).Authorization
          : "";
        return new Response(
          JSON.stringify({
            code: auth === "Bearer fresh-token" ? 0 : -1,
            msg: auth === "Bearer fresh-token" ? "ok" : "missing token",
          }),
          { status: auth === "Bearer fresh-token" ? 200 : 401 },
        );
      }
      return new Response(JSON.stringify({ code: -1, msg: "unexpected" }), {
        status: 404,
      });
    }) as typeof fetch;

    let token = "";
    const page = {
      addInitScript: async () => {},
      goto: async () => {},
      evaluate: async (fn: unknown, arg: string) => {
        const text = String(fn);
        if (text.includes("localStorage.setItem")) {
          token = arg;
          return undefined;
        }
        if (text.includes("localStorage.getItem")) {
          if (!token) {
            return {
              authenticated: false,
              http_status: 0,
              code: null,
              reason: "No localStorage token.",
            };
          }
          return {
            authenticated: true,
            http_status: 200,
            code: 0,
            reason: "Token accepted by backend.",
          };
        }
        return undefined;
      },
    };

    const result = await ensureAuthenticatedBrowser(page, {
      frontendUrl: "http://127.0.0.1:3000",
      backendUrl: "http://127.0.0.1:5300",
      user: "qa@example.invalid",
      password: "password",
    });

    assert.equal(result.status, "pass");
    assert.equal(result.injected, true);
    assert.equal(token, "fresh-token");
  } finally {
    globalThis.fetch = previousFetch;
    if (previousRepo === undefined) delete process.env.LANGBOT_REPO;
    else process.env.LANGBOT_REPO = previousRepo;
    rmSync(tmp, { recursive: true, force: true });
  }
});

function ctx(args: string[]): CommandContext {
  return { root, args };
}

function capture(fn: () => number): { code: number; output: string } {
  const originalLog = console.log;
  const lines: string[] = [];
  console.log = (...args: unknown[]) => {
    lines.push(args.map(String).join(" "));
  };
  try {
    const code = fn();
    return { code, output: lines.join("\n") };
  } finally {
    console.log = originalLog;
  }
}

function captureAll(fn: () => number): {
  code: number;
  output: string;
  error: string;
} {
  const originalLog = console.log;
  const originalWrite = process.stderr.write;
  const lines: string[] = [];
  const errors: string[] = [];
  console.log = (...args: unknown[]) => {
    lines.push(args.map(String).join(" "));
  };
  process.stderr.write = ((chunk: string | Uint8Array) => {
    errors.push(String(chunk));
    return true;
  }) as typeof process.stderr.write;
  try {
    const code = fn();
    return { code, output: lines.join("\n"), error: errors.join("") };
  } finally {
    console.log = originalLog;
    process.stderr.write = originalWrite;
  }
}

function suiteResult(
  caseId: string,
  runId: string,
  status = "pass",
  evidence = ["ui", "screenshot", "console", "backend_log"],
): string {
  return JSON.stringify({
    source: "final",
    case_id: caseId,
    run_id: `${runId}-${caseId}`,
    status,
    reason: `${caseId} ${status}`,
    started_at_local: "2026-05-21T10:30:00.000+08:00",
    finished_at_local: "2026-05-21T10:31:00.000+08:00",
    evidence_collected: evidence,
  });
}

function withEnv<T>(values: Record<string, string>, fn: () => T): T {
  const previous = new Map(
    Object.keys(values).map((key) => [key, process.env[key]]),
  );
  try {
    for (const [key, value] of Object.entries(values)) process.env[key] = value;
    return fn();
  } finally {
    for (const [key, value] of previous) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
}

async function captureAsync(
  fn: () => Promise<number>,
): Promise<{ code: number; output: string }> {
  const originalLog = console.log;
  const lines: string[] = [];
  console.log = (...args: unknown[]) => {
    lines.push(args.map(String).join(" "));
  };
  try {
    const code = await fn();
    return { code, output: lines.join("\n") };
  } finally {
    console.log = originalLog;
  }
}

async function startFakeProviderForTest(): Promise<{
  baseUrl: string;
  stop: () => Promise<void>;
}> {
  const child = spawn(
    process.execPath,
    [
      join(root, "scripts/e2e/fake-openai-provider.mjs"),
      "--host=127.0.0.1",
      "--port=0",
    ],
    {
      cwd: root,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );

  const started = await new Promise<{ baseUrl: string }>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error("Timed out waiting for fake provider startup."));
    }, 5000);
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
      const newline = stdout.indexOf("\n");
      if (newline < 0) return;
      clearTimeout(timer);
      try {
        const payload = JSON.parse(stdout.slice(0, newline));
        resolve({ baseUrl: payload.base_url });
      } catch (error) {
        reject(error);
      }
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("exit", (code) => {
      if (code === null) return;
      clearTimeout(timer);
      reject(
        new Error(`Fake provider exited before startup: ${code}; ${stderr}`),
      );
    });
  });

  return {
    baseUrl: started.baseUrl,
    stop: async () => {
      if (child.exitCode !== null) return;
      child.kill("SIGTERM");
      await new Promise<void>((resolve) => child.once("exit", () => resolve()));
    },
  };
}

async function requestFakeProvider(
  provider: { baseUrl: string },
  payload: Record<string, unknown>,
): Promise<Record<string, any>> {
  const response = await fetch(`${provider.baseUrl}/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "langbot-e2e-fake-model",
      stream: false,
      ...payload,
    }),
  });
  assert.equal(response.status, 200);
  return await response.json();
}

function fakeProviderMessage(json: Record<string, any>): Record<string, any> {
  return json.choices?.[0]?.message || {};
}

test("validate accepts the repository assets", () => {
  const result = capture(() => commandValidate(root));
  assert.equal(result.code, 0);
  assert.match(result.output, /^OK/m);
});

test("validate allows blank shared env values but requires declared keys", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-validate-env-template-"));
  try {
    const schemasDir = join(tmp, "schemas");
    const skillsDir = join(tmp, "skills");
    const testingDir = join(skillsDir, "langbot-testing");
    mkdirSync(schemasDir, { recursive: true });
    mkdirSync(testingDir, { recursive: true });
    for (const schemaName of [
      "case.schema.json",
      "suite.schema.json",
      "troubleshooting.schema.json",
      "skill-index.schema.json",
    ]) {
      writeFileSync(join(schemasDir, schemaName), "{}");
    }
    writeFileSync(
      join(testingDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );
    const envText = [
      "LANGBOT_FRONTEND_URL=http://127.0.0.1:3000",
      "LANGBOT_BACKEND_URL=http://127.0.0.1:5300",
      "LANGBOT_DEV_FRONTEND_URL=http://127.0.0.1:3000",
      "LANGBOT_REPO=",
      "LANGBOT_WEB_REPO=",
      "LANGBOT_BROWSER_PROFILE=",
      "LANGBOT_CHROMIUM_EXECUTABLE=",
    ].join("\n");
    writeFileSync(join(skillsDir, ".env"), envText);
    writeFileSync(join(skillsDir, ".env.example"), envText);

    const result = capture(() => commandValidate(tmp));

    assert.equal(result.code, 0);
    assert.match(result.output, /^OK/m);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("index includes case summaries for agent discovery", () => {
  const result = capture(() => commandIndex({ root, args: ["index"] }));
  assert.equal(result.code, 0);
  const index = JSON.parse(
    readFileSync(join(root, "skills.index.json"), "utf8"),
  );
  const testing = index.skills.find(
    (skill: { name: string }) => skill.name === "langbot-testing",
  );
  assert.ok(testing);
  assert.ok(
    testing.case_summaries.some(
      (item: { id: string; priority: string; evidence_required: string[] }) =>
        item.id === "pipeline-debug-chat" &&
        item.priority === "p0" &&
        item.evidence_required.includes("backend_log"),
    ),
  );
  assert.ok(
    testing.case_summaries.some(
      (item: {
        id: string;
        setup_automation: string[];
        setup_provides_env: string[];
      }) =>
        item.id === "agent-runner-qa-debug-chat" &&
        item.setup_automation.includes("case:agent-runner-live-install") &&
        item.setup_provides_env.includes(
          "LANGBOT_QA_AGENT_RUNNER_PIPELINE_URL",
        ),
    ),
  );
  assert.ok(
    testing.suite_summaries.some(
      (item: { id: string; cases: string[] }) =>
        item.id === "core-smoke" && item.cases.includes("pipeline-debug-chat"),
    ),
  );
  assert.ok(
    testing.fixtures.some(
      (item: { id: string; related_cases: string[] }) =>
        item.id === "mcp-stdio-echo-server" &&
        item.related_cases.includes("mcp-stdio-tool-call"),
    ),
  );
});

test("index check detects stale index without writing", () => {
  const path = join(root, "skills.index.json");
  const current = capture(() => commandIndex({ root, args: ["index"] }));
  assert.equal(current.code, 0);

  const fresh = readFileSync(path, "utf8");
  try {
    const ok = capture(() =>
      commandIndex({ root, args: ["index", "--check"] }),
    );
    assert.equal(ok.code, 0);
    assert.match(ok.output, /^OK /);

    writeFileSync(path, "{}\n");
    const stale = captureAll(() =>
      commandIndex({ root, args: ["index", "--check"] }),
    );
    assert.equal(stale.code, 1);
    assert.match(stale.error, /index is stale/);
    assert.equal(readFileSync(path, "utf8"), "{}\n");
  } finally {
    writeFileSync(path, fresh);
  }
});

test("case list exposes seeded QA cases", () => {
  const result = capture(() => commandCaseList(ctx(["case", "list"])));
  assert.equal(result.code, 0);
  assert.match(result.output, /pipeline-debug-chat/);
  assert.match(result.output, /provider-deepseek/);
  assert.match(result.output, /webui-login-state/);
});

test("case list JSON filters by reusable agent-selection metadata", () => {
  const result = capture(() =>
    commandCaseList(
      ctx(["case", "list", "--json", "--priority", "p0", "--automation"]),
    ),
  );
  assert.equal(result.code, 0);
  const rows = JSON.parse(result.output);
  assert.ok(rows.length >= 2);
  assert.ok(rows.every((row: { priority: string }) => row.priority === "p0"));
  assert.ok(rows.every((row: { automation: string }) => row.automation));
  assert.ok(
    rows.some(
      (row: { id: string; evidence_required: string[]; readiness: string }) =>
        row.id === "pipeline-debug-chat" &&
        row.evidence_required.includes("backend_log") &&
        row.readiness,
    ),
  );
});

test("case list distinguishes machine readiness from manual precondition checks", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-case-manual-readiness-"));
  try {
    const skillDir = join(tmp, "skills", "langbot-testing");
    mkdirSync(join(skillDir, "cases"), { recursive: true });
    writeFileSync(
      join(skillDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );
    writeFileSync(
      join(tmp, "skills", ".env"),
      "LANGBOT_FRONTEND_URL=http://127.0.0.1:3000\n",
    );
    writeFileSync(
      join(skillDir, "cases", "manual-case.yaml"),
      [
        "id: manual-case",
        "title: Manual Case",
        "mode: agent-browser",
        "area: pipeline",
        "type: smoke",
        "priority: p2",
        "risk: medium",
        "ci_eligible: false",
        "tags:",
        "  - smoke",
        "skills:",
        "  - langbot-testing",
        "env:",
        "  - LANGBOT_FRONTEND_URL",
        "preconditions:",
        "  - Confirm the target pipeline is safe to modify.",
        "steps:",
        "  - Open the page.",
        "checks:",
        "  - UI: Page opens.",
        "evidence_required:",
        "  - ui",
      ].join("\n"),
    );

    const machineReady = capture(() =>
      commandCaseList({ root: tmp, args: ["case", "list", "--machine-ready"] }),
    );
    assert.equal(machineReady.code, 0);
    assert.match(machineReady.output, /manual-case/);
    assert.match(machineReady.output, /manual-check/);

    const ready = capture(() =>
      commandCaseList({ root: tmp, args: ["case", "list", "--ready"] }),
    );
    assert.equal(ready.code, 0);
    assert.doesNotMatch(ready.output, /manual-case/);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("case show prints structured agent-browser case", () => {
  const result = capture(() =>
    commandCaseShow(ctx(["case", "show", "pipeline-debug-chat"])),
  );
  assert.equal(result.code, 0);
  assert.match(result.output, /^id: pipeline-debug-chat/m);
  assert.match(result.output, /^mode: agent-browser/m);
  assert.match(result.output, /^checks:/m);
});

test("case new writes required selection metadata", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-case-new-"));
  try {
    const skillDir = join(tmp, "skills", "langbot-testing");
    mkdirSync(skillDir, { recursive: true });
    writeFileSync(
      join(skillDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );

    const result = capture(() =>
      commandCaseNew({
        root: tmp,
        args: ["case", "new", "new-case", "--title", "New Case"],
      }),
    );

    assert.equal(result.code, 0);
    const text = readFileSync(join(skillDir, "cases", "new-case.yaml"), "utf8");
    assert.match(text, /^priority: p2/m);
    assert.match(text, /^risk: medium/m);
    assert.match(text, /^ci_eligible: false/m);
    assert.match(text, /^evidence_required:/m);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("suite list and plan expose reusable case groups", () => {
  const list = capture(() =>
    commandSuiteList(ctx(["suite", "list", "--json", "--priority", "p0"])),
  );
  assert.equal(list.code, 0);
  const suites = JSON.parse(list.output);
  assert.ok(
    suites.some(
      (suite: { id: string; cases: string[] }) =>
        suite.id === "core-smoke" && suite.cases.includes("webui-login-state"),
    ),
  );

  const plan = capture(() =>
    commandSuitePlan(ctx(["suite", "plan", "core-smoke", "--json"])),
  );
  assert.equal(plan.code, 0);
  const suitePlan = JSON.parse(plan.output);
  assert.equal(suitePlan.id, "core-smoke");
  assert.ok(
    suitePlan.cases.some(
      (item: { id: string; evidence_required: string[] }) =>
        item.id === "pipeline-debug-chat" &&
        item.evidence_required.includes("backend_log"),
    ),
  );
  assert.ok(
    suitePlan.commands.some(
      (item: { id: string; automation: string }) =>
        item.id === "pipeline-debug-chat" &&
        item.automation.includes("test run"),
    ),
  );

  const localAgent = capture(() =>
    commandSuitePlan(ctx(["suite", "plan", "local-agent-gate", "--json"])),
  );
  assert.equal(localAgent.code, 0);
  const localAgentPlan = JSON.parse(localAgent.output);
  assert.ok(
    ["ready", "missing", "manual_check"].includes(
      localAgentPlan.readiness.status,
    ),
  );
  const basic = localAgentPlan.cases.find(
    (item: { id: string }) => item.id === "local-agent-basic-debug-chat",
  );
  assert.equal(basic.automation_readiness.pipeline_env_required, true);
});

test("suite show prints structured suite YAML", () => {
  const result = capture(() =>
    commandSuiteShow(ctx(["suite", "show", "local-agent-gate"])),
  );
  assert.equal(result.code, 0);
  assert.match(result.output, /^id: local-agent-gate/m);
  assert.match(result.output, /^cases:/m);
  assert.match(result.output, /local-agent-effective-prompt-debug-chat/);
});

test("suite start creates a run handoff with per-case evidence commands", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-suite-start-"));
  try {
    const evidenceRoot = join(tmp, "evidence");
    const result = capture(() =>
      commandSuiteStart(
        ctx([
          "suite",
          "start",
          "core-smoke",
          "--run-id",
          "core-smoke-local",
          "--evidence-dir",
          evidenceRoot,
          "--json",
        ]),
      ),
    );
    assert.equal(result.code, 0);
    const start = JSON.parse(result.output);
    assert.equal(start.suite.id, "core-smoke");
    assert.equal(start.run_id, "core-smoke-local");
    assert.equal(start.evidence_root, evidenceRoot);
    assert.equal(start.manifest_path, join(evidenceRoot, "suite-start.json"));
    assert.equal(start.handoff_path, join(evidenceRoot, "suite-start.md"));
    assert.match(start.report_command, /bin\/lbs suite report core-smoke/);
    assert.ok(existsSync(join(evidenceRoot, "suite-start.json")));
    assert.ok(existsSync(join(evidenceRoot, "suite-start.md")));
    const pipeline = start.cases.find(
      (item: { id: string }) => item.id === "pipeline-debug-chat",
    );
    assert.ok(pipeline);
    assert.ok(existsSync(join(evidenceRoot, "pipeline-debug-chat")));
    assert.match(
      pipeline.automation_command,
      /bin\/lbs test run pipeline-debug-chat/,
    );
    assert.match(
      pipeline.report_command,
      /--evidence-dir .+pipeline-debug-chat/,
    );
    assert.match(
      pipeline.result_command_template,
      /bin\/lbs test result pipeline-debug-chat/,
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("suite report aggregates case result JSON files", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-suite-report-"));
  try {
    const evidenceRoot = join(tmp, "suite-evidence");
    const runId = "suite-report-run";
    for (const [caseId, status] of [
      ["webui-login-state", "pass"],
      ["pipeline-debug-chat", "pass"],
      ["local-agent-basic-debug-chat", "env_issue"],
    ]) {
      const dir = join(evidenceRoot, caseId);
      mkdirSync(dir, { recursive: true });
      writeFileSync(
        join(dir, "result.json"),
        suiteResult(caseId, runId, status),
      );
    }

    const result = capture(() =>
      commandSuiteReport(
        ctx([
          "suite",
          "report",
          "core-smoke",
          "--run-id",
          runId,
          "--evidence-dir",
          evidenceRoot,
          "--json",
        ]),
      ),
    );

    assert.equal(result.code, 0);
    const report = JSON.parse(result.output);
    assert.equal(report.status, "env_issue");
    assert.equal(report.counts.pass, 2);
    assert.equal(report.counts.env_issue, 1);
    assert.ok(
      report.cases.some(
        (item: { id: string; result: { status: string } }) =>
          item.id === "local-agent-basic-debug-chat" &&
          item.result.status === "env_issue",
      ),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("suite report treats pass without required evidence as incomplete", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-suite-report-evidence-"));
  try {
    const evidenceRoot = join(tmp, "suite-evidence");
    const runId = "suite-report-evidence";
    for (const caseId of [
      "webui-login-state",
      "pipeline-debug-chat",
      "local-agent-basic-debug-chat",
    ]) {
      const dir = join(evidenceRoot, caseId);
      mkdirSync(dir, { recursive: true });
      writeFileSync(
        join(dir, "result.json"),
        suiteResult(caseId, runId, "pass", ["ui"]),
      );
    }

    const result = capture(() =>
      commandSuiteReport(
        ctx([
          "suite",
          "report",
          "core-smoke",
          "--run-id",
          runId,
          "--evidence-dir",
          evidenceRoot,
          "--json",
        ]),
      ),
    );

    assert.equal(result.code, 0);
    const report = JSON.parse(result.output);
    assert.equal(report.status, "incomplete");
    assert.ok(
      report.cases.some(
        (item: { id: string; result: { evidence_missing: string[] } }) =>
          item.id === "pipeline-debug-chat" &&
          item.result.evidence_missing.includes("backend_log"),
      ),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("suite report marks missing case evidence as incomplete", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-suite-report-missing-"));
  try {
    const evidenceRoot = join(tmp, "suite-evidence");
    const runId = "suite-report-missing";
    mkdirSync(join(evidenceRoot, "webui-login-state"), { recursive: true });
    writeFileSync(
      join(evidenceRoot, "webui-login-state", "result.json"),
      suiteResult("webui-login-state", runId, "pass"),
    );

    const result = capture(() =>
      commandSuiteReport(
        ctx([
          "suite",
          "report",
          "core-smoke",
          "--run-id",
          runId,
          "--evidence-dir",
          evidenceRoot,
          "--json",
        ]),
      ),
    );

    assert.equal(result.code, 0);
    const report = JSON.parse(result.output);
    assert.equal(report.status, "incomplete");
    assert.ok(
      report.cases.some(
        (item: { id: string; result: { status: string } }) =>
          item.id === "pipeline-debug-chat" && item.result.status === "missing",
      ),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("suite report rejects result files from the wrong case or run", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-suite-report-mismatch-"));
  try {
    const evidenceRoot = join(tmp, "suite-evidence");
    const runId = "suite-report-mismatch";
    for (const caseId of [
      "webui-login-state",
      "pipeline-debug-chat",
      "local-agent-basic-debug-chat",
    ]) {
      const dir = join(evidenceRoot, caseId);
      mkdirSync(dir, { recursive: true });
      writeFileSync(
        join(dir, "result.json"),
        suiteResult(caseId, runId, "pass"),
      );
    }
    writeFileSync(
      join(evidenceRoot, "pipeline-debug-chat", "result.json"),
      suiteResult("webui-login-state", runId, "pass"),
    );
    writeFileSync(
      join(evidenceRoot, "local-agent-basic-debug-chat", "result.json"),
      suiteResult("local-agent-basic-debug-chat", "old-run", "pass"),
    );

    const result = capture(() =>
      commandSuiteReport(
        ctx([
          "suite",
          "report",
          "core-smoke",
          "--run-id",
          runId,
          "--evidence-dir",
          evidenceRoot,
          "--json",
        ]),
      ),
    );

    assert.equal(result.code, 0);
    const report = JSON.parse(result.output);
    assert.equal(report.status, "fail");
    assert.ok(
      report.cases.some(
        (item: { id: string; result: { status: string; reason: string } }) =>
          item.id === "pipeline-debug-chat" &&
          item.result.status === "invalid" &&
          item.result.reason.includes("case_id mismatch"),
      ),
    );
    assert.ok(
      report.cases.some(
        (item: { id: string; result: { status: string; reason: string } }) =>
          item.id === "local-agent-basic-debug-chat" &&
          item.result.status === "invalid" &&
          item.result.reason.includes("run_id mismatch"),
      ),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("suite run executes automated cases and aggregates a verdict", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-suite-run-"));
  try {
    const skillDir = join(tmp, "skills", "langbot-testing");
    const casesDir = join(skillDir, "cases");
    const suitesDir = join(skillDir, "suites");
    const scriptsDir = join(tmp, "scripts");
    mkdirSync(casesDir, { recursive: true });
    mkdirSync(suitesDir, { recursive: true });
    mkdirSync(scriptsDir, { recursive: true });
    writeFileSync(
      join(skillDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );
    writeFileSync(join(tmp, "skills", ".env"), "");
    writeFileSync(
      join(casesDir, "one.yaml"),
      [
        "id: one",
        "title: One",
        "mode: probe",
        "area: qa",
        "type: smoke",
        "priority: p2",
        "risk: low",
        "ci_eligible: true",
        "automation: scripts/pass.mjs",
        "evidence_required:",
        "  - filesystem",
      ].join("\n"),
    );
    writeFileSync(
      join(casesDir, "two.yaml"),
      [
        "id: two",
        "title: Two",
        "mode: probe",
        "area: qa",
        "type: smoke",
        "priority: p2",
        "risk: low",
        "ci_eligible: true",
        "automation: scripts/pass.mjs",
        "evidence_required:",
        "  - filesystem",
      ].join("\n"),
    );
    writeFileSync(
      join(suitesDir, "mini.yaml"),
      [
        "id: mini",
        "title: Mini",
        "description: Mini suite.",
        "type: smoke",
        "priority: p2",
        "tags:",
        "  - qa",
        "cases:",
        "  - one",
        "  - two",
      ].join("\n"),
    );
    writeFileSync(
      join(scriptsDir, "pass.mjs"),
      [
        "import { mkdirSync, writeFileSync } from 'node:fs';",
        "import { join } from 'node:path';",
        "mkdirSync(process.env.LBS_EVIDENCE_DIR, { recursive: true });",
        "writeFileSync(join(process.env.LBS_EVIDENCE_DIR, 'result.json'), JSON.stringify({",
        "  case_id: process.env.LBS_CASE_ID,",
        "  run_id: process.env.LBS_RUN_ID,",
        "  status: 'pass',",
        "  reason: `${process.env.LBS_CASE_ID} pass`,",
        "  evidence_collected: ['filesystem']",
        "}));",
        "writeFileSync(join(process.env.LBS_EVIDENCE_DIR, 'automation-result.json'), JSON.stringify({ status: 'pass' }));",
      ].join("\n"),
    );

    const result = capture(() =>
      commandSuiteRun({
        root: tmp,
        args: [
          "suite",
          "run",
          "mini",
          "--run-id",
          "mini-run",
          "--evidence-dir",
          join(tmp, "evidence"),
          "--json",
        ],
      }),
    );

    assert.equal(result.code, 0);
    const payload = JSON.parse(result.output);
    assert.equal(payload.report.status, "pass");
    assert.equal(payload.report.counts.pass, 2);
    assert.deepEqual(
      payload.executions.map((item: { status: string }) => item.status),
      ["ok", "ok"],
    );
    assert.ok(existsSync(join(tmp, "evidence", "one", "result.json")));
    assert.ok(existsSync(join(tmp, "evidence", "two", "result.json")));
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("suite run JSON captures failed case output", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-suite-run-fail-"));
  try {
    const skillDir = join(tmp, "skills", "langbot-testing");
    const casesDir = join(skillDir, "cases");
    const suitesDir = join(skillDir, "suites");
    const scriptsDir = join(tmp, "scripts");
    mkdirSync(casesDir, { recursive: true });
    mkdirSync(suitesDir, { recursive: true });
    mkdirSync(scriptsDir, { recursive: true });
    writeFileSync(
      join(skillDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );
    writeFileSync(join(tmp, "skills", ".env"), "");
    writeFileSync(
      join(casesDir, "fail-case.yaml"),
      [
        "id: fail-case",
        "title: Fail Case",
        "mode: probe",
        "area: qa",
        "type: smoke",
        "priority: p2",
        "risk: low",
        "ci_eligible: true",
        "automation: scripts/fail.mjs",
      ].join("\n"),
    );
    writeFileSync(
      join(suitesDir, "mini.yaml"),
      [
        "id: mini",
        "title: Mini",
        "description: Mini suite.",
        "type: smoke",
        "priority: p2",
        "tags:",
        "  - qa",
        "cases:",
        "  - fail-case",
      ].join("\n"),
    );
    writeFileSync(
      join(scriptsDir, "fail.mjs"),
      "console.error('child failure detail'); process.exit(1);\n",
    );

    const result = capture(() =>
      commandSuiteRun({
        root: tmp,
        args: [
          "suite",
          "run",
          "mini",
          "--run-id",
          "mini-run",
          "--evidence-dir",
          join(tmp, "evidence"),
          "--json",
        ],
      }),
    );

    assert.equal(result.code, 1);
    const payload = JSON.parse(result.output);
    assert.equal(payload.executions[0].status, "nonzero");
    assert.match(payload.executions[0].stderr, /child failure detail/);
    assert.equal(payload.report.status, "fail");
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("suite run preserves classified env_issue automation results", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-suite-run-env-issue-"));
  try {
    const skillDir = join(tmp, "skills", "langbot-testing");
    const casesDir = join(skillDir, "cases");
    const suitesDir = join(skillDir, "suites");
    const scriptsDir = join(tmp, "scripts");
    mkdirSync(casesDir, { recursive: true });
    mkdirSync(suitesDir, { recursive: true });
    mkdirSync(scriptsDir, { recursive: true });
    writeFileSync(
      join(skillDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );
    writeFileSync(join(tmp, "skills", ".env"), "");
    writeFileSync(
      join(casesDir, "env-case.yaml"),
      [
        "id: env-case",
        "title: Env Case",
        "mode: probe",
        "area: qa",
        "type: smoke",
        "priority: p2",
        "risk: low",
        "ci_eligible: true",
        "automation: scripts/env-issue.mjs",
        "evidence_required:",
        "  - filesystem",
      ].join("\n"),
    );
    writeFileSync(
      join(suitesDir, "mini.yaml"),
      [
        "id: mini",
        "title: Mini",
        "description: Mini suite.",
        "type: smoke",
        "priority: p2",
        "tags:",
        "  - qa",
        "cases:",
        "  - env-case",
      ].join("\n"),
    );
    writeFileSync(
      join(scriptsDir, "env-issue.mjs"),
      [
        "import { mkdirSync, writeFileSync } from 'node:fs';",
        "import { join } from 'node:path';",
        "mkdirSync(process.env.LBS_EVIDENCE_DIR, { recursive: true });",
        "const result = {",
        "  case_id: process.env.LBS_CASE_ID,",
        "  run_id: process.env.LBS_RUN_ID,",
        "  status: 'env_issue',",
        "  reason: 'backend not reachable',",
        "  evidence_collected: ['filesystem']",
        "};",
        "writeFileSync(join(process.env.LBS_EVIDENCE_DIR, 'result.json'), JSON.stringify(result));",
        "writeFileSync(join(process.env.LBS_EVIDENCE_DIR, 'automation-result.json'), JSON.stringify({ ...result, source: 'automation' }));",
        "process.exit(2);",
      ].join("\n"),
    );

    const result = capture(() =>
      commandSuiteRun({
        root: tmp,
        args: [
          "suite",
          "run",
          "mini",
          "--run-id",
          "mini-run",
          "--evidence-dir",
          join(tmp, "evidence"),
          "--json",
        ],
      }),
    );

    assert.equal(result.code, 2);
    const payload = JSON.parse(result.output);
    assert.equal(payload.executions[0].status, "classified");
    assert.equal(payload.report.status, "env_issue");
    assert.equal(payload.report.execution_status, "ok");
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("suite run failure cannot be masked by stale pass result", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-suite-run-stale-pass-"));
  try {
    const skillDir = join(tmp, "skills", "langbot-testing");
    const casesDir = join(skillDir, "cases");
    const suitesDir = join(skillDir, "suites");
    const scriptsDir = join(tmp, "scripts");
    const evidenceDir = join(tmp, "evidence");
    mkdirSync(casesDir, { recursive: true });
    mkdirSync(suitesDir, { recursive: true });
    mkdirSync(scriptsDir, { recursive: true });
    mkdirSync(join(evidenceDir, "fail-case"), { recursive: true });
    writeFileSync(
      join(skillDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );
    writeFileSync(join(tmp, "skills", ".env"), "");
    writeFileSync(
      join(casesDir, "fail-case.yaml"),
      [
        "id: fail-case",
        "title: Fail Case",
        "mode: probe",
        "area: qa",
        "type: smoke",
        "priority: p2",
        "risk: low",
        "ci_eligible: true",
        "automation: scripts/fail.mjs",
        "evidence_required:",
        "  - filesystem",
      ].join("\n"),
    );
    writeFileSync(
      join(suitesDir, "mini.yaml"),
      [
        "id: mini",
        "title: Mini",
        "description: Mini suite.",
        "type: smoke",
        "priority: p2",
        "tags:",
        "  - qa",
        "cases:",
        "  - fail-case",
      ].join("\n"),
    );
    writeFileSync(join(scriptsDir, "fail.mjs"), "process.exit(1);\n");
    writeFileSync(
      join(evidenceDir, "fail-case", "result.json"),
      JSON.stringify({
        case_id: "fail-case",
        run_id: "stale-run-fail-case",
        status: "pass",
        evidence_collected: ["filesystem"],
      }),
    );

    const result = capture(() =>
      commandSuiteRun({
        root: tmp,
        args: [
          "suite",
          "run",
          "mini",
          "--run-id",
          "stale-run",
          "--evidence-dir",
          evidenceDir,
          "--json",
        ],
      }),
    );

    assert.equal(result.code, 1);
    const payload = JSON.parse(result.output);
    assert.equal(payload.executions[0].status, "nonzero");
    assert.equal(payload.report.status, "fail");
    assert.equal(payload.report.execution_status, "fail");
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("suite run dry-run plans automation without creating evidence", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-suite-run-dry-"));
  try {
    const skillDir = join(tmp, "skills", "langbot-testing");
    const casesDir = join(skillDir, "cases");
    const suitesDir = join(skillDir, "suites");
    const scriptsDir = join(tmp, "scripts");
    mkdirSync(casesDir, { recursive: true });
    mkdirSync(suitesDir, { recursive: true });
    mkdirSync(scriptsDir, { recursive: true });
    writeFileSync(
      join(skillDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );
    writeFileSync(join(tmp, "skills", ".env"), "");
    writeFileSync(
      join(casesDir, "dry-case.yaml"),
      [
        "id: dry-case",
        "title: Dry Case",
        "mode: probe",
        "area: qa",
        "type: smoke",
        "priority: p2",
        "risk: low",
        "ci_eligible: true",
        "automation: scripts/fail-if-run.mjs",
      ].join("\n"),
    );
    writeFileSync(
      join(suitesDir, "dry-suite.yaml"),
      [
        "id: dry-suite",
        "title: Dry Suite",
        "description: Dry run suite.",
        "type: smoke",
        "priority: p2",
        "tags:",
        "  - qa",
        "cases:",
        "  - dry-case",
      ].join("\n"),
    );
    writeFileSync(join(scriptsDir, "fail-if-run.mjs"), "process.exit(9);\n");

    const evidenceDir = join(tmp, "evidence");
    const result = capture(() =>
      commandSuiteRun({
        root: tmp,
        args: [
          "suite",
          "run",
          "dry-suite",
          "--run-id",
          "dry-run",
          "--evidence-dir",
          evidenceDir,
          "--dry-run",
          "--json",
        ],
      }),
    );

    assert.equal(result.code, 0);
    const payload = JSON.parse(result.output);
    assert.equal(payload.executions[0].status, "planned");
    assert.match(payload.executions[0].command, /test run dry-case/);
    assert.equal(payload.report.status, "incomplete");
    assert.equal(existsSync(evidenceDir), false);
    assert.equal(existsSync(join(tmp, "reports", "dry-run.md")), false);

    const markdown = capture(() =>
      commandSuiteRun({
        root: tmp,
        args: [
          "suite",
          "run",
          "dry-suite",
          "--run-id",
          "dry-run-markdown",
          "--evidence-dir",
          join(tmp, "evidence-md"),
          "--dry-run",
        ],
      }),
    );
    assert.equal(markdown.code, 0);
    assert.match(markdown.output, /# Suite Report: dry-suite/);
    assert.equal(
      existsSync(join(tmp, "reports", "dry-run-markdown.md")),
      false,
    );
    assert.equal(existsSync(join(tmp, "evidence-md")), false);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("suite run skips manual-check cases unless explicitly included", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-suite-run-manual-"));
  try {
    const skillDir = join(tmp, "skills", "langbot-testing");
    const casesDir = join(skillDir, "cases");
    const suitesDir = join(skillDir, "suites");
    const scriptsDir = join(tmp, "scripts");
    mkdirSync(casesDir, { recursive: true });
    mkdirSync(suitesDir, { recursive: true });
    mkdirSync(scriptsDir, { recursive: true });
    writeFileSync(
      join(skillDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );
    writeFileSync(join(tmp, "skills", ".env"), "");
    writeFileSync(
      join(casesDir, "manual-case.yaml"),
      [
        "id: manual-case",
        "title: Manual Case",
        "mode: probe",
        "area: qa",
        "type: smoke",
        "priority: p2",
        "risk: low",
        "ci_eligible: true",
        "preconditions:",
        "  - Confirm this case is safe to run.",
        "automation: scripts/pass.mjs",
        "evidence_required:",
        "  - filesystem",
      ].join("\n"),
    );
    writeFileSync(
      join(suitesDir, "manual-suite.yaml"),
      [
        "id: manual-suite",
        "title: Manual Suite",
        "description: Manual check suite.",
        "type: smoke",
        "priority: p2",
        "tags:",
        "  - qa",
        "cases:",
        "  - manual-case",
      ].join("\n"),
    );
    writeFileSync(
      join(scriptsDir, "pass.mjs"),
      [
        "import { mkdirSync, writeFileSync } from 'node:fs';",
        "import { join } from 'node:path';",
        "mkdirSync(process.env.LBS_EVIDENCE_DIR, { recursive: true });",
        "writeFileSync(join(process.env.LBS_EVIDENCE_DIR, 'result.json'), JSON.stringify({ case_id: process.env.LBS_CASE_ID, run_id: process.env.LBS_RUN_ID, status: 'pass', evidence_collected: ['filesystem'] }));",
      ].join("\n"),
    );

    const skipped = capture(() =>
      commandSuiteRun({
        root: tmp,
        args: [
          "suite",
          "run",
          "manual-suite",
          "--run-id",
          "manual-run",
          "--evidence-dir",
          join(tmp, "evidence"),
          "--json",
        ],
      }),
    );
    assert.equal(skipped.code, 1);
    const skippedPayload = JSON.parse(skipped.output);
    assert.equal(skippedPayload.executions[0].status, "skipped");
    assert.match(skippedPayload.executions[0].reason, /manual_check/);
    assert.equal(
      existsSync(join(tmp, "evidence", "manual-case", "result.json")),
      false,
    );

    const included = capture(() =>
      commandSuiteRun({
        root: tmp,
        args: [
          "suite",
          "run",
          "manual-suite",
          "--run-id",
          "manual-run-included",
          "--evidence-dir",
          join(tmp, "evidence-included"),
          "--include-manual-check",
          "--json",
        ],
      }),
    );
    assert.equal(included.code, 0);
    const includedPayload = JSON.parse(included.output);
    assert.equal(includedPayload.executions[0].status, "ok");
    assert.equal(includedPayload.report.status, "pass");
    assert.ok(
      existsSync(join(tmp, "evidence-included", "manual-case", "result.json")),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("suite run skips cases with missing machine readiness unless explicitly included", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-suite-run-readiness-"));
  try {
    const skillDir = join(tmp, "skills", "langbot-testing");
    const casesDir = join(skillDir, "cases");
    const suitesDir = join(skillDir, "suites");
    const fixturesDir = join(skillDir, "fixtures");
    const scriptsDir = join(tmp, "scripts");
    mkdirSync(casesDir, { recursive: true });
    mkdirSync(suitesDir, { recursive: true });
    mkdirSync(fixturesDir, { recursive: true });
    mkdirSync(scriptsDir, { recursive: true });
    writeFileSync(
      join(skillDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );
    writeFileSync(join(tmp, "skills", ".env"), "");
    writeFileSync(
      join(casesDir, "not-ready-case.yaml"),
      [
        "id: not-ready-case",
        "title: Not Ready Case",
        "mode: probe",
        "area: qa",
        "type: smoke",
        "priority: p2",
        "risk: low",
        "ci_eligible: true",
        "env:",
        "  - LBS_TEST_SUITE_RUN_MISSING_ENV",
        "automation_env:",
        "  - LBS_TEST_SUITE_RUN_MISSING_AUTOMATION_ENV",
        "automation: scripts/pass.mjs",
        "evidence_required:",
        "  - filesystem",
      ].join("\n"),
    );
    writeFileSync(
      join(fixturesDir, "fixtures.json"),
      `${JSON.stringify(
        [
          {
            id: "missing-fixture",
            title: "Missing fixture",
            kind: "file",
            path: "fixtures/missing.txt",
            related_cases: ["not-ready-case"],
            checks: ["exists"],
          },
        ],
        null,
        2,
      )}\n`,
    );
    writeFileSync(
      join(suitesDir, "readiness-suite.yaml"),
      [
        "id: readiness-suite",
        "title: Readiness Suite",
        "description: Readiness suite.",
        "type: smoke",
        "priority: p2",
        "tags:",
        "  - qa",
        "cases:",
        "  - not-ready-case",
      ].join("\n"),
    );
    writeFileSync(
      join(scriptsDir, "pass.mjs"),
      [
        "import { mkdirSync, writeFileSync } from 'node:fs';",
        "import { join } from 'node:path';",
        "mkdirSync(process.env.LBS_EVIDENCE_DIR, { recursive: true });",
        "writeFileSync(join(process.env.LBS_EVIDENCE_DIR, 'result.json'), JSON.stringify({ case_id: process.env.LBS_CASE_ID, run_id: process.env.LBS_RUN_ID, status: 'pass', evidence_collected: ['filesystem'] }));",
      ].join("\n"),
    );

    const skipped = capture(() =>
      commandSuiteRun({
        root: tmp,
        args: [
          "suite",
          "run",
          "readiness-suite",
          "--run-id",
          "readiness-run",
          "--evidence-dir",
          join(tmp, "evidence"),
          "--json",
        ],
      }),
    );
    assert.equal(skipped.code, 1);
    const skippedPayload = JSON.parse(skipped.output);
    assert.equal(skippedPayload.executions[0].status, "skipped");
    assert.match(skippedPayload.executions[0].reason, /readiness missing/);
    assert.match(
      skippedPayload.executions[0].reason,
      /LBS_TEST_SUITE_RUN_MISSING_ENV/,
    );
    assert.match(
      skippedPayload.executions[0].reason,
      /LBS_TEST_SUITE_RUN_MISSING_AUTOMATION_ENV/,
    );
    assert.match(skippedPayload.executions[0].reason, /missing-fixture/);
    assert.equal(
      existsSync(join(tmp, "evidence", "not-ready-case", "result.json")),
      false,
    );

    const included = capture(() =>
      commandSuiteRun({
        root: tmp,
        args: [
          "suite",
          "run",
          "readiness-suite",
          "--run-id",
          "readiness-run-included",
          "--evidence-dir",
          join(tmp, "evidence-included"),
          "--include-not-ready",
          "--json",
        ],
      }),
    );
    assert.equal(included.code, 0);
    const includedPayload = JSON.parse(included.output);
    assert.equal(includedPayload.executions[0].status, "ok");
    assert.equal(includedPayload.report.status, "pass");
    assert.ok(
      existsSync(
        join(tmp, "evidence-included", "not-ready-case", "result.json"),
      ),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("suite new writes a reusable suite skeleton", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-suite-new-"));
  try {
    const skillDir = join(tmp, "skills", "langbot-testing");
    mkdirSync(skillDir, { recursive: true });
    writeFileSync(
      join(skillDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );

    const result = capture(() =>
      commandSuiteNew({
        root: tmp,
        args: ["suite", "new", "new-suite", "--title", "New Suite"],
      }),
    );

    assert.equal(result.code, 0);
    const text = readFileSync(
      join(skillDir, "suites", "new-suite.yaml"),
      "utf8",
    );
    assert.match(text, /^description:/m);
    assert.match(text, /^priority: p2/m);
    assert.match(text, /^cases:/m);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("fixture list and check expose reusable fixture readiness", () => {
  const list = capture(() =>
    commandFixtureList(ctx(["fixture", "list", "langbot-testing", "--json"])),
  );
  assert.equal(list.code, 0);
  const fixtures = JSON.parse(list.output);
  assert.ok(
    fixtures.some(
      (item: { id: string; exists: boolean }) =>
        item.id === "mcp-stdio-echo-server" && item.exists === true,
    ),
  );

  const check = capture(() =>
    commandFixtureCheck(ctx(["fixture", "check", "langbot-testing", "--json"])),
  );
  assert.equal(check.code, 0);
  const report = JSON.parse(check.output);
  assert.equal(report.status, "pass");
  assert.ok(
    report.fixtures.some(
      (item: { id: string }) => item.id === "qa-plugin-smoke-package",
    ),
  );
});

test("fixture check reports missing manifest paths", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-fixture-check-"));
  try {
    const skillDir = join(tmp, "skills", "langbot-testing");
    mkdirSync(join(skillDir, "fixtures"), { recursive: true });
    writeFileSync(
      join(skillDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );
    writeFileSync(
      join(skillDir, "fixtures", "fixtures.json"),
      JSON.stringify([
        {
          id: "missing-fixture",
          title: "Missing Fixture",
          path: "fixtures/missing.txt",
        },
      ]),
    );

    const result = capture(() =>
      commandFixtureCheck({
        root: tmp,
        args: ["fixture", "check", "langbot-testing", "--json"],
      }),
    );

    assert.equal(result.code, 1);
    const report = JSON.parse(result.output);
    assert.equal(report.status, "fail");
    assert.ok(
      report.findings.some(
        (finding: { id?: string }) => finding.id === "missing-fixture",
      ),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("fixture check verifies QA AgentRunner source shape", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-fixture-check-"));
  try {
    const skillDir = join(tmp, "skills", "langbot-testing");
    const fixtureDir = join(skillDir, "fixtures", "plugins", "qa-agent-runner");
    mkdirSync(join(fixtureDir, "components", "agent_runner"), {
      recursive: true,
    });
    writeFileSync(
      join(skillDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );
    writeFileSync(
      join(skillDir, "fixtures", "fixtures.json"),
      JSON.stringify([
        {
          id: "qa-agent-runner-source",
          title: "QA AgentRunner",
          path: "fixtures/plugins/qa-agent-runner/manifest.yaml",
          checks: ["exists", "qa_agent_runner_source"],
        },
      ]),
    );
    writeFileSync(
      join(fixtureDir, "manifest.yaml"),
      "spec:\n  components:\n    AgentRunner: {}\nexecution:\n  python:\n    attr: QAAgentRunnerPlugin\n",
    );

    const result = capture(() =>
      commandFixtureCheck({
        root: tmp,
        args: ["fixture", "check", "langbot-testing", "--json"],
      }),
    );

    assert.equal(result.code, 1);
    const report = JSON.parse(result.output);
    assert.ok(
      report.findings.some(
        (finding: { kind?: string; path?: string }) =>
          finding.kind === "fixture_check_missing_file" &&
          finding.path?.endsWith("components/agent_runner/default.py"),
      ),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("fixture check accepts complete QA AgentRunner source shape", () => {
  const result = capture(() =>
    commandFixtureCheck(ctx(["fixture", "check", "langbot-testing", "--json"])),
  );
  assert.equal(result.code, 0);
  const report = JSON.parse(result.output);
  assert.ok(
    report.fixtures.some(
      (item: { id: string; checks: string[] }) =>
        item.id === "qa-agent-runner-source" &&
        item.checks.includes("qa_agent_runner_source"),
    ),
  );
});

test("fixture check rejects invalid plugin package files", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-fixture-check-"));
  try {
    const skillDir = join(tmp, "skills", "langbot-testing");
    mkdirSync(join(skillDir, "fixtures"), { recursive: true });
    writeFileSync(
      join(skillDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );
    writeFileSync(join(skillDir, "fixtures", "bad.lbpkg"), "not a zip");
    writeFileSync(
      join(skillDir, "fixtures", "fixtures.json"),
      JSON.stringify([
        {
          id: "bad-package",
          title: "Bad Package",
          path: "fixtures/bad.lbpkg",
          checks: ["exists", "zip_package"],
        },
      ]),
    );

    const result = capture(() =>
      commandFixtureCheck({
        root: tmp,
        args: ["fixture", "check", "langbot-testing", "--json"],
      }),
    );

    assert.equal(result.code, 1);
    const report = JSON.parse(result.output);
    assert.ok(
      report.findings.some(
        (finding: { kind?: string; id?: string }) =>
          finding.kind === "fixture_check_invalid_zip" &&
          finding.id === "bad-package",
      ),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("debug chat classifier prefers latest response leaf over body counts", () => {
  const result = classifyDebugChatResult({
    beforeText: "OK from an older chat",
    afterText: "OK from an older chat\nUser: say OK\nBot: OK",
    expectedText: "OK",
    prompt: "say OK",
    latestExpectedLeaf: "Bot: OK",
    latestFailureLeaf: "",
  });

  assert.equal(result.status, "pass");
  assert.match(result.reason, /latest visible response leaf/);
});

test("debug chat classifier distinguishes new failure signals from old history", () => {
  assert.equal(
    findNewFailureSignal(
      "Agent runner temporarily unavailable",
      "Agent runner temporarily unavailable",
    ),
    "",
  );
  assert.equal(
    findNewFailureSignal("", "Agent runner temporarily unavailable"),
    "Agent runner temporarily unavailable",
  );

  const result = classifyDebugChatResult({
    beforeText: "",
    afterText: "Agent runner temporarily unavailable",
    expectedText: "OK",
    prompt: "say OK",
    latestExpectedLeaf: "",
    latestFailureLeaf: "Agent runner temporarily unavailable",
  });

  assert.equal(result.status, "fail");
  assert.match(result.reason, /known failure signal/);

  const custom = classifyDebugChatResult({
    beforeText: "",
    afterText: "Bot: qa-plugin-smoke:mcp-ok-local-agent",
    expectedText: "qa_mcp_echo:mcp-ok-local-agent",
    prompt: "call mcp",
    latestExpectedLeaf: "",
    latestFailureLeaf: "Bot: qa-plugin-smoke:mcp-ok-local-agent",
    failureSignals: ["qa-plugin-smoke:mcp-ok-local-agent"],
  });

  assert.equal(custom.status, "fail");
  assert.equal(custom.failure_signal, "qa-plugin-smoke:mcp-ok-local-agent");
});

test("debug chat classifier lets new failure signals override stale expected history", () => {
  const result = classifyDebugChatResult({
    beforeText: "Bot: qa_mcp_echo:mcp-ok-local-agent",
    afterText: [
      "Bot: qa_mcp_echo:mcp-ok-local-agent",
      "User: Call qa_mcp_echo",
      "Bot: Agent runner temporarily unavailable.",
    ].join("\n"),
    expectedText: "qa_mcp_echo:mcp-ok-local-agent",
    prompt: "Call qa_mcp_echo",
    latestExpectedLeaf: "Bot: qa_mcp_echo:mcp-ok-local-agent",
    latestFailureLeaf: "Bot: Agent runner temporarily unavailable.",
  });

  assert.equal(result.status, "fail");
  assert.equal(result.failure_signal, "Agent runner temporarily unavailable");
});

test("debug chat classifier does not pass on stale expected history without a new occurrence", () => {
  const result = classifyDebugChatResult({
    beforeText: "Bot: qa_mcp_echo:mcp-ok-local-agent",
    afterText: [
      "Bot: qa_mcp_echo:mcp-ok-local-agent",
      "User: Call qa_mcp_echo",
    ].join("\n"),
    expectedText: "qa_mcp_echo:mcp-ok-local-agent",
    prompt: "Call qa_mcp_echo",
    latestExpectedLeaf: "Bot: qa_mcp_echo:mcp-ok-local-agent",
    latestFailureLeaf: "",
  });

  assert.equal(result.status, "fail");
  assert.equal(result.final_count, 1);
  assert.equal(result.min_expected_count, 2);
});

test("debug chat classifier accounts for prompt echo occurrences", () => {
  assert.equal(minExpectedOccurrences("", "OK", "say OK"), 2);
  const result = classifyDebugChatResult({
    beforeText: "",
    afterText: "User: say OK",
    expectedText: "OK",
    prompt: "say OK",
    latestExpectedLeaf: "User: say OK",
    latestFailureLeaf: "",
  });

  assert.equal(result.status, "fail");
  assert.equal(result.min_expected_count, 2);
  assert.equal(result.final_count, 1);
});

test("debug chat classifier requires new assistant evidence when message bubbles are available", () => {
  const prompt = "If all steps succeed, final answer must be E2E_OK:skill";
  const result = classifyDebugChatResult({
    beforeText: "",
    afterText: `User: ${prompt}`,
    expectedText: "E2E_OK:skill",
    prompt,
    latestExpectedLeaf: prompt,
    latestFailureLeaf: "",
    beforeMessages: [],
    afterMessages: [{ role: "user", text: prompt }],
    latestAssistantText: "",
  });

  assert.equal(result.status, "fail");
  assert.match(result.reason, /new assistant message/);
  assert.equal(result.before_assistant_expected_count, 0);
  assert.equal(result.after_assistant_expected_count, 0);
});

test("debug chat classifier passes when expected text appears in a new assistant message", () => {
  const prompt = "Return only E2E_OK:skill";
  const result = classifyDebugChatResult({
    beforeText: "",
    afterText: `User: ${prompt}\nBot: E2E_OK:skill`,
    expectedText: "E2E_OK:skill",
    prompt,
    latestExpectedLeaf: "E2E_OK:skill",
    latestFailureLeaf: "",
    beforeMessages: [],
    afterMessages: [
      { role: "user", text: prompt },
      { role: "assistant", text: "E2E_OK:skill" },
    ],
    latestAssistantText: "E2E_OK:skill",
  });

  assert.equal(result.status, "pass");
  assert.match(result.reason, /new assistant message/);
  assert.equal(result.before_assistant_expected_count, 0);
  assert.equal(result.after_assistant_expected_count, 1);
});

test("debug chat classifier allows a recovered failure when latest assistant is successful", () => {
  const expectedText = "E2E_OK:skill";
  const result = classifyDebugChatResult({
    beforeText: "",
    afterText: [
      "Bot: Agent runner temporarily unavailable",
      `Bot: recovered and completed ${expectedText}`,
    ].join("\n"),
    expectedText,
    prompt: "Modify the existing skill",
    latestExpectedLeaf: `recovered and completed ${expectedText}`,
    latestFailureLeaf: "Agent runner temporarily unavailable",
    beforeMessages: [],
    afterMessages: [
      { role: "assistant", text: "Agent runner temporarily unavailable" },
      { role: "assistant", text: `recovered and completed ${expectedText}` },
    ],
    latestAssistantText: `recovered and completed ${expectedText}`,
  });

  assert.equal(result.status, "pass");
  assert.equal(result.before_assistant_expected_count, 0);
  assert.equal(result.after_assistant_expected_count, 1);
});

test("env doctor explains a missing backend listener with a startup hint", async () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-env-doctor-"));
  try {
    const skillsDir = join(tmp, "skills");
    const repoDir = join(tmp, "LangBot");
    const webDir = join(repoDir, "web");
    const browserProfile = join(tmp, "browser-profile");
    const chromium = join(tmp, "chromium");
    mkdirSync(skillsDir, { recursive: true });
    mkdirSync(webDir, { recursive: true });
    mkdirSync(browserProfile, { recursive: true });
    writeFileSync(chromium, "");
    writeFileSync(
      join(skillsDir, ".env"),
      [
        "LANGBOT_BACKEND_URL=http://127.0.0.1:59998",
        "LANGBOT_FRONTEND_URL=http://127.0.0.1:59998",
        "LANGBOT_DEV_FRONTEND_URL=http://127.0.0.1:59998",
        `LANGBOT_REPO=${repoDir}`,
        `LANGBOT_WEB_REPO=${webDir}`,
        `LANGBOT_BROWSER_PROFILE=${browserProfile}`,
        `LANGBOT_CHROMIUM_EXECUTABLE=${chromium}`,
        "LANGBOT_PROXY_HTTP=http://127.0.0.1:7890",
        "LANGBOT_PROXY_SOCKS=socks5://127.0.0.1:7890",
        "LANGBOT_NO_PROXY=localhost,127.0.0.1,::1",
      ].join("\n"),
    );

    const result = await captureAsync(() =>
      commandEnvDoctor({ root: tmp, args: ["env", "doctor"] }),
    );

    assert.equal(result.code, 1);
    assert.match(
      result.output,
      /FAIL: LANGBOT_BACKEND_URL: no HTTP service reachable because 127\.0\.0\.1:59998 is not listening/,
    );
    assert.match(
      result.output,
      new RegExp(
        `WARN: LANGBOT_BACKEND_URL: start backend: cd ${repoDir.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")} && uv run main.py`,
      ),
    );
    assert.match(
      result.output,
      new RegExp(
        `WARN: LANGBOT_FRONTEND_URL: start frontend: cd ${webDir.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")} && pnpm dev`,
      ),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("env doctor does not require proxy variables", async () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-env-doctor-no-proxy-"));
  try {
    const skillsDir = join(tmp, "skills");
    const repoDir = join(tmp, "LangBot");
    const webDir = join(repoDir, "web");
    const browserProfile = join(tmp, "browser-profile");
    const chromium = join(tmp, "chromium");
    mkdirSync(skillsDir, { recursive: true });
    mkdirSync(webDir, { recursive: true });
    mkdirSync(browserProfile, { recursive: true });
    writeFileSync(chromium, "");
    writeFileSync(
      join(skillsDir, ".env"),
      [
        "LANGBOT_BACKEND_URL=http://127.0.0.1:59997",
        "LANGBOT_FRONTEND_URL=http://127.0.0.1:59997",
        "LANGBOT_DEV_FRONTEND_URL=http://127.0.0.1:59997",
        `LANGBOT_REPO=${repoDir}`,
        `LANGBOT_WEB_REPO=${webDir}`,
        `LANGBOT_BROWSER_PROFILE=${browserProfile}`,
        `LANGBOT_CHROMIUM_EXECUTABLE=${chromium}`,
      ].join("\n"),
    );

    const result = await captureAsync(() =>
      commandEnvDoctor({ root: tmp, args: ["env", "doctor"] }),
    );

    assert.equal(result.code, 1);
    assert.doesNotMatch(
      result.output,
      /missing LANGBOT_PROXY|missing LANGBOT_NO_PROXY/,
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("env doctor reports missing socksio for active SOCKS proxy", async () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-env-doctor-socksio-"));
  const originalAllProxy = process.env.ALL_PROXY;
  const originalAllProxyLower = process.env.all_proxy;
  try {
    delete process.env.ALL_PROXY;
    delete process.env.all_proxy;
    const skillsDir = join(tmp, "skills");
    const repoDir = join(tmp, "LangBot");
    const webDir = join(repoDir, "web");
    const venvBin = join(repoDir, ".venv", "bin");
    const browserProfile = join(tmp, "browser-profile");
    const chromium = join(tmp, "chromium");
    mkdirSync(skillsDir, { recursive: true });
    mkdirSync(webDir, { recursive: true });
    mkdirSync(venvBin, { recursive: true });
    mkdirSync(browserProfile, { recursive: true });
    writeFileSync(chromium, "");
    const python = join(venvBin, "python");
    writeFileSync(python, "#!/bin/sh\nexit 1\n");
    chmodSync(python, 0o755);
    writeFileSync(
      join(skillsDir, ".env"),
      [
        "LANGBOT_BACKEND_URL=http://127.0.0.1:59996",
        "LANGBOT_FRONTEND_URL=http://127.0.0.1:59996",
        "LANGBOT_DEV_FRONTEND_URL=http://127.0.0.1:59996",
        `LANGBOT_REPO=${repoDir}`,
        `LANGBOT_WEB_REPO=${webDir}`,
        `LANGBOT_BROWSER_PROFILE=${browserProfile}`,
        `LANGBOT_CHROMIUM_EXECUTABLE=${chromium}`,
        "ALL_PROXY=socks5://127.0.0.1:7890",
      ].join("\n"),
    );

    const result = await captureAsync(() =>
      commandEnvDoctor({ root: tmp, args: ["env", "doctor"] }),
    );

    assert.equal(result.code, 1);
    assert.match(result.output, /FAIL: SOCKS proxy ALL_PROXY is configured/);
    assert.match(result.output, /cannot import socksio/);
    assert.match(result.output, /-m pip install socksio/);
  } finally {
    if (originalAllProxy === undefined) delete process.env.ALL_PROXY;
    else process.env.ALL_PROXY = originalAllProxy;
    if (originalAllProxyLower === undefined) delete process.env.all_proxy;
    else process.env.all_proxy = originalAllProxyLower;
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("env show redacts secret-like values by default", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-env-show-redact-"));
  try {
    mkdirSync(join(tmp, "skills"), { recursive: true });
    writeFileSync(
      join(tmp, "skills", ".env"),
      [
        "LANGBOT_FRONTEND_URL=http://127.0.0.1:3000",
        "LANGBOT_API_KEY=sk-test-secret",
        "LANGBOT_PROXY_HTTP=http://user:pass@127.0.0.1:7890",
      ].join("\n"),
    );

    const text = capture(() =>
      commandEnvShow({ root: tmp, args: ["env", "show"] }),
    );
    assert.equal(text.code, 0);
    assert.match(text.output, /LANGBOT_API_KEY=\[redacted\]/);
    assert.match(
      text.output,
      /LANGBOT_PROXY_HTTP=http:\/\/\[redacted\]@127\.0\.0\.1:7890/,
    );
    assert.doesNotMatch(text.output, /sk-test-secret|user:pass/);

    const json = capture(() =>
      commandEnvShow({ root: tmp, args: ["env", "show", "--json"] }),
    );
    assert.equal(json.code, 0);
    const parsed = JSON.parse(json.output);
    assert.equal(parsed.LANGBOT_API_KEY, "[redacted]");
    assert.equal(parsed.LANGBOT_PROXY_HTTP, "http://[redacted]@127.0.0.1:7890");
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test plan renders agent-browser QA guidance", () => {
  const result = capture(() =>
    commandTestPlan(ctx(["test", "plan", "pipeline-debug-chat"])),
  );
  assert.equal(result.code, 0);
  assert.match(result.output, /Mode: agent-browser/);
  assert.match(
    result.output,
    /Use browser\/UI interaction as the primary QA path/,
  );
  assert.match(result.output, /API\/curl\/log checks are diagnostic only/);
  assert.match(result.output, /## Browser Steps/);
  assert.match(result.output, /## Success Signals/);
  assert.match(result.output, /## Required Evidence/);
  assert.match(result.output, /## Automation Readiness/);
  assert.match(result.output, /## Fixture Readiness/);
  assert.match(result.output, /## Manual Readiness/);
  assert.match(result.output, /backend_log/);
});

test("test plan JSON is parseable and includes troubleshooting patterns", () => {
  const result = capture(() =>
    commandTestPlan(ctx(["test", "plan", "pipeline-debug-chat", "--json"])),
  );
  assert.equal(result.code, 0);
  const plan = JSON.parse(result.output);
  assert.equal(plan.id, "pipeline-debug-chat");
  assert.equal(plan.mode, "agent-browser");
  assert.ok(["ready", "missing"].includes(plan.automation_readiness.status));
  assert.ok(plan.automation_readiness.defaulted.includes("LANGBOT_E2E_PROMPT"));
  assert.ok(
    plan.automation_readiness.defaulted.includes("LANGBOT_E2E_EXPECTED_TEXT"),
  );
  assert.equal(plan.manual_readiness.status, "manual_check");
  assert.ok(plan.success_patterns.includes("Streaming completed"));
  assert.ok(
    plan.troubleshooting.some(
      (entry: { id: string }) => entry.id === "plugin-runtime-timeout",
    ),
  );
});

test("test plan JSON exposes missing case-specific pipeline readiness", () => {
  const result = capture(() =>
    commandTestPlan(
      ctx(["test", "plan", "local-agent-basic-debug-chat", "--json"]),
    ),
  );
  assert.equal(result.code, 0);
  const plan = JSON.parse(result.output);
  assert.equal(plan.env_readiness.status, "ready");
  assert.ok(["ready", "missing"].includes(plan.automation_readiness.status));
  assert.ok(plan.automation_readiness.pipeline_env_required);
  assert.ok(
    plan.automation_readiness.missing.includes(
      "LANGBOT_LOCAL_AGENT_PIPELINE_URL|LANGBOT_LOCAL_AGENT_PIPELINE_NAME",
    ) ||
      plan.automation_readiness.configured.some((key: string) =>
        key.startsWith("LANGBOT_LOCAL_AGENT_PIPELINE_"),
      ),
  );
});

test("generic pipeline readiness accepts either URL or name target", () => {
  const originalUrl = process.env.LANGBOT_PIPELINE_URL;
  const originalName = process.env.LANGBOT_PIPELINE_NAME;
  try {
    withEnv(
      {
        LANGBOT_BROWSER_PROFILE: "/tmp/langbot-test-profile",
        LANGBOT_CHROMIUM_EXECUTABLE: "/tmp/langbot-test-chromium",
      },
      () => {
        process.env.LANGBOT_PIPELINE_URL =
          "http://127.0.0.1:3000/home/agents?id=only-url";
        process.env.LANGBOT_PIPELINE_NAME = "";

        const ready = capture(() =>
          commandTestPlan(
            ctx(["test", "plan", "pipeline-debug-chat", "--json"]),
          ),
        );
        assert.equal(ready.code, 0);
        const plan = JSON.parse(ready.output);
        assert.equal(plan.env_readiness.status, "ready");
        assert.equal(plan.automation_readiness.status, "ready");
        assert.ok(
          plan.automation_readiness.required.includes(
            "LANGBOT_PIPELINE_URL|LANGBOT_PIPELINE_NAME",
          ),
        );
      },
    );

    process.env.LANGBOT_PIPELINE_URL = "";
    process.env.LANGBOT_PIPELINE_NAME = "";

    const missing = capture(() =>
      commandTestPlan(ctx(["test", "plan", "pipeline-debug-chat", "--json"])),
    );
    assert.equal(missing.code, 0);
    const missingPlan = JSON.parse(missing.output);
    assert.equal(missingPlan.env_readiness.status, "missing");
    assert.ok(
      missingPlan.env_readiness.missing.includes(
        "LANGBOT_PIPELINE_URL|LANGBOT_PIPELINE_NAME",
      ),
    );
    assert.equal(missingPlan.automation_readiness.status, "missing");
    assert.ok(
      missingPlan.automation_readiness.missing.includes(
        "LANGBOT_PIPELINE_URL|LANGBOT_PIPELINE_NAME",
      ),
    );
  } finally {
    if (originalUrl === undefined) delete process.env.LANGBOT_PIPELINE_URL;
    else process.env.LANGBOT_PIPELINE_URL = originalUrl;
    if (originalName === undefined) delete process.env.LANGBOT_PIPELINE_NAME;
    else process.env.LANGBOT_PIPELINE_NAME = originalName;
  }
});

test("test recommend maps AgentRunner ledger changes to focused probes", () => {
  const result = capture(() =>
    commandTestRecommend(
      ctx([
        "test",
        "recommend",
        "--file",
        "LangBot/src/langbot/pkg/agent/runner/run_ledger_store.py",
        "--file",
        "LangBot/tests/unit_tests/agent/test_run_ledger_store.py",
        "--json",
      ]),
    ),
  );
  assert.equal(result.code, 0);
  const report = JSON.parse(result.output);
  const ids = report.recommendations.map((item: { id: string }) => item.id);
  assert.ok(ids.includes("agent-runner-ledger-invariants"));
  assert.ok(ids.includes("agent-runner-ledger-stress"));
  assert.ok(ids.includes("agent-runner-ledger-contention"));
  assert.ok(ids.includes("agent-runner-async-db-readiness"));
  assert.ok(ids.includes("agent-runner-ledger-concurrency"));
  assert.ok(
    report.commands.every(
      (command: string) =>
        !command.startsWith("bin/lbs test run ") ||
        command.endsWith(" --dry-run"),
    ),
  );
  assert.ok(
    report.notes.some((note: string) => note.includes("Remove --dry-run")),
  );
});

test("test recommend maps AgentRunner result changes to fixture contract", () => {
  const result = capture(() =>
    commandTestRecommend(
      ctx([
        "test",
        "recommend",
        "--file",
        "langbot-plugin-sdk/src/langbot_plugin/api/entities/builtin/agent_runner/result.py",
        "--json",
      ]),
    ),
  );
  assert.equal(result.code, 0);
  const report = JSON.parse(result.output);
  const ids = report.recommendations.map((item: { id: string }) => item.id);
  assert.ok(ids.includes("agent-runner-fixture-contract"));
  assert.ok(ids.includes("agent-runner-behavior-matrix"));
  assert.ok(!ids.includes("agent-runner-ledger-invariants"));
});

test("test recommend maps QA AgentRunner fixture changes to live install", () => {
  const result = capture(() =>
    commandTestRecommend(
      ctx([
        "test",
        "recommend",
        "--file",
        "langbot-skills/skills/langbot-testing/fixtures/plugins/qa-agent-runner/components/agent_runner/default.py",
        "--json",
      ]),
    ),
  );
  assert.equal(result.code, 0);
  const report = JSON.parse(result.output);
  const ids = report.recommendations.map((item: { id: string }) => item.id);
  assert.ok(ids.includes("agent-runner-fixture-contract"));
  assert.ok(ids.includes("agent-runner-live-install"));
  assert.ok(ids.includes("agent-runner-qa-debug-chat"));
});

test("test recommend maps QA plugin smoke fixture changes to live install", () => {
  const result = capture(() =>
    commandTestRecommend(
      ctx([
        "test",
        "recommend",
        "--file",
        "langbot-skills/skills/langbot-testing/fixtures/plugins/qa-plugin-smoke/main.py",
        "--json",
      ]),
    ),
  );
  assert.equal(result.code, 0);
  const report = JSON.parse(result.output);
  const ids = report.recommendations.map((item: { id: string }) => item.id);
  assert.ok(ids.includes("qa-plugin-smoke-live-install"));
});

test("test recommend keeps git status paths intact", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-recommend-git-"));
  const originalRepos = {
    LANGBOT_REPO: process.env.LANGBOT_REPO,
    LANGBOT_PLUGIN_SDK_REPO: process.env.LANGBOT_PLUGIN_SDK_REPO,
    LANGBOT_AGENT_RUNNER_REPO: process.env.LANGBOT_AGENT_RUNNER_REPO,
    LANGBOT_LOCAL_AGENT_REPO: process.env.LANGBOT_LOCAL_AGENT_REPO,
  };
  try {
    const repo = join(tmp, "LangBot");
    mkdirSync(join(repo, "src", "langbot", "pkg", "agent", "runner"), {
      recursive: true,
    });
    spawnSync("git", ["init"], { cwd: repo });
    spawnSync("git", ["config", "user.email", "qa@example.test"], {
      cwd: repo,
    });
    spawnSync("git", ["config", "user.name", "QA"], { cwd: repo });
    writeFileSync(join(repo, "README.md"), "test\n");
    writeFileSync(
      join(
        repo,
        "src",
        "langbot",
        "pkg",
        "agent",
        "runner",
        "run_ledger_store.py",
      ),
      "# test\n",
    );
    spawnSync(
      "git",
      ["add", "README.md", "src/langbot/pkg/agent/runner/run_ledger_store.py"],
      { cwd: repo },
    );
    spawnSync("git", ["commit", "-m", "init"], { cwd: repo });
    writeFileSync(
      join(
        repo,
        "src",
        "langbot",
        "pkg",
        "agent",
        "runner",
        "run_ledger_store.py",
      ),
      "# changed\n",
    );

    process.env.LANGBOT_REPO = repo;
    process.env.LANGBOT_PLUGIN_SDK_REPO = join(tmp, "missing-sdk");
    process.env.LANGBOT_AGENT_RUNNER_REPO = join(tmp, "missing-runner");
    process.env.LANGBOT_LOCAL_AGENT_REPO = join(tmp, "missing-local");
    const result = capture(() =>
      commandTestRecommend({ root, args: ["test", "recommend", "--json"] }),
    );

    assert.equal(result.code, 0);
    const report = JSON.parse(result.output);
    assert.ok(
      report.changed_files.includes(
        "LangBot/src/langbot/pkg/agent/runner/run_ledger_store.py",
      ),
    );
    assert.ok(
      !report.changed_files.some((file: string) =>
        file.includes("LangBot/rc/"),
      ),
    );
  } finally {
    for (const [key, value] of Object.entries(originalRepos)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test start creates a run handoff with a bounded report command", () => {
  const result = capture(() =>
    commandTestStart(ctx(["test", "start", "pipeline-debug-chat"])),
  );
  assert.equal(result.code, 0);
  assert.match(result.output, /^# Test Start: pipeline-debug-chat/m);
  assert.match(result.output, /bin\/lbs test plan pipeline-debug-chat/);
  assert.match(
    result.output,
    /bin\/lbs test run pipeline-debug-chat --run-id .+ --output reports\/evidence\/.+pipeline-debug-chat/,
  );
  assert.match(
    result.output,
    /bin\/lbs test report pipeline-debug-chat --since ".+" --console-log reports\/evidence\/.+\/console\.log --evidence-dir reports\/evidence\/.+ --output reports\/.+pipeline-debug-chat\.md/,
  );
  assert.match(result.output, /Streaming completed/);
});

test("test start JSON is parseable for agent orchestration", () => {
  const result = capture(() =>
    commandTestStart(ctx(["test", "start", "pipeline-debug-chat", "--json"])),
  );
  assert.equal(result.code, 0);
  const start = JSON.parse(result.output);
  assert.equal(start.case.id, "pipeline-debug-chat");
  assert.match(start.run_id, /pipeline-debug-chat$/);
  assert.match(start.started_at_local, /\d{4}-\d{2}-\d{2}T/);
  assert.match(start.report_command, /--since/);
  assert.match(
    start.result_command_template,
    /bin\/lbs test result pipeline-debug-chat/,
  );
  assert.match(
    start.automation.command,
    /bin\/lbs test run pipeline-debug-chat/,
  );
  assert.ok(start.success_patterns.includes("Streaming completed"));
  assert.ok(start.evidence_required.includes("backend_log"));
});

test("test result writes a suite-readable result.json and enforces pass evidence", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-test-result-"));
  try {
    const evidenceDir = join(tmp, "pipeline-run");
    const ok = capture(() =>
      commandTestResult(
        ctx([
          "test",
          "result",
          "pipeline-debug-chat",
          "--result",
          "pass",
          "--reason",
          "Debug Chat returned OK and logs were clean.",
          "--evidence-dir",
          evidenceDir,
          "--started-at",
          "2026-05-21T10:30:00.000+08:00",
          "--evidence",
          "ui,screenshot,console,backend_log",
          "--json",
        ]),
      ),
    );

    assert.equal(ok.code, 0);
    const record = JSON.parse(ok.output);
    assert.equal(record.source, "final");
    assert.equal(record.status, "pass");
    assert.equal(record.evidence_status, "complete");
    assert.deepEqual(record.evidence_missing, []);
    assert.equal(
      JSON.parse(readFileSync(join(evidenceDir, "result.json"), "utf8"))
        .case_id,
      "pipeline-debug-chat",
    );

    const missing = captureAll(() =>
      commandTestResult(
        ctx([
          "test",
          "result",
          "pipeline-debug-chat",
          "--result",
          "pass",
          "--reason",
          "Missing backend evidence should not be accepted as pass.",
          "--evidence-dir",
          join(tmp, "missing-evidence"),
          "--evidence",
          "ui",
        ]),
      ),
    );
    assert.equal(missing.code, 1);
    assert.match(missing.error, /missing required evidence/);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test run dry-run exposes case automation script and evidence paths", () => {
  const result = capture(() =>
    commandTestRun(
      ctx([
        "test",
        "run",
        "pipeline-debug-chat",
        "--run-id",
        "run-123",
        "--output",
        "reports/evidence/run-123",
        "--dry-run",
      ]),
    ),
  );
  assert.equal(result.code, 0);
  assert.match(result.output, /^# Test Automation: pipeline-debug-chat/m);
  assert.match(result.output, /scripts\/e2e\/pipeline-debug-chat\.mjs/);
  assert.match(
    result.output,
    /console_log: reports\/evidence\/run-123\/console\.log/,
  );
  assert.match(
    result.output,
    /automation_result_json: reports\/evidence\/run-123\/automation-result\.json/,
  );
  assert.match(
    result.output,
    /result_json: reports\/evidence\/run-123\/result\.json/,
  );
  assert.match(result.output, /LANGBOT_PIPELINE_URL/);
});

test("test run dry-run JSON is parseable for automation orchestration", () => {
  const result = capture(() =>
    commandTestRun(
      ctx([
        "test",
        "run",
        "webui-login-state",
        "--run-id",
        "login-run",
        "--dry-run",
        "--json",
      ]),
    ),
  );
  assert.equal(result.code, 0);
  const run = JSON.parse(result.output);
  assert.equal(run.case.id, "webui-login-state");
  assert.equal(run.run_id, "login-run");
  assert.equal(run.automation.script, "scripts/e2e/webui-login-state.mjs");
  assert.equal(run.automation.exists, true);
  assert.match(
    run.automation.automation_result_json,
    /automation-result\.json$/,
  );
  assert.match(run.automation.result_json, /result\.json$/);
  assert.match(run.automation.report_command, /--console-log/);
});

test("test run JSON executes automation unless dry-run is explicit", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-run-json-exec-"));
  try {
    const skillDir = join(tmp, "skills", "langbot-testing");
    const casesDir = join(skillDir, "cases");
    const scriptsDir = join(tmp, "scripts");
    mkdirSync(casesDir, { recursive: true });
    mkdirSync(scriptsDir, { recursive: true });
    writeFileSync(
      join(skillDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );
    writeFileSync(join(tmp, "skills", ".env"), "");
    writeFileSync(
      join(casesDir, "json-exec.yaml"),
      [
        "id: json-exec",
        "title: JSON Exec",
        "mode: probe",
        "area: qa",
        "type: smoke",
        "priority: p2",
        "risk: low",
        "ci_eligible: true",
        "automation: scripts/write-marker.mjs",
      ].join("\n"),
    );
    writeFileSync(
      join(scriptsDir, "write-marker.mjs"),
      [
        "import { writeFileSync } from 'node:fs';",
        "import { join } from 'node:path';",
        "writeFileSync(join(process.env.LBS_ROOT, 'json-ran.txt'), 'yes');",
      ].join("\n"),
    );

    const result = capture(() =>
      commandTestRun({
        root: tmp,
        args: ["test", "run", "json-exec", "--run-id", "json-run", "--json"],
      }),
    );

    assert.equal(result.code, 0);
    assert.equal(readFileSync(join(tmp, "json-ran.txt"), "utf8"), "yes");
    const payload = JSON.parse(result.output);
    assert.equal(payload.exit_status, 0);
    assert.equal(payload.automation_execution.status, "ok");
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test run lets explicit environment override automation defaults", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-run-env-override-"));
  const originalPatch = process.env.LANGBOT_E2E_RUNNER_CONFIG_PATCH_JSON;
  try {
    const skillDir = join(tmp, "skills", "langbot-testing");
    const casesDir = join(skillDir, "cases");
    const scriptsDir = join(tmp, "scripts");
    mkdirSync(casesDir, { recursive: true });
    mkdirSync(scriptsDir, { recursive: true });
    writeFileSync(
      join(skillDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );
    writeFileSync(join(tmp, "skills", ".env"), "");
    writeFileSync(
      join(casesDir, "env-override.yaml"),
      [
        "id: env-override",
        "title: Env Override",
        "mode: agent-browser",
        "area: pipeline",
        "type: smoke",
        "priority: p2",
        "risk: low",
        "ci_eligible: false",
        "automation: scripts/write-env.mjs",
        'automation_runner_config_patch_json: \'{"source":"default"}\'',
      ].join("\n"),
    );
    writeFileSync(
      join(scriptsDir, "write-env.mjs"),
      [
        "import { writeFileSync } from 'node:fs';",
        "import { join } from 'node:path';",
        "writeFileSync(join(process.env.LBS_ROOT, 'env-out.json'), JSON.stringify({",
        "  patch: process.env.LANGBOT_E2E_RUNNER_CONFIG_PATCH_JSON,",
        "}));",
      ].join("\n"),
    );

    process.env.LANGBOT_E2E_RUNNER_CONFIG_PATCH_JSON = '{"source":"explicit"}';
    const result = capture(() =>
      commandTestRun({
        root: tmp,
        args: ["test", "run", "env-override", "--run-id", "env-run"],
      }),
    );

    assert.equal(result.code, 0);
    const observed = JSON.parse(
      readFileSync(join(tmp, "env-out.json"), "utf8"),
    );
    assert.equal(observed.patch, '{"source":"explicit"}');
  } finally {
    if (originalPatch === undefined)
      delete process.env.LANGBOT_E2E_RUNNER_CONFIG_PATCH_JSON;
    else process.env.LANGBOT_E2E_RUNNER_CONFIG_PATCH_JSON = originalPatch;
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test run expands env references in automation defaults", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-run-env-expand-"));
  try {
    const skillDir = join(tmp, "skills", "langbot-testing");
    const casesDir = join(skillDir, "cases");
    const scriptsDir = join(tmp, "scripts");
    mkdirSync(casesDir, { recursive: true });
    mkdirSync(scriptsDir, { recursive: true });
    writeFileSync(
      join(skillDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );
    writeFileSync(
      join(tmp, "skills", ".env"),
      "QA_KB_UUID=kb-from-env\nQA_MODEL_UUID=model-from-env\n",
    );
    writeFileSync(
      join(casesDir, "env-expand.yaml"),
      [
        "id: env-expand",
        "title: Env Expand",
        "mode: agent-browser",
        "area: pipeline",
        "type: smoke",
        "priority: p2",
        "risk: low",
        "ci_eligible: false",
        "automation: scripts/write-expanded-env.mjs",
        'automation_runner_config_patch_json: \'{"knowledge-bases":["${QA_KB_UUID}"],"model":{"primary":"${QA_MODEL_UUID}"}}\'',
      ].join("\n"),
    );
    writeFileSync(
      join(scriptsDir, "write-expanded-env.mjs"),
      [
        "import { writeFileSync } from 'node:fs';",
        "import { join } from 'node:path';",
        "writeFileSync(join(process.env.LBS_ROOT, 'expanded-env-out.json'), JSON.stringify({",
        "  patch: process.env.LANGBOT_E2E_RUNNER_CONFIG_PATCH_JSON,",
        "}));",
      ].join("\n"),
    );

    const dryRun = capture(() =>
      commandTestRun({
        root: tmp,
        args: [
          "test",
          "run",
          "env-expand",
          "--run-id",
          "env-expand-dry",
          "--dry-run",
          "--json",
        ],
      }),
    );
    assert.equal(dryRun.code, 0);
    const plan = JSON.parse(dryRun.output);
    assert.equal(
      plan.automation.env_defaults.LANGBOT_E2E_RUNNER_CONFIG_PATCH_JSON,
      '{"knowledge-bases":["kb-from-env"],"model":{"primary":"model-from-env"}}',
    );

    const run = capture(() =>
      commandTestRun({
        root: tmp,
        args: ["test", "run", "env-expand", "--run-id", "env-expand-run"],
      }),
    );
    assert.equal(run.code, 0);
    const observed = JSON.parse(
      readFileSync(join(tmp, "expanded-env-out.json"), "utf8"),
    );
    assert.equal(
      observed.patch,
      '{"knowledge-bases":["kb-from-env"],"model":{"primary":"model-from-env"}}',
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test run setup automation isolates evidence and reloads env", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-run-setup-automation-"));
  try {
    const skillDir = join(tmp, "skills", "langbot-testing");
    const casesDir = join(skillDir, "cases");
    const scriptsDir = join(tmp, "scripts");
    mkdirSync(casesDir, { recursive: true });
    mkdirSync(scriptsDir, { recursive: true });
    writeFileSync(
      join(skillDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );
    writeFileSync(join(tmp, "skills", ".env"), "SETUP_VALUE=\n");
    writeFileSync(
      join(casesDir, "setup-main.yaml"),
      [
        "id: setup-main",
        "title: Setup Main",
        "mode: agent-browser",
        "area: pipeline",
        "type: smoke",
        "priority: p2",
        "risk: low",
        "ci_eligible: false",
        "env:",
        "  - SETUP_VALUE",
        "setup_automation:",
        '  - "node:scripts/write-setup-env.mjs --write-env"',
        "setup_provides_env:",
        "  - SETUP_VALUE",
        "automation: scripts/read-setup-env.mjs",
      ].join("\n"),
    );
    writeFileSync(
      join(casesDir, "setup-env-issue.yaml"),
      [
        "id: setup-env-issue",
        "title: Setup Env Issue",
        "mode: agent-browser",
        "area: pipeline",
        "type: smoke",
        "priority: p2",
        "risk: low",
        "ci_eligible: false",
        "setup_automation:",
        '  - "node:scripts/write-setup-env-issue.mjs"',
        "automation: scripts/read-setup-env.mjs",
      ].join("\n"),
    );
    writeFileSync(
      join(casesDir, "setup-fail-after-pass.yaml"),
      [
        "id: setup-fail-after-pass",
        "title: Setup Fail After Pass",
        "mode: agent-browser",
        "area: pipeline",
        "type: smoke",
        "priority: p2",
        "risk: low",
        "ci_eligible: false",
        "setup_automation:",
        '  - "node:scripts/write-setup-pass-then-fail.mjs"',
        "automation: scripts/read-setup-env.mjs",
      ].join("\n"),
    );
    writeFileSync(
      join(scriptsDir, "write-setup-env.mjs"),
      [
        "import { mkdirSync, writeFileSync } from 'node:fs';",
        "import { dirname, join } from 'node:path';",
        "const local = join(process.env.LBS_ROOT, 'skills', '.env.local');",
        "writeFileSync(local, 'SETUP_VALUE=from-setup\\n');",
        "mkdirSync(process.env.LBS_EVIDENCE_DIR, { recursive: true });",
        "writeFileSync(join(process.env.LBS_EVIDENCE_DIR, 'automation-result.json'), JSON.stringify({ status: 'pass', stage: 'setup' }));",
        "writeFileSync(join(process.env.LBS_EVIDENCE_DIR, 'result.json'), JSON.stringify({ status: 'pass', stage: 'setup' }));",
        "writeFileSync(join(dirname(process.env.LBS_EVIDENCE_DIR), 'setup-ran.txt'), 'yes');",
      ].join("\n"),
    );
    writeFileSync(
      join(scriptsDir, "read-setup-env.mjs"),
      [
        "import { mkdirSync, writeFileSync } from 'node:fs';",
        "import { join } from 'node:path';",
        "mkdirSync(process.env.LBS_EVIDENCE_DIR, { recursive: true });",
        "writeFileSync(join(process.env.LBS_ROOT, 'main-observed.json'), JSON.stringify({ value: process.env.SETUP_VALUE }));",
        "writeFileSync(join(process.env.LBS_EVIDENCE_DIR, 'automation-result.json'), JSON.stringify({ status: 'pass', stage: 'main' }));",
        "writeFileSync(join(process.env.LBS_EVIDENCE_DIR, 'result.json'), JSON.stringify({ status: 'pass', stage: 'main' }));",
        "if (process.env.SETUP_VALUE !== 'from-setup') process.exit(1);",
      ].join("\n"),
    );
    writeFileSync(
      join(scriptsDir, "write-setup-env-issue.mjs"),
      [
        "import { mkdirSync, writeFileSync } from 'node:fs';",
        "import { join } from 'node:path';",
        "mkdirSync(process.env.LBS_EVIDENCE_DIR, { recursive: true });",
        "writeFileSync(join(process.env.LBS_EVIDENCE_DIR, 'automation-result.json'), JSON.stringify({ status: 'env_issue', reason: 'setup env missing' }));",
        "process.exit(2);",
      ].join("\n"),
    );
    writeFileSync(
      join(scriptsDir, "write-setup-pass-then-fail.mjs"),
      [
        "import { mkdirSync, writeFileSync } from 'node:fs';",
        "import { join } from 'node:path';",
        "mkdirSync(process.env.LBS_EVIDENCE_DIR, { recursive: true });",
        "writeFileSync(join(process.env.LBS_EVIDENCE_DIR, 'automation-result.json'), JSON.stringify({ status: 'pass', reason: 'stale pass before crash' }));",
        "process.exit(1);",
      ].join("\n"),
    );

    const dryRun = capture(() =>
      commandTestRun({
        root: tmp,
        args: [
          "test",
          "run",
          "setup-main",
          "--run-id",
          "setup-run",
          "--output",
          join(tmp, "evidence"),
          "--dry-run",
          "--json",
        ],
      }),
    );
    assert.equal(dryRun.code, 0);
    const plan = JSON.parse(dryRun.output);
    assert.equal(plan.setup_automation.length, 1);
    assert.match(
      plan.setup_automation[0].evidence_dir,
      /setup\/01-write-setup-env$/,
    );
    assert.match(
      plan.setup_automation[0].command,
      /^node scripts\/write-setup-env\.mjs --write-env$/,
    );
    assert.equal(plan.setup_automation[0].dry_run_command, "");
    assert.equal(existsSync(join(tmp, "skills", ".env.local")), false);

    const run = capture(() =>
      commandTestRun({
        root: tmp,
        args: [
          "test",
          "run",
          "setup-main",
          "--run-id",
          "setup-run",
          "--output",
          join(tmp, "evidence"),
        ],
      }),
    );
    assert.equal(run.code, 0);
    const observed = JSON.parse(
      readFileSync(join(tmp, "main-observed.json"), "utf8"),
    );
    assert.equal(observed.value, "from-setup");
    const setupResult = JSON.parse(
      readFileSync(
        join(
          tmp,
          "evidence",
          "setup",
          "01-write-setup-env",
          "automation-result.json",
        ),
        "utf8",
      ),
    );
    const mainResult = JSON.parse(
      readFileSync(join(tmp, "evidence", "automation-result.json"), "utf8"),
    );
    assert.equal(setupResult.stage, "setup");
    assert.equal(mainResult.stage, "main");

    const envIssue = capture(() =>
      commandTestRun({
        root: tmp,
        args: [
          "test",
          "run",
          "setup-env-issue",
          "--run-id",
          "setup-env-issue-run",
          "--output",
          join(tmp, "evidence-env-issue"),
        ],
      }),
    );
    assert.equal(envIssue.code, 2);
    const parentResult = JSON.parse(
      readFileSync(
        join(tmp, "evidence-env-issue", "automation-result.json"),
        "utf8",
      ),
    );
    assert.equal(parentResult.status, "env_issue");
    assert.equal(parentResult.reason, "setup env missing");

    const failAfterPass = capture(() =>
      commandTestRun({
        root: tmp,
        args: [
          "test",
          "run",
          "setup-fail-after-pass",
          "--run-id",
          "setup-fail-after-pass-run",
          "--output",
          join(tmp, "evidence-fail-after-pass"),
        ],
      }),
    );
    assert.equal(failAfterPass.code, 1);
    const failAfterPassResult = JSON.parse(
      readFileSync(
        join(tmp, "evidence-fail-after-pass", "automation-result.json"),
        "utf8",
      ),
    );
    assert.equal(failAfterPassResult.status, "fail");
    assert.equal(failAfterPassResult.reason, "stale pass before crash");
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test run setup automation can execute another case outside this source repo", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-run-setup-case-"));
  try {
    const skillDir = join(tmp, "skills", "langbot-testing");
    const casesDir = join(skillDir, "cases");
    const scriptsDir = join(tmp, "scripts");
    mkdirSync(casesDir, { recursive: true });
    mkdirSync(scriptsDir, { recursive: true });
    writeFileSync(
      join(skillDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );
    writeFileSync(join(tmp, "skills", ".env"), "SETUP_VALUE=\n");
    writeFileSync(
      join(casesDir, "setup-child.yaml"),
      [
        "id: setup-child",
        "title: Setup Child",
        "mode: probe",
        "area: qa",
        "type: smoke",
        "priority: p2",
        "risk: low",
        "ci_eligible: true",
        "automation: scripts/write-child-env.mjs",
      ].join("\n"),
    );
    writeFileSync(
      join(casesDir, "setup-parent.yaml"),
      [
        "id: setup-parent",
        "title: Setup Parent",
        "mode: probe",
        "area: qa",
        "type: smoke",
        "priority: p2",
        "risk: low",
        "ci_eligible: true",
        "setup_automation:",
        '  - "case:setup-child"',
        "setup_provides_env:",
        "  - SETUP_VALUE",
        "automation: scripts/read-child-env.mjs",
      ].join("\n"),
    );
    writeFileSync(
      join(scriptsDir, "write-child-env.mjs"),
      [
        "import { mkdirSync, writeFileSync } from 'node:fs';",
        "import { join } from 'node:path';",
        "writeFileSync(join(process.env.LBS_ROOT, 'skills', '.env.local'), 'SETUP_VALUE=from-child\\n');",
        "mkdirSync(process.env.LBS_EVIDENCE_DIR, { recursive: true });",
        "writeFileSync(join(process.env.LBS_EVIDENCE_DIR, 'automation-result.json'), JSON.stringify({ status: 'pass' }));",
        "writeFileSync(join(process.env.LBS_EVIDENCE_DIR, 'result.json'), JSON.stringify({ status: 'pass' }));",
      ].join("\n"),
    );
    writeFileSync(
      join(scriptsDir, "read-child-env.mjs"),
      [
        "import { mkdirSync, writeFileSync } from 'node:fs';",
        "import { join } from 'node:path';",
        "mkdirSync(process.env.LBS_EVIDENCE_DIR, { recursive: true });",
        "writeFileSync(join(process.env.LBS_EVIDENCE_DIR, 'automation-result.json'), JSON.stringify({ status: 'pass', value: process.env.SETUP_VALUE }));",
        "writeFileSync(join(process.env.LBS_EVIDENCE_DIR, 'result.json'), JSON.stringify({ status: 'pass', value: process.env.SETUP_VALUE }));",
        "if (process.env.SETUP_VALUE !== 'from-child') process.exit(1);",
      ].join("\n"),
    );

    const run = capture(() =>
      commandTestRun({
        root: tmp,
        args: [
          "test",
          "run",
          "setup-parent",
          "--run-id",
          "setup-parent-run",
          "--output",
          join(tmp, "evidence"),
        ],
      }),
    );

    assert.equal(run.code, 0);
    assert.ok(
      existsSync(
        join(tmp, "evidence", "setup", "01-setup-child", "result.json"),
      ),
    );
    const result = JSON.parse(
      readFileSync(join(tmp, "evidence", "automation-result.json"), "utf8"),
    );
    assert.equal(result.value, "from-child");
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test run automation inherits parent process environment", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-run-env-inherit-"));
  try {
    const skillDir = join(tmp, "skills", "langbot-testing");
    const casesDir = join(skillDir, "cases");
    const scriptsDir = join(tmp, "scripts");
    mkdirSync(casesDir, { recursive: true });
    mkdirSync(scriptsDir, { recursive: true });
    writeFileSync(
      join(skillDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );
    writeFileSync(join(tmp, "skills", ".env"), "");
    writeFileSync(
      join(casesDir, "env-inherit.yaml"),
      [
        "id: env-inherit",
        "title: Env Inherit",
        "mode: probe",
        "area: qa",
        "type: smoke",
        "priority: p2",
        "risk: low",
        "ci_eligible: true",
        "automation: scripts/read-path.mjs",
      ].join("\n"),
    );
    writeFileSync(
      join(scriptsDir, "read-path.mjs"),
      [
        "import { mkdirSync, writeFileSync } from 'node:fs';",
        "import { join } from 'node:path';",
        "mkdirSync(process.env.LBS_EVIDENCE_DIR, { recursive: true });",
        "writeFileSync(join(process.env.LBS_EVIDENCE_DIR, 'automation-result.json'), JSON.stringify({ status: process.env.PATH ? 'pass' : 'fail' }));",
        "process.exit(process.env.PATH ? 0 : 1);",
      ].join("\n"),
    );

    const run = capture(() =>
      commandTestRun({
        root: tmp,
        args: [
          "test",
          "run",
          "env-inherit",
          "--run-id",
          "env-inherit-run",
          "--output",
          join(tmp, "evidence"),
        ],
      }),
    );

    assert.equal(run.code, 0);
    const result = JSON.parse(
      readFileSync(join(tmp, "evidence", "automation-result.json"), "utf8"),
    );
    assert.equal(result.status, "pass");
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test run dry-run marks missing setup case targets", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-run-setup-missing-case-"));
  try {
    const skillDir = join(tmp, "skills", "langbot-testing");
    const casesDir = join(skillDir, "cases");
    const scriptsDir = join(tmp, "scripts");
    mkdirSync(casesDir, { recursive: true });
    mkdirSync(scriptsDir, { recursive: true });
    writeFileSync(
      join(skillDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );
    writeFileSync(join(tmp, "skills", ".env"), "");
    writeFileSync(
      join(casesDir, "setup-parent.yaml"),
      [
        "id: setup-parent",
        "title: Setup Parent",
        "mode: probe",
        "area: qa",
        "type: smoke",
        "priority: p2",
        "risk: low",
        "ci_eligible: true",
        "setup_automation:",
        '  - "case:missing-child"',
        "automation: scripts/pass.mjs",
      ].join("\n"),
    );
    writeFileSync(join(scriptsDir, "pass.mjs"), "process.exit(0);\n");

    const result = capture(() =>
      commandTestRun({
        root: tmp,
        args: ["test", "run", "setup-parent", "--dry-run", "--json"],
      }),
    );

    assert.equal(result.code, 0);
    const run = JSON.parse(result.output);
    assert.equal(run.setup_automation[0].entry, "case:missing-child");
    assert.doesNotMatch(run.setup_automation[0].command, /--dry-run/);
    assert.match(run.setup_automation[0].dry_run_command, /--dry-run/);
    assert.equal(run.setup_automation[0].exists, false);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("local-agent effective prompt case has runnable automation defaults", () => {
  const result = capture(() =>
    commandTestRun(
      ctx([
        "test",
        "run",
        "local-agent-effective-prompt-debug-chat",
        "--run-id",
        "effective-run",
        "--dry-run",
        "--json",
      ]),
    ),
  );
  assert.equal(result.code, 0);
  const run = JSON.parse(result.output);
  assert.equal(run.automation.script, "scripts/e2e/pipeline-debug-chat.mjs");
  assert.equal(
    run.automation.env_defaults.LANGBOT_E2E_PROMPT,
    "qa-effective-prompt",
  );
  assert.equal(
    run.automation.env_defaults.LANGBOT_E2E_EXPECTED_TEXT,
    "PROMPT_PREPROCESS_OK",
  );
  assert.equal(
    run.automation.env_defaults.LANGBOT_E2E_RESPONSE_TIMEOUT_MS,
    "180000",
  );
  assert.equal(run.automation.pipeline_env_required, true);
  assert.ok(
    run.automation.env_aliases.some(
      (alias: { target: string; source: string }) =>
        alias.target === "LANGBOT_E2E_PIPELINE_URL" &&
        alias.source === "LANGBOT_LOCAL_AGENT_PIPELINE_URL",
    ),
  );
});

test("local-agent basic case can setup the local-agent pipeline env", () => {
  withEnv(
    {
      LANGBOT_BROWSER_PROFILE: "/tmp/langbot-test-profile",
      LANGBOT_CHROMIUM_EXECUTABLE: "/tmp/langbot-test-chromium",
    },
    () => {
      const result = capture(() =>
        commandTestRun(
          ctx([
            "test",
            "run",
            "local-agent-basic-debug-chat",
            "--dry-run",
            "--json",
          ]),
        ),
      );
      assert.equal(result.code, 0);
      const run = JSON.parse(result.output);
      assert.deepEqual(
        run.setup_automation.map((item: { entry: string }) => item.entry),
        ["node:scripts/e2e/ensure-local-agent-pipeline.mjs --write-env"],
      );

      const planResult = capture(() =>
        commandTestPlan(
          ctx(["test", "plan", "local-agent-basic-debug-chat", "--json"]),
        ),
      );
      assert.equal(planResult.code, 0);
      const plan = JSON.parse(planResult.output);
      assert.deepEqual(plan.setup_provides_env, [
        "LANGBOT_LOCAL_AGENT_PIPELINE_URL",
        "LANGBOT_LOCAL_AGENT_PIPELINE_NAME",
      ]);
      assert.equal(plan.automation_readiness.status, "ready");
    },
  );
});

test("local-agent nonstreaming case disables stream output through automation defaults", () => {
  const result = capture(() =>
    commandTestRun(
      ctx([
        "test",
        "run",
        "local-agent-nonstreaming-debug-chat",
        "--dry-run",
        "--json",
      ]),
    ),
  );
  assert.equal(result.code, 0);
  const run = JSON.parse(result.output);
  assert.equal(run.automation.script, "scripts/e2e/pipeline-debug-chat.mjs");
  assert.equal(
    run.automation.env_defaults.LANGBOT_E2E_PROMPT,
    "Reply only NONSTREAM_OK.",
  );
  assert.equal(
    run.automation.env_defaults.LANGBOT_E2E_EXPECTED_TEXT,
    "NONSTREAM_OK",
  );
  assert.equal(run.automation.env_defaults.LANGBOT_E2E_STREAM_OUTPUT, "0");
  assert.equal(run.automation.pipeline_env_required, true);
});

test("local-agent multimodal case exposes image fixture automation defaults", () => {
  const result = capture(() =>
    commandTestRun(
      ctx([
        "test",
        "run",
        "local-agent-multimodal-debug-chat",
        "--dry-run",
        "--json",
      ]),
    ),
  );
  assert.equal(result.code, 0);
  const run = JSON.parse(result.output);
  assert.equal(run.automation.script, "scripts/e2e/pipeline-debug-chat.mjs");
  assert.equal(
    run.automation.env_defaults.LANGBOT_E2E_EXPECTED_TEXT,
    "IMAGE_OK",
  );
  assert.match(
    run.automation.env_defaults.LANGBOT_E2E_IMAGE_BASE64_PATH,
    /red-square\.png\.base64$/,
  );
  assert.equal(run.automation.pipeline_env_required, true);
});

test("fake provider returns IMAGE_OK only when image metadata is present", async () => {
  const provider = await startFakeProviderForTest();
  try {
    const request = async (content: string) => {
      const json = await requestFakeProvider(provider, {
        messages: [{ role: "user", content }],
      });
      return fakeProviderMessage(json).content;
    };

    assert.equal(
      await request(
        "I attached an image. Reply only IMAGE_OK if you received the image.[Image]",
      ),
      "IMAGE_OK",
    );
    assert.equal(
      await request("Say hello for a plain text request."),
      "OK",
    );
  } finally {
    await provider.stop();
  }
});

test("fake provider drives steering through qa_plugin_sleep and follow-up context", async () => {
  const provider = await startFakeProviderForTest();
  try {
    const initial = fakeProviderMessage(
      await requestFakeProvider(provider, {
        tools: [
          {
            type: "function",
            function: {
              name: "qa_plugin_sleep",
              parameters: {
                type: "object",
                properties: {
                  seconds: { type: "number" },
                  text: { type: "string" },
                },
              },
            },
          },
        ],
        messages: [
          {
            role: "user",
            content:
              "First call qa_plugin_sleep with text=steering-e2e-anchor. If no follow-up was injected, reply only STEERING_NO_FOLLOWUP.",
          },
        ],
      }),
    );
    assert.equal(initial.tool_calls?.[0]?.function?.name, "qa_plugin_sleep");
    assert.equal(
      initial.tool_calls?.[0]?.function?.arguments,
      JSON.stringify({ seconds: 8, text: "steering-e2e-anchor" }),
    );

    const noFollowup = fakeProviderMessage(
      await requestFakeProvider(provider, {
        messages: [
          {
            role: "user",
            content:
              "First call qa_plugin_sleep with text=steering-e2e-anchor. If no follow-up was injected, reply only STEERING_NO_FOLLOWUP.",
          },
          initial,
          {
            role: "tool",
            tool_call_id: "call_qa_plugin_sleep_steering",
            content: "qa-plugin-smoke:sleep:8:steering-e2e-anchor",
          },
        ],
      }),
    );
    assert.equal(noFollowup.content, "STEERING_NO_FOLLOWUP");

    const withFollowup = fakeProviderMessage(
      await requestFakeProvider(provider, {
        messages: [
          {
            role: "user",
            content:
              "First call qa_plugin_sleep with text=steering-e2e-anchor. If no follow-up was injected, reply only STEERING_NO_FOLLOWUP.",
          },
          initial,
          {
            role: "tool",
            tool_call_id: "call_qa_plugin_sleep_steering",
            content: "qa-plugin-smoke:sleep:8:steering-e2e-anchor",
          },
          {
            role: "user",
            content:
              "This is a steering follow-up. Return only qa_steering_sentinel_6194.",
          },
        ],
      }),
    );
    assert.equal(withFollowup.content, "qa_steering_sentinel_6194");
  } finally {
    await provider.stop();
  }
});

test("MCP stdio case passes case-specific failure signals to automation defaults", () => {
  const result = capture(() =>
    commandTestRun(
      ctx(["test", "run", "mcp-stdio-tool-call", "--dry-run", "--json"]),
    ),
  );
  assert.equal(result.code, 0);
  const run = JSON.parse(result.output);
  assert.match(
    run.automation.env_defaults.LANGBOT_E2E_FAILURE_SIGNALS,
    /qa-plugin-smoke:mcp-ok-local-agent/,
  );
  assert.match(
    run.automation.env_defaults.LANGBOT_E2E_FAILURE_SIGNALS,
    /model_not_found/,
  );
});

test("MCP stdio tool-call case setups pipeline and registered MCP server", () => {
  withEnv({ LANGBOT_MCP_QA_STDIO_SERVER_UUID: "mcp-server-uuid" }, () => {
    const result = capture(() =>
      commandTestRun(
        ctx(["test", "run", "mcp-stdio-tool-call", "--dry-run", "--json"]),
      ),
    );
    assert.equal(result.code, 0);
    const run = JSON.parse(result.output);
    assert.deepEqual(
      run.setup_automation.map((item: { entry: string }) => item.entry),
      [
        "node:scripts/e2e/ensure-local-agent-pipeline.mjs --write-env",
        "case:mcp-stdio-register",
      ],
    );
    assert.equal(
      run.automation.env_defaults.LANGBOT_E2E_EXPECTED_RUNNER_ID,
      "plugin:langbot/local-agent/default",
    );
    assert.equal(run.automation.env_defaults.LANGBOT_E2E_RESET_DEBUG_CHAT, "1");
    assert.equal(
      run.automation.env_defaults.LANGBOT_E2E_RESTORE_EXTENSIONS,
      "1",
    );
    assert.deepEqual(
      JSON.parse(run.automation.env_defaults.LANGBOT_E2E_EXTENSIONS_PATCH_JSON),
      {
        enable_all_plugins: false,
        bound_plugins: [{ author: "langbot", name: "local-agent" }],
        enable_all_mcp_servers: false,
        bound_mcp_servers: ["mcp-server-uuid"],
        enable_all_skills: false,
        bound_skills: [],
      },
    );

    const planResult = capture(() =>
      commandTestPlan(ctx(["test", "plan", "mcp-stdio-tool-call", "--json"])),
    );
    assert.equal(planResult.code, 0);
    const plan = JSON.parse(planResult.output);
    assert.deepEqual(plan.setup_provides_env, [
      "LANGBOT_LOCAL_AGENT_PIPELINE_URL",
      "LANGBOT_LOCAL_AGENT_PIPELINE_NAME",
      "LANGBOT_MCP_QA_STDIO_SERVER_UUID",
    ]);
    assert.ok(
      !plan.preconditions.some((item: string) =>
        item.includes("points to the local-agent pipeline"),
      ),
    );
  });
});

test("generic pipeline automation can still use the shared pipeline env", () => {
  const result = capture(() =>
    commandTestRun(
      ctx(["test", "run", "pipeline-debug-chat", "--dry-run", "--json"]),
    ),
  );
  assert.equal(result.code, 0);
  const run = JSON.parse(result.output);
  assert.equal(run.automation.pipeline_env_required, false);
  assert.deepEqual(run.automation.env_aliases, []);
  assert.ok(
    run.automation.required_env.includes(
      "LANGBOT_PIPELINE_URL|LANGBOT_PIPELINE_NAME",
    ),
  );
});

test("AgentRunner live install case exposes package automation defaults", () => {
  const result = capture(() =>
    commandTestRun(
      ctx(["test", "run", "agent-runner-live-install", "--dry-run", "--json"]),
    ),
  );
  assert.equal(result.code, 0);
  const run = JSON.parse(result.output);
  assert.equal(
    run.automation.env_defaults.LANGBOT_E2E_PLUGIN_PACKAGE,
    "skills/langbot-testing/fixtures/plugins/qa-agent-runner/dist/qa-agent-runner-0.1.0.lbpkg",
  );
  assert.equal(
    run.automation.env_defaults.LANGBOT_E2E_EXPECTED_PLUGIN_ID,
    "qa/agent-runner",
  );
  assert.equal(
    run.automation.env_defaults.LANGBOT_E2E_EXPECTED_RUNNER_ID,
    "plugin:qa/agent-runner/default",
  );
});

test("QA plugin live install checks the fixture package before installed state", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-install-qa-plugin-"));
  try {
    const result = spawnSync(
      process.execPath,
      [join(root, "scripts/e2e/install-qa-plugin-smoke.mjs")],
      {
        cwd: root,
        env: {
          ...process.env,
          LBS_RUN_ID: "missing-package",
          LBS_EVIDENCE_DIR: join(tmp, "evidence"),
          LANGBOT_BACKEND_URL: "http://127.0.0.1:59999",
          LANGBOT_E2E_LOGIN_USER: "qa@example.test",
          LANGBOT_E2E_PLUGIN_PACKAGE: join(tmp, "missing.lbpkg"),
        },
        encoding: "utf8",
      },
    );
    assert.equal(result.status, 1);
    const output = JSON.parse(result.stdout);
    assert.match(output.reason, /missing\.lbpkg/);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("AgentRunner QA Debug Chat case uses dedicated pipeline env", () => {
  const result = capture(() =>
    commandTestRun(
      ctx(["test", "run", "agent-runner-qa-debug-chat", "--dry-run", "--json"]),
    ),
  );
  assert.equal(result.code, 0);
  const run = JSON.parse(result.output);
  assert.equal(run.automation.script, "scripts/e2e/pipeline-debug-chat.mjs");
  assert.equal(run.automation.pipeline_env_required, true);
  assert.equal(
    run.automation.env_defaults.LANGBOT_E2E_EXPECTED_RUNNER_ID,
    "plugin:qa/agent-runner/default",
  );
  assert.deepEqual(
    run.setup_automation.map((item: { entry: string }) => item.entry),
    [
      "case:agent-runner-live-install",
      "node:scripts/e2e/ensure-qa-agent-runner-pipeline.mjs --write-env",
    ],
  );
  assert.ok(
    run.automation.env_aliases.some(
      (alias: { target: string; source: string }) =>
        alias.target === "LANGBOT_E2E_PIPELINE_URL" &&
        alias.source === "LANGBOT_QA_AGENT_RUNNER_PIPELINE_URL",
    ),
  );
});

test("AgentRunner QA Debug Chat setup automation removes manual readiness", () => {
  withEnv(
    {
      LANGBOT_BROWSER_PROFILE: "/tmp/langbot-test-profile",
      LANGBOT_CHROMIUM_EXECUTABLE: "/tmp/langbot-test-chromium",
    },
    () => {
      const planResult = capture(() =>
        commandTestPlan(
          ctx(["test", "plan", "agent-runner-qa-debug-chat", "--json"]),
        ),
      );
      assert.equal(planResult.code, 0);
      const plan = JSON.parse(planResult.output);
      assert.equal(plan.manual_readiness.status, "not_required");
      assert.deepEqual(plan.setup_provides_env, [
        "LANGBOT_QA_AGENT_RUNNER_PIPELINE_URL",
        "LANGBOT_QA_AGENT_RUNNER_PIPELINE_NAME",
      ]);
      assert.equal(plan.automation_readiness.status, "ready");

      const suiteResult = capture(() =>
        commandSuitePlan(
          ctx(["suite", "plan", "agent-runner-release-gate", "--json"]),
        ),
      );
      assert.equal(suiteResult.code, 0);
      const suite = JSON.parse(suiteResult.output);
      assert.ok(
        !suite.readiness.manual_check_cases.includes(
          "agent-runner-qa-debug-chat",
        ),
      );
    },
  );
});

test("ACP AgentRunner Debug Chat case setups the ACP pipeline env", () => {
  const result = capture(() =>
    commandTestRun(
      ctx([
        "test",
        "run",
        "acp-agent-runner-debug-chat",
        "--dry-run",
        "--json",
      ]),
    ),
  );
  assert.equal(result.code, 0);
  const run = JSON.parse(result.output);
  assert.deepEqual(
    run.setup_automation.map((item: { entry: string }) => item.entry),
    ["node:scripts/e2e/ensure-acp-agent-runner-pipeline.mjs --write-env"],
  );
  assert.ok(
    run.automation.env_aliases.some(
      (alias: { target: string; source: string }) =>
        alias.target === "LANGBOT_E2E_PIPELINE_URL" &&
        alias.source === "LANGBOT_ACP_AGENT_RUNNER_PIPELINE_URL",
    ),
  );

  const planResult = capture(() =>
    commandTestPlan(
      ctx(["test", "plan", "acp-agent-runner-debug-chat", "--json"]),
    ),
  );
  assert.equal(planResult.code, 0);
  const plan = JSON.parse(planResult.output);
  assert.deepEqual(plan.setup_provides_env, [
    "LANGBOT_ACP_AGENT_RUNNER_PIPELINE_URL",
    "LANGBOT_ACP_AGENT_RUNNER_PIPELINE_NAME",
  ]);
  assert.ok(
    !plan.preconditions.some((item: string) =>
      item.includes("pipeline AI runner"),
    ),
  );
});

test("local-agent plugin cases setup the QA plugin smoke fixture", () => {
  const result = capture(() =>
    commandTestRun(
      ctx([
        "test",
        "run",
        "local-agent-plugin-tool-call-debug-chat",
        "--dry-run",
        "--json",
      ]),
    ),
  );
  assert.equal(result.code, 0);
  const run = JSON.parse(result.output);
  assert.deepEqual(
    run.setup_automation.map((item: { entry: string }) => item.entry),
    [
      "node:scripts/e2e/ensure-local-agent-pipeline.mjs --write-env",
      "case:qa-plugin-smoke-live-install",
    ],
  );
});

test("local-agent RAG case only requires the KB fixture env", () => {
  const result = capture(() =>
    commandTestRun(
      ctx(["test", "run", "local-agent-rag-debug-chat", "--dry-run", "--json"]),
    ),
  );
  assert.equal(result.code, 0);
  const run = JSON.parse(result.output);
  assert.ok(
    run.automation.required_env.includes("LANGBOT_LOCAL_AGENT_RAG_KB_UUID"),
  );
  assert.ok(
    !run.automation.required_env.includes(
      "LANGBOT_LOCAL_AGENT_RAG_TEXT_MODEL_UUID",
    ),
  );
  assert.equal(
    run.automation.env_defaults.LANGBOT_E2E_RUNNER_CONFIG_PATCH_JSON,
    JSON.stringify({
      "knowledge-bases": [loadEnv(root).LANGBOT_LOCAL_AGENT_RAG_KB_UUID || ""],
    }),
  );
});

test("LangRAG retrieve readiness requires a KB UUID alternative", () => {
  const result = capture(() =>
    commandTestPlan(ctx(["test", "plan", "langrag-kb-retrieve", "--json"])),
  );
  assert.equal(result.code, 0);
  const plan = JSON.parse(result.output);
  assert.ok(
    plan.automation_readiness.required.includes(
      "LANGBOT_LOCAL_AGENT_RAG_KB_UUID|LANGBOT_RAG_KB_UUID",
    ),
  );
});

test("local-agent RAG multimodal case setups the KB fixture env", () => {
  const result = capture(() =>
    commandTestRun(
      ctx([
        "test",
        "run",
        "local-agent-rag-multimodal-debug-chat",
        "--dry-run",
        "--json",
      ]),
    ),
  );
  assert.equal(result.code, 0);
  const run = JSON.parse(result.output);
  assert.ok(
    run.automation.required_env.includes("LANGBOT_LOCAL_AGENT_RAG_KB_UUID"),
  );
  assert.equal(
    run.automation.env_defaults.LANGBOT_E2E_RUNNER_CONFIG_PATCH_JSON,
    JSON.stringify({
      "knowledge-bases": [loadEnv(root).LANGBOT_LOCAL_AGENT_RAG_KB_UUID || ""],
    }),
  );
  assert.deepEqual(
    run.setup_automation.map((item: { entry: string }) => item.entry),
    [
      "node:scripts/e2e/ensure-local-agent-pipeline.mjs --write-env",
      "node:scripts/e2e/ensure-langrag-sentinel-kb.mjs --write-env",
    ],
  );
});

test("test report renders a reusable evidence template", () => {
  const result = capture(() =>
    commandTestReport(
      ctx(["test", "report", "pipeline-debug-chat", "--no-auto-log"]),
    ),
  );
  assert.equal(result.code, 0);
  assert.match(result.output, /^# Test Report: pipeline-debug-chat/m);
  assert.match(
    result.output,
    /result: pass \| fail \| blocked \| env_issue \| flaky/,
  );
  assert.match(result.output, /## Log Guard/);
  assert.match(result.output, /## Automation Result/);
  assert.match(result.output, /## Required Evidence/);
  assert.match(result.output, /no log files provided/);
});

test("test report promotes loaded automation evidence into result section", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-report-automation-"));
  try {
    writeFileSync(
      join(tmp, "automation-result.json"),
      JSON.stringify({
        status: "pass",
        reason: "latency thresholds passed",
        url: "http://127.0.0.1:5300",
        artifacts: { metrics_json: join(tmp, "metrics.json") },
      }),
    );

    const result = capture(() =>
      commandTestReport(
        ctx([
          "test",
          "report",
          "langbot-live-backend-latency",
          "--evidence-dir",
          tmp,
          "--no-auto-log",
        ]),
      ),
    );

    assert.equal(result.code, 0);
    assert.match(
      result.output,
      /## Result\n- result: pass\n- reason: latency thresholds passed/,
    );
    assert.match(result.output, /- target_tested: http:\/\/127\.0\.0\.1:5300/);
    assert.doesNotMatch(result.output, /target_tested: TODO/);
    assert.match(result.output, /## Automation Result/);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("validate rejects dangling case references and missing automation scripts", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-validate-strict-"));
  try {
    const schemasDir = join(tmp, "schemas");
    const skillsDir = join(tmp, "skills");
    const envSetupDir = join(skillsDir, "langbot-env-setup");
    const testingDir = join(skillsDir, "langbot-testing");
    mkdirSync(schemasDir, { recursive: true });
    mkdirSync(join(testingDir, "cases"), { recursive: true });
    mkdirSync(join(testingDir, "fixtures"), { recursive: true });
    mkdirSync(join(testingDir, "suites"), { recursive: true });
    mkdirSync(envSetupDir, { recursive: true });
    for (const schemaName of [
      "case.schema.json",
      "suite.schema.json",
      "troubleshooting.schema.json",
      "skill-index.schema.json",
    ]) {
      writeFileSync(join(schemasDir, schemaName), "{}");
    }
    writeFileSync(
      join(envSetupDir, "SKILL.md"),
      "---\nname: langbot-env-setup\ndescription: Env setup.\n---\n\n# Env\n",
    );
    writeFileSync(
      join(testingDir, "SKILL.md"),
      "---\nname: langbot-testing\ndescription: Testing.\n---\n\n# Testing\n",
    );
    writeFileSync(
      join(skillsDir, ".env"),
      [
        "LANGBOT_FRONTEND_URL=http://127.0.0.1:3000",
        "LANGBOT_BACKEND_URL=http://127.0.0.1:5300",
        "LANGBOT_DEV_FRONTEND_URL=http://127.0.0.1:3000",
        "LANGBOT_REPO=/tmp/langbot",
        "LANGBOT_WEB_REPO=/tmp/langbot/web",
        "LANGBOT_BROWSER_PROFILE=/tmp/browser",
        "LANGBOT_CHROMIUM_EXECUTABLE=/tmp/chromium",
        "LANGBOT_PROXY_HTTP=http://127.0.0.1:7890",
        "LANGBOT_PROXY_SOCKS=socks5://127.0.0.1:7890",
        "LANGBOT_NO_PROXY=localhost,127.0.0.1,::1",
      ].join("\n"),
    );
    writeFileSync(
      join(testingDir, "cases", "bad.yaml"),
      [
        "id: bad",
        "title: Bad",
        "mode: agent-browser",
        "area: pipeline",
        "type: smoke",
        "priority: p9",
        "risk: medium",
        "ci_eligible: false",
        "tags:",
        "  - smoke",
        "skills:",
        "  - langbot-env-setup",
        "  - langbot-testing",
        "env:",
        "  - LANGBOT_FRONTEND_URL",
        "automation: scripts/e2e/missing.mjs",
        "setup_provides_env:",
        "  - LANGBOT_PIPELINE_URL",
        "steps:",
        "  - Open UI.",
        "checks:",
        "  - UI works.",
        "evidence_required:",
        "  - ui",
        "troubleshooting:",
        "  - missing-trouble",
      ].join("\n"),
    );
    for (const [id, target] of [
      ["cycle-a", "cycle-b"],
      ["cycle-b", "cycle-a"],
    ]) {
      writeFileSync(
        join(testingDir, "cases", `${id}.yaml`),
        [
          `id: ${id}`,
          `title: ${id}`,
          "mode: probe",
          "area: qa",
          "type: smoke",
          "priority: p2",
          "risk: low",
          "ci_eligible: true",
          "tags:",
          "  - smoke",
          "skills:",
          "  - langbot-testing",
          "setup_automation:",
          `  - \"case:${target}\"`,
          "steps:",
          "  - Run probe.",
          "checks:",
          "  - Probe works.",
          "evidence_required:",
          "  - filesystem",
        ].join("\n"),
      );
    }
    writeFileSync(
      join(testingDir, "suites", "bad-suite.yaml"),
      [
        "id: bad-suite",
        "title: Bad Suite",
        "description: Bad suite for strict validation.",
        "type: release_gate",
        "priority: p1",
        "tags:",
        "  - gate",
        "cases:",
        "  - missing-case",
      ].join("\n"),
    );
    writeFileSync(
      join(testingDir, "fixtures", "fixtures.json"),
      JSON.stringify([
        {
          id: "bad-fixture",
          title: "Bad Fixture",
          path: "fixtures/missing.txt",
          related_cases: ["missing-case"],
        },
      ]),
    );

    const result = captureAll(() => commandValidate(tmp));

    assert.equal(result.code, 1);
    assert.match(result.error, /priority/);
    assert.match(result.error, /missing-trouble/);
    assert.match(result.error, /missing-case/);
    assert.match(result.error, /bad-fixture/);
    assert.match(result.error, /automation script does not exist/);
    assert.match(result.error, /setup_provides_env/);
    assert.match(result.error, /setup_automation case cycle detected/);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test report JSON scans logs and redacts secrets", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-report-"));
  try {
    const logPath = join(tmp, "backend.log");
    writeFileSync(
      logPath,
      [
        "INFO request started",
        "Action invoke_llm_stream call timed out",
        "Traceback (most recent call last):",
        "API_KEY=sk-test-secret",
      ].join("\n"),
    );

    const result = capture(() =>
      commandTestReport(
        ctx([
          "test",
          "report",
          "pipeline-debug-chat",
          "--backend-log",
          logPath,
          "--json",
        ]),
      ),
    );
    assert.equal(result.code, 0);
    assert.doesNotMatch(result.output, /sk-test-secret/);

    const report = JSON.parse(result.output);
    assert.equal(report.log_guard.status, "fail");
    assert.ok(
      report.log_guard.findings.some(
        (finding: { kind: string }) => finding.kind === "case_failure_pattern",
      ),
    );
    assert.ok(
      report.log_guard.findings.some(
        (finding: { troubleshooting_id?: string }) =>
          finding.troubleshooting_id === "plugin-runtime-timeout",
      ),
    );
    assert.ok(
      report.log_guard.findings.some(
        (finding: { kind: string }) => finding.kind === "python_traceback",
      ),
    );

    const secretFinding = report.log_guard.findings.find(
      (finding: { kind: string }) => finding.kind === "secret_leak",
    );
    assert.ok(secretFinding);
    assert.match(secretFinding.excerpt, /\[redacted\]/);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test report does not treat invalid api key wording as a secret leak", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-report-api-key-wording-"));
  try {
    const logPath = join(tmp, "backend.log");
    writeFileSync(
      logPath,
      "RequesterError: 模型请求失败: 无效的 api-key: Error code: 401 - invalid api key\n",
    );

    const result = capture(() =>
      commandTestReport(
        ctx([
          "test",
          "report",
          "mcp-stdio-tool-call",
          "--backend-log",
          logPath,
          "--json",
        ]),
      ),
    );
    assert.equal(result.code, 0);
    assert.match(result.output, /api-key: Error code/);

    const report = JSON.parse(result.output);
    assert.ok(
      !report.log_guard.findings.some(
        (finding: { kind: string }) => finding.kind === "secret_leak",
      ),
    );
    assert.ok(
      report.log_guard.findings.some(
        (finding: { troubleshooting_id?: string }) =>
          finding.troubleshooting_id === "local-agent-model-route-unavailable",
      ),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test report records declared success signals from logs", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-report-success-"));
  try {
    const logPath = join(tmp, "backend.log");
    writeFileSync(
      logPath,
      [
        "[05-21 10:31:00.000] websocket.py (1) - [INFO] : Processing request from person_websocket",
        "[05-21 10:31:01.000] runner.py (2) - [INFO] : Conversation(0) Streaming completed",
      ].join("\n"),
    );

    const result = capture(() =>
      commandTestReport(
        ctx([
          "test",
          "report",
          "pipeline-debug-chat",
          "--backend-log",
          logPath,
          "--json",
        ]),
      ),
    );
    assert.equal(result.code, 0);
    const report = JSON.parse(result.output);
    assert.equal(report.log_guard.status, "pass");
    assert.equal(report.log_guard.success_signals.length, 2);
    assert.ok(
      report.log_guard.success_signals.some(
        (signal: { pattern: string }) =>
          signal.pattern === "Streaming completed",
      ),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test report warns when declared success signals are missing", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-report-missing-success-"));
  try {
    const logPath = join(tmp, "backend.log");
    writeFileSync(logPath, "INFO request started\nINFO request ended\n");

    const result = capture(() =>
      commandTestReport(
        ctx([
          "test",
          "report",
          "pipeline-debug-chat",
          "--backend-log",
          logPath,
          "--json",
        ]),
      ),
    );
    assert.equal(result.code, 0);
    const report = JSON.parse(result.output);
    assert.equal(report.log_guard.status, "warning");
    assert.ok(
      report.log_guard.findings.some(
        (finding: { kind: string }) =>
          finding.kind === "missing_success_signal",
      ),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test report can limit log guard to tail lines", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-report-tail-"));
  try {
    const logPath = join(tmp, "backend.log");
    writeFileSync(
      logPath,
      [
        "ERROR old failure outside scan window",
        "INFO middle",
        "Action invoke_llm_stream call timed out",
        "API_KEY=sk-tail-secret",
      ].join("\n"),
    );

    const result = capture(() =>
      commandTestReport(
        ctx([
          "test",
          "report",
          "pipeline-debug-chat",
          "--backend-log",
          logPath,
          "--tail-lines",
          "2",
          "--json",
        ]),
      ),
    );
    assert.equal(result.code, 0);
    const report = JSON.parse(result.output);
    assert.equal(report.log_guard.scan.mode, "tail-lines");
    assert.equal(report.log_guard.scan.tail_lines, 2);
    assert.equal(report.log_guard.sources[0].line_count, 2);
    assert.equal(report.log_guard.sources[0].start_line, 3);
    assert.ok(
      report.log_guard.findings.some(
        (finding: { troubleshooting_id?: string }) =>
          finding.troubleshooting_id === "plugin-runtime-timeout",
      ),
    );
    assert.ok(
      !report.log_guard.findings.some(
        (finding: { kind: string; excerpt?: string }) =>
          finding.kind === "error_log" &&
          finding.excerpt?.includes("old failure"),
      ),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test report can limit log guard with since timestamp", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-report-since-"));
  try {
    const logPath = join(tmp, "backend.log");
    writeFileSync(
      logPath,
      [
        "[05-21 09:59:00.000] old.py (1) - [ERROR] : old failure outside scan window",
        "[05-21 10:31:00.000] runner.py (2) - [ERROR] : Action invoke_llm_stream call timed out",
        "Traceback continuation should stay with the matching timestamp block",
        "[05-21 10:32:00.000] secrets.py (3) - [INFO] : API_KEY=sk-since-secret",
      ].join("\n"),
    );

    const result = capture(() =>
      commandTestReport(
        ctx([
          "test",
          "report",
          "pipeline-debug-chat",
          "--backend-log",
          logPath,
          "--since",
          "2026-05-21T10:30:00+08:00",
          "--json",
        ]),
      ),
    );
    assert.equal(result.code, 0);
    const report = JSON.parse(result.output);
    assert.equal(report.log_guard.scan.mode, "since");
    assert.equal(report.log_guard.sources[0].line_count, 3);
    assert.equal(report.log_guard.sources[0].start_line, 2);
    assert.equal(report.log_guard.sources[0].timestamped_line_count, 3);
    assert.ok(
      report.log_guard.findings.some(
        (finding: { line?: number; troubleshooting_id?: string }) =>
          finding.line === 2 &&
          finding.troubleshooting_id === "plugin-runtime-timeout",
      ),
    );
    assert.ok(
      !report.log_guard.findings.some((finding: { excerpt?: string }) =>
        finding.excerpt?.includes("old failure"),
      ),
    );
    assert.doesNotMatch(result.output, /sk-since-secret/);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test report can limit log guard with since and until timestamps", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-report-window-"));
  try {
    const logPath = join(tmp, "backend.log");
    writeFileSync(
      logPath,
      [
        "[05-21 10:29:59.000] old.py (1) - [ERROR] : old failure outside scan window",
        "[05-21 10:31:00.000] runner.py (2) - [INFO] : Processing request from person_websocket",
        "[05-21 10:31:01.000] runner.py (3) - [INFO] : Conversation(0) Streaming completed",
        "[05-21 10:32:01.000] later.py (4) - [ERROR] : later failure outside scan window",
      ].join("\n"),
    );

    const result = capture(() =>
      commandTestReport(
        ctx([
          "test",
          "report",
          "pipeline-debug-chat",
          "--backend-log",
          logPath,
          "--since",
          "2026-05-21T10:30:00+08:00",
          "--until",
          "2026-05-21T10:32:00+08:00",
          "--json",
        ]),
      ),
    );
    assert.equal(result.code, 0);
    const report = JSON.parse(result.output);
    assert.equal(report.log_guard.scan.mode, "since+until");
    assert.equal(report.log_guard.sources[0].line_count, 2);
    assert.equal(report.log_guard.sources[0].start_line, 2);
    assert.equal(report.log_guard.sources[0].end_line, 3);
    assert.equal(report.log_guard.status, "pass");
    assert.ok(
      !report.log_guard.findings.some((finding: { excerpt?: string }) =>
        finding.excerpt?.includes("old failure"),
      ),
    );
    assert.ok(
      !report.log_guard.findings.some((finding: { excerpt?: string }) =>
        finding.excerpt?.includes("later failure"),
      ),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test report classifies model route failures as env_issue", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-report-env-issue-"));
  try {
    const logPath = join(tmp, "backend.log");
    writeFileSync(
      logPath,
      "[05-21 10:31:00.000] runner.py (2) - [ERROR] : runner.llm_error model_not_found no available channel for model gpt-test\n",
    );

    const result = capture(() =>
      commandTestReport(
        ctx([
          "test",
          "report",
          "local-agent-plugin-tool-call-debug-chat",
          "--backend-log",
          logPath,
          "--json",
        ]),
      ),
    );
    assert.equal(result.code, 0);
    const report = JSON.parse(result.output);
    assert.equal(report.log_guard.status, "env_issue");
    assert.ok(
      report.log_guard.findings.some(
        (finding: { severity?: string; troubleshooting_id?: string }) =>
          finding.severity === "env_issue" &&
          finding.troubleshooting_id === "local-agent-model-route-unavailable",
      ),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test report infers scan window from automation result evidence", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-report-evidence-window-"));
  try {
    const evidenceDir = join(tmp, "evidence", "run-123");
    mkdirSync(evidenceDir, { recursive: true });
    const consoleLog = join(evidenceDir, "console.log");
    writeFileSync(
      consoleLog,
      [
        "[05-21 10:29:59.000] old.js (1) - [ERROR] : old failure outside scan window",
        "[05-21 10:31:00.000] runner.js (2) - [INFO] : Processing request from person_websocket",
        "[05-21 10:31:01.000] runner.js (3) - [INFO] : Conversation(0) Streaming completed",
        "[05-21 10:32:01.000] later.js (4) - [ERROR] : later failure outside scan window",
      ].join("\n"),
    );
    writeFileSync(
      join(evidenceDir, "automation-result.json"),
      JSON.stringify({
        source: "automation",
        status: "pass",
        reason: "UI sentinel appeared.",
        started_at_local: "2026-05-21T10:30:00.000+08:00",
        finished_at_local: "2026-05-21T10:32:00.000+08:00",
      }),
    );

    const result = capture(() =>
      commandTestReport(
        ctx([
          "test",
          "report",
          "pipeline-debug-chat",
          "--console-log",
          consoleLog,
          "--no-auto-log",
          "--json",
        ]),
      ),
    );
    assert.equal(result.code, 0);
    const report = JSON.parse(result.output);
    assert.equal(report.log_guard.scan.mode, "since+until");
    assert.equal(report.log_guard.scan.since, "2026-05-21T10:30:00.000+08:00");
    assert.equal(report.log_guard.scan.until, "2026-05-21T10:32:00.000+08:00");
    assert.equal(report.log_guard.sources[0].line_count, 2);
    assert.equal(report.log_guard.status, "pass");
    assert.equal(report.automation_result.status, "loaded");
    assert.equal(report.automation_result.result, "pass");
    assert.equal(report.automation_result.reason, "UI sentinel appeared.");
    assert.ok(
      !report.log_guard.findings.some((finding: { excerpt?: string }) =>
        finding.excerpt?.includes("old failure"),
      ),
    );
    assert.ok(
      !report.log_guard.findings.some((finding: { excerpt?: string }) =>
        finding.excerpt?.includes("later failure"),
      ),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test report does not treat final result as automation evidence", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-report-final-result-"));
  try {
    const evidenceDir = join(tmp, "evidence", "run-final");
    mkdirSync(evidenceDir, { recursive: true });
    const consoleLog = join(evidenceDir, "console.log");
    writeFileSync(
      consoleLog,
      "[05-21 10:31:00.000] ui.js (1) - [INFO] : opened\n",
    );
    writeFileSync(
      join(evidenceDir, "result.json"),
      JSON.stringify({
        source: "final",
        status: "pass",
        reason: "Final manual decision.",
        started_at_local: "2026-05-21T10:30:00.000+08:00",
        finished_at_local: "2026-05-21T10:32:00.000+08:00",
        evidence_collected: ["ui", "screenshot", "console"],
      }),
    );

    const result = capture(() =>
      commandTestReport(
        ctx([
          "test",
          "report",
          "webui-login-state",
          "--console-log",
          consoleLog,
          "--no-auto-log",
          "--json",
        ]),
      ),
    );

    assert.equal(result.code, 0);
    const report = JSON.parse(result.output);
    assert.equal(report.automation_result.status, "not_provided");
    assert.match(
      report.automation_result.reason,
      /only final result\.json is present/,
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test report still scans untimestamped explicit console evidence within an inferred run window", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-report-untimestamped-console-"));
  try {
    const evidenceDir = join(tmp, "evidence", "run-untimestamped");
    mkdirSync(evidenceDir, { recursive: true });
    const consoleLog = join(evidenceDir, "console.log");
    writeFileSync(
      consoleLog,
      "[error] Uncaught TypeError: Cannot read properties of undefined\n",
    );
    writeFileSync(
      join(evidenceDir, "result.json"),
      JSON.stringify({
        status: "pass",
        reason: "UI sentinel appeared.",
        started_at_local: "2026-05-21T10:30:00.000+08:00",
        finished_at_local: "2026-05-21T10:32:00.000+08:00",
      }),
    );

    const result = capture(() =>
      commandTestReport(
        ctx([
          "test",
          "report",
          "webui-login-state",
          "--console-log",
          consoleLog,
          "--no-auto-log",
          "--json",
        ]),
      ),
    );

    assert.equal(result.code, 0);
    const report = JSON.parse(result.output);
    assert.equal(report.log_guard.scan.mode, "since+until");
    assert.equal(report.log_guard.sources[0].timestamped_line_count, 0);
    assert.ok(report.log_guard.sources[0].line_count >= 1);
    assert.equal(report.log_guard.status, "fail");
    assert.ok(
      report.log_guard.findings.some(
        (finding: { kind: string }) =>
          finding.kind === "frontend_uncaught_error",
      ),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("test report can write markdown to an output path", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-report-output-"));
  try {
    const output = join(tmp, "reports", "pipeline-debug-chat.md");
    const result = capture(() =>
      commandTestReport(
        ctx(["test", "report", "pipeline-debug-chat", "--output", output]),
      ),
    );
    assert.equal(result.code, 0);
    assert.match(result.output, /pipeline-debug-chat\.md$/);
    assert.match(
      readFileSync(output, "utf8"),
      /^# Test Report: pipeline-debug-chat/m,
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("log scan reuses case-aware log guard patterns", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-log-scan-"));
  try {
    const logPath = join(tmp, "backend.log");
    writeFileSync(
      logPath,
      [
        "[05-21 10:31:00.000] process.py (1) - [INFO] : Processing request from person_websocket",
        "[05-21 10:31:01.000] chat.py (2) - [INFO] : Conversation(0) Streaming completed",
        "[05-21 10:31:02.000] runner.py (3) - [ERROR] : Action invoke_llm_stream call timed out",
      ].join("\n"),
    );

    const result = capture(() =>
      commandLogScan(
        ctx([
          "log",
          "scan",
          "--backend-log",
          logPath,
          "--case",
          "pipeline-debug-chat",
          "--json",
        ]),
      ),
    );

    assert.equal(result.code, 0);
    const report = JSON.parse(result.output);
    assert.equal(report.status, "fail");
    assert.ok(
      report.success_signals.some(
        (signal: { pattern: string }) =>
          signal.pattern === "Streaming completed",
      ),
    );
    assert.ok(
      report.findings.some(
        (finding: { kind: string }) => finding.kind === "case_failure_pattern",
      ),
    );

    const strict = capture(() =>
      commandLogScan(
        ctx([
          "log",
          "scan",
          "--backend-log",
          logPath,
          "--case",
          "pipeline-debug-chat",
          "--strict",
          "--json",
        ]),
      ),
    );
    assert.equal(strict.code, 1);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("log guard start and stop bound a QA log window", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-log-guard-"));
  try {
    const logPath = join(tmp, "backend.log");
    const outputDir = join(tmp, "guards");
    writeFileSync(logPath, "INFO before guard\n");

    const start = capture(() =>
      commandLogGuard(
        ctx([
          "log",
          "guard",
          "start",
          "--run-id",
          "qa-run",
          "--output-dir",
          outputDir,
          "--backend-log",
          logPath,
          "--case",
          "pipeline-debug-chat",
          "--json",
        ]),
      ),
    );
    assert.equal(start.code, 0);
    const session = JSON.parse(start.output);
    assert.equal(session.run_id, "qa-run");
    assert.ok(existsSync(join(outputDir, "qa-run.json")));

    appendFileSync(logPath, "Traceback (most recent call last):\n");
    const stop = capture(() =>
      commandLogGuard(
        ctx([
          "log",
          "guard",
          "stop",
          "--run-id",
          "qa-run",
          "--output-dir",
          outputDir,
          "--json",
        ]),
      ),
    );

    assert.equal(stop.code, 1);
    const report = JSON.parse(stop.output);
    assert.equal(report.session.run_id, "qa-run");
    assert.equal(report.result.status, "fail");
    assert.ok(
      report.result.findings.some(
        (finding: { kind: string }) => finding.kind === "python_traceback",
      ),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("log watch observes appended LangBot backend lines", async () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-log-watch-"));
  try {
    const logPath = join(tmp, "backend.log");
    writeFileSync(logPath, "INFO existing line\n");

    const watching = captureAsync(() =>
      commandLogWatch(
        ctx([
          "log",
          "watch",
          "--backend-log",
          logPath,
          "--duration-ms",
          "220",
          "--interval-ms",
          "20",
          "--strict",
          "--json",
        ]),
      ),
    );
    setTimeout(() => {
      appendFileSync(logPath, "Traceback (most recent call last):\n");
    }, 50);

    const result = await watching;
    assert.equal(result.code, 1);
    const summary = JSON.parse(result.output);
    assert.equal(summary.mode, "watch");
    assert.equal(summary.status, "fail");
    assert.ok(summary.bytes_read > 0);
    assert.ok(
      summary.findings.some(
        (finding: { kind: string }) => finding.kind === "python_traceback",
      ),
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test("trouble search finds structured troubleshooting entries", () => {
  const result = capture(() =>
    commandTroubleSearch(ctx(["trouble", "search", "proxy"])),
  );
  assert.equal(result.code, 0);
  assert.match(result.output, /proxy-env-mismatch/);
});

test("env local overrides shared env defaults", () => {
  const tmp = mkdtempSync(join(tmpdir(), "lbs-env-"));
  try {
    mkdirSync(join(tmp, "skills"));
    writeFileSync(
      join(tmp, "skills", ".env"),
      "LANGBOT_REPO=/shared\nLANGBOT_BACKEND_URL=http://127.0.0.1:5300\n",
    );
    writeFileSync(join(tmp, "skills", ".env.local"), "LANGBOT_REPO=/local\n");

    assert.deepEqual(loadEnv(tmp), {
      LANGBOT_REPO: "/local",
      LANGBOT_BACKEND_URL: "http://127.0.0.1:5300",
    });
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});
