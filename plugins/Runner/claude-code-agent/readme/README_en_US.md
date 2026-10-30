# Claude Code Agent

## Overview

Run Claude Code CLI as a LangBot Runner.

## Package information

- **Runner ID**: `plugin:langbot-team/ClaudeCodeAgent/default`
- **Version**: `0.1.3`
- **Repository**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/claude-code-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/claude-code-agent)

## Capabilities

- **Enabled**: `streaming`, `tool calling`, `knowledge retrieval`, `steering`
- **Not declared**: `multimodal input`, `interrupt`

## Configuration

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `daemon-enabled` | `boolean` | No | false |
| `daemon-host` | `string` | No | `127.0.0.1` |
| `daemon-port` | `integer` | No | `8767` |
| `daemon-token` | `secret` | No | Empty |
| `location` | `select` | Yes | `local` |
| `workspace` | `string` | No | Empty |
| `advanced-settings` | `boolean` | No | false |
| `command` | `string` | No | `claude` |
| `args-json` | `string` | No | `[]` |
| `env-json` | `string` | No | `{}` |
| `ssh-target` | `string` | No | Empty |
| `ssh-port` | `integer` | No | `22` |
| `daemon-id` | `string` | No | Empty |
| `timeout` | `integer` | No | `300` |
| `streaming` | `boolean` | No | true |
| `reuse-session` | `boolean` | No | true |
| `dangerously-skip-permissions` | `boolean` | No | true |
| `knowledge-bases` | `knowledge-base-multi-selector` | No | `[]` |
| `langbot-assets-enabled` | `boolean` | No | true |
| `mcp-bridge-transport` | `select` | No | `auto` |
| `mcp-servers-json` | `string` | No | `[]` |

## Host permissions

- **`tools`**: `detail`, `call`
- **`knowledge_bases`**: `retrieve`
- **`history`**: `page`

## Installation and usage

1. Install the plugin from the LangBot plugin marketplace.
2. Select the Runner ID below in the Pipeline Runner selector.
3. Fill in connection settings from the table and store credentials in secret fields in the admin UI.

## Security and limitations

- The runner can use only LangBot resources authorized for the current run.
- By default, Claude Code runs with `--dangerously-skip-permissions` because LangBot does not yet expose an interactive approval flow. Use it only with trusted workspaces and a constrained operating-system account. Set `dangerously-skip-permissions` to false to restore Claude Code's normal permission checks.
- Availability, model abilities, and rate limits depend on the external service.
- See the localized README files under `readme/` for translated guidance.

- Follow-ups are injected between turns, not mid-token.
- Follow-up turns currently carry text only; attachments on follow-ups are not
  yet forwarded.
- Steering only applies when the run has a conversation scope; otherwise the
  runner transparently falls back to single-turn execution.

## Structured interactions

The runner exposes a real MCP tool named `ask_user_question` through the
run-scoped LangBot MCP bridge. Its standard Claude `tool_use` event is converted
to LangBot's provider-neutral `interaction.requested` contract. The CLI process
is stopped while the user is answering. A card submission starts a new
AgentRun, resumes the same Claude Code session, and sends the answer as the next
authoritative user turn. Claude CLI must complete an MCP call before persisting
a resumable session, so it cannot accept a second result for the old
`tool_use_id` after the process exits. No Python coroutine or Claude process is
kept waiting for the user.


## Shared-worker candidate / daemon upgrade

This version pins `langbot-plugin==0.6.1` and remains dedicated; no shared-worker eligibility is claimed.
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
