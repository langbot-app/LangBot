# LANG-17 post-merge integration

## Fixed inputs and scope

Core base: `7974a430680f813eae58e60d85c58ef935a144f3` (PR #2706 merge).
Plugins base: `31a05080b58f2cda8b1acecee668b2cda5503c4b`.
SDK base: `7ac774f72eadb104ffb2d5b0c2c7850b667f65ed` (published version 0.7.13).
All three integration branches are `agent/langbot-local-qa/602fe0ce0551`.
The previous core branch at `3794a7ee` has a separate preserved worktree;
the pre-merge migration stash and LANG-16 branches remain intact.

This is a local integration combination, not a released distribution. The SDK
package still reports 0.7.13 after a local build, so the Git revision and patched
manager file hash must accompany that version. The core dependency lock still
points at the published SDK; deployment through that lock alone omits this SDK fix.
No new PR, merge, release, deployment, or default-branch write is performed.

## Reconciliation against LANG-16

| Earlier change | Merge/upstream disposition | Integration action |
| --- | --- | --- |
| Core catch-all group gating (`e212f9ea`) | Covered differently: upstream checks ordinary routed group messages at the response stage, including explicit filters; interaction/Dify callback exceptions remain | Preserve upstream policy; do not restore the old filtered-binding bypass |
| Core busy-session steering gate / stable random draw (`e212f9ea`) | Absent; new tests reproduce unrelated input being claimed and prefixes not being stripped | Port only controller/random changes; preserve original queued message via a copy |
| Original monitoring row on stage exception (`e212f9ea`) | Absent; direct failure test shows no status update before error-detail failure | Port the original-row error transition before optional detail recording |
| Groq outbound metadata (`fefe4d85`) | Upstream independently covers message, tool-call and function envelopes, separated from reasoning sanitization | No port; rerun requester regressions |
| Migration install diagnostics (`079e945b`) | Absent | Port allowlisted error kind/HTTP status, UI translations, MCP and skill documentation together |
| LocalAgent lazy Box (`f33146a0`) | Absent from current plugins master | Port lock-protected attachment/tool preparation and tests; no ordinary-answer acquisition |
| SDK no-listener event admission (`11b52589`) | Absent from SDK 0.7.13/current master | Port component-kind admission and subscriber-contract tests; retain ordered listener dispatch |
| Old LANG-17 missing-table migration patch | Consolidated 0039 already skips absent tables | Do not apply the old 0039/0040 patch |
| Missing columns in partial historical tables | Still fails in consolidated 0039: all eight new cases fail before repair | Check available columns before creating each index; preserve data and unrelated indexes |
| Historical inline TTL / reference-only writes / CAS | Upstream additions, not earlier task fixes | Keep implementation; verify cleanup, cursor, ownership, failure/rollback and read paths |
| SQLite 3.53 flattened expiry query plan | Previous task test adjustment still necessary | Retain indexed owner lookup assertions for flattened EXISTS plans |

## Automated regression

- Core migration/storage/response/install group: **176 passed** (includes SQLite
  fresh/baseline/upgrade paths and eight new partial-schema tests).
- Core controller, queue, error handling and LiteLLM requester group: **153 passed**.
- Response rules, pending interaction migration and migration runtime group:
  **73 passed**. Some tests overlap the preceding groups; totals are not unique.
- Real PostgreSQL 16 + pgvector: **49 passed**, including 28 media contracts,
  13 migration/runtime tests, and eight partial-schema cases. Each run uses one
  owned, resource-limited container. The first image lacked pgvector (35 passed,
  six environment failures); it was removed and replaced, not counted as success.
- SDK manager: before **7 failed / 61 passed**, after **68 passed**.
- LocalAgent Box/shared tests: before **2 failed / 32 passed**; current full
  LocalAgent suite **270 passed**, excluding the obsolete exact-version release
  assertion in `test_shared_release.py`. This is not a full plugin release gate.
- TypeScript typecheck and production build pass. Ruff and whitespace checks pass.

Missing-column tests deliberately construct partial schemas; they prove migration
tolerance, not that every such schema is a supported complete application schema.
The migration does not fabricate missing business columns or recover missing data.

## Actual services and operations

All probes start real Core, WebSocket RT, plugin workers and frontend in task-owned
directories. Ports: 16399, 16400/16401, 14000, 13280/13281 and optional model fixture
16420. Runtime config, SQLite, plugins, cache, logs and tokens are isolated. Box is
disabled and DOCKER_HOST points at a nonexistent task socket. No real QQ traffic.
The supervisor enforces 2 GiB aggregate RSS and five consecutive >200% CPU samples,
records processes, and cleans only owned PIDs after checking the Multica daemon PID.

- `live-20261018-163651`: ordinary/other-mention/unrelated burst ignored; keyword,
  bot mention, private and image controls respond. Busy Runner consumes the keyword
  follow-up but not ordinary group chatter. Image response and real browser monitoring page pass; CAS read/write
  behavior is covered separately by storage regressions. Database has 38 successful + two failed user records,
  five successful assistant records, five completed + two failed runs, and no
  nonhistorical pending/running rows. All owned processes stopped.
- `live-20261018-163855`: deliberately invalid response-rule configuration raises
  a stage exception. Original user row is error, optional error detail is recorded;
  two positive controls still succeed. No nonhistorical pending rows remain.
- `live-20261018-164140`: real current LocalAgent package with `box-enabled=true`
  and `exec` allowed, while Core Box is disabled. Unrelated message makes no model
  call; ordinary answer succeeds via a loopback OpenAI streaming protocol fixture.
  This verifies lazy acquisition for plain answers, not a real LLM or sandbox tool.
- `live-20261018-164300`: copy of the task's actual v4.10.10 seed database boots
  through 0039; original account authenticates, bot and legacy pipeline survive,
  and migration preview remains available. Original seed is unchanged. The first
  probe mistakenly queried `pipelines` instead of `legacy_pipelines`; corrected
  probe passed. This does not claim real Dify/DeerFlow backend conversion coverage.

The 64 deliberately seeded raw historical pending rows remain historical. In-flight
SSE excludes them, but dashboard aggregate still counts raw status. Changing that
user-visible statistic awaits the separately identified product decision; it does
not block independent fixes or tests above.

## Reproduction and evidence boundaries

The `tests/manual/lang17_*` probes are reusable and bounded. `lang17_live.py` runs
the ordinary ingress test by default; LANG17_FAULT=1 selects the stage-failure case,
LANG17_LOCALAGENT=1 selects the loopback-model LocalAgent case, and LANG17_SEED_DB
plus LANG17_UPGRADE_ACCOUNT selects a copy of a task-owned old installation.
Never point these at a real user's data or credentials. Build LocalAgent's package
from the integration plugins checkout into the task evidence directory first.

Synthetic model/protocol tests are identified explicitly. Real Groq remains deferred.
Process-scoped mainland egress, actual Dify/interaction provider setup and securely
supplied real-model credentials are not available in this run. Box isolation was
subsequently provisioned as documented below; shared Docker is never sufficient. No claim of
overnight model/history leak freedom, mainland network success, or complete nine-item
LANG-16 acceptance follows from the bounded tests here.

## Bounded multi-plugin load

Same integration Core with published SDK 0.7.13 versus the locally patched SDK:
healthy reply after another plugin's blocking Runner improved from 3.162 s to
0.389 s (control input was sent at +0.3 s). RAISE/TIMEOUT/EXIT controls stayed around
0.39–0.41 s. This comparison targets the no-listener RPC stall, not whole-system
throughput or all listener failures.

Patched combination ran 749.9 s, including 60 ten-second soak rounds and recovery,
with 3,232 synthetic inputs. Final queue/cache/workspace counts were zero; all owned
processes stopped. Peak RSS: Core 609.20 MiB, RT 72.95 MiB, combined RT children
185.83 MiB, production-preview frontend 122.75 MiB. Sampled average CPU: Core
28.33%, RT 1.44%, RT children 0.46%, frontend 0.05%. These averages include startup,
faults and load; the 70.85 s baseline has different duration/load and is not a
valid CPU percentage improvement comparison. Plugin-list API max was 24 ms.

The 160-message burst produced 100 inbound monitoring records. QueryPool's existing
100-per-Workspace cap discards queued oldest work under overload; the 60-record
difference is consistent with that policy. There is no per-rejection log to prove
each individual discarded input. Do not describe all 3,232 inputs as successful
replies. The 3,000 unrelated messages and 60 soak controls are separately present.
Final persisted states: user success 3,168 / error 4; assistant success 168 / error 1.
No pending monitoring rows remain at recovery. This load has no real LLM history.

## Box isolation and an additional wrapper regression

Created task machine `lang17-qa-602fe0ce` with OrbStack isolated mode, networking
isolation, no SSH-agent forwarding, 1 GiB memory / 1 CPU / 3 GiB disk, and exactly
one selective mount: this task's Box directory. Installed a new Docker daemon;
its ID differs from the existing daemon and its initial container inventory was
empty. A task-only `docker` wrapper pins every SDK Docker CLI call to that machine
and its explicit Unix socket. Existing host Docker is not used by Box.

Alpine initially did not enable delegated cgroup controllers; the first resource-
limited container failed on missing `pids.max`. Moved only this machine's init
processes into a child cgroup, enabled cpu/memory/pids controllers, and restarted
only its newly installed Docker service. A bounded Docker smoke command passed.
No host cgroup, Docker configuration or existing service was changed.

`live-20261018-170317`: real LocalAgent + Core + RT + Box, loopback model protocol.
Unrelated input -> 0 sessions, plain answer -> 0 sessions, exec tool -> 1 session.
The model fixture receives actual `LANG17_TOOL_OK` stdout from the container. Box
health is live. Container sample: 1.078 MiB RSS of a 512 MiB limit, 2 PIDs, 0.00%
CPU at sampling; this is an idle sample, not peak container usage.

This run also exposed a pre-existing wrapper outbox scan on ordinary replies,
contrary to the documented explicit attachment contract. Removed that implicit
RPC/scan and preserved explicit file-only Message/MessageChunk output. Six new
regressions fail before repair (four unexpected scans, two missing file-only
outputs); all 27 wrapper tests pass afterward. Final real Box rerun is recorded
in the attached run summary. No implicit outbox discovery is promised.

Final Box rerun `live-20261018-170523` passes with session counts 0/0/1, real
container stdout, healthy Box, no implicit collection warning, and no surviving
Core/RT/Box/frontend/probe processes. Shared Docker container IDs are unchanged.
The task-owned isolated machine is stopped (not a persistent service handoff);
its bounded disk is retained for audit. No daemon/container cleanup crossed into
the shared engine. The initial cgroup failure is excluded from acceptance.

## Installation failure paths

`live-20261018-170848` exercises both actual migration-install and extension-install
APIs against a loopback marketplace fault server. HTTP 503, disconnect, truncated
body, timeout and offline cases all terminate (10/10). Timeout takes about 15.2 s;
other cases take about 0.02–1.04 s. All five migration results contain allowlisted
diagnostics, preserving the failure reason without raw request secrets. These are
fault simulations, not China-mainland network tests.

The first EventListener matrix mixed LBLOCK with a Runner substring match for
BLOCK, causing two intentional stalls. It is retained as exploratory evidence;
the corrected fixture matches Runner fault tokens exactly and is rerun separately.
Subscriber-order and prevent-postorder controls passed in that initial run.

Actual public-marketplace migration install `live-20261018-171007`: downloaded
and initialized LocalAgent 0.2.1, task completed in 7.11 s, and the synthetic
4.10.10 pipeline reported migrated. This checks current Core/RT installation,
not whether that published plugin includes this task's lazy-Box source patch.

Actual extension marketplace install `live-20261018-171058` also succeeds. Both
success paths use fresh task data and the real public marketplace; no existing
user installation is reused. See the sanitized installation summary for timing.

## Source checkpoint caveat

The probes were run on the fixed merge checkout with an uncommitted task diff,
so their raw metrics record the merge SHA. Core implementation during the long
load corresponds to checkpoint `709e5e7a` (reconstructed and committed afterward).
The final commit additionally removes wrapper scans and fixes file-only output;
that change has its own 27-test and real Box/installation regressions. The long
load was not repeated after that small wrapper change. Exact final three-repo
SHAs and installed-code hashes accompany the evidence manifest.

Corrected listener matrix `live-20261018-171152` passes subscription mutation order
and prevent-postorder controls. Healthy response latency is 3.156 s for LBLOCK
(listener-only fault) and 3.161 s for BLOCK in a plugin that also has listeners;
RAISE/TIMEOUT/EXIT controls are about 0.39–0.41 s. Thus skipping no-listener workers
does not isolate a synchronous blocking EventListener. Queues recover to zero,
with no owned process survivors. Changing listener failure/timeout propagation
requires a separate contract decision; no parallel dispatch was introduced.

At long-load recovery, Core retains 200 completed + 9 running task wrappers and
two RT worker children; Core RSS is 565.36 MiB versus 540.44 MiB before plugin
installation. The health field `id_index=3189` is a monotonically increasing ID
counter, not a collection of retained tasks. This is not evidence of 3,189 live
tasks or an overnight memory-leak diagnosis.

## Outstanding acceptance inputs

- Real model credentials through a secure mechanism for growing-history/image
  workloads; the loopback model test is not a substitute. Real Groq stays deferred.
- A process-scoped mainland exit without changing the user's VPN/routing.
- A real Dify/interactive callback test environment. Callback unit/contracts pass,
  but live third-party callback acceptance is not claimed.
- Product decision on raw historical Running totals versus effective leases;
  preserve current behavior until decided. Blocking EventListener behavior remains
  an explicit serial-contract limit, not a claim of complete fault isolation.

All independently executable work in this integration pass is delivered. These
gaps remain on LANG-16's nine-item acceptance ledger; neither the merged PR nor
this task-branch push constitutes complete project acceptance.
