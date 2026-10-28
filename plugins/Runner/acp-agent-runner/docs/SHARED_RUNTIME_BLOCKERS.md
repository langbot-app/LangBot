# Coding Runners: shared-runtime release BLOCKED on SDK 0.6.0b5

This is a dependency design and reproducible **RED gate**, not an implementation or certification. It applies to ACPAgentRunner 0.1.12, ClaudeCodeAgent 0.1.10 and CodexAgent 0.1.16. No supported mode was removed, no version/dependency/declaration was changed, and no new package should be signed from this work.

## Provenance and exercised boundaries

- Plugin base: canonical `langbot-app/langbot-plugins` main `bacb88696dc9b41f65857c35c9d6bd431d4924b5`.
- SDK: installed genuine `langbot-plugin==0.6.0b5`; all 245 SHA-256-bearing distribution RECORD entries verified. SDK/Core source was not modified.
- Host inspected: exact public Core `e897c575e048941f68593f61e53f4b451668a1d5`, resolved from the parent release's `core-merge.json` (the compact handoff concatenated its short SHA and version). Initial `e897c5754` lookup returned 422; no conclusion was based on that nonexistent revision.
- New dedicated test: `Runner/certification-tests/test_coding_runner_shared_blockers.py`. Real SDK imports, real loopback WebSocket hub/daemon exchange, real disposable ACP child process and real Codex filesystem preparation. No live daemon, SSH target, vendor model, account or secret is used.
- Historical exact archives are loaded by `PluginArtifactStore.install_package` and checked by `PluginDependencyEnvironmentStore.prepare`, not just a requirements-string comparison. All packaged Python and requirements bytes are compared with the source under review before admission.
- These tests deliberately combine conflicting configurations in one interpreter. They demonstrate unsafe reusable library/plugin behavior; **they do not demonstrate cross-tenant access in a deployed installation-isolated worker**. Process isolation alone is not a substitute for supported Host authority over native paths and execution.

| Exact historical archive | SHA-256 | b5 admission |
|---|---|---|
| ACPAgentRunner 0.1.12 | `39dad83666eb27e6b7e2d0f6e28a05bdcc8a53accf517eddb4748a256ba3631a` | rejected: pins b3 |
| ClaudeCodeAgent 0.1.10 | `269c2ed34436234d21a94b7faf234a76ddc40310ad78f518eeaf3873c812a15c` | rejected: pins b3 |
| CodexAgent 0.1.16 | `7aa4721b9b3104b330de23e52b89a45b382498768406c83cb33d13a9fd6469f9` | rejected: pins b3 |

## Reproduced blockers

1. **All three daemon paths route configuration B through A's connection.** Start the genuine SDK hub with synthetic token A, connect a daemon, then call each real Runner's `_run_daemon` with token B, another port and the same daemon display ID. The authenticated A socket receives B's `run.start` and prompt/workspace payload. Each Runner skips `hub.start()` once `hub.is_running`, bypassing its existing conflict check. A positive control proves calling `start()` with B would reject. Merely adding that call fails closed on conflict but cannot supply installation ownership or a usable shared listener.
2. **SDK daemon event ownership is absent.** Through two genuine WebSockets authenticated to the hub, daemon B can emit a completed event for A's known job ID; A's iterator accepts it. `api/agent_tools/daemon.py:389-461` discards sender identity for run events/finish and does not compare MCP request sender to job owner. This probe establishes event injection given a known job ID, not discovery of random job IDs or a deployed exploit.
3. **Cancellation has no remote quiescence acknowledgement.** Cancelling a job causes the hub to forget it, then send best-effort `run.cleanup`; an intentionally uncooperative daemon need not stop. No acknowledgement, lease tombstone or quarantine exists. The test does not claim every standard daemon ignores cancellation; it proves the Host cannot certify remote completion from the local cancellation result.
4. **Codex's unique run directory is not isolation.** `_prepare_local_codex_home` creates distinct A/B directories but links/copies worker `CODEX_HOME/auth.json` and the same `sessions` tree into both. The test reads synthetic foreign credentials/session files through B's run home. No real home is inspected.
5. **ACP inherits worker environment and accepts local cwd without Host authority.** Its real `AcpStdioClient` launches a disposable Python child with `env={}`; the child receives a synthetic worker-only secret and runs in the configured temporary cwd. Claude and Codex have the same `env = {**os.environ, **config['env']}` local/SSH launcher pattern (static evidence: `pkg/native_cli.py:628` and `:924`). Their full native launchers are not dynamically exercised by this probe.
6. **All exact old packages fail b5 dependency admission.** None reaches the installer. A version/pin/declaration-only change would hide this admission failure without fixing authority.

Default test result: **2 controls pass, 10 safety/admission assertions strict-XFAIL**. Enforcing mode: **2 pass, 10 fail**, exit 1. This is a blocked release, not a 12-test certification PASS. SDK Pydantic deprecation warnings are separate from the failures. The initial evidence also retains one corrected test-harness typo (`invoke_tool` versus genuine `call_tool`).

## Actual b5/Host capability boundary

`Runner.get_run_api(ctx)` creates an invocation-bound `RunnerAPIProxy`. The public API provides scoped `get_box_status`, `list_boxes`, `acquire_box`, `bind_box`, attachment import/export, and ordinary `call_tool`; **there is no public duplex process start/stdin/stdout/wait/stop API or daemon registry/lease API**. `ctx.api` exists during `Runner.invoke`; `ctx.get_run_api` is not the b5 interface.

Core's exact `pkg/plugin/box_actions.py` validates the run session/caller and Box capability through authenticated action context. This is the boundary to extend, not a tenant name in Runner configuration. `pkg/box/runner.py:142-158` permits only the `image` option; plugins cannot supply mounts, resource policy or execution identity. Binding checks Workspace membership and prevents switching an already-bound run.

Although lower-level Box managed-process primitives exist, they are not exposed through the Runner proxy. On the exact release, `pkg/box/service.py:559-561` explicitly rejects Cloud managed processes; `:522-555` enforces network off, and `pkg/box/admission.py` enforces zero managed-process allowance. A one-shot `exec` tool is not an ACP/Codex duplex transport. Using hidden Box credentials, unmanaged background processes, repeated file polling to evade the managed-process gate, or local subprocess fallback would violate those contracts. Network-off also prevents normal provider authentication/model access and ACP npx adapter downloads.

## Minimal dependency change for parent approval (proposed, not shipped)

### 1. Host-owned execution targets and run leases

Add a small execution broker at the authenticated Host boundary. Register `target_ref` records through a supported owner/admin management API, never from arbitrary Runner config. A record binds a backend (`box`, `ssh`, `daemon`), Workspace/installation access policy, credential reference, workspace root, executable/network policy and generation. Derive the effective Workspace, installation, installed artifact and active run from existing authenticated action context + run ledger; callers must not supply authoritative tenant strings.

Expose these **new** run-scoped SDK operations (names are a proposal, not b5 APIs):

| Operation | Request additions beyond implicit `run_id` | Response/contract |
|---|---|---|
| `open_run_process` | idempotent `request_id`, granted `target_ref`, argv, relative cwd, explicit env overrides, optional opaque resume handle | opaque process handle, generation and bounded I/O limits; reconcile the request ID if caller disconnects before receiving the handle |
| `write_run_process` | handle, sequence, bounded bytes, EOF flag | idempotent accepted sequence, explicit backpressure |
| `read_run_process` | handle, cursor, byte cap, bounded wait | sequenced stdout/stderr bytes, next cursor, exit state; bounded buffers and no lost event on retry |
| `get_run_process` | handle or open request ID | authoritative lifecycle state, generation, exit status and cleanup/fence status |
| `close_run_process` | handle or open request ID, reason | stop process group, drain/revoke resources, acknowledge quiescence; ambiguity retains a fenced tombstone rather than reporting safe stop |

Capability discovery may use existing Host-generated available-API metadata; absence must fail before any listener, file write or subprocess. Every operation revalidates active run, installation generation and handle ownership. State must survive or be explicitly invalidated on broker restart/reconcile/uninstall. Process handles cannot be used as resumable conversation IDs; resume handles are separately scoped to installation, target generation and conversation. Cross-run continuation requires Host validation, not a raw vendor session ID.

### 2. Box backend and policy prerequisite

Implement the broker against Box-owned process supervision, not the plugin worker filesystem. Do not expose a Box control token/socket URL to plugins. Map `location=local` explicitly to a managed coding target with a documented migration: paths are inside its authorized workspace, not arbitrary Host absolute paths. Keep dedicated behavior unchanged; unsupported old shared configuration gets an explicit migration error, never silent mode removal.

The coding profile needs an approved scoped managed-process quota and restricted provider/registry egress or preinstalled pinned CLI/adapters plus a model proxy. Do not silently turn on general Cloud network access or lift the existing global sandbox policy. Workspace storage, HOME, XDG caches, CLI credentials and sessions must be provisioned within the authorized target scope. Environment starts from an allowlist; no worker `os.environ`, SSH agent, Docker socket or shared Codex home inheritance. Validate symlinks/path traversal and reserve CLI credential/cache paths from env overrides. Preserve per-conversation resume with Host-scoped storage and explicit concurrent-write control.

### 3. SSH and daemon backends

Preserve both modes via the same broker. SSH `target_ref` resolves an approved hostname, host-key policy, secret reference and remote root; run config cannot choose arbitrary hosts/key files or bypass allowlists through extra SSH arguments. Give the remote supervisor the same process-group stop acknowledgement/lease requirements.

Daemon listeners belong to the trusted broker/operator, not plugin initialization or a process-global SDK key. Enrollment credentials bind installation/target identity; hello-supplied display IDs and tenant strings carry no authority. Bind each connection incarnation and each job to that identity. Validate event, finish, MCP and cancel-ack sender against **job owner + incarnation + generation**. Key all queues/locks by trusted owner and opaque job handle. A known job ID alone must never authorize delivery or tools. Empty tokens are forbidden for shared daemon targets.

Extend the daemon protocol with bounded queues/output/frame sizes, sequenced frames, cancellation acknowledgement, heartbeat/lease expiry and reconnect reconciliation. Revoke MCP/asset capabilities before returning completion. If the daemon disconnects or cannot prove stop, fence that target and retain unresolved job state; do not route another run into the same mutable session. This is more than renaming `_global_hubs` keys.

### 4. Runner refactor after dependencies ship

Keep protocol parsing, streaming, approval prompts, steering, multimodal input and conversation state behavior. Replace local/SSH stdio and daemon launch transport with the above invocation-bound handle. Read the effective installation configuration through a trusted invocation snapshot; do not use process-environment fallback or cached global configuration as authority. Route LangBot tools through the existing per-invocation API; Host-managed MCP/asset leases must close only the owning run and avoid worker-global listener settings.

First release the SDK/Host/broker contract and approved policy; then implement all three Runner transports. Do not label a package shared-safe if only daemon mode works while local/SSH silently disappear. If explicitly choosing a supported subset later, that is a separately approved product/migration decision, not this repair's completion.

## Required GREEN and package gates

1. Run the present assertions unmarked, preserving the historical RED results. Add two-owner same-worker real SDK RPC tests with colliding display/session IDs, conflicting credentials/config, cross-generation handles and hostile daemon event/MCP injection.
2. Exercise actual Box broker process I/O and approved network behavior, not just a Host mock. Test local/SSH/daemon modes, model sessions, continuation, approval, tool access and file import/export parity.
3. Cancel before start acknowledgement, during input/output and during repeated cancellation; prove process-group exit or durable fencing. Cover daemon disconnect/replacement, lease expiry, burst output bounds, worker/Host restart and uninstall. Assert B remains usable when A cancels and no token/session/workspace is shared accidentally.
4. Only after dependencies and behavior pass, bump the then-current versions, pin the real released SDK, add the shared declaration, and build official `lbp` archives outside the repository from a committed snapshot. No new archive is appropriate on b5 alone.
5. Validate exact archive dependency preparation and cache readback without shadow SDK installation, packaged discovery/RPC, independent exact-digest review, normal signing and scoped two-Workspace acceptance. Existing unsigned b3 archives remain rejected; no force install or manifest-only certification.

## Reproduce locally

Use a read-only b5 interpreter with pytest/pytest-asyncio, separately from legacy SDK-stub suites:

```bash
export CODING_RUNNER_RELEASE_DIR=/path/to/retained/runner-release/packages
# Known-blocker inventory, not approval:
$B5_PYTHON -m pytest Runner/certification-tests/test_coding_runner_shared_blockers.py -q
# Actual RED release gate (expected exit 1 until dependencies/implementations exist):
CODING_RUNNER_ENFORCE_SHARED_SAFETY=1 $B5_PYTHON -m pytest \
  Runner/certification-tests/test_coding_runner_shared_blockers.py -q
```

If archives are not supplied, the three exact-archive tests skip explicitly; that run cannot establish package admission. Local run evidence includes JUnit/logs, SDK RECORD verification, exact public Host source and archive hashes under `/home/rock/work/coding-runners-shared-evidence/`. No publication, approval, signing, live accounts, SDK/Core edits or aggregate CI/lock changes were performed.
