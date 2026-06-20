---
name: langbot-testing
description: Test LangBot WebUI and core product flows with an automated browser and backend logs. Use when validating the configured LangBot frontend, pipeline Debug Chat, model provider setup and test buttons, bot and knowledge-base UI flows, or troubleshooting failed LangBot end-to-end tests.
---

# LangBot Testing

Use this skill when an agent needs to verify LangBot behavior through the WebUI instead of only reading code.

## Routing

- **General WebUI testing**: read `references/web-ui-testing.md`.
- **Pipeline Debug Chat**: read `references/pipeline-debug-chat.md`.
- **Dify AgentRunner**: read `references/dify-agent-runner.md`.
- **Model provider setup or test button**: read `references/model-provider-testing.md`.
- **Plugin install/runtime/tool/page smoke**: read `references/plugin-e2e-smoke.md`.
- **Local Agent Runner**: read `references/local-agent-runner.md`.
- **Local Agent Runner path coverage**: read `references/local-agent-runner-coverage.md`.
- **Diff-aware AgentRunner QA after code changes**: read `references/agent-runner-qa-workflow.md`.
- **Agent Runner release gate**: read `references/agent-runner-release-gate.md`.
- **Sandbox-backed skill authoring**: read `references/sandbox-skill-authoring.md`.
- **LangRAG knowledge bases**: read `references/langrag-knowledge-base.md`.
- **MCP stdio tool testing**: read `references/mcp-stdio-testing.md`.
- **Known failures and fixes**: read `references/troubleshooting.md`.
- **Reusable test groups**: run `bin/lbs suite list` and `bin/lbs suite plan <suite-id>` before manually assembling a case set.

## Rules

- Read `../.env` first and use `LANGBOT_FRONTEND_URL` and `LANGBOT_BACKEND_URL` instead of hardcoded ports.
- If a standalone frontend dev server is running, `LANGBOT_FRONTEND_URL` may point to `LANGBOT_DEV_FRONTEND_URL`; otherwise it may point to the backend WebUI.
- Confirm the backend and frontend are actually running before testing.
- Run `bin/lbs fixture check` before fixture-heavy MCP, RAG, multimodal, or plugin smoke tests.
- For runner externalization release checks, run `bin/lbs test run agent-runner-release-preflight` before the full `agent-runner-release-gate` suite so configuration blockers are separated from product failures.
- Read `Manual Readiness` in `bin/lbs test plan <case-id>`; `manual_check` means the declared preconditions or setup still need operator confirmation for this run.
- Use an authenticated browser profile prepared by `langbot-env-setup`.
- Do not expose API keys, OAuth secrets, tokens, or localStorage token values in output.
- A WebUI test is not complete until the visible UI result is checked against backend logs or network behavior.
- For a suite, use `bin/lbs suite start <suite-id>` to create the suite evidence root, per-case directories, and `suite-start.json`/`suite-start.md` handoff files; use `bin/lbs test result <case-id>` to write final per-case `result.json`, then run `bin/lbs suite report <suite-id> --evidence-dir <dir>`.
- Do not mark a case `pass` until `test result --evidence` covers every value in the case's `evidence_required`.
- For runner-specific Debug Chat cases, use the case-specific pipeline env declared by `automation_pipeline_url_env` / `automation_pipeline_name_env`; do not silently reuse a generic `LANGBOT_PIPELINE_URL`.
