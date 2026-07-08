#!/usr/bin/env node

import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { env } from "node:process";
import {
  apiJson,
  ensureEvidence,
  evidencePaths,
  loadEnvFiles,
  resetAndAuthLocalUser,
  writeResult,
} from "./lib/langbot-e2e.mjs";

const caseId = env.LBS_CASE_ID || "ensure-langrag-sentinel-kb";

await loadEnvFiles();
const paths = evidencePaths(caseId);
await ensureEvidence(paths);

const backendUrl = env.LANGBOT_BACKEND_URL || "";
const user = env.LANGBOT_E2E_LOGIN_USER || "";
const password = env.LANGBOT_E2E_LOGIN_PASSWORD || "LangBotE2ELocalPass!2026";
const expectedText = env.LANGBOT_E2E_EXPECTED_TEXT || "azalea-cobalt-7421";
const query = env.LANGBOT_E2E_RETRIEVE_QUERY || "What is the local agent runner retrieval sentinel?";
const writeEnv = process.argv.includes("--write-env");
const checkOnly = process.argv.includes("--check-only");
const envLocalPath = resolve("skills/.env.local");
const kbName = env.LANGBOT_E2E_RAG_KB_NAME || "qa-local-agent-rag";
const sentinelPath = resolve(env.LANGBOT_E2E_RAG_SENTINEL_DOC || "skills/langbot-testing/fixtures/rag/sentinel-doc.txt");
const waitMs = Number(env.LANGBOT_E2E_RAG_WAIT_MS || 180_000);

const result = {
  source: "automation",
  case_id: caseId,
  run_id: paths.runId,
  status: "fail",
  reason: "",
  backend_url: backendUrl,
  expected_text: expectedText,
  query,
  kb_uuid: "",
  kb_name: "",
  kb_created: false,
  uploaded_file_id: "",
  store_task_id: "",
  embedding_model_uuid: "",
  engine_plugin_id: "",
  checked_bases: [],
  file_statuses: [],
  wrote_env: false,
  evidence: {
    automation_result_json: paths.automationResultJson,
    result_json: paths.resultJson,
  },
  evidence_collected: ["api_diagnostic"],
};

try {
  if (!backendUrl) throw new Error("LANGBOT_BACKEND_URL is not configured.");
  if (!user) throw new Error("LANGBOT_E2E_LOGIN_USER is required.");

  const auth = await resetAndAuthLocalUser({ backendUrl, user, password });
  const basesResponse = await apiJson(backendUrl, "/api/v1/knowledge/bases", { token: auth.token });
  if (basesResponse.status >= 400 || basesResponse.json.code !== 0) {
    throw new Error(basesResponse.json.msg || `Failed to list knowledge bases: HTTP ${basesResponse.status}.`);
  }

  let bases = basesResponse.json.data?.bases || [];
  await findSentinelBase(backendUrl, auth.token, bases, result);

  if (!result.kb_uuid && !checkOnly) {
    const targetBase = bases.find((base) => {
      const uuid = base.uuid || base.id || "";
      return (base.name || "") === kbName && !hasRetrieveFailure(result.checked_bases, uuid);
    });
    result.kb_uuid = targetBase?.uuid || targetBase?.id || "";
    result.kb_name = targetBase?.name || kbName;

    if (!result.kb_uuid) {
      const setup = await createKnowledgeBase(backendUrl, auth.token, kbName);
      result.kb_uuid = setup.kbUuid;
      result.kb_name = kbName;
      result.kb_created = true;
      result.embedding_model_uuid = setup.embeddingModelUuid;
      result.engine_plugin_id = setup.enginePluginId;
    }

    const upload = await uploadDocument(backendUrl, auth.token, sentinelPath);
    result.uploaded_file_id = upload.fileId;

    const store = await apiJson(backendUrl, `/api/v1/knowledge/bases/${encodeURIComponent(result.kb_uuid)}/files`, {
      method: "POST",
      token: auth.token,
      body: { file_id: upload.fileId },
    });
    if (store.status >= 400 || store.json.code !== 0) {
      throw new Error(store.json.msg || `Failed to store file in knowledge base: HTTP ${store.status}.`);
    }
    result.store_task_id = store.json.data?.task_id || "";

    const ready = await waitForSentinel(backendUrl, auth.token, result.kb_uuid, query, expectedText, waitMs);
    result.file_statuses = ready.fileStatuses;
    if (ready.matched) {
      result.checked_bases.push(ready.checked);
    }
  }

  if (!result.kb_uuid) {
    result.status = "env_issue";
    result.reason = checkOnly
      ? `No existing knowledge base retrieved expected sentinel: ${expectedText}`
      : `Could not create or verify LangRAG sentinel knowledge base: ${expectedText}`;
  } else {
    if (writeEnv) {
      await upsertEnvLocal(envLocalPath, {
        LANGBOT_LOCAL_AGENT_RAG_KB_UUID: result.kb_uuid,
      });
      result.wrote_env = true;
    }
    result.status = "pass";
    result.reason = `Found LangRAG sentinel knowledge base: ${result.kb_uuid}`;
  }
} catch (error) {
  result.status = /not configured|required|No existing knowledge base/.test(error.message) ? "env_issue" : "fail";
  result.reason = error.message;
} finally {
  await writeResult(paths, result);
  console.log(JSON.stringify(result, null, 2));
}

process.exit(result.status === "pass" ? 0 : result.status === "env_issue" ? 2 : 1);

async function findSentinelBase(backendUrl, token, bases, result) {
  for (const base of bases) {
    const uuid = base.uuid || base.id || "";
    if (!uuid) continue;
    const checked = await retrieveSentinel(backendUrl, token, uuid, base.name || "", result.query, result.expected_text);
    result.checked_bases.push(checked);
    if (checked.matched) {
      result.kb_uuid = uuid;
      result.kb_name = checked.name;
      return;
    }
  }
}

async function createKnowledgeBase(backendUrl, token, name) {
  const enginesResponse = await apiJson(backendUrl, "/api/v1/knowledge/engines", { token });
  if (enginesResponse.status >= 400 || enginesResponse.json.code !== 0) {
    throw new Error(enginesResponse.json.msg || `Failed to list knowledge engines: HTTP ${enginesResponse.status}.`);
  }
  const engines = enginesResponse.json.data?.engines || [];
  const engine = engines.find((item) => item.plugin_id === "langbot-team/LangRAG")
    || engines.find((item) => JSON.stringify(item.name || item.label || "").includes("LangRAG"));
  const enginePluginId = engine?.plugin_id || "";
  if (!enginePluginId) throw new Error("LangRAG knowledge engine is not installed.");

  const embeddingModelUuid = await pickEmbeddingModel(backendUrl, token);
  const create = await apiJson(backendUrl, "/api/v1/knowledge/bases", {
    method: "POST",
    token,
    body: {
      name,
      description: "Automated LangBot agent-runner RAG sentinel knowledge base.",
      knowledge_engine_plugin_id: enginePluginId,
      creation_settings: {
        embedding_model_uuid: embeddingModelUuid,
        index_type: "chunk",
        chunk_size: 512,
        overlap: 50,
      },
      retrieval_settings: {
        top_k: 5,
        search_type: "vector",
        query_rewrite: "off",
        rerank: "off",
        context_window: 0,
      },
    },
  });
  const kbUuid = create.json.data?.uuid || "";
  if (create.status >= 400 || create.json.code !== 0 || !kbUuid) {
    throw new Error(create.json.msg || `Failed to create knowledge base: HTTP ${create.status}.`);
  }
  return { kbUuid, embeddingModelUuid, enginePluginId };
}

async function pickEmbeddingModel(backendUrl, token) {
  const configured = env.LANGBOT_LOCAL_AGENT_RAG_EMBEDDING_MODEL_UUID || env.LANGBOT_RAG_EMBEDDING_MODEL_UUID || "";
  if (configured) return configured;

  const modelsResponse = await apiJson(backendUrl, "/api/v1/provider/models/embedding", { token });
  if (modelsResponse.status >= 400 || modelsResponse.json.code !== 0) {
    throw new Error(modelsResponse.json.msg || `Failed to list embedding models: HTTP ${modelsResponse.status}.`);
  }
  const models = modelsResponse.json.data?.models || [];
  const preferred = models.find((model) => /chroma|MiniLM/i.test(model.name || ""))
    || models.find((model) => /text-embedding-3-small/i.test(model.name || ""))
    || [...models].sort((a, b) => (a.prefered_ranking ?? 9999) - (b.prefered_ranking ?? 9999))[0];
  const uuid = preferred?.uuid || "";
  if (!uuid) throw new Error("No embedding model is configured.");
  return uuid;
}

async function uploadDocument(backendUrl, token, path) {
  const bytes = await readFile(path);
  const form = new FormData();
  form.append("file", new Blob([bytes], { type: "text/plain" }), "sentinel-doc.txt");
  const response = await fetch(`${backendUrl.replace(/\/$/, "")}/api/v1/files/documents`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: form,
  });
  const json = await response.json().catch(() => ({}));
  const fileId = json.data?.file_id || "";
  if (response.status >= 400 || json.code !== 0 || !fileId) {
    throw new Error(json.msg || `Failed to upload sentinel document: HTTP ${response.status}.`);
  }
  return { fileId };
}

async function waitForSentinel(backendUrl, token, kbUuid, query, expectedText, timeoutMs) {
  const started = Date.now();
  let fileStatuses = [];
  let lastChecked = null;
  while (Date.now() - started < timeoutMs) {
    const files = await apiJson(backendUrl, `/api/v1/knowledge/bases/${encodeURIComponent(kbUuid)}/files`, { token });
    fileStatuses = files.json.data?.files || fileStatuses;
    lastChecked = await retrieveSentinel(backendUrl, token, kbUuid, kbName, query, expectedText);
    if (lastChecked.matched) {
      return { matched: true, fileStatuses, checked: lastChecked };
    }
    if (fileStatuses.some((item) => item.status === "failed")) break;
    await sleep(2_000);
  }
  result.reason = lastChecked?.msg
    || `LangRAG sentinel was not retrievable within ${timeoutMs}ms; file statuses: ${JSON.stringify(fileStatuses)}`;
  result.kb_uuid = "";
  return { matched: false, fileStatuses, checked: lastChecked };
}

async function retrieveSentinel(backendUrl, token, uuid, name, query, expectedText) {
  const retrieve = await apiJson(backendUrl, `/api/v1/knowledge/bases/${encodeURIComponent(uuid)}/retrieve`, {
    method: "POST",
    token,
    body: { query },
  });
  const text = JSON.stringify(retrieve.json.data?.results || []);
  return {
    uuid,
    name,
    http_status: retrieve.status,
    code: retrieve.json.code ?? null,
    msg: retrieve.json.msg || "",
    matched: text.includes(expectedText),
  };
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function hasRetrieveFailure(checkedBases, uuid) {
  const checked = checkedBases.find((item) => item.uuid === uuid);
  return checked && (checked.http_status >= 500 || (typeof checked.code === "number" && checked.code < 0));
}

async function upsertEnvLocal(path, values) {
  let text = "";
  try {
    text = await readFile(path, "utf8");
  } catch {
    text = "";
  }
  const lines = text.split(/\r?\n/);
  const keys = new Set(Object.keys(values));
  const output = [];
  for (const line of lines) {
    const match = line.match(/^([A-Z][A-Z0-9_]*)=/);
    if (match && keys.has(match[1])) {
      output.push(`${match[1]}=${values[match[1]]}`);
      keys.delete(match[1]);
    } else if (line !== "" || output.length > 0) {
      output.push(line);
    }
  }
  if (keys.size > 0 && output.length > 0 && output[output.length - 1] !== "") output.push("");
  for (const key of keys) output.push(`${key}=${values[key]}`);
  await writeFile(path, `${output.join("\n").replace(/\n+$/, "")}\n`, "utf8");
}
