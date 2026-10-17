# LANG-16: release 4.11 local QA

This report separates reproduced defects from unverified user reports. A bounded local run does not
rule out an overnight leak or establish the reporter's exact network failure.

## Revisions, authorization and isolation

- Upgrade source: v4.10.10, `a63808caa6f10bc11f711373cabc11ffb6519b00`, SDK 0.5.7.
- Target/before baseline: official v4.11.0, `502b38130f9878b405498b93e4203593573eb19b`, SDK 0.7.11.
- Core task branch: `qa/lang-16-v4.11.0`. This document accompanies the tested core changes.
- LocalAgent task branch: `agent/langbot-local-qa/7acb7953fc8d`, fix commit
  `f33146a0c263f643d1bba803c640af2ac7906f46` in `langbot-app/langbot-plugins`.
- SDK task branch: `qa/lang-16-sdk-0.7.11`, fix `11b525892fb0d4ea8b478958ebab717e90fe462a`
  in `langbot-app/langbot-plugin-sdk`, based on v0.7.11 `e10d8385b2843a25e30219f9153f3227c8a0009f`.
  Code is pushed; no SDK package or LocalAgent marketplace release has occurred.
- macOS 27.0 arm64, 36 GiB RAM, Python 3.12.14, Node 26.10.0, pnpm 8.9.2.
- Dedicated task worktrees; existing core/RT/Box/frontend on 5399, 5400/5401, 5410, 3000 were left alone.
- Test core 15399, RT 15400/15401, Box 15410, Vite 13000, OneBot peers 12280/12281,
  synthetic marketplace 15420. Every startup uses new data/config/plugin/cache/log directories.
- Only synthetic OneBot peers, never real QQ destinations. Live model tests use the member-authorized
  gateway with deepseek-chat and 128 output tokens; secrets entered through getpass, never committed.
  The credential database/journals were deleted after testing. Raw config/log files are not deliverables.
- Single concurrent stack, two-second sampling, 2 GiB total owned RSS stop limit (3 GiB for browser tests),
  CPU >200% for five samples stops a run; duration hard cap 900 seconds. 100% CPU means one logical core.
  A deliberately blocking plugin is bounded to three seconds. No unbounded deadlock injection.
- Cleanup records owned process identities, checks the Multica daemon PID and verifies survivors.
  Docker cleanup is restricted to containers with mounts below the freshly created probe directory.
- Updated authorization permits commits/pushes to task branches. No external PR, merge or deployment.

## 1–2. Migration installation and diagnostics

Both real marketplace paths installed LocalAgent 0.2.1 successfully on this Mac:
`baseline-20261017-152549` migration (12.13 s) and `152708` extensions (11.11 s), 866380-byte package.
They share the downloader, proxy-aware HTTP client and 15-second timeout. Migration prefers pinned
0.2.1 and may fall back to latest when absent; extension installation can request latest or pinned.
The reported path discrepancy did not reproduce. A progress screenshot alone does not prove success.

`baseline-20261017-193519` uses real core APIs/downloader against a synthetic loopback HTTP server,
with NO_PROXY for localhost to avoid the host proxy changing disconnects into 502 responses:

| Injected condition | Migration diagnostic | Migration / extension completion |
| --- | --- | --- |
| HTTP 503 | http_status, HTTP 503 | 1.07 / 1.02 s |
| Peer closes without response | incomplete_response | 1.02 / 1.03 s |
| Truncated body, 18/9999 bytes | incomplete_response | 1.04 / 1.03 s |
| 17-second silent response | read_timeout | 15.19 / 15.19 s |
| Listener offline/refused connection | connect_error | 1.04 / 0.02 s |

All ten tasks reached done; migration pipelines stayed blocked with categorized errors. The new task
metadata allowlists diagnostic kind and HTTP status, excluding exception text, URLs, headers and bodies.
Unit cases deliberately embed fake credentials to verify they cannot leak through the new field.
This does not change download retries/timeouts or claim all existing extension error text is sanitized.

`baseline-20261017-193742`: real Edge browser, first-run wizard skipped, migration reviewed, automatic
installation attempted, failure details expanded. Visible `Network diagnostic: http_status · HTTP 503`,
0 migrated/1 needs attention, no page errors; screenshot visually inspected. Locale label added for all
existing migration locales. MCP remains curated and exposes no migration tool; HTTP/task schema documented.

These are synthetic network faults, not verified mainland-China direct-network measurements. The Mac's
actual marketplace route succeeded. A separate proxy-disabled HTTPS trace returned loc=JP and the
route used utun4 (tunnel), so this host still cannot establish mainland direct-network behavior.
No VPN/system proxy setting was changed. Exact user proxy/DNS/network conditions remain unknown.

## 3. Unrelated ingress and eager Box creation: two independent defects

4.10.10 default pipeline resolution used routed_by_rule=False. Migration creates a catch-all binding
with empty filters; 4.11 incorrectly marked every binding explicitly routed, bypassing group response
rules. `botmgr.py` now marks only bindings with filters as explicitly routed. Explicit filtered routes
retain their legacy override behavior. Empty-filter bindings now obey configured group response rules.

- Before `baseline-20261017-151907`: unmentioned ordinary chat reached the handler.
- After `152221`: ordinary chat, @another user and 30 unrelated burst messages filtered; keyword,
  @bot and private controls entered chat. All 35 inbound rows terminal, query cached/queued zero.
- `153000`: real marketplace LocalAgent with no authorized model; 32 unrelated inputs filtered,
  three positive controls failed with the expected model-selection error; no pending rows remained.

Busy-session steering happens before the normal stage chain. Controller now runs the same response gate
on a copied message before offering it to the active Runner. Failed claims preserve the original chain.
Random admission draws are cached per query so queue rechecks cannot increase admission probability.
These steering details have automated coverage; successful live steering acceptance is not claimed.

Separate LocalAgent defect: preparing Box whenever sandbox tools were enabled created a sandbox for a
plain answer even when no tool ran. The plugin now prepares eagerly only for incoming attachments;
sandbox call_tool acquires lazily under a lock. Non-sandbox tools delegate without acquisition. A tool
result carries sandbox_outbox so the model can discover the lazy-created delivery directory.

Real model + Docker + OneBot comparison (same prompts, gateway/model):

| Run | Before input | Unrelated chat | Plain QA_OK, no tools | Actual exec |
| --- | ---: | ---: | ---: | ---: |
| Before, `154144`, marketplace 0.2.1 | 0 | 0 | 1 | 1 |
| After, `192121`, task-built package | 0 | 0 | 0 | 1 |

Numbers are Box session counts. The tool executed `printf LANG16_TOOL_OK` successfully; messages ended
success and queue/cache returned to zero. Sandbox limits: 1 CPU, 512 MiB, 128 PIDs, read-only rootfs,
mount under task directory. Owned processes/container were removed. Marketplace and repository sources
have other differences, so this is a behavior comparison, not a throughput claim. Attachment import,
scoped export and concurrent acquisition are regression-tested; the live prompts had no attachments.

## Real 4.10.10 database upgrade

`baseline-20261017-193212` started actual 4.10.10 in its locked SDK environment, initialized a synthetic
account, pipeline and disabled OneBot bot, then stopped cleanly. `193444` copied its database AND instance
identity into a new 4.11 data directory. Alembic moved from `0021_merge_reasoning_config` to
`0037_metadata_text`; real migration downloaded/activated LocalAgent and migrated the pipeline.
The original default bot binding became message.received with filters=[]. Enabling the bot and sending
ordinary chat filtered it; @bot reached Runner and failed only because this test intentionally had no
model. Both inbound records were terminal. This is synthetic old data, not the reporter's database.
An initial DB-only copy (`193241`) correctly failed the instance identity guard and is excluded.

## 4. Runtime/plugin fault isolation

`baseline-20261017-152407`: terminate only owned RT at 20 s, restart at 27 s. Core health stayed 200;
RT-connected false at 22.98–27.13 s, true by 29.22 s; reconnect delays 1/2/4 seconds.

The extended matrix uses real installed synthetic SDK Runner packages in dedicated worker processes:
handler RuntimeError, bounded timeout, three-second busy loop, OneBot disconnect/reconnect, os._exit(17),
initialization exception and invalid dependency specification. A separate healthy plugin receives control
messages and GET /plugins is timed at each stage. No cloud model is used in this fault/load fixture.
This does not establish fault isolation for certified shared-runtime pools or arbitrary user plugins.

The baseline does show cross-plugin latency coupling: healthy controls after RAISE/TIMEOUT/EXIT arrived
about 0.40 s after fault initiation (sent at +0.30 s), but BLOCK's healthy response arrived at +3.169 s.
Core/RT health stayed responsive. SDK 0.7.11 `runtime/plugin/mgr.py:3166` serially emits the event to
every initialized plugin in scope without first excluding plugins with no EventListener components;
Core `plugin/connector.py:2344` serially visits installation bindings. Both QA plugins declare only a
Runner, so the unrelated worker's event RPC waits behind its busy event loop. This is latency coupling,
not a reproduced whole-RT crash. The initial repository-registration blocker was removed by Mika;
the SDK is now fixed in its task worktree and pushed (see below).

Causal configuration control `baseline-20261017-200408`: disable enable_all_plugins and bind each
pipeline only to its required QA plugin. The same BLOCK control arrived at +0.393 s, versus +3.191 s
with all plugins enabled; other controls were +0.428–0.448 s. Both database and monitoring executions
API showed zero running queries at all post-fault checkpoints. This is a verified temporary workaround
when a pipeline does not need the other plugins, not a replacement for an SDK fix. No existing user
pipeline configuration was changed.

## SDK root fix and real subscriber contract follow-up

SDK `11b52589` skips workers whose initialized component list contains no EventListener. The list is
refreshed from the worker after initialization; this is not a pipeline-binding workaround. Existing
scope/enabled/status/connection filters, serial context mutation, response provenance, trusted query
identity and prevent_postorder handling remain intact. Event-type subscriptions remain worker-local:
a plugin with an EventListener may still receive an event it does not subscribe to. No parallel
broadcast, event schema change, exception swallowing or package version change was introduced.

Seven new no-listener regression cases fail on unmodified v0.7.11 and pass with the fix. The focused
manager/worker/control-handler regression suite passes **473 tests, 5 skipped, 11 warnings**. Skips are
two unavailable exact plugin archives, Linux shared-worker/nsjail tests and platform-specific launcher
cases. An existing synchronous component-list test used asyncio.run inside a suite managed by
pytest-asyncio, orphaning a loop (also reproduced on unmodified SDK). It now uses async/await under
pytest's lifecycle. No warning filters were relaxed; final stderr is empty. Ruff and diff checks pass.

All new real runs use core behavior at `8ffd38c6` (this follow-up changes only QA scripts/docs), real
RT/Box/frontend and two separately installed synthetic plugins, with enable_all_plugins=True. Before
uses the preserved PyPI SDK 0.7.11 environment. After uses a new task-only venv populated from the same
frozen dependencies, then `uv pip install --python <task-venv>/bin/python --no-deps ./langbot-plugin-sdk`.
The SDK wheel is built from the task worktree, not a patch to installed site-packages. Core, RT, Box
and their plugin workers use that interpreter. LANG16_CORE_PYTHON selects it; no uv sync replaces it.
Existing user environments and both earlier repository results are preserved. LocalAgent remains
`f33146a0` / task-built 0.2.1; its real model/Box acceptance above used SDK 0.7.11 before this SDK change.
The SDK fault fixture uses QA plugins, not LocalAgent or a model; a new three-way live LLM run is not
claimed. Production adoption requires a coordinated dependency/package update, which is not published here.

| Real run | No-listener RAISE / TIMEOUT / BLOCK / EXIT healthy reply after fault start |
| --- | --- |
| Before `201631` (43.59 s) | 0.413 / 0.399 / **3.177** / 0.409 s |
| After `201723` (60.31 s including startup) | 0.424 / 0.390 / **0.393** / 0.412 s |

Controls are sent at +0.30 s. Both completed all cases; monitoring executions API running=0 at every
post-fault checkpoint, including OneBot disconnect/reconnect. All owned process survivors=[]; all four
services reached health 200. Startup timings are not a controlled cold-start benchmark.

Actual subscribers, after `201830` (73.14 s): the two real EventListeners produce
`HealthyProbe>FaultProbe>` by serially accumulating reply_message_chain. prevent_default bypasses
Runner; prevent_postorder yields only `HealthyProbe>`. Faulty listener RuntimeError, bounded timeout,
worker exit and subsequent healthy controls are exercised. Controls after those faults are
0.416 / 0.405 / 0.803 s. With listeners present, a Runner BLOCK still delays a healthy event to 3.171 s.
The combined LBLOCK input intentionally matches both the listener and Runner: each busy-loops for
three seconds, giving 6.190 s healthy latency. At the five-second checkpoint two executions remain
running, then both finish; subsequent checkpoints and final queue are zero. This is bounded waiting,
not a leak or successful isolation of a faulty subscriber. Subscriber exceptions still abort their
current event; later queries recover. OneBot transport and worker disconnect paths both recover.
The unmodified SDK control `202001` (73.12 s) produced the identical ordered/prevented replies;
LRAISE/LTIMEOUT/LBLOCK/LEXIT controls were 0.424/0.421/6.173/0.784 s, and Runner BLOCK was 3.182 s.
Results are in the follow-up evidence package. No arbitrary unbounded hang or shared-worker isolation
claim is made. All owned processes are cleaned before handoff.

Reproduce with LANG16_MATRIX=1 LANG16_SHORT=1 LANG16_SECONDS=180; add LANG16_LISTENERS=1 for real
subscriber checks. Use LANG16_CORE_PYTHON for the isolated built SDK. The listener harness asserts
exact ordered/prevented replies. Run only one stack at a time and retain supervisor resource limits.

## 5, 7–9. Terminal states and resources

A malformed response config missing random reproduced a stale monitoring row: `152004` had an empty
queue but the inbound row stayed pending after a real KeyError; a separate assistant error row existed.
`MonitoringHelper.record_query_error` now finishes the original inbound record before optional error
details. `152315` retest finished both rows as error with an empty queue. Unit coverage also fails the
optional detail write. This is a concrete stale-state defect, not proof of the reported 242 tasks' cause.

Empty startup `150152`, approximately 90 seconds, all four health endpoints HTTP 200:

| Process | Peak / final RSS MiB | Mean CPU after 30 s |
| --- | --- | ---: |
| Core | 538.0 / 531.7 | 0.33% |
| RT | 63.5 / 63.5 | 0.03% |
| Box | 73.2 / 73.2 | 0.03% |
| Vite frontend | 350.9 / 346.8 | 0.10% |

The load preserves the release default per-conversation limiter (60 messages / 60 seconds, drop).
The 160-message burst exercises the 100-query cache bound; evicted queued queries have not yet
created monitoring rows. Every ten seconds the soak sends 50 unrelated group messages and one
keyword control in a different group. Extended matched measurements are recorded below. The frontend is a development server, not a
production build. RSS/threads/file descriptors/process counts and runtime health task/queue/session
counters are sampled; these are not heap profiles. Long-lived production memory exhaustion and the
reported 67694–68034-second pending workload must not be declared disproved by minute-scale probes.

## Host shutdown cancellation and lease recovery

`baseline-20261017-200457` runs a real QA Runner waiting for 60 seconds. Before shutdown, the actual
monitoring executions API reports one running pipeline query. The supervisor sends TERM only to its
recorded core PID, while RT remains available for orderly shutdown, then cleans the remaining owned
processes. The inbound row is still pending immediately after host shutdown; this path relies on the
existing execution lease, not the new stage-error patch.

`baseline-20261017-200536` starts a fresh isolated core from that stopped synthetic database plus its
instance identity. At 20:07:23 local time, its lease maintenance logs `Marked 1 interrupted executions
as failed after host lease expiry`; the row is error (about 130 seconds after shutdown, consistent with
120-second lease and 20-second maintenance interval). This validates shutdown cancellation/recovery,
not a nonexistent public OneBot task-cancel endpoint or cleanup of legacy rows without leases.

## Matched load measurements

Before `baseline-20261017-193933` uses unmodified 502b3813; after `195149` uses product fixes at
079e945b. Each completed about 731 seconds, including faults, a 160-message burst, 60 cycles of
50 unrelated + 1 keyword input at ten-second intervals, and 20 seconds idle recovery: 3232 inputs total.
Both use SDK 0.7.11 and the same synthetic Runner behavior. The machine remains shared with existing
user services; rate-limit window alignment and restart backoff jitter are not microbenchmark-controlled.

| Process | Soak mean CPU before / after | Soak peak RSS MiB before / after |
| --- | ---: | ---: |
| Core | 66.23% / 30.95% | 557.73 / 558.84 |
| RT | 4.89% / 2.05% | 65.19 / 65.03 |
| RT workers, summed | 1.53% / 0.65% | 165.67 / 177.83 |
| Box | 0.01% / 0.02% | 73.48 / 73.31 |
| Vite | 0.10% / 0.12% | 274.62 / 276.59 |

- Unrelated inputs: 3000 before / 3000 after. Before, all 3000 produced replies (660 actual Runner
  replies, 2340 rate-limit notices); after, zero produced replies. All 60 keyword soak
  controls produced Runner replies in both runs.
- Query cache peaked at 100 (99 queued, 1 executing) in the burst; final cached/queued=0 in both.
  Sixty queued inputs were evicted before monitoring-row creation. The 3172 recorded inbound rows
  ended as 3168 success + 3 error + 1 pending before, versus 3168 success + 4 error after.
- The remaining before pending row was the disconnected peer's failed reply, not active work.
- Application completed-task retention stayed bounded at 200. Workers returned to two running
  processes; transient initialization retries peaked at three. Final core/RT/worker/Box/web descriptors
  were 48/16/14/9/30 in both runs. No monotonic RSS/worker growth or OOM reproduced in this window.
- Recovery mean core CPU was 0.50% / 0.55%, RT 0.10% / 0.08%. Peak RSS was essentially unchanged;
  lower final RSS across processes is not evidence of a heap-leak fix (OS residency can change).
- All four services had zero failed health probes after first readiness; no resource threshold fired;
  owned process survivors were empty. GET /plugins max was 25 / 23 ms, zero failures.
- Cross-plugin BLOCK latency remained: healthy response at +3.169 / +3.191 s from fault initiation,
  versus about +0.40 s for other fault controls. These core fixes do not repair that SDK coupling.

The soak excludes actual LLM/history growth and has no sandbox workload; real LocalAgent/Box behavior
was tested separately above. Container CPU/RSS was not profiled; recorded container settings are limits,
not measured usage. No claim is made about the reporter's 18-hour workload or full memory-leak absence.

## 6. Groq request schema

Local reconstruction showed provider_specific_fields passed through outbound history/tool calls; the
pinned LiteLLM Groq adapter preserves non-null keys. The Groq-only request-boundary fix deep-copies
outgoing messages and strips that metadata from messages/tool calls. Stored history retains Gemini
signatures for fallback, and other providers retain serialization. A proxy identified solely as OpenAI
without a Groq model/provider identity is outside this fix's scope.

Tests cover explicit/inferred Groq, streaming/non-streaming, tools, immutable history and provider
fallback metadata. Two tests send real LiteLLM HTTP/JSON and SSE requests to a synthetic loopback
server. They are protocol regressions, not real Groq calls. Real Groq remains explicitly deferred.

## Validation and reproduction

- Core focused suite: 255 passed, 41 warnings, including controller, response rules, monitoring failure,
  queue lifecycle, migration service and LiteLLM.
- LocalAgent suite: 254 passed, 10 warnings. `test_shared_release.py` excluded because it asserts SDK
  exactly 0.7.4 while the target release pins 0.7.11; this is not a full plugin release-gate pass.
- Frontend TypeScript noEmit passed; Ruff and git diff --check passed.
- Evidence is attached to LANG-16; no raw credentials, database or full application logs are published.

Reproduce the focused core suite from the task checkout:

```sh
.venv/bin/pytest tests/unit_tests/pipeline/test_controller.py tests/unit_tests/pipeline/test_controller_tenancy.py tests/unit_tests/pipeline/test_resprule.py tests/unit_tests/pipeline/test_monitoring_failure.py tests/unit_tests/pipeline/test_pool.py tests/unit_tests/pipeline/test_query_pool.py tests/unit_tests/pipeline/test_pipeline_migration_runtime.py tests/unit_tests/platform/test_botmgr_execution_trace.py tests/unit_tests/provider/test_litellmchat.py tests/unit_tests/api/service/test_pipeline_migration.py
```

For LocalAgent, run `python -m pytest tests --ignore=tests/test_shared_release.py` from its directory
using the target SDK 0.7.11 environment. Run `node_modules/.bin/tsc --noEmit` from the web directory.

Run probes from the task checkout with locked dependencies and free isolated ports:

```sh
.venv/bin/python tests/manual/lang16_baseline.py
LANG16_ONEBOT=1 .venv/bin/python tests/manual/lang16_baseline.py
LANG16_NETWORK=1 LANG16_SECONDS=150 .venv/bin/python tests/manual/lang16_baseline.py
LANG16_MATRIX=1 LANG16_SOAK_ROUNDS=60 LANG16_SECONDS=900 .venv/bin/python tests/manual/lang16_baseline.py
```

Use LANG16_CORE_SOURCE for a separate unmodified baseline worktree; use LANG16_CORE_PYTHON for old
locked dependencies. LANG16_UPGRADE=old seeds old data; after uses LANG16_SEED_DB and
LANG16_UPGRADE_ACCOUNT from that isolated run. The supervisor copies only task-owned synthetic data.
Live model runner requires LANG16_LLM_BASE_URL and prompts for the key; never place a key in arguments.
LANG16_PLUGIN_PACKAGE selects the task-built package. Review environment/config before running;
only this task's directories and recorded resource identities may be cleaned.

Excluded exploratory runs: initial Box default-port conflict; incomplete UI run interrupted by platform;
invalid Runner config nesting; network harness missing description; browser RSS threshold; incorrect UI
wizard/tour/wait selectors; initial matrix control accidentally repeated fault keywords (`192332`); before-run !qa command parsing (`193812`, intentionally stopped).
They are not acceptance evidence. A resource limit fired safely during browser setup, not production load.

## Final issue-by-issue disposition

| Item | Disposition | Boundary |
| --- | --- | --- |
| 1 Installation detail | Redacted network diagnostics implemented; real API and browser failure flow verified | Original user network incident itself not reproduced |
| 2 Installation path discrepancy | Both actual marketplace paths succeed; ten synthetic fault/path cases terminate | Mainland route blocked: proxy-disabled egress is JP through utun4 |
| 3 Box/unrelated messages | Catch-all gate, busy steering gate and LocalAgent lazy Box fixes delivered | Explicit filtered bindings keep their override; live steering acceptance/attachments are not covered by live prompts |
| 4 RT coupling | SDK no-listener RPC admission fixed and pushed; real healthy BLOCK latency 3.177→0.393 s; subscriber order/prevention preserved | Faulty EventListeners can still delay/abort later subscribers by the serial contract; no whole-RT crash reproduced |
| 5 Memory exhaustion | Not reproduced in bounded process-separated runs | No heap or overnight real-LLM-history soak; not a leak-free guarantee |
| 6 Groq | Outbound schema correction and local JSON/SSE regressions delivered | Real Groq explicitly deferred, not passed |
| 7 Processing records | Stage-exception and disconnected-reply stale rows fixed and retested | No bulk rewriting of historical pending records; host-shutdown recovery recorded separately |
| 8 Backlog CPU/memory | Matched workload CPU reduction measured; bounded queue and recovery verified | Peak memory unchanged; cannot attribute reporter's exact resource spike |
| 9 Startup/ongoing resources | Cold/idle/message/fault/burst/ten-minute soak and recovery measured | Development frontend and synthetic load; limits described above |

Remaining environment requirement: an authorized process-only mainland egress on this Mac, or an
explicitly authorized isolated direct-connect window, for the network acceptance gap. SDK registration,
checkout, root fix and task-branch push are complete. No change to the existing VPN or user services is authorized or needed
for the completed tests. No new paid resource/account permission is assumed. Until those are resolved
(or explicitly deferred), this is a partial delivery and LANG-16 must not be marked fully accepted.


## Explicit unaccepted long-history scope

Real LLM windows were approximately 120.01 s (`154144`) and 119.08 s (`192121`), including startup;
each used two prompted turns (plain answer and exec tool request), plus one filtered unrelated message.
This is not a growing-history benchmark. The ten-minute synthetic soak used 3232 total inputs per run,
including 60 keyword controls and 3000 unrelated messages, but no model/history growth. Serialized
conversation-history bytes and peak prompt tokens were not measured. Overnight real LLM history,
long-lived tool histories and eventual memory saturation therefore remain unaccepted; no 18-hour or
leak-free assurance is given. No overnight process is left running. Groq real calls remain explicitly
deferred. These limits are separate from the now-completed SDK no-listener fix.
