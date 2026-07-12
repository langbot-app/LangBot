# Agent Runner Release Gate

Use this reference when judging whether runner externalization is release-ready. The goal is not to enumerate every possible prompt. The gate covers product abilities and trust boundaries with deterministic normal-path cases, then leaves rare negative branches to unit and contract tests.

## Coverage Strategy

Treat the release gate as five layers:

| Layer | Purpose | Primary Assets |
| --- | --- | --- |
| Contract gate | Protocol, SDK, auth, stores, and plugin handler behavior without a browser. | `agent-runner-fixture-contract`, `agent-runner-behavior-matrix`, `agent-runner-ledger-invariants`, `agent-runner-ledger-stress`, `agent-runner-ledger-contention`, `agent-runner-runtime-chaos`, `agent-runner-ledger-concurrency`, plus unit and contract tests in touched repos. |
| Environment preflight | Prove the selected live instance is configured for the full gate before expensive browser cases start. | `agent-runner-live-install`, `agent-runner-qa-debug-chat`, `agent-runner-release-preflight`. |
| Fixture gate | Prove deterministic plugin, RAG, multimodal, and MCP fixtures are installed and registered. | `plugin-e2e-smoke`, `langrag-kb-retrieve`, `mcp-stdio-register`. |
| Local-agent capability gate | Prove normal user-facing local-agent paths through WebUI Debug Chat. | `local-agent-gate` cases. |
| External harness gate | Prove ACP can execute an external coding agent through the WebUI Debug Chat path. | `acp-agent-runner-debug-chat`. |

Run the full release gate with:

```bash
rtk bin/lbs suite run agent-runner-release-gate --dry-run --json
rtk bin/lbs suite plan agent-runner-release-gate
rtk bin/lbs suite start agent-runner-release-gate --run-id agent-runner-release-<date>
```

Confirm readiness and `manual_check` preconditions before removing `--dry-run`
or running the generated per-case commands. Then finish with:

```bash
rtk bin/lbs suite report agent-runner-release-gate --evidence-dir reports/evidence/agent-runner-release-<date>
```

For a quick early blocker check, run:

```bash
rtk bin/lbs test run agent-runner-release-preflight --dry-run
```

For the code-level AgentRunner probes, run:

```bash
rtk bin/lbs test run agent-runner-behavior-matrix --dry-run
rtk bin/lbs test run agent-runner-fixture-contract --dry-run
rtk bin/lbs test run agent-runner-ledger-invariants --dry-run
rtk bin/lbs test run agent-runner-ledger-stress --dry-run
rtk bin/lbs test run agent-runner-ledger-contention --dry-run
rtk bin/lbs test run agent-runner-async-db-readiness --dry-run
rtk bin/lbs test run agent-runner-ledger-concurrency --dry-run
rtk bin/lbs test run agent-runner-runtime-chaos --dry-run
rtk bin/lbs test run agent-runner-live-install --dry-run
rtk bin/lbs test run agent-runner-qa-debug-chat --dry-run
```

`agent-runner-behavior-matrix` executes the deterministic behavior fixture at
`fixtures/agent-runner/qa-runner-behaviors.json` through Host result
normalization. It covers normal completed output, streaming output, empty output,
malformed payloads, and controlled failure output without a model provider.

`agent-runner-fixture-contract` imports the source fixture at
`fixtures/plugins/qa-agent-runner` and executes normal, streaming, and
controlled-failure paths with SDK protocol entities. It proves the deterministic
QA runner source is usable before a live installation/browser case uses it.
`bin/lbs fixture check` also verifies the matching
`fixtures/plugins/qa-agent-runner/dist/qa-agent-runner-0.1.0.lbpkg` package is
present and is a zip package.

`agent-runner-live-install` uploads that package to a local LangBot backend and
checks that `qa/agent-runner` is installed and
`plugin:qa/agent-runner/default` appears in pipeline runner metadata. It is an
API integration gate, not a Debug Chat execution proof.

`agent-runner-qa-debug-chat` is the deterministic live execution proof. It uses
a pipeline created by `scripts/e2e/ensure-qa-agent-runner-pipeline.mjs` and
expects Debug Chat to return `QA_AGENT_RUNNER_OK:<input>` through
`plugin:qa/agent-runner/default`.

`agent-runner-ledger-invariants` is the fast Host ledger probe. It uses
synchronous SQLite and checks run status sets, terminal status validation,
ledger table/index DDL, and a minimal insert/read path without a browser or
`aiosqlite`.

`agent-runner-ledger-stress` is a fast deterministic stress baseline. It uses
synchronous SQLite to create 100 queued runs and simulates five runtimes claiming
each run exactly once. It does not replace async/PostgreSQL concurrency tests,
but catches schema and ordering regressions quickly.

`agent-runner-ledger-contention` is a local write-contention probe. It uses a
file-backed SQLite database, 120 queued runs, and eight worker threads to verify
that each run is claimed exactly once under concurrent writers. It still does
not replace async/PostgreSQL concurrency tests.

`agent-runner-async-db-readiness` checks whether direct `aiosqlite` startup is
healthy before running async Host ledger pytest probes.

`agent-runner-ledger-concurrency` is the async Host pytest probe. It exercises
selected run ledger store/API auth tests from `LANGBOT_REPO` or `../LangBot`.
If it times out before any test result and a direct `aiosqlite.connect()` script
also hangs, classify the run with troubleshooting id
`aiosqlite-connect-hangs` instead of treating it as a browser E2E failure.

`agent-runner-runtime-chaos` runs SDK AgentRunner runtime and pull API handler
tests from `LANGBOT_PLUGIN_SDK_REPO` or `../langbot-plugin-sdk`.
Each probe writes `automation-result.json` and probe logs under
`LBS_EVIDENCE_DIR`.

## Normal-Path Matrix

| Product Path | Case Coverage | What It Proves |
| --- | --- | --- |
| Authenticated WebUI session | `webui-login-state`, `agent-runner-release-preflight` | The browser profile can operate the same backend that later cases use. |
| Generic Pipeline Debug Chat | `pipeline-debug-chat` | The WebUI Debug Chat path itself works before runner-specific failures are diagnosed. |
| Deterministic QA runner install | `agent-runner-live-install` | A local `.lbpkg` AgentRunner package can install and register a runner. |
| Deterministic QA runner Debug Chat | `agent-runner-qa-debug-chat` | The installed QA runner executes through WebUI Debug Chat without a model provider. |
| Required runner plugins | `agent-runner-release-preflight` | `langbot-team/LocalAgent` and `langbot-team/ACPAgentRunner` are visible to the host. |
| Required QA plugin tools | `plugin-e2e-smoke`, `agent-runner-release-preflight`, `qa-plugin-smoke-live-install` | The deterministic `qa_plugin_echo` and `qa_plugin_fail` tools are exposed before tool-loop and tool-error cases start. |
| Knowledge base fixture | `langrag-kb-retrieve`, `local-agent-rag-debug-chat` | LangRAG data is queryable and the runner inserts retrieved context. |
| Effective prompt bridge | `local-agent-effective-prompt-debug-chat` | Host prompt preprocessing reaches the runner. |
| History and compaction | `local-agent-context-compaction-debug-chat` | Runner-owned history budgeting keeps recoverable older context. |
| Streaming LLM | `local-agent-basic-debug-chat` | The default streaming path returns a visible answer. |
| Non-streaming LLM | `local-agent-nonstreaming-debug-chat` | The non-streaming adapter path returns a visible answer. |
| Plugin tool loop | `local-agent-plugin-tool-call-debug-chat` | Function-call capable models can call host plugin tools through authorization. |
| Plugin tool error recovery | `local-agent-tool-error-recovery-debug-chat` | Tool execution errors are serialized into model-facing tool results and the model can produce a final answer instead of failing the run. |
| Parallel plugin tool batch | `local-agent-parallel-tools-rag-compaction-debug-chat` | Local-agent executes multiple same-turn plugin tool calls and returns both results with RAG and compacted history. |
| MCP registration | `mcp-stdio-register` | The deterministic stdio MCP server is registered and exposes `qa_mcp_echo`. |
| MCP tool loop | `mcp-stdio-tool-call` | Local-agent can call the registered MCP tool through the same tool loop. |
| Multimodal input | `local-agent-multimodal-debug-chat` | Image upload and structured input reach the runner. |
| Multimodal plus RAG | `local-agent-rag-multimodal-debug-chat` | RAG still works when structured image input is present. |
| ACP external harness execution | `acp-agent-runner-debug-chat` | ACP executes the configured coding agent and returns visible Debug Chat output. |

## Status Taxonomy

Use the same final result categories for every case:

- `pass`: the visible UI behavior and required evidence match the case checks.
- `fail`: the configured product path is reachable, but LangBot or the runner behaves incorrectly.
- `blocked`: the test instance is not configured for this gate, for example missing pipeline, wrong runner id, missing required plugin, or unreachable ACP agent runtime.
- `env_issue`: the runtime dependency is unhealthy, for example backend down, plugin runtime down, Box down, provider route unavailable, invalid API key, or missing model ability in the selected route.
- `flaky`: the path can pass but the run hit a transient network, marketplace, upstream provider, or timing problem that needs a rerun and evidence.

Do not count `blocked` or `env_issue` as product pass. They are useful release signals because they prevent false confidence.

## PR Gate

Before a browser release run, also keep the code-level gate green in the repos touched by the branch:

```bash
# langbot-agent-runner
rtk uv run pytest -q

# langbot-plugin-sdk
rtk uv run pytest -q

# langbot-skills saved AgentRunner probes
rtk bin/lbs test run agent-runner-behavior-matrix --dry-run
rtk bin/lbs test run agent-runner-ledger-invariants --dry-run
rtk bin/lbs test run agent-runner-ledger-stress --dry-run
rtk bin/lbs test run agent-runner-async-db-readiness --dry-run
rtk bin/lbs test run agent-runner-ledger-concurrency --dry-run
rtk bin/lbs test run agent-runner-runtime-chaos --dry-run

# LangBot, target the touched package first, then broaden if shared behavior changed
rtk uv run pytest -q <targeted tests>
```

These tests cover field-level protocol conformance, SDK proxy behavior, auth failures, and negative branches that should not depend on a live provider. The browser gate then proves the normal user paths still compose correctly.

## Release Decision

For runner externalization, a release candidate is acceptable only when:

- PR contract tests are green in every touched repo.
- `agent-runner-release-preflight` has no blockers and no environment issues.
- Every case in `agent-runner-release-gate` has a final `result.json`.
- No `pass` result is missing required evidence.
- Any skipped case is explicitly classified as `blocked` or `env_issue` with a concrete owner and follow-up.
