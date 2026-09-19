#!/usr/bin/env node

import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { env } from "node:process";
import { spawnSync } from "node:child_process";
import {
  apiJson,
  boxWorkspaceNamespace,
  ensureEvidence,
  evidencePaths,
  loadEnvFiles,
  resetAndAuthLocalUser,
  resolveWorkspaceUuid,
  writeResult,
} from "./lib/langbot-e2e.mjs";

const DEFAULT_LOCAL_PASSWORD = "LangBotE2ELocalPass!2026";

await loadEnvFiles();
const paths = evidencePaths("reset-complex-agent-task");
await ensureEvidence(paths);

const scriptDir = dirname(fileURLToPath(import.meta.url));
const source = resolve(
  scriptDir,
  "../../skills/langbot-testing/fixtures/complex-agent-task/workspace",
);
const repo = env.LANGBOT_REPO || "";
let target = "";
const result = {
  source: "setup_automation",
  case_id: "reset-complex-agent-task",
  run_id: paths.runId,
  status: "fail",
  reason: "",
  target,
  initial_test_exit_code: null,
  evidence_collected: ["filesystem"],
};

try {
  if (!repo) throw new Error("LANGBOT_REPO is required.");
  const backendUrl = env.LANGBOT_BACKEND_URL || "";
  const user = env.LANGBOT_E2E_LOGIN_USER || "";
  const password = env.LANGBOT_E2E_LOGIN_PASSWORD || DEFAULT_LOCAL_PASSWORD;
  if (!backendUrl) throw new Error("LANGBOT_BACKEND_URL is required.");
  if (!user) throw new Error("LANGBOT_E2E_LOGIN_USER is required.");

  const auth = await resetAndAuthLocalUser({ backendUrl, user, password });
  const workspaceUuid = await resolveWorkspaceUuid(backendUrl, auth.token);
  const bootstrap = await apiJson(backendUrl, "/api/v1/workspaces/bootstrap", {
    token: auth.token,
    skipWorkspace: true,
  });
  const workspaceAccess = (bootstrap.json.data?.workspaces || []).find(
    (entry) => (entry.workspace?.uuid || entry.uuid) === workspaceUuid,
  );
  const instanceUuid = workspaceAccess?.workspace?.instance_uuid || workspaceAccess?.instance_uuid || "";
  if (!instanceUuid) throw new Error("Workspace bootstrap did not include instance_uuid.");

  const boxWorkspace = env.LANGBOT_BOX_WORKSPACE_HOST_PATH || resolve(
    repo,
    "data/box/default/tenants",
    boxWorkspaceNamespace(instanceUuid, workspaceUuid),
  );
  target = resolve(boxWorkspace, "order-orchestrator");
  result.target = target;
  result.workspace_uuid = workspaceUuid;
  await rm(target, { recursive: true, force: true });
  await mkdir(dirname(target), { recursive: true });
  await cp(source, target, { recursive: true });

  const baseline = spawnSync(
    "python3",
    ["-m", "unittest", "discover", "-s", "tests", "-v"],
    { cwd: target, encoding: "utf8", timeout: 60_000 },
  );
  result.initial_test_exit_code = baseline.status;
  result.initial_failure_preview = `${baseline.stdout || ""}\n${baseline.stderr || ""}`.slice(0, 4000);
  if (baseline.error) throw baseline.error;
  if (baseline.status === 0) throw new Error("Complex task baseline unexpectedly passes; the fixture must start failing.");

  await upsertEnvLocal(resolve("skills/.env.local"), {
    LANGBOT_COMPLEX_AGENT_WORKSPACE: target,
  });

  result.status = "pass";
  result.reason = "Complex task workspace reset and failing baseline confirmed.";
} catch (error) {
  result.status = /required|ENOENT/.test(error.message) ? "env_issue" : "fail";
  result.reason = error.message;
}

await writeResult(paths, result);
console.log(JSON.stringify(result, null, 2));
process.exit(result.status === "pass" ? 0 : result.status === "env_issue" ? 2 : 1);

async function upsertEnvLocal(path, updates) {
  let content = "";
  try {
    content = await readFile(path, "utf8");
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  const lines = content ? content.split(/\r?\n/) : [];
  for (const [key, value] of Object.entries(updates)) {
    const replacement = `${key}=${value}`;
    const index = lines.findIndex((line) => line.startsWith(`${key}=`));
    if (index >= 0) lines[index] = replacement;
    else lines.push(replacement);
  }
  await writeFile(path, `${lines.filter(Boolean).join("\n")}\n`, "utf8");
}
