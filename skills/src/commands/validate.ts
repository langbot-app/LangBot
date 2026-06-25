import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { stderr } from "node:process";
import type { Skill, StructuredItem } from "../types.ts";
import { loadFixtureItems } from "../fixtures.ts";
import {
  caseEvidenceValues,
  caseModeValues,
  casePriorityValues,
  caseRequiredLists,
  caseRequiredStrings,
  caseRiskValues,
  caseTypeValues,
  requiredEnvKeys,
  suiteRequiredLists,
  suiteRequiredStrings,
  suiteTypeValues,
  troubleRequiredLists,
  troubleRequiredStrings,
  troubleshootingCategoryValues,
} from "../constants.ts";
import { boolValue, envExamplePath, envPath, listValue, loadSkills, loadStructuredItems, parseEnvFile, scalar } from "../fs.ts";
import { envKeyPattern, isEnvAnyGroup, splitEnvAnyGroup } from "../env-groups.ts";
import { parseSetupAutomationEntry, validateSetupAutomationEntry } from "../setup-automation.ts";

const refRe = /(?:\]\(|`)(references\/[A-Za-z0-9_.\-/]+\.md)(?:\)|`)/g;

function validateStructuredItem(item: StructuredItem, requiredStrings: string[], requiredLists: string[]): string[] {
  const errors: string[] = [];
  const listKeys = item.path.includes("/cases/") && scalar(item.fields, "mode") === "probe"
    ? requiredLists.filter((key) => key !== "env")
    : requiredLists;
  for (const key of requiredStrings) {
    if (!scalar(item.fields, key)) errors.push(`${item.path}: missing '${key}'`);
  }
  for (const key of listKeys) {
    if (listValue(item.fields, key).length === 0) errors.push(`${item.path}: missing '${key}' entries`);
  }
  const id = scalar(item.fields, "id");
  if (id && !/^[a-z0-9][a-z0-9_-]*$/.test(id)) {
    errors.push(`${item.path}: id must use lowercase letters, digits, dashes, or underscores`);
  }
  return errors;
}

function validateEnum(item: StructuredItem, key: string, values: string[]): string[] {
  const value = scalar(item.fields, key);
  if (!value) return [];
  return values.includes(value) ? [] : [`${item.path}: '${key}' must be one of ${values.join(", ")}`];
}

function validateListEnum(item: StructuredItem, key: string, values: string[]): string[] {
  const allowed = new Set(values);
  return listValue(item.fields, key)
    .filter((value) => !allowed.has(value))
    .map((value) => `${item.path}: '${key}' contains unsupported value '${value}'`);
}

function validateDuplicateListValues(item: StructuredItem, keys: string[]): string[] {
  const errors: string[] = [];
  for (const key of keys) {
    const seen = new Set<string>();
    for (const value of listValue(item.fields, key)) {
      if (seen.has(value)) errors.push(`${item.path}: '${key}' contains duplicate value '${value}'`);
      seen.add(value);
    }
  }
  return errors;
}

function validateEnvKeyList(item: StructuredItem, key: string): string[] {
  return listValue(item.fields, key)
    .filter((value) => !envKeyPattern.test(value))
    .map((value) => `${item.path}: '${key}' contains invalid env key '${value}'`);
}

function validateEnvKeyScalar(item: StructuredItem, key: string): string[] {
  const value = scalar(item.fields, key);
  if (!value) return [];
  return envKeyPattern.test(value)
    ? []
    : [`${item.path}: '${key}' contains invalid env key '${value}'`];
}

function validateJsonScalar(item: StructuredItem, key: string): string[] {
  const value = scalar(item.fields, key);
  if (!value) return [];
  try {
    JSON.parse(value);
    return [];
  } catch (error) {
    return [`${item.path}: '${key}' must be valid JSON: ${(error as Error).message}`];
  }
}

function validateEnvAnyList(item: StructuredItem, key: string): string[] {
  return listValue(item.fields, key)
    .filter((value) => !isEnvAnyGroup(value))
    .map((value) => `${item.path}: '${key}' contains invalid env any-group '${value}'`);
}

function validateCaseItem(root: string, item: StructuredItem, skillNames: Set<string>, troubleIds: Set<string>, caseIds: Set<string>): string[] {
  const errors = [
    ...validateEnum(item, "mode", caseModeValues),
    ...validateEnum(item, "type", caseTypeValues),
    ...validateEnum(item, "priority", casePriorityValues),
    ...validateEnum(item, "risk", caseRiskValues),
    ...validateListEnum(item, "evidence_required", caseEvidenceValues),
    ...validateDuplicateListValues(item, [
      "tags",
      "skills",
      "env",
      "env_any",
      "automation_env",
      "automation_env_any",
      "setup_automation",
      "setup_provides_env",
      "evidence_required",
      "troubleshooting",
    ]),
    ...validateEnvKeyList(item, "env"),
    ...validateEnvAnyList(item, "env_any"),
    ...validateEnvKeyList(item, "automation_env"),
    ...validateEnvAnyList(item, "automation_env_any"),
    ...validateEnvKeyList(item, "setup_provides_env"),
    ...validateEnvKeyScalar(item, "automation_pipeline_url_env"),
    ...validateEnvKeyScalar(item, "automation_pipeline_name_env"),
    ...validateJsonScalar(item, "automation_filesystem_checks_json"),
    ...validateJsonScalar(item, "metrics_thresholds_json"),
    ...validateJsonScalar(item, "load_profile_json"),
    ...validateJsonScalar(item, "fault_model_json"),
    ...listValue(item.fields, "setup_automation").flatMap((entry) => (
      validateSetupAutomationEntry(root, entry, caseIds).map((error) => `${item.path}: ${error}`)
    )),
  ];

  if (boolValue(item.fields, "ci_eligible") === undefined) {
    errors.push(`${item.path}: missing or invalid boolean 'ci_eligible'`);
  }

  for (const skill of listValue(item.fields, "skills")) {
    if (!skillNames.has(skill)) errors.push(`${item.path}: references unknown skill '${skill}'`);
  }

  for (const id of listValue(item.fields, "troubleshooting")) {
    if (!troubleIds.has(id)) errors.push(`${item.path}: references unknown troubleshooting '${id}'`);
  }

  const automation = scalar(item.fields, "automation");
  if (!automation && listValue(item.fields, "automation_env").length > 0) {
    errors.push(`${item.path}: 'automation_env' requires 'automation'`);
  }
  if (!automation && listValue(item.fields, "automation_env_any").length > 0) {
    errors.push(`${item.path}: 'automation_env_any' requires 'automation'`);
  }
  if (!automation && (scalar(item.fields, "automation_pipeline_url_env") || scalar(item.fields, "automation_pipeline_name_env"))) {
    errors.push(`${item.path}: automation pipeline env aliases require 'automation'`);
  }
  if (listValue(item.fields, "setup_provides_env").length > 0 && listValue(item.fields, "setup_automation").length === 0) {
    errors.push(`${item.path}: 'setup_provides_env' requires 'setup_automation'`);
  }
  for (const key of ["automation_pipeline_url_env", "automation_pipeline_name_env"]) {
    const value = scalar(item.fields, key);
    if (!value) continue;
    const declared = new Set([
      ...listValue(item.fields, "env"),
      ...listValue(item.fields, "env_any").flatMap(splitEnvAnyGroup),
      ...listValue(item.fields, "automation_env"),
      ...listValue(item.fields, "automation_env_any").flatMap(splitEnvAnyGroup),
    ]);
    if (!declared.has(value)) {
      errors.push(`${item.path}: '${key}' value '${value}' must be listed in env, env_any, automation_env, or automation_env_any`);
    }
  }
  if (automation && !existsSync(join(root, automation))) {
    errors.push(`${item.path}: automation script does not exist: ${automation}`);
  }
  for (const entry of listValue(item.fields, "setup_automation")) {
    const spec = parseSetupAutomationEntry(entry);
    if (spec.kind === "case" && spec.target === scalar(item.fields, "id")) {
      errors.push(`${item.path}: setup_automation cannot reference the same case '${spec.target}'`);
    }
  }

  const timeout = scalar(item.fields, "automation_response_timeout_ms");
  if (timeout && (!/^\d+$/.test(timeout) || Number.parseInt(timeout, 10) <= 0)) {
    errors.push(`${item.path}: 'automation_response_timeout_ms' must be a positive integer string`);
  }
  for (const key of [
    "automation_debug_chat_load_requests",
    "automation_debug_chat_load_concurrency",
    "automation_debug_chat_load_timeout_ms",
    "automation_debug_chat_load_response_p95_ms",
    "automation_debug_chat_load_first_response_p95_ms",
  ]) {
    const value = scalar(item.fields, key);
    if (value && (!/^\d+$/.test(value) || Number.parseInt(value, 10) <= 0)) {
      errors.push(`${item.path}: '${key}' must be a positive integer string`);
    }
  }
  const loadMaxErrorRate = scalar(item.fields, "automation_debug_chat_load_max_error_rate");
  if (loadMaxErrorRate && (!/^(?:0(?:\.\d+)?|1(?:\.0+)?)$/.test(loadMaxErrorRate))) {
    errors.push(`${item.path}: 'automation_debug_chat_load_max_error_rate' must be a number string between 0 and 1`);
  }
  const streamOutput = scalar(item.fields, "automation_stream_output");
  if (streamOutput && !["0", "1", "false", "true"].includes(streamOutput)) {
    errors.push(`${item.path}: 'automation_stream_output' must be one of 0, 1, false, or true`);
  }
  for (const key of ["automation_debug_chat_load_stream", "automation_debug_chat_load_reset"]) {
    const value = scalar(item.fields, key);
    if (value && !["0", "1", "false", "true"].includes(value)) {
      errors.push(`${item.path}: '${key}' must be one of 0, 1, false, or true`);
    }
  }
  const imageBase64Fixture = scalar(item.fields, "automation_image_base64_fixture");
  if (imageBase64Fixture && !existsSync(join(root, imageBase64Fixture))) {
    errors.push(`${item.path}: automation image fixture does not exist: ${imageBase64Fixture}`);
  }

  return errors;
}

function validateSetupAutomationCycles(caseItems: StructuredItem[]): string[] {
  const byId = new Map(caseItems.map((item) => [scalar(item.fields, "id"), item]));
  const visiting = new Set<string>();
  const visited = new Set<string>();
  const errors: string[] = [];

  function visit(id: string, path: string[]): void {
    if (visited.has(id)) return;
    if (visiting.has(id)) {
      const cycle = [...path.slice(path.indexOf(id)), id].join(" -> ");
      const item = byId.get(id);
      errors.push(`${item?.path ?? id}: setup_automation case cycle detected: ${cycle}`);
      return;
    }
    const item = byId.get(id);
    if (!item) return;
    visiting.add(id);
    for (const entry of listValue(item.fields, "setup_automation")) {
      const spec = parseSetupAutomationEntry(entry);
      if (spec.kind === "case") visit(spec.target, [...path, spec.target]);
    }
    visiting.delete(id);
    visited.add(id);
  }

  for (const id of byId.keys()) visit(id, [id]);
  return errors;
}

function validateTroubleshootingItem(item: StructuredItem, caseIds: Set<string>): string[] {
  const errors = [
    ...validateEnum(item, "category", troubleshootingCategoryValues),
    ...validateDuplicateListValues(item, ["symptoms", "patterns", "likely_causes", "fix_steps", "related_cases"]),
  ];
  for (const id of listValue(item.fields, "related_cases")) {
    if (!caseIds.has(id)) errors.push(`${item.path}: references unknown case '${id}'`);
  }
  return errors;
}

function validateFixtures(root: string, caseIds: Set<string>): string[] {
  const { items, errors } = loadFixtureItems(root);
  const result = [...errors];
  const seen = new Map<string, string>();
  for (const item of items) {
    if (!/^[a-z0-9][a-z0-9_-]*$/.test(item.id)) {
      result.push(`${item.manifest_path}: fixture id '${item.id}' must use lowercase letters, digits, dashes, or underscores`);
    }
    if (seen.has(item.id)) {
      result.push(`${item.manifest_path}: duplicate fixture id '${item.id}' also used by ${seen.get(item.id)}`);
    } else {
      seen.set(item.id, item.manifest_path);
    }
    if (!item.exists) result.push(`${item.manifest_path}: fixture path does not exist: ${item.path}`);
    for (const caseId of item.related_cases) {
      if (!caseIds.has(caseId)) result.push(`${item.manifest_path}: fixture '${item.id}' references unknown case '${caseId}'`);
    }
  }
  return result;
}

function validateSuiteItem(item: StructuredItem, caseIds: Set<string>): string[] {
  const errors = [
    ...validateEnum(item, "type", suiteTypeValues),
    ...validateEnum(item, "priority", casePriorityValues),
    ...validateDuplicateListValues(item, ["tags", "cases"]),
  ];
  for (const id of listValue(item.fields, "cases")) {
    if (!caseIds.has(id)) errors.push(`${item.path}: references unknown case '${id}'`);
  }
  return errors;
}

function validateDuplicateIds(items: StructuredItem[], label: string): string[] {
  const errors: string[] = [];
  const seen = new Map<string, string>();
  for (const item of items) {
    const id = scalar(item.fields, "id");
    if (!id) continue;
    const key = `${item.skill}:${id}`;
    if (seen.has(key)) errors.push(`${item.path}: duplicate ${label} id '${id}' also used by ${seen.get(key)}`);
    else seen.set(key, item.path);
  }
  return errors;
}

function validateGlobalDuplicateIds(items: StructuredItem[], label: string): string[] {
  const errors: string[] = [];
  const seen = new Map<string, string>();
  for (const item of items) {
    const id = scalar(item.fields, "id");
    if (!id) continue;
    if (seen.has(id)) errors.push(`${item.path}: duplicate global ${label} id '${id}' also used by ${seen.get(id)}`);
    else seen.set(id, item.path);
  }
  return errors;
}

function validateEnv(root: string): string[] {
  const path = envPath(root);
  const examplePath = envExamplePath(root);
  const errors: string[] = [];
  if (!existsSync(path)) return [`${path}: missing shared env file`];
  const env = parseEnvFile(path);
  for (const key of requiredEnvKeys) {
    if (!(key in env)) errors.push(`${path}: missing ${key}`);
  }
  if (!existsSync(examplePath)) {
    errors.push(`${examplePath}: missing env template`);
  } else {
    const example = parseEnvFile(examplePath);
    for (const key of requiredEnvKeys) {
      if (!(key in example)) errors.push(`${examplePath}: missing template key ${key}`);
    }
  }
  return errors;
}

function validateSchemas(root: string): string[] {
  const errors: string[] = [];
  for (const name of ["case.schema.json", "suite.schema.json", "troubleshooting.schema.json", "skill-index.schema.json"]) {
    const path = join(root, "schemas", name);
    if (!existsSync(path)) {
      errors.push(`${path}: missing schema`);
      continue;
    }
    try {
      JSON.parse(readFileSync(path, "utf8"));
    } catch (error) {
      errors.push(`${path}: invalid JSON schema (${String(error)})`);
    }
  }
  return errors;
}

function validateSkill(skill: Skill): string[] {
  const errors: string[] = [];
  if (!skill.name) errors.push(`${skill.path}: missing frontmatter name`);
  if (!skill.description) errors.push(`${skill.path}: missing frontmatter description`);
  if (skill.name && skill.name !== skill.directory) {
    errors.push(`${skill.path}: name '${skill.name}' does not match directory '${skill.directory}'`);
  }

  const refs = new Set<string>();
  for (const match of skill.body.matchAll(refRe)) refs.add(match[1]);
  for (const ref of Array.from(refs).sort()) {
    if (!existsSync(join(skill.path, ref))) {
      errors.push(`${skill.path}: referenced file does not exist: ${ref}`);
    }
  }

  const legacyTroubleshooting = join(skill.path, "references", "troubleshooting.md");
  if (existsSync(legacyTroubleshooting)) {
    const text = readFileSync(legacyTroubleshooting, "utf8");
    if (text.includes("\n## ") && !text.includes("### Symptom")) {
      errors.push(`${legacyTroubleshooting}: troubleshooting entries should include '### Symptom'`);
    }
  }

  return errors;
}

export function commandValidate(root: string): number {
  const skills = loadSkills(root);
  const caseItems = loadStructuredItems(root, "cases");
  const suiteItems = loadStructuredItems(root, "suites");
  const troubleItems = loadStructuredItems(root, "troubleshooting");
  const skillNames = new Set(skills.map((skill) => skill.name));
  const caseIds = new Set(caseItems.map((item) => scalar(item.fields, "id")).filter(Boolean));
  const troubleIds = new Set(troubleItems.map((item) => scalar(item.fields, "id")).filter(Boolean));
  const errors = [
    ...validateEnv(root),
    ...validateSchemas(root),
    ...skills.flatMap(validateSkill),
    ...caseItems.flatMap((item) => validateStructuredItem(item, caseRequiredStrings, caseRequiredLists)),
    ...caseItems.flatMap((item) => validateCaseItem(root, item, skillNames, troubleIds, caseIds)),
    ...validateSetupAutomationCycles(caseItems),
    ...suiteItems.flatMap((item) => validateStructuredItem(item, suiteRequiredStrings, suiteRequiredLists)),
    ...suiteItems.flatMap((item) => validateSuiteItem(item, caseIds)),
    ...troubleItems.flatMap((item) => validateStructuredItem(item, troubleRequiredStrings, troubleRequiredLists)),
    ...troubleItems.flatMap((item) => validateTroubleshootingItem(item, caseIds)),
    ...validateFixtures(root, caseIds),
    ...validateDuplicateIds(caseItems, "case"),
    ...validateDuplicateIds(suiteItems, "suite"),
    ...validateDuplicateIds(troubleItems, "troubleshooting"),
    ...validateGlobalDuplicateIds(caseItems, "case"),
    ...validateGlobalDuplicateIds(suiteItems, "suite"),
    ...validateGlobalDuplicateIds(troubleItems, "troubleshooting"),
  ];

  if (errors.length > 0) {
    for (const error of errors) stderr.write(`ERROR: ${error}\n`);
    return 1;
  }
  console.log("OK");
  return 0;
}
