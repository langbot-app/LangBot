# Agent Runner Pluginization Phase 1 QA Report

Date: 2026-05-18

## Environment

- LangBot repo: `/home/glwuy/langbot-app/LangBot`
- LangBot branch/commit: `feat/agent-runner-plugin` / `036affe0`
- SDK repo commit: `/home/glwuy/langbot-app/sdk` / `feed530`
- langbot-skills commit: `/home/glwuy/langbot-app/langbot-skills` / `a82f006`
- Backend: `http://127.0.0.1:5300`, started from the `LangBot` worktree
- Frontend: `http://127.0.0.1:3000`, started from `LangBot/web`
- Pipeline: `565ec946-01a6-496d-8b8c-056a4eab7f4d` / `测试`
- Runner: `plugin:langbot/local-agent/default`
- Runner config summary: primary model configured, knowledge base `qa-local-agent-rag-20260516` bound, rerank disabled
- Installed runner plugins observed: `langbot/local-agent`, `langbot/dify-agent`
- Supporting plugins observed: `qa/plugin-smoke`, `langbot-team/LangRAG`

Evidence files:

- `/home/glwuy/langbot-app/phase1-runner-config.png`
- `/home/glwuy/langbot-app/phase1-local-agent-debug-chat.png`
- `/home/glwuy/langbot-app/phase1-console.log`
- Backend log: `/home/glwuy/langbot-app/LangBot/data/logs/langbot-2026-05-18.log`

## Automated Checks

| Check | Status | Evidence |
| --- | --- | --- |
| `uv run --frozen pytest tests/unit_tests/agent` | PASS | `241 passed, 16 warnings` |
| `uv run --frozen pytest tests/unit_tests/agent/test_handler_auth.py tests/unit_tests/agent/test_orchestrator_integration.py tests/unit_tests/agent/test_result_normalizer.py` | PASS | `96 passed, 11 warnings` |
| `langbot-skills` local env/tooling regression | PASS | `npm test`: `7 passed`; `bin/lbs validate`: `OK` |

## UI Cases Executed

| Matrix ID | Status | Evidence |
| --- | --- | --- |
| P0-ENV-01 | PASS | WebUI opened at `http://127.0.0.1:3000/home/pipelines`; backend responded on `5300`. |
| P0-ENV-02 | PASS | Logs show plugin runtime connected and plugins initialized without restart loop. |
| P0-ENV-03 | PASS | Pipeline AI runner UI and metadata show `plugin:langbot/local-agent/default` and `plugin:langbot/dify-agent/default`. |
| P0-ENV-04 | PASS | Existing default-style pipeline uses `ai.runner.id` and `ai.runner_config`; config page loaded and displayed runner config. |
| P0-ENV-05 | PASS | Debug Chat message returned `PHASE1_LOCAL_AGENT_PLAIN_OK`; logs show `[Action] run_agent`. |
| P0-ENV-06 | PASS | Agent unit baseline passed. |
| P1-LA-01 | PASS | Plain text Debug Chat returned `PHASE1_LOCAL_AGENT_PLAIN_OK`. |
| P1-LA-02 | PASS | Sending `qa-effective-prompt` returned `PROMPT_PREPROCESS_OK`. |
| P1-LA-03 | PASS | Second turn referenced the first marker and returned `PHASE1_LOCAL_AGENT_PLAIN_OK`. |
| P1-LA-04 | PASS | Stream mode enabled; UI showed bot response and logs reported streaming completion. |
| P1-LA-05 | PASS | Stream mode disabled; UI returned `PHASE1_LOCAL_AGENT_NONSTREAM_OK` without a blank/duplicate card. |
| P1-LA-06 | PASS | Prompt triggered tool call; logs show tool call started/completed for `qa_echo`; UI returned `qa-plugin-smoke:PHASE1_TOOL_CALL_OK`. |
| P1-LA-08 | PASS | Bound LangRAG KB retrieval returned sentinel `azalea-cobalt-7421`; logs show `retrieve_knowledge`. |
| P1-LA-13 | PASS | Uploaded 64x64 red-square fixture; UI returned `RED_IMAGE_OK`. |

## Unit Or Protocol Covered Cases

| Matrix ID | Status | Evidence |
| --- | --- | --- |
| P1-AUTH-01 | PASS | `test_handler_auth.py` covers unauthorized model rejection. |
| P1-AUTH-02 | PASS | `test_handler_auth.py` covers unauthorized tool rejection. |
| P1-AUTH-03 | PASS | `test_handler_auth.py` covers unauthorized knowledge-base rejection. |
| P1-AUTH-04 | PASS | `test_handler_auth.py` covers storage permission validation. |
| P1-AUTH-05 | PASS | `test_handler_auth.py` covers session expiry and unregister behavior. |
| P1-AUTH-06 | PASS | `test_handler_auth.py` covers caller plugin identity mismatch. |
| P1-LA-15 | PASS | `test_orchestrator_integration.py` covers `state.updated` handling. |
| P1-LA-16 | PASS | `test_orchestrator_integration.py` and `test_result_normalizer.py` cover `run.failed`. |
| P1-LA-17 | PASS | `test_result_normalizer.py` covers `run.completed` without message. |
| P1-CFG-01 | PASS | Config migration unit tests in the full agent suite passed. |
| P1-CFG-04 | PASS | Chat handler unit tests cover runner-not-found controlled errors. |
| P1-CFG-05 | PASS | Authorization unit tests cover bound resource restrictions. |
| P2-EVT-01 | PASS | `test_orchestrator_integration.py` asserts `message.received`. |
| P2-EVT-02 | PASS | `src/langbot/pkg/agent/runner/events.py` defines reserved event names. |
| P2-EVT-03 | PASS | `test_result_normalizer.py` covers `action.requested` as log-only/no execution. |

## Blocked Or N/A

| Matrix ID | Status | Reason |
| --- | --- | --- |
| P1-LA-07 | BLOCKED | Needs a dedicated restricted-pipeline or malicious-runner fixture to force an unauthorized tool call through the runner. Unit-level authorization passes. |
| P1-LA-09 | BLOCKED | Needs a dedicated restricted-pipeline or malicious-runner fixture to force unauthorized KB access. Unit-level authorization passes. |
| P1-LA-10 | BLOCKED | No rerank model configured for this environment. |
| P1-LA-11 | BLOCKED | Primary/fallback failure injection was not configured for this run. |
| P1-LA-12 | BLOCKED | No known think-output model/path configured for this run. |
| P1-LA-14 | N/A | Debug Chat UI exposes image upload but no generic file upload control in this run. |
| P1-CFG-03 | BLOCKED | Runner switching to an external runner requires a usable external runner config; only Dify is discoverable and no Dify credentials are configured. |
| P2-EXT-01 | BLOCKED | Dify runner is discoverable, but no Dify API key/app config is available. |
| P2-EXT-02 | N/A | `n8n-agent` runner is not discoverable in metadata. |
| P2-EXT-03 | N/A | `coze-agent` runner is not discoverable in metadata. |
| P2-EXT-04 | N/A | `dashscope-agent` runner is not discoverable in metadata. |
| P2-EXT-05 | N/A | `langflow-agent` runner is not discoverable in metadata. |
| P2-EXT-06 | N/A | `tbox-agent` runner is not discoverable in metadata. |

## Notes

- The current environment is strong enough to validate the main pluginized local-agent path: WebUI, runner registry, prompt preprocessing, history, streaming, non-streaming, tool calls, LangRAG retrieval, image input, and host-side authorization/unit protocol behavior all passed.
- External runner smoke cannot close without credentials or installed runner plugins beyond Dify.
- Console capture contains stale errors from earlier service restarts and diagnostic cross-origin fetch attempts. During the executed Debug Chat flows, the UI completed normally and the backend processed all tested queries.
- `langbot-skills` now supports machine-local `skills/.env.local` overrides, so local worktree/port changes do not need to modify shared `skills/.env`.

## Recommendation

Do not mark the whole Phase 1 matrix fully closed yet. It is reasonable to treat the local-agent Phase 1 core path as PASS, but Phase 1 closure still needs either:

- explicit acceptance that authorization/error/state cases are covered by unit/protocol tests rather than UI malicious-runner fixtures, and
- external runner credentials or a decision to keep external runner smoke BLOCKED by environment.
