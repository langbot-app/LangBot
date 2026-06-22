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

- **Runner**: `local-agent` (in-process logic, direct Run API, skill tools in `use_funcs`) · `acp-agent-runner` (external harness, remote-ssh claude-code over ACP, MCP gateway via **HTTP proxy**) · `claude-code-agent` (external harness, claude-code CLI, MCP gateway via **stdio bridge** — pipeline `28fd37ac`, remote-ssh→101).

### Runner transport difference (important for remote-ssh)

Both external runners receive the same host-generated gateway `AgentMCPServerConfig`, but inject it differently:

- **claude-code-agent → stdio bridge.** The mcp config is shipped to the remote host base64-over-SSH-stdin and consumed via `--mcp-config`; the gateway entry is a `command/args` (stdio) MCP server whose process tunnels back to the host over the SSH stdio pipe. **No extra config needed on remote-ssh** — works out of the box.
- **acp-agent-runner → HTTP proxy.** The gateway is a localhost HTTP MCP proxy passed via ACP `session/new {mcpServers}`. On `remote-ssh` the remote claude must HTTP-reach the host, so you **must** set `langbot-assets-gateway-public-url` (or `mcp-public-url`) to a host URL the remote can reach. Without it the remote `mcpServers` entry points at the *remote's* localhost → `langbot_*` tools never enter claude's tool list.

This is a **runner-plugin transport detail, not a host all-tool-branch issue** — proven by claude-code-agent discovering skills end-to-end with the unmodified branch.
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
| `skill-discovery-via-mcp-gateway` | external harness calls `langbot_list_assets(['skills'])` and receives pipeline-visible skills | claude-code / acp | **PASS (claude-code-agent)** — pipeline `28fd37ac`, remote-ssh→101: `PROBEDONE skills=1 tools=15` in 24s, proving the all-tool `skills` asset class is discoverable end-to-end by an external harness. **acp blocked (config)** — needs `langbot-assets-gateway-public-url` in remote-ssh (HTTP-proxy transport); without it claude reports langbot tools "not available in my direct tool list" → `PROBEDONE 0 0` |
| `skill-activation-cross-runner-parity` | local-agent and external harness both reach skills via their paths (`use_funcs` vs `langbot_call_tool`) | local-agent + claude-code | **PARTIAL** — local-agent (use_funcs) ✓ and claude-code-agent (langbot_list_assets via stdio gateway) ✓ both discover skills; acp parity pending public-url config |

## Known issues

- [#2271](https://github.com/langbot-app/LangBot/issues/2271) — activated `/workspace/.skills/<name>` missing `scripts/`/`data/` on docker backend (nested bind mount). **Pre-existing** (Feat/sandbox #2072), not introduced by this branch (the mount/register chain is byte-identical to `origin/master` across host loader, `box/service.py`, SDK box backend, SDK box runtime). This branch only **exposed** the path end-to-end for the first time. Blocks the OPERATE step on docker+shared-fs.

## Exit criteria

1. Unit matrix green across host/sdk/local-agent, 0 new failures. **(DONE)**
2. `skill-tool-exposure-no-capability` + `skill-activation-persistence` + `toolresource-parameters-prefill` covered by unit. **(DONE)**
3. `sandbox-skill-authoring-e2e` OPERATE step passes on at least one backend once #2271 is fixed (or a backend that avoids nested mounts), proving real end-to-end skill use. **(BLOCKED on #2271)**
4. `skill-discovery-via-mcp-gateway` passes on an external harness. **(DONE — claude-code-agent: skills=1 tools=15, 24s)**
5. `skill-activation-cross-runner-parity` passes on acp once `langbot-assets-gateway-public-url` is configured for the remote-ssh HTTP-proxy transport. **(PENDING acp config)**

## How to run

- **Unit**: LangBot `make test`; SDK `uv run pytest`; local-agent `uv run pytest tests/`.
- **Browser e2e**: per-pipeline Debug Chat; canonical skill prompt pattern in [`sandbox-skill-authoring.md`](./sandbox-skill-authoring.md). Automatable cases use the `automation_*` fields + `scripts/e2e/pipeline-debug-chat.mjs`.
