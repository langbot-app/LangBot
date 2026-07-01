# AgentRunner QA Workflow

Use this workflow when an agent finishes AgentRunner-related code and enters a
test phase.

## Order

1. Inspect changed repositories with `rtk git status --short` and
   `rtk git diff --stat`.
   Also run `rtk git diff --name-only` and, when untracked files are present,
   `rtk git ls-files --others --exclude-standard` so new probes, fixtures, and
   cases are not missed.
2. Choose the smallest relevant checks:
   - Fast contract probes first.
   - Targeted repo tests second.
   - Browser cases only after contract probes are green or clearly classified.
3. Start from saved assets:
   - `rtk bin/lbs test recommend`
   - `rtk bin/lbs suite plan agent-runner-release-gate`
   - `rtk bin/lbs case list --tag agent-runner`
   - `rtk bin/lbs trouble search agent-runner`
4. Run probes before browser cases:
   - `rtk bin/lbs test run agent-runner-fixture-contract --dry-run`
   - `rtk bin/lbs test run agent-runner-live-install --dry-run` when a local LangBot
     backend is available and installing the QA fixture is acceptable.
   - `rtk bin/lbs test run agent-runner-qa-debug-chat --dry-run` when WebUI live
     execution needs deterministic coverage without a model provider. This
     case runs its setup automation first: install the QA AgentRunner fixture,
     create/update the QA pipeline, write the case-specific pipeline env, then
     execute Debug Chat.
   - `rtk bin/lbs test run agent-runner-ledger-invariants --dry-run`
   - `rtk bin/lbs test run agent-runner-ledger-contention --dry-run`
   - `rtk bin/lbs test run agent-runner-runtime-chaos --dry-run`
   - `rtk bin/lbs test run agent-runner-ledger-concurrency --dry-run` when async DB
     readiness is known good.
5. Run browser release paths only after environment preflight:
   - `rtk bin/lbs test run agent-runner-release-preflight --dry-run`
   - `rtk bin/lbs suite start agent-runner-release-gate --run-id <id>`

Remove `--dry-run` only after readiness and `manual_check` preconditions are
confirmed for the current test instance.

## Diff Triage

Use changed paths to choose checks. Start with the most specific row that
matches the diff, then add adjacent rows only when shared contracts changed.
For the common case, run `rtk bin/lbs test recommend` first and use this table
only to review or adjust the generated list.

| Changed Path or Area | First Checks | Add Browser Case When |
| --- | --- | --- |
| `LangBot/src/langbot/pkg/agent/runner/*`, `tests/unit_tests/agent/test_result_normalizer.py`, protocol/result/context/resource builders | `rtk bin/lbs test run agent-runner-fixture-contract --dry-run`; `rtk bin/lbs test run agent-runner-behavior-matrix --dry-run`; targeted LangBot unit tests for touched files | Result shape, user-visible runner output, or Debug Chat delivery changed: add `pipeline-debug-chat` or `local-agent-basic-debug-chat`. |
| `LangBot/src/langbot/pkg/entity/persistence/agent_run.py`, `run_journal.py`, run ledger store/API/auth tests, claim/lease/status code | `rtk bin/lbs test run agent-runner-ledger-invariants --dry-run`; `rtk bin/lbs test run agent-runner-ledger-stress --dry-run`; `rtk bin/lbs test run agent-runner-ledger-contention --dry-run`; `rtk bin/lbs test run agent-runner-async-db-readiness --dry-run` before `rtk bin/lbs test run agent-runner-ledger-concurrency --dry-run` | Debug Chat run lifecycle, resume, or visible completion changed: add `local-agent-basic-debug-chat`. |
| `langbot-plugin-sdk/src/langbot_plugin/api/entities/builtin/agent_runner/*`, `api/proxies/agent_run_api.py`, runtime pull handlers, plugin manager/runtime IO | `rtk bin/lbs test run agent-runner-runtime-chaos --dry-run`; `rtk bin/lbs test run agent-runner-behavior-matrix --dry-run`; targeted SDK pytest | Runtime delivery or tool-call surface changed: add `agent-runner-release-preflight`, then `local-agent-basic-debug-chat`. |
| `langbot-agent-runner/*/components/agent_runner/*`, external runner daemon/client code, ACP/Codex/Claude runner command wrappers | Repo-local targeted tests; `rtk bin/lbs test run agent-runner-runtime-chaos --dry-run`; `rtk bin/lbs test run agent-runner-release-preflight --dry-run` | ACP or external coding runner behavior changed: add `acp-agent-runner-debug-chat`. |
| Prompt preprocessing, effective prompt, pipeline AI config, runner binding/default runner migration | `rtk bin/lbs test run agent-runner-behavior-matrix --dry-run`; targeted LangBot pipeline/agent tests | The runner reads host-provided prompt or saved runner config: add `local-agent-effective-prompt-debug-chat`. |
| Context window, transcript, history/event state, compaction, checkpoint/steering | `rtk bin/lbs test run agent-runner-behavior-matrix --dry-run`; targeted LangBot agent state/context tests | Multi-turn memory, compaction, or steering behavior changed: add `local-agent-context-compaction-debug-chat` and, for steering-specific changes, `local-agent-steering-debug-chat`. |
| Plugin tool authorization, host tool listing, MCP tool bridge, function-call conversion | `rtk bin/lbs test run agent-runner-behavior-matrix --dry-run`; targeted plugin/MCP/tool tests | Tool execution is user-visible: add `local-agent-plugin-tool-call-debug-chat`; for MCP-specific changes add `mcp-stdio-register` then `mcp-stdio-tool-call`. |
| RAG context injection, knowledge base retrieval, resource packaging | Targeted LangBot RAG/resource tests; `rtk bin/lbs test run agent-runner-behavior-matrix --dry-run` when runner input shape changed | Runner answer should include retrieved context: add `langrag-kb-retrieve` and `local-agent-rag-debug-chat`. |
| Streaming/non-streaming adapter, provider message conversion, image or multimodal payloads | `rtk bin/lbs test run agent-runner-behavior-matrix --dry-run`; targeted provider/pipeline tests | User-visible transport changed: add `local-agent-basic-debug-chat`, `local-agent-nonstreaming-debug-chat`, or `local-agent-multimodal-debug-chat` matching the diff. |
| Only `langbot-skills` cases, probes, fixtures, references, schemas, or CLI planning code | `rtk bin/lbs validate`; relevant `rtk bin/lbs test plan <case-id>` or `rtk bin/lbs test run <probe-id> --dry-run` if supported | Do not run browser cases unless the edited asset itself changes the browser path being validated. |

If a diff crosses more than two rows or touches protocol, ledger, SDK runtime,
and browser-visible runner behavior together, stop trying to hand-pick a tiny
set and use `agent-runner-release-gate`.

## Recommended Minimal Sets

- Protocol or normalization only: `agent-runner-fixture-contract`,
  `agent-runner-behavior-matrix`, plus targeted repo unit tests.
- Ledger persistence only: `agent-runner-ledger-invariants`,
  `agent-runner-ledger-stress`, `agent-runner-ledger-contention`, and
  `agent-runner-async-db-readiness`; run `agent-runner-ledger-concurrency` only
  when async DB readiness passes.
- SDK runtime only: `agent-runner-runtime-chaos` plus targeted SDK pytest.
- Local-agent user path: `agent-runner-release-preflight` then
  `local-agent-basic-debug-chat`; add the specific RAG/tool/MCP/context/
  multimodal case only when the diff touches that contract.
- External ACP runner path: `agent-runner-release-preflight` then
  `acp-agent-runner-debug-chat`.

## Asset Rules

- If a stable product path is missing, add one `cases/*.yaml` file.
- If a non-UI invariant or stress check is missing, add one `mode: probe` case
  and one script under `probes/`.
- If the failure repeats, add one `troubleshooting/*.yaml` entry.
- Keep probe scripts deterministic. Prefer stdlib, existing repo tests, and
  local fixtures over real provider calls.
- Do not mark a browser case passed from API/curl/probe evidence alone.

## Result Classification

- `pass`: declared checks and required evidence passed.
- `fail`: product or contract behavior is wrong.
- `env_issue`: the target could not run because a runtime dependency failed,
  such as `aiosqlite.connect()` hanging before Host ledger tests start.
- `blocked`: required pipeline, plugin, credential, or fixture is missing.
- `flaky`: rerun needed because evidence shows transient instability.

## Maintenance Gate

After adding or editing QA assets:

```bash
rtk bin/lbs validate
rtk bin/lbs index
rtk npm test
```

Commit only reusable assets and code. Do not commit `reports/evidence/*`
run output.
