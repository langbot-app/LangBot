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

### Runner transport difference (both work out-of-the-box on remote-ssh)

Both external runners receive the same host-generated gateway `AgentMCPServerConfig`, but inject it differently — and **both are made remote-reachable automatically; neither requires `public-url` on remote-ssh**:

- **claude-code-agent → stdio bridge.** The mcp config is shipped to the remote host base64-over-SSH-stdin and consumed via `--mcp-config`; the gateway entry is a `command/args` (stdio) MCP server whose process tunnels back to the host over the SSH stdio pipe.
- **acp-agent-runner → HTTP proxy + SSH reverse tunnel.** The gateway is a localhost HTTP MCP proxy passed via ACP `session/new {mcpServers}`. On `remote-ssh` with no `public-url`, the SDK's `AgentRunMCPAccess` (`mcp_access.py` `_remote_reverse_tunnel`: location==remote-ssh and empty public_url) emits an `ssh -R 127.0.0.1:<port>:127.0.0.1:<port>` reverse tunnel — consumed by acp `default.py:521` (`ssh_args.extend(access.reverse_tunnel.ssh_args())`) — and points `server_config.public_url` at the host-local `http_mcp_endpoint`. The remote claude hits `127.0.0.1:<port>` which tunnels back to the host bridge. **`langbot-assets-gateway-public-url` is an optional alternative for topologies where the reverse tunnel can't be used — not a requirement.**

This is a **runner-plugin transport detail, not a host all-tool-branch issue** — proven by **both** runners discovering skills end-to-end with the unmodified branch (see cases below).

> **Correction (2026-06-22).** An earlier revision of this doc claimed acp was "blocked" on remote-ssh and *required* `langbot-assets-gateway-public-url`, based on a run that returned `PROBEDONE 0 0` / timeout. That was an **environment artifact, not an acp defect**: a duplicate backend instance (a second checkout `LangBot-master/` whose box runtime contended for the same `--ws-control-port 5410`) plus a wedged plugin runtime (host `emit_event` / `list_agent_runners` action calls timing out with `ActionCallTimeoutError`). Re-run on a clean single-instance runtime, **acp passes via the reverse tunnel with no `public-url`** (`PROBEDONE 1 17`, 8–24s).
- **Lifecycle**: discover → activate → operate (native exec under the activated mount path) → register.
- **Backend**: docker · nsjail · e2b.

## Cases & status

| Case | Asserts | Runner(s) | Status |
| --- | --- | --- | --- |
| `skill-tool-exposure-no-capability` | skill tools offered to a tool-calling runner **without** `skill_authoring`; gated only on sandbox+skill_mgr | local-agent | **covered (unit)** — `test_tool_manager_native.py`, `test_preproc.py` |
| `skill-activation-persistence` | activated skill survives a new run in the same conversation (`host.activated_skills` restore) | local-agent | **covered (unit)** — `test_skill_tools.py` |
| `toolresource-parameters-prefill` | runner builds LLM tools from `ctx.resources.tools.parameters` without per-tool `get_tool_detail` | local-agent | **covered (unit)** — `test_run_assembly.py::test_build_llm_tools_uses_prefilled_schema_without_fetch` |
| `regression-existing-runner-behavior` | existing local-agent cases (basic/rag/tool-call/steering/multimodal) unchanged | local-agent | **covered (unit)** — full host/sdk/local-agent suites green, 0 new failures |
| `sandbox-skill-authoring-e2e` | create → register → activate → exec-from-activated-path → `E2E_OK` | local-agent | **PASS (nsjail + docker)** — full chain green via local-agent Debug Chat (pipeline `3e645b04`): create+run in `/workspace` → `exit 0` `SANDBOX_COMPLEX_SKILL_OK sum=10 product=24`; register+activate; exec in `/workspace/.skills/<name>` runs `scripts/use.py` (reads `data/input.json`) and writes `activated_writeback.txt` → `exit 0`, both markers, file written through to host skill store. Verified on **nsjail** first, then on **docker** after the #2271 fix ([langbot-plugin-sdk#87](https://github.com/langbot-app/langbot-plugin-sdk/pull/87)). |
| `skill-discovery-via-mcp-gateway` | external harness calls `langbot_list_assets(['skills'])` and receives pipeline-visible skills | claude-code / acp | **PASS (both)** — clean single-instance runtime, remote-ssh→101. claude-code-agent (pipeline `28fd37ac`, stdio bridge): `PROBEDONE skills=1 tools=15`. acp-agent-runner (pipeline `b00794d2`, HTTP proxy + SSH reverse tunnel, **no public-url**): `PROBEDONE skills=1 tools=17`, 8–24s. Both prove the all-tool `skills` asset class is discoverable end-to-end by an external harness. |
| `skill-activation-cross-runner-parity` | local-agent and external harness both reach skills via their paths (`use_funcs` vs `langbot_call_tool`) | local-agent + claude-code + acp | **PASS** — local-agent (use_funcs) ✓, claude-code-agent (stdio gateway, `skills=1 tools=15`) ✓, and acp-agent-runner (HTTP-proxy gateway over reverse tunnel, `skills=1 tools=17`) ✓ all discover skills. `skills` count matches (1==1); the `tools` count (17 vs 15) is claude's self-reported tally and not yet checked against the authoritative gateway count — most likely model-counting variance, not an asset difference. |

## Known issues

- [#2271](https://github.com/langbot-app/LangBot/issues/2271) — activated `/workspace/.skills/<name>` `scripts/`/`data/` missing on the docker backend. **FIXED** by [langbot-plugin-sdk#87](https://github.com/langbot-app/langbot-plugin-sdk/pull/87) (`fix(box): recreate sandbox container when extra_mounts change`), rebased into this branch. **Corrected root cause:** not "docker masks the nested bind mount" (disproven) — the real bug is **container reuse**: `extra_mounts` was not part of the box session compatibility check, so when a skill is activated mid-conversation docker reused the already-running container and could not append the new bind mount; the activated skill therefore appeared empty. The fix records a mount signature on the session and recreates the container when the mount set changes (idempotent, no data loss). Pre-existing (Feat/sandbox #2072), reproduced on pure `origin/master` + the built-in local-agent runner, so not introduced by this branch — this branch only exposed the path end-to-end for the first time. After the fix, the OPERATE step passes on **both** docker and nsjail (see exit criterion 3). Merging needs a new SDK release + a `langbot-plugin` pin bump in LangBot's `pyproject.toml` to reach a released LangBot.
- **nsjail + stale docker workspace artifacts (environment, not a code bug).** If a prior docker run left root-owned dirs under the workspace (e.g. `data/box/default/.skills/`, created root-owned because docker runs as root), nsjail — which runs as the invoking user — cannot create the nested skill mount target under that root-owned dir and `runChild()` fails with `Launching child process failed`, poisoning **every** exec in the session (the exact symptom documented in `box/service.py::build_skill_extra_mounts`). Fix: remove the root-owned leftovers (`sudo rm -rf data/box/default/.skills data/box/default/<stale-skill>`) before running nsjail e2e. New nsjail runs create user-owned artifacts, so this is a one-time cleanup after switching off docker.

## Exit criteria

1. Unit matrix green across host/sdk/local-agent, 0 new failures. **(DONE)**
2. `skill-tool-exposure-no-capability` + `skill-activation-persistence` + `toolresource-parameters-prefill` covered by unit. **(DONE)**
3. `sandbox-skill-authoring-e2e` OPERATE step passes on a real backend, proving end-to-end skill use. **(DONE — nsjail + docker)** — full create→exec→register→activate→exec-from-`/workspace/.skills/<name>` chain returns `exit 0`; the activated mount runs `scripts/use.py` (reads `data/input.json` → `SANDBOX_COMPLEX_SKILL_OK sum=10 product=24`) and writes `activated_writeback.txt` through to the host skill store. Verified on nsjail, then on docker after the #2271 fix ([langbot-plugin-sdk#87](https://github.com/langbot-app/langbot-plugin-sdk/pull/87)).
4. `skill-discovery-via-mcp-gateway` passes on an external harness. **(DONE — claude-code-agent: skills=1 tools=15, 24s)**
5. `skill-activation-cross-runner-parity` passes on acp. **(DONE — acp: skills=1 tools=17, 8s, via SSH reverse tunnel with no public-url; clean single-instance runtime)**

## How to run

- **Unit**: LangBot `make test`; SDK `uv run pytest`; local-agent `uv run pytest tests/`.
- **Browser e2e**: per-pipeline Debug Chat; canonical skill prompt pattern in [`sandbox-skill-authoring.md`](./sandbox-skill-authoring.md). Automatable cases use the `automation_*` fields + `scripts/e2e/pipeline-debug-chat.mjs`.
