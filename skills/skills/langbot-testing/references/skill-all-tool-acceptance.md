# Acceptance matrix — skill all-tool model

Acceptance criteria for the branch that unifies LangBot skills as **authorized
tools** (`feat/agent-runner-plugin`). Skills are no longer gated behind the
`skill_authoring` capability; `activate` / `register_skill` / native `exec` are
exposed like native tools, gated only on **sandbox + skill_mgr**. Discovery is
tool-driven (`langbot_list_assets` gains a `skills` asset class for external
harnesses). Host persists activated skills to `host.activated_skills`
(last-write-wins) and prefills `ToolResource.parameters` so runners skip
per-tool `get_tool_detail`.

## What changed (scope under test)

| Layer | Change |
| --- | --- |
| host | `toolmgr.get_all_tools` drops `include_skill_authoring`; `SkillToolLoader` self-gates on sandbox+skill_mgr |
| host | `preproc` drops the `include_skill_authoring` branch; bound-skills + skills resource gate on `skill_mgr` |
| host | `resource_builder` stops gating skills on `skill_authoring`; fills `ToolResource.parameters` via `tool_mgr.get_tool_schema` |
| host | `persist_activated_skill` writes `host.activated_skills` (conversation scope) |
| sdk | `ToolResource.parameters` (full JSON schema); `langbot_list_assets` `skills` asset class |
| local-agent | `build_llm_tools` prefers `ctx.resources.tools.parameters`, falls back to `get_tool_detail`; `DEFAULT_MAX_TOOL_ITERATIONS` 20→100 |

## Dimensions

- **Runner**: `local-agent` (in-process logic, direct Run API, skill tools in `use_funcs`) · `acp-agent-runner` (external harness, remote-ssh claude-code, MCP gateway) · `claude-code-agent` (external harness, claude-code CLI, MCP gateway — *no pipeline yet*).
- **Lifecycle**: discover → activate → operate (native exec under the activated mount path) → register.
- **Backend**: docker · nsjail · e2b.

## Cases & status

| Case | Asserts | Runner(s) | Status |
| --- | --- | --- | --- |
| `skill-tool-exposure-no-capability` | skill tools offered to a tool-calling runner **without** `skill_authoring`; gated only on sandbox+skill_mgr | local-agent | **covered (unit)** — `test_tool_manager_native.py`, `test_preproc.py` |
| `skill-activation-persistence` | activated skill survives a new run in the same conversation (`host.activated_skills` restore) | local-agent | **covered (unit)** — `test_skill_tools.py` |
| `toolresource-parameters-prefill` | runner builds LLM tools from `ctx.resources.tools.parameters` without per-tool `get_tool_detail` | local-agent | **covered (unit)** — `test_run_assembly.py::test_build_llm_tools_uses_prefilled_schema_without_fetch` |
| `regression-existing-runner-behavior` | existing local-agent cases (basic/rag/tool-call/steering/multimodal) unchanged | local-agent | **covered (unit)** — full host/sdk/local-agent suites green, 0 new failures |
| `sandbox-skill-authoring-e2e` | create → register → activate → exec-from-activated-path → `E2E_OK` | local-agent | **partial** — authorization chain passes (agent calls exec/register/activate, skill registered 0→1); **OPERATE step blocked by [#2271](https://github.com/langbot-app/LangBot/issues/2271)** on docker+shared-fs |
| `skill-discovery-via-mcp-gateway` | external harness calls `langbot_list_assets(['skills'])` and receives pipeline-visible skills | acp / claude-code | **blocked (env)** — remote claude-code unresponsive (`runner.timeout`); link is alive (runner started, reached execution) |
| `skill-activation-cross-runner-parity` | local-agent and external harness both reach `activate` via their paths (`use_funcs` vs `langbot_call_tool`) | local-agent + acp | **blocked (env)** |

## Known issues

- [#2271](https://github.com/langbot-app/LangBot/issues/2271) — activated `/workspace/.skills/<name>` missing `scripts/`/`data/` on docker backend (nested bind mount). **Pre-existing** (Feat/sandbox #2072), not introduced by this branch (the mount/register chain is byte-identical to `origin/master` across host loader, `box/service.py`, SDK box backend, SDK box runtime). This branch only **exposed** the path end-to-end for the first time. Blocks the OPERATE step on docker+shared-fs.

## Exit criteria

1. Unit matrix green across host/sdk/local-agent, 0 new failures. **(DONE)**
2. `skill-tool-exposure-no-capability` + `skill-activation-persistence` + `toolresource-parameters-prefill` covered by unit. **(DONE)**
3. `sandbox-skill-authoring-e2e` OPERATE step passes on at least one backend once #2271 is fixed (or a backend that avoids nested mounts), proving real end-to-end skill use. **(BLOCKED on #2271)**
4. `skill-discovery-via-mcp-gateway` + `skill-activation-cross-runner-parity` pass on acp once remote claude-code is responsive. **(BLOCKED on env)**

## How to run

- **Unit**: LangBot `make test`; SDK `uv run pytest`; local-agent `uv run pytest tests/`.
- **Browser e2e**: per-pipeline Debug Chat; canonical skill prompt pattern in [`sandbox-skill-authoring.md`](./sandbox-skill-authoring.md). Automatable cases use the `automation_*` fields + `scripts/e2e/pipeline-debug-chat.mjs`.
