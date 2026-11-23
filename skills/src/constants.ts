export const requiredEnvKeys = [
  "LANGBOT_FRONTEND_URL",
  "LANGBOT_BACKEND_URL",
  "LANGBOT_DEV_FRONTEND_URL",
  "LANGBOT_REPO",
  "LANGBOT_WEB_REPO",
  "LANGBOT_BROWSER_PROFILE",
  "LANGBOT_CHROMIUM_EXECUTABLE",
];

export const caseModeValues = ["agent-browser", "probe"];
export const caseTypeValues = [
  "smoke",
  "regression",
  "feature",
  "provider",
  "exploratory",
  "contract",
  "performance",
  "reliability",
  "chaos",
  "security",
];
export const casePriorityValues = ["p0", "p1", "p2"];
export const caseRiskValues = ["low", "medium", "high"];
export const caseEvidenceValues = [
  "ui",
  "screenshot",
  "console",
  "network",
  "backend_log",
  "frontend_log",
  "api_diagnostic",
  "filesystem",
  "metrics",
  "trace",
  "profile",
  "resource_log",
];
export const testResultStatusValues = ["pass", "fail", "blocked", "env_issue", "flaky"];
export const troubleshootingCategoryValues = ["product", "env_issue", "external_dependency", "blocked", "flaky"];
export const suiteTypeValues = [
  "smoke",
  "regression",
  "release_gate",
  "exploratory",
  "contract",
  "performance",
  "reliability",
  "chaos",
  "security",
];
export const suiteRequiredStrings = ["id", "title", "description", "type", "priority"];
export const suiteRequiredLists = ["tags", "cases"];

export const caseRequiredStrings = ["id", "title", "mode", "area", "type", "priority", "risk"];
export const caseRequiredLists = ["tags", "skills", "env", "steps", "checks", "evidence_required"];
export const troubleRequiredStrings = ["id", "title", "verification"];
export const troubleRequiredLists = ["symptoms", "patterns", "likely_causes", "fix_steps"];
