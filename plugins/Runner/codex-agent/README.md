# Codex Agent

## Overview

Run Codex CLI as a LangBot Runner.

## Package information

- **Runner ID**: `plugin:langbot-team/CodexAgent/default`
- **Version**: `0.1.9`
- **Repository**: [https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/codex-agent](https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/codex-agent)

## Capabilities

- **Enabled**: `streaming`, `tool calling`, `knowledge retrieval`, `steering`
- **Not declared**: `multimodal input`, `interrupt`

## Configuration

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `daemon-enabled` | `boolean` | No | false |
| `daemon-host` | `string` | No | `127.0.0.1` |
| `daemon-port` | `integer` | No | `8768` |
| `daemon-token` | `secret` | No | Empty |
| `location` | `select` | Yes | `local` |
| `workspace` | `string` | No | Empty |
| `advanced-settings` | `boolean` | No | false |
| `command` | `string` | No | `codex` |
| `args-json` | `string` | No | `[]` |
| `env-json` | `string` | No | `{}` |
| `ssh-target` | `string` | No | Empty |
| `ssh-port` | `integer` | No | `22` |
| `daemon-id` | `string` | No | Empty |
| `timeout` | `integer` | No | `1800` |
| `streaming` | `boolean` | No | true |
| `reuse-session` | `boolean` | No | true |
| `approval-policy` | `select` | No | `never` |
| `sandbox-mode` | `select` | No | `danger-full-access` |
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

- The default configuration starts Codex with `approvalPolicy=never` and `sandbox=danger-full-access` and does not wait for interactive approval. Use the default only with trusted workspaces and a constrained operating-system account.
- The runner can use only LangBot resources authorized for the current run.
- Availability, model abilities, and rate limits depend on the external service.
- See the full Chinese README at the package root for advanced behavior and product-specific limitations.

## Structured interactions

The runner registers a real Codex app-server dynamic tool named
`ask_user_question` and also accepts Codex's native
`item/tool/requestUserInput` request. Both are converted to LangBot's
provider-neutral `interaction.requested` contract, so Lark, DingTalk, and other
delivery adapters can render the same fields and actions.

The app-server process is stopped while the user is answering. The submission
starts a new AgentRun and resumes the same Codex thread. Codex app-server does
not support replying to an old JSON-RPC tool request from a new process, so the
answer is delivered as the next authoritative user turn rather than injected
as the old tool result. This is a provider transport limitation; the interaction
is still a real model tool call and no process is kept waiting.

Codex app-server command-execution and file-change approval requests are also
converted to action-only confirmation cards. The previous turn is cancelled
while the user decides. Approval resumes the same thread and grants exactly one
matching retry; a different command or file change requires a new approval.


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

Codex retains authentication and resume files in the installation's own
`$HOME/.codex` (or explicitly configured `CODEX_HOME`). Per-run MCP configuration
remains separate; persisted sessions/auth intentionally remain available across
turns. Concurrent writes to the same resumed session are serialized by a
POSIX file lock in its shared sessions directory. Different accounts/session IDs
remain independent. This is continuity within an installation, not a claim that
Agent configurations sharing an external account are separate security tenants.
