# ACP Runner

`acp-agent-runner` runs an Agent Client Protocol compatible agent process as a LangBot Runner.

It is a thin runtime adapter:

- LangBot remains the control plane.
- The plugin starts an ACP server over stdio, such as `npx -y @zed-industries/codex-acp`, `npx -y @agentclientprotocol/claude-agent-acp@0.62.0`, `opencode acp`, or `npx -y @google/gemini-cli --acp`.
- In daemon mode, a user-side `langbot-runner-daemon` connects outward to the plugin and starts the ACP process on the user's machine.
- The plugin speaks ACP JSON-RPC: `initialize`, `session/new`, `session/load` or `session/resume`, and `session/prompt`.
- ACP `session/update` text chunks are streamed back to LangBot.
- LangBot multimodal input is mapped to ACP prompt content blocks when the selected ACP runtime advertises the matching prompt capability.
- LangBot tools, knowledge bases, and history are exposed through the SDK-owned run-scoped MCP bridge.

## Runner ID

`plugin:langbot-team/ACPAgentRunner/default`

## Configuration

Common local examples:

```text
provider = claude-code
location = local
workspace = /path/to/workspace
```

```text
provider = codex
location = local
workspace = /path/to/workspace
```

For custom ACP commands, set `provider=custom` and `acp-command`, for example:

```text
provider = custom
location = local
workspace = /path/to/workspace
acp-command = opencode acp
```

For a user workstation behind NAT, enable the plugin daemon hub and run the user-side daemon:

```text
# Plugin config
daemon-enabled = true
daemon-host = 0.0.0.0
daemon-port = 8766
daemon-token = <shared-token>
```

```bash
cd acp-agent-runner
python daemon.py \
  --url ws://<langbot-public-host>:8766 \
  --daemon-id alice-laptop \
  --token <shared-token>
```

Then configure the runner:

```text
provider = codex
location = daemon
daemon-id = alice-laptop
workspace = /Users/alice/project
```

Custom mode is for ACP stdio commands that are not built in, or for users who
accept weaker/no ACP session recovery for a specific runtime:

```text
provider = custom
location = local
workspace = /path/to/workspace
acp-command = kimi acp
```

```text
provider = custom
location = local
workspace = /path/to/workspace
acp-command = agent acp
```

```text
provider = custom
location = local
workspace = /path/to/workspace
acp-command = goose acp
```

`acp-command` must start an ACP JSON-RPC stdio server, not an interactive-only
CLI. The runner still calls `initialize`, then `session/resume` or
`session/load` when a stored session id exists and the runtime advertises that
capability, otherwise `session/new`. Set `reuse-session=false` to force a fresh
ACP session each run:

```text
provider = custom
location = local
workspace = /path/to/workspace
acp-command = kimi acp
reuse-session = false
```

Useful options:

- `provider`: built-in ACP launch preset. Current presets are limited to ACP runtimes that advertise `loadSession` or `sessionCapabilities.resume` and have no known public cross-process resume blocker. Use `custom` for anything else.
- `location`: `local`, `remote-ssh`, or `daemon`.
- `workspace`: agent workspace directory. In `remote-ssh` and `daemon` modes this path is on the remote/user machine.
- `advanced-settings`: reveals bridge, timeout, session, and process tuning controls. It only changes form visibility.
- `ssh-target`: SSH target for `remote-ssh`, for example `yhh@101.34.71.12`.
- `ssh-port`: SSH port. Defaults to `22`.
- `ssh-identity-file`: optional private key path on the LangBot host.
- `daemon-id`: stable ID of a connected user-side runner daemon for `location=daemon`.
- `daemon-connect-timeout`: seconds to wait for the selected daemon to come online.
- `acp-command`: optional command override. Required only for `provider=custom`.
- `env-json`: JSON object merged into the process environment.
- `reuse-session`: persists and reuses `external.acp_session_id` when the ACP agent supports `session/resume` or `session/load`.
- `knowledge-bases`: selects the LangBot knowledge bases authorized for retrieval in this runner.
- `langbot-assets-enabled`: injects the LangBot run-scoped MCP bridge into ACP `mcpServers`.
- `langbot-assets-mode`: `auto`, `ephemeral`, or `gateway`. `auto` currently preserves the existing per-run bridge behavior; `gateway` registers the run in the SDK-owned long-lived HTTP MCP gateway.
- `langbot-assets-gateway-port`: optional fixed port for `langbot-assets-mode=gateway`. Use a fixed port when another platform such as Dify needs to register the gateway URL.
- `langbot-assets-gateway-public-url`: optional externally reachable MCP URL, for example `https://example.com/mcp`.

Headless ACP permission requests are answered with `allow_once` by default.
LangBot does not yet expose an interactive approval UI for these requests.

## Steering (follow-up input)

This runner declares `capabilities.steering: true`. When a run is still in
progress and the user sends another message, LangBot absorbs it into the active
run instead of starting a new one. The runner drains these follow-ups at each
turn boundary via `steering_pull` and runs them as additional ACP
`session/prompt` turns that resume the same session (`session/resume` or
`session/load`). The run emits a single terminal `run.completed` once no
follow-ups remain.

Notes:

- Follow-ups are injected between turns, not mid-token.
- Follow-up turns currently carry text only; attachments on follow-ups are not
  yet forwarded (the first turn still maps full multimodal input as described
  below).
- In `daemon` mode follow-ups are still drained (no message loss), but session
  continuity across follow-up turns is best-effort.
- Steering only applies when the run has a conversation scope; otherwise the
  runner transparently falls back to single-turn execution.

## Multimodal Input

The runner accepts LangBot structured input and attachments. It maps them to ACP
`session/prompt` content blocks according to the selected runtime's
`agentCapabilities.promptCapabilities`:

- inline image base64/data URLs are sent as ACP `image` blocks only when the
  runtime advertises image prompt support;
- inline file base64/data URLs are sent as embedded ACP `resource` blocks only
  when the runtime advertises embedded context support;
- URL-backed images or files are sent as ACP `resource_link` blocks;
- unsupported inline attachments are not silently dropped; the prompt receives a
  short attachment note explaining which content was not sent.

Provider support still depends on the ACP executable being launched. A runtime
that does not advertise image prompt support can still handle normal text input
and URL resource links, but it will not receive inline image bytes.

Built-in provider commands are intentionally unpinned and assume the selected
runtime can run on the target machine. Built-in presets must support ACP session
recovery through `loadSession` or `sessionCapabilities.resume`; otherwise this
runner would silently degrade into single-turn execution after each stdio
process exits.

| Provider | Default ACP command | Verified session recovery signal |
| --- | --- | --- |
| `auggie` | `npx -y @augmentcode/auggie --acp` | `loadSession` |
| `autohand` | `npx -y @autohandai/autohand-acp` | `loadSession`, `session/resume` |
| `claude-code` | `npx -y @agentclientprotocol/claude-agent-acp@0.62.0` | `loadSession`, `session/resume` |
| `codebuddy-code` | `npx -y @tencent-ai/codebuddy-code --acp` | `loadSession` |
| `codex` | `npx -y @zed-industries/codex-acp` | `loadSession`, `session/resume` |
| `deepagents` | `npx -y deepagents-acp` | `loadSession` |
| `dimcode` | `npx -y dimcode acp` | `loadSession`, `session/resume` |
| `dirac` | `npx -y dirac-cli --acp` | `loadSession` |
| `factory-droid` | `npx -y droid exec --output-format acp-daemon` | `loadSession`, `session/resume` |
| `gemini` | `npx -y @google/gemini-cli --acp` | `loadSession` |
| `glm-agent` | `npx -y glm-acp-agent` | `loadSession`, `session/resume` |
| `kilo` | `npx -y @kilocode/cli acp` | `loadSession`, `session/resume` |
| `opencode` | `opencode acp` | `loadSession`, `session/resume` |
| `pi-acp` | `npx -y pi-acp` | `loadSession` |
| `qwen-code` | `npx -y @qwen-code/qwen-code --acp --experimental-skills` | `loadSession`, `session/resume` |

The following ACP-capable or ACP-adjacent CLIs are not built-in presets because
they do not currently meet the session recovery bar for this runner:

| Provider | Reason |
| --- | --- |
| `agoragentic` | `initialize` reports `loadSession: false` and no `session/resume`. |
| `cline` | Headless `initialize` did not complete during verification, so session recovery could not be confirmed. |
| `cursor` | Public reports show `loadSession: true` is advertised, but `session/load` fails for ACP-created sessions. |
| `github-copilot` | Registry npx launch did not start a usable ACP binary during verification. |
| `goose` | Upstream docs say ACP providers do not support session resume or fork yet. |
| `kimi` | Public issue reports ACP load/switch starts with blank history even though CLI history exists. |
| `langcli` | No registry/npm-verifiable ACP stdio package was available during verification. |
| `nova` | Headless `initialize` did not complete during verification, so session recovery could not be confirmed. |
| `qoder` | Public report shows ACP-created sessions cannot be loaded across process restarts despite `loadSession: true`. |
| `sigit` | Packaged binary could not be verified in the test environment and no public session recovery evidence was found. |

Other ACP-compatible runtimes from the public ACP registry can still be used via
`provider=custom` and `acp-command`. DeepSeek's official Deep Code CLI is not a
built-in preset yet because its current public docs describe the interactive
`deepcode` CLI and MCP support, but do not document an ACP stdio mode.

For a remote Claude ACP process over SSH:

```text
provider = claude-code
location = remote-ssh
ssh-target = yhh@101.34.71.12
workspace = /home/yhh/langbot-e2e/acp-workspace
```

Remote mode does not connect to a long-running ACP TCP service. LangBot starts
the ACP process itself over SSH:

```text
LangBot host
  -> ssh user@host "cd <workspace> && exec <acp-command>"
  -> ACP JSON-RPC over ssh stdio
```

When LangBot assets are enabled, the runner also starts a temporary run-scoped
MCP bridge on the LangBot host and adds an SSH reverse tunnel on the same SSH
connection:

```text
remote ACP process
  -> http://127.0.0.1:<forwarded-port>/mcp
  -> SSH -R tunnel
  -> LangBot run-scoped MCP bridge
```

The remote host must allow non-interactive SSH login from the LangBot host and
must already have the selected agent runtime installed, authenticated, and
available on `PATH` for non-interactive shells.

Platform notes:

- Linux remote: default path. The wrapper uses `bash -lc`, creates the workspace
  directory, changes into it, then execs `acp-command`.
- macOS remote: same as Linux when the remote has `bash` and the selected agent
  runtime available to non-interactive SSH sessions. If a Homebrew/npm path is
  missing, set it through `env-json` or use an absolute command path.
- Windows remote: not identical to Linux/macOS. Configure the hidden
  `remote-shell=powershell` key manually; the wrapper uses PowerShell to create
  the workspace and run `acp-command`. Windows OpenSSH must support reverse
  forwarding for LangBot MCP assets to work. A first-class Windows UI option is
  not exposed yet.

If a network policy blocks SSH reverse forwarding, set
`mcp-bridge-transport=http` plus `mcp-public-url` to a URL reachable from the
remote host, or disable LangBot asset injection with `langbot-assets-enabled=false`.

## Run-Scoped LangBot Assets

By default the plugin starts a temporary run-scoped MCP bridge for each run. The
bridge URL and token are injected into ACP `mcpServers`, and the bridge is
stopped when the run finishes.

In `location=daemon`, the ACP process does not call the plugin's MCP bridge
directly. The user-side daemon starts a localhost HTTP MCP proxy, injects that
local URL into ACP, then forwards MCP JSON-RPC requests over the already-open
WebSocket connection back to the plugin. The plugin handles those requests with
the current run's `RunnerAPIProxy`, so LangBot assets remain scoped by
`run_id` and the Host authorization snapshot. The user's workstation does not
need a public IP or inbound port for this path.
Runner code should import the SDK proxy from
`langbot_plugin.api.proxies.runner`.

To test the long-lived HTTP MCP gateway path with ACP, set:

```text
langbot-assets-enabled = true
langbot-assets-mode = gateway
langbot-assets-gateway-port = 8765
```

In gateway mode, the SDK starts one process-long HTTP MCP gateway and registers
each LangBot run with a short-lived run token. ACP receives the gateway MCP URL
and token through `mcpServers` headers, so the model can call stable LangBot
gateway tools without seeing the token. The gateway tool list is stable and
includes:

- `langbot_list_assets`
- `langbot_get_current_event`
- `langbot_history_page`
- `langbot_retrieve_knowledge`
- `langbot_get_tool_detail`
- `langbot_call_tool`

Host-authorized platform and event actions are projected through the same MCP
surface as `tool_type=platform` tools. Use `langbot_list_assets` with
`asset_types=["platform_tools"]` to inspect them, then call them through
`langbot_call_tool`. Event-level action targets are frozen by LangBot for the
current run; platform-level actions may accept explicit target IDs. The ACP
process never receives the platform adapter or its credentials directly.

The stable tool list is intentionally compatible with platforms such as Dify
that cache MCP provider tools. For those platforms, the same gateway can accept
the short-lived `run_token` as a tool argument instead of an HTTP header.
Register the provider URL with the `/mcp` path, for example
`http://<langbot-host>:8765/mcp` or the value configured in
`langbot-assets-gateway-public-url`.

The current LangBot `run_id` is included in the prompt for diagnostics only. ACP agents should follow MCP tool schemas exactly and should not add `run_id` to tool calls unless a specific tool schema asks for it.

## Complete configuration index

In addition to the common fields described above, the current runner exposes:

- `daemon-connect-timeout` for waiting on a selected daemon.
- `langbot-assets-gateway-host`, `langbot-assets-gateway-port`, `langbot-assets-gateway-public-url`, and `langbot-assets-token-ttl` for Asset Gateway mode.
- `ssh-connect-timeout`, `ssh-extra-options`, and `ssh-identity-file` for SSH execution.
- `startup-timeout` and `initialize-timeout` for ACP process startup and handshake deadlines.
- `create-session-if-missing` for recovery fallback behavior.
- `streaming` for incremental output.
- `append-run-scope-prompt` for adding LangBot run-scope guidance.
- `mcp-servers-json` for additional MCP server configuration.

## Scope

This plugin intentionally does not implement an agent platform, task board, workspace manager, or provider-specific CLI behavior. Provider setup, login, model selection, and tool permission semantics still belong to the ACP agent executable being launched.


## Shared-worker candidate / daemon upgrade

This version pins `langbot-plugin==0.6.0b5` and remains dedicated; no shared-worker eligibility is claimed.
It is a candidate, not a certificate or proof of vendor execution. Local,
remote-SSH and daemon modes remain available. Native children use the worker's
nsjail/cgroup policy, not the separate Box managed-process quota.

- Shared native mode defaults to **`/data/workspace`**, an installation-private
  writable directory. Explicit native paths must exist and be writable inside
  the jail; `/plugin` is read-only. Dedicated/OSS defaults are unchanged.
- Shared daemon listeners require a **different random token per installation**
  (at least 32 characters, at least 12 distinct characters; generate with
  `python -c 'import secrets; print(secrets.token_urlsafe(32))'`). Length checks
  cannot prove randomness or cross-installation uniqueness: provision unique
  secrets, do not reuse the example/config default. Loopback is shared between
  workers. Assign a unique explicit `daemon-port` per installation and configure
  TLS routing for remote clients; port conflicts fail with configuration guidance.
- Upgrade **both `daemon.py` and its entire `pkg/` directory** from this exact
  plugin version on the target. Stock b5/older clients are rejected: the bundled
  plugin-owned relay negotiates `coding-relay-v1`. No installed SDK is patched.
- A daemon ID cannot replace a connected socket. Jobs/events/MCP/finish belong
  to the accepted socket incarnation. Cancellation revokes run tools and waits
  for client process-group cleanup before acknowledging, or fences that daemon.
  A disconnect cancels and awaits the client's jobs before any reconnect.
- Unresolved shared jobs retain `.pending` markers under
  `/data/.coding-relay-v1/<runner-prefix>/`; worker restart does **not** clear
  them. Stop and verify all remote jobs on that target before an operator removes
  its marker and reconnects. Never rename the target to bypass a fence. An
  already dispatched MCP/SSH/upstream side effect is not rolled back by cancel.
- Remote SSH/daemon accounts are **trusted execution targets**, not independent
  tenant sandboxes. Terminating local SSH does not prove remote process-tree
  exit; use a controlled target and verify remote quiescence before reuse.
  POSIX cleanup covers descendants that remain in the launched process group;
  deliberately detached processes require target-owner cleanup.
- Install reviewed CLI/SSH binaries at jail-visible locations and provision
  installation-owned credentials. These are functional prerequisites, separate
  from certification, signing, and two-Workspace live acceptance. Do not relax
  global Box policy or use unreviewed automatic installers to satisfy them.
