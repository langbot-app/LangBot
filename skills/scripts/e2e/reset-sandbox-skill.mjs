#!/usr/bin/env node

import { env } from "node:process";
import {
  apiJson,
  ensureEvidence,
  evidencePaths,
  loadEnvFiles,
  resetAndAuthLocalUser,
  writeResult,
} from "./lib/langbot-e2e.mjs";

const DEFAULT_LOCAL_PASSWORD = "LangBotE2ELocalPass!2026";
const caseId = "reset-sandbox-skill";

await loadEnvFiles();
const paths = evidencePaths(caseId);
await ensureEvidence(paths);

const nameArgument = process.argv.find((argument) => argument.startsWith("--name="));
const skillName = nameArgument?.slice("--name=".length).trim() || "";
const backendUrl = env.LANGBOT_BACKEND_URL || "";
const result = {
  source: "setup_automation",
  case_id: caseId,
  run_id: paths.runId,
  status: "fail",
  reason: "",
  skill_name: skillName,
  existed: false,
  deleted: false,
  evidence_collected: ["api_diagnostic"],
};

try {
  if (!backendUrl) throw new Error("LANGBOT_BACKEND_URL is not configured.");
  if (!skillName || !/^[A-Za-z0-9_-]+$/.test(skillName)) {
    throw new Error("--name must contain only letters, numbers, hyphens, or underscores.");
  }

  const user = env.LANGBOT_E2E_LOGIN_USER || "";
  if (!user) throw new Error("LANGBOT_E2E_LOGIN_USER is required.");
  const password = env.LANGBOT_E2E_LOGIN_PASSWORD || DEFAULT_LOCAL_PASSWORD;
  const auth = await resetAndAuthLocalUser({ backendUrl, user, password });
  const listed = await apiJson(backendUrl, "/api/v1/skills", { token: auth.token });
  if (listed.status >= 400 || listed.json.code !== 0) {
    throw new Error(listed.json.msg || `Skill listing failed with HTTP ${listed.status}.`);
  }

  result.existed = (listed.json.data?.skills || []).some((skill) => skill?.name === skillName);
  if (result.existed) {
    const deleted = await apiJson(
      backendUrl,
      `/api/v1/skills/${encodeURIComponent(skillName)}`,
      { method: "DELETE", token: auth.token },
    );
    if (deleted.status >= 400 || deleted.json.code !== 0) {
      throw new Error(deleted.json.msg || `Skill deletion failed with HTTP ${deleted.status}.`);
    }
    result.deleted = true;
  }

  result.status = "pass";
  result.reason = result.deleted
    ? `Removed stale sandbox skill ${skillName}.`
    : `Sandbox skill ${skillName} was already absent.`;
} catch (error) {
  result.status = /ECONNREFUSED|fetch failed|not configured|required/.test(error.message)
    ? "env_issue"
    : "fail";
  result.reason = error.message;
}

await writeResult(paths, result);
console.log(JSON.stringify(result, null, 2));
process.exit(result.status === "pass" ? 0 : result.status === "env_issue" ? 2 : 1);
