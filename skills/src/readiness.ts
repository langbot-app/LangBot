import { env as processEnv } from "node:process";
import type { StructuredItem } from "./types.ts";
import { loadFixtureItems } from "./fixtures.ts";
import { listValue, loadEnv, scalar } from "./fs.ts";
import { splitEnvAnyGroup } from "./env-groups.ts";

type EnvSource = Record<string, string | undefined>;

export type EnvReadiness = {
  status: "ready" | "missing" | "not_required";
  required: string[];
  configured: string[];
  missing: string[];
  values: Record<string, string>;
};

export type AutomationReadiness = EnvReadiness & {
  script: string;
  defaulted: string[];
  pipeline_env_required: boolean;
  env_aliases: Array<{
    target: string;
    source: string;
    configured: boolean;
  }>;
};

export type ManualReadiness = {
  status: "manual_check" | "not_required";
  preconditions: string[];
  setup: string[];
  cleanup: string[];
};

export type FixtureReadiness = {
  status: "ready" | "missing" | "not_required";
  required: Array<{
    id: string;
    kind: string;
    path: string;
    exists: boolean;
  }>;
  missing: string[];
};

const secretKeyRe = /(?:api[_-]?key|authorization|bearer|credential|jwt|oauth|password|secret|token)/i;

export function redactEnvValue(key: string, value: string): string {
  if (!value) return "";
  if (secretKeyRe.test(key)) return "[redacted]";
  return value.replace(/(https?:\/\/)([^:@/\s]+):([^@/\s]+)@/i, "$1[redacted]@");
}

export function runtimeEnv(root: string): Record<string, string> {
  const result: Record<string, string> = { ...loadEnv(root) };
  for (const [key, value] of Object.entries(processEnv)) {
    if (typeof value === "string") result[key] = value;
  }
  return result;
}

function envReadiness(
  keys: string[],
  env: EnvSource,
  defaults: Record<string, string> = {},
  anyGroups: string[] = [],
  providedBySetup: Set<string> = new Set(),
): EnvReadiness {
  const required = [...keys];
  const configured = required.filter((key) => Boolean(env[key]) || Boolean(defaults[key]) || providedBySetup.has(key));
  const missing = required.filter((key) => !env[key] && !defaults[key] && !providedBySetup.has(key));
  const values: Record<string, string> = Object.fromEntries(
    required.map((key) => [key, redactEnvValue(key, env[key] ?? defaults[key] ?? setupProvidedValue(key, providedBySetup))]),
  );

  for (const group of anyGroups) {
    const keysInGroup = splitEnvAnyGroup(group);
    required.push(group);
    const configuredKeys = keysInGroup.filter((key) => Boolean(env[key]) || Boolean(defaults[key]) || providedBySetup.has(key));
    if (configuredKeys.length === 0) missing.push(group);
    else configured.push(...configuredKeys);
    for (const key of keysInGroup) {
      values[key] = redactEnvValue(key, env[key] ?? defaults[key] ?? setupProvidedValue(key, providedBySetup));
    }
  }

  return {
    status: required.length === 0 ? "not_required" : missing.length === 0 ? "ready" : "missing",
    required,
    configured: Array.from(new Set(configured)),
    missing,
    values,
  };
}

function setupProvidedValue(key: string, providedBySetup: Set<string>): string {
  return providedBySetup.has(key) ? "[provided by setup_automation]" : "";
}

export function setupProvidedEnv(item: StructuredItem): Set<string> {
  return new Set(listValue(item.fields, "setup_provides_env"));
}

export function automationEnvDefaults(item: StructuredItem, env: EnvSource = processEnv): Record<string, string> {
  const mapping: Array<[string, string]> = [
    ["automation_prompt", "LANGBOT_E2E_PROMPT"],
    ["automation_prompts_json", "LANGBOT_E2E_PROMPTS_JSON"],
    ["automation_expected_text", "LANGBOT_E2E_EXPECTED_TEXT"],
    ["automation_response_timeout_ms", "LANGBOT_E2E_RESPONSE_TIMEOUT_MS"],
    ["automation_stream_output", "LANGBOT_E2E_STREAM_OUTPUT"],
    ["automation_image_base64_fixture", "LANGBOT_E2E_IMAGE_BASE64_PATH"],
    ["automation_runner_config_patch_json", "LANGBOT_E2E_RUNNER_CONFIG_PATCH_JSON"],
    ["automation_restore_runner_config", "LANGBOT_E2E_RESTORE_RUNNER_CONFIG"],
    ["automation_expected_runner_id", "LANGBOT_E2E_EXPECTED_RUNNER_ID"],
    ["automation_reset_debug_chat", "LANGBOT_E2E_RESET_DEBUG_CHAT"],
    ["automation_debug_chat_session_type", "LANGBOT_E2E_DEBUG_CHAT_SESSION_TYPE"],
    ["automation_filesystem_checks_json", "LANGBOT_E2E_FILESYSTEM_CHECKS_JSON"],
    ["automation_plugin_package", "LANGBOT_E2E_PLUGIN_PACKAGE"],
    ["automation_expected_plugin_id", "LANGBOT_E2E_EXPECTED_PLUGIN_ID"],
    ["automation_expected_tool", "LANGBOT_E2E_EXPECTED_TOOL"],
  ];
  const defaults: Record<string, string> = {};
  for (const [field, envKey] of mapping) {
    const value = scalar(item.fields, field);
    if (value) defaults[envKey] = expandEnvRefs(value, env);
  }
  const failurePatterns = listValue(item.fields, "failure_patterns");
  if (failurePatterns.length > 0) defaults.LANGBOT_E2E_FAILURE_SIGNALS = failurePatterns.join("\n");
  return defaults;
}

function expandEnvRefs(value: string, env: EnvSource): string {
  return value.replace(/\$\{([A-Z][A-Z0-9_]*)\}|\$([A-Z][A-Z0-9_]*)/g, (_match, braced, bare) => {
    return env[braced || bare] || "";
  });
}

export function caseEnvReadiness(item: StructuredItem, env: EnvSource): EnvReadiness {
  const aliasSources = new Set(automationEnvAliases(item, env).map((alias) => alias.source));
  const provided = setupProvidedEnv(item);
  return envReadiness(
    listValue(item.fields, "env").filter((key) => !aliasSources.has(key)),
    env,
    {},
    listValue(item.fields, "env_any"),
    provided,
  );
}

function automationEnvAliases(item: StructuredItem, env: EnvSource): Array<{
  target: string;
  source: string;
  configured: boolean;
}> {
  const provided = setupProvidedEnv(item);
  const mapping: Array<[string, string]> = [
    ["automation_pipeline_url_env", "LANGBOT_E2E_PIPELINE_URL"],
    ["automation_pipeline_name_env", "LANGBOT_E2E_PIPELINE_NAME"],
  ];
  return mapping
    .map(([field, target]) => {
      const source = scalar(item.fields, field);
      return source ? { target, source, configured: Boolean(env[source]) || provided.has(source) } : null;
    })
    .filter((item): item is { target: string; source: string; configured: boolean } => item !== null);
}

export function automationPipelineEnvRequired(item: StructuredItem): boolean {
  return Boolean(scalar(item.fields, "automation_pipeline_url_env") || scalar(item.fields, "automation_pipeline_name_env"));
}

export function caseAutomationReadiness(item: StructuredItem, env: EnvSource): AutomationReadiness {
  const script = scalar(item.fields, "automation");
  const aliases = automationEnvAliases(item, env);
  const aliasSources = new Set(aliases.map((alias) => alias.source));
  const defaults = automationEnvDefaults(item, env);
  const provided = setupProvidedEnv(item);
  const requiredKeys = listValue(item.fields, "automation_env").filter((key) => !aliasSources.has(key));
  const readiness = envReadiness(requiredKeys, env, defaults, listValue(item.fields, "automation_env_any"), provided);
  const defaulted = requiredKeys.filter((key) => !env[key] && Boolean(defaults[key]));
  const aliasConfigured = aliases.some((alias) => alias.configured);
  const aliasMissing = automationPipelineEnvRequired(item) && !aliasConfigured
    ? [aliases.map((alias) => alias.source).join("|")]
    : [];
  const missing = [...readiness.missing, ...aliasMissing].filter(Boolean);
  const configured = [
    ...readiness.configured,
    ...aliases.filter((alias) => alias.configured).map((alias) => alias.source),
  ];
  const values = {
    ...readiness.values,
    ...Object.fromEntries(aliases.map((alias) => [
      alias.source,
      redactEnvValue(alias.source, env[alias.source] ?? setupProvidedValue(alias.source, provided)),
    ])),
  };
  return {
    ...readiness,
    status: script ? missing.length === 0 ? "ready" : "missing" : "not_required",
    script,
    defaulted,
    required: [...readiness.required, ...aliases.map((alias) => alias.source)],
    configured,
    missing,
    values,
    pipeline_env_required: automationPipelineEnvRequired(item),
    env_aliases: aliases,
  };
}

export function resolvedAutomationEnvOverrides(item: StructuredItem, env: EnvSource): Record<string, string> {
  const overrides: Record<string, string> = {};
  for (const alias of automationEnvAliases(item, env)) {
    const value = env[alias.source];
    if (value) overrides[alias.target] = value;
  }
  for (const [key, value] of Object.entries(automationEnvDefaults(item, env))) {
    overrides[key] = expandEnvRefs(value, env);
  }
  if (automationPipelineEnvRequired(item)) overrides.LANGBOT_E2E_PIPELINE_REQUIRED = "1";
  return overrides;
}

export function caseManualReadiness(item: StructuredItem): ManualReadiness {
  const preconditions = listValue(item.fields, "preconditions");
  const setup = listValue(item.fields, "setup");
  const cleanup = listValue(item.fields, "cleanup");
  return {
    status: preconditions.length > 0 || setup.length > 0 ? "manual_check" : "not_required",
    preconditions,
    setup,
    cleanup,
  };
}

export function caseFixtureReadiness(root: string, caseId: string): FixtureReadiness {
  const fixtures = loadFixtureItems(root).items
    .filter((item) => item.related_cases.includes(caseId))
    .map((item) => ({
      id: item.id,
      kind: item.kind,
      path: item.path,
      exists: item.exists,
    }));
  const missing = fixtures.filter((item) => !item.exists).map((item) => item.id);
  return {
    status: fixtures.length === 0 ? "not_required" : missing.length === 0 ? "ready" : "missing",
    required: fixtures,
    missing,
  };
}
