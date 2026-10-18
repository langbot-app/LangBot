# PR 2706 local verification

## Versions and delivery boundary

- Reviewed PR: https://github.com/langbot-app/LangBot/pull/2706
- Final PR head: `57077740bdcccbc8701eed3db9ef1421670fa9df`.
- Merged by the upstream maintainer on 2026-10-18 at 05:26:43 UTC, merge commit `7974a430680f813eae58e60d85c58ef935a144f3`.
- Runtime comparison baseline: `399685962e5c6bc5a4b7c711fd5afab20c775cd7`.
- macOS arm64, Python 3.12.14, SQLite 3.53.1, pinned SDK 0.7.13.
- This follow-up changes a query-plan regression test, not production behavior. It is delivered on the task branch, without opening another PR or modifying the merged PR branch.

The earlier local migration patch remains preserved in the task's Git stash and evidence archive. The author subsequently consolidated the migrations and corrected the migration fixtures; applying that obsolete patch would reintroduce a removed migration.

## Remaining product decision: stale pending counts

Real browser acceptance on the final head reproduced a remaining P2 monitoring discrepancy: the dashboard Running card shows **64**, while the authenticated in-flight SSE snapshot reports `active_total=0` for the same 64 historical pending records without an owner or lease. The real execution-list response was HTTP 200, its rows rendered, and the browser reported no JavaScript errors. The screenshot and `history-api.json` are attached to LANG-17.

This is a pre-existing issue that the PR fixes for the activity stream but leaves in the dashboard summary; it is not attributed as a new regression. `MonitoringService._get_execution_summary()` groups raw stored status without the new lease condition; `pending` maps to `running`. The historical execution list retains the same raw-status semantics.

Recommended decision: use the valid-lease definition consistently for active counts and the Running filter, while preserving historical database statuses for audit. Alternative: retain the historical-status statistic but rename/explain it and present the live count separately. No historical rows should be rewritten merely to make the card agree. These alternatives change user-visible semantics, so the task's explicit product-design approval gate applies. This follow-up does not implement either choice.

## Finding and correction

The final head failed `test_event_scan_budget_advances_past_foreign_events_without_reading_payloads` on SQLite 3.53.1. The test classified queries using the word `CORRELATED` in EXPLAIN output. This SQLite version flattens the ownership EXISTS check and reports:

```text
SEARCH agent_run_event USING INTEGER PRIMARY KEY (rowid=?)
SEARCH agent_run EXISTS USING INDEX ix_agent_run_run_id (run_id=?)
```

The query still uses the intended indexed lookup. The follow-up classifies the payload query by its SQL EXISTS clause, retains the primary-key assertion, and adds an explicit owner-index assertion. Candidate scans must still use the covering media-TTL index, and neither path may use a temporary B-tree. No test is skipped and no index assertion is removed.

Severity: P3 test portability failure, not a demonstrated production query regression.

## Automated verification

- Focused backend suite before follow-up: 267 passed, 1 failed, 1 skipped.
- After follow-up: 268 passed, 1 skipped. Includes media persistence/TTL/contracts, monitoring execution/session queries, response rules, provider metadata, journals, run ledgers and SQLite migrations.
- The skipped case requires PostgreSQL for monitoring sessions; it is not counted as a pass.
- Separately: 28 media-reference integration cases passed against a real disposable PostgreSQL 16 container, covering ORM and published DDL. Container limited to 512 MiB, one CPU and 128 PIDs; its recorded ID and task label were verified before removal.
- Ruff and formatting passed for the modified test; diff whitespace check passed.
- 11 monitoring Playwright browser regressions passed (real frontend, mocked API fixtures); they supplement rather than replace the separate real-backend browser probe.
- Final frontend TypeScript check and production build passed. The build reports existing large-chunk warnings.
- All reported final PR checks succeeded, including Python 3.11/3.12/3.13, SQLite/PostgreSQL migrations, integration/contracts, coverage, lint, frontend Playwright and CLA. The sole review thread is resolved. The branch rules returned CLA as the required status check; no mandatory human-review rule was returned.

## Real runtime checks

The evidence archive contains bounded foreground supervisors and a synthetic OneBot peer. They start the actual Core, SDK Plugin Runtime, installed QA Runner plugin and frontend on dedicated ports, with separate config, database, plugins, caches and logs. The Runner is a deterministic fixture, not a real LLM. No QQ server or real recipient is contacted.

Box is disabled for these paths and `DOCKER_HOST` points to a nonexistent task-local socket. Neither response-rule filtering nor monitoring/image persistence needs a sandbox. Box creation and LocalAgent tool execution are not claimed as verified by this test.

Inputs include ordinary group text, keyword, bot mention, other-user mention, private text, explicit Runner exception, timeout and a 30-message unrelated burst. The final version also exercises an image reply through the real Runner action, OneBot delivery and monitoring persistence. The recorded image is a CAS reference with `base64=null`, and the saved PNG is 68 bytes.

The successful production-frontend run lasted 71.23 seconds. Sampled peak RSS was Core 620.6 MiB, RT 64.1 MiB, plugin worker 63.0 MiB and frontend 131.9 MiB. Mean sampled CPU was 11.75%, 0.58%, 0.08% and 0.59% respectively, including startup. The final health sample reported zero queued/cached queries, zero blocking-executor pending/running jobs, zero message aggregation buffers and zero telemetry executions in flight. Background application tasks remain expected; their count is not a message backlog.

Before seeding synthetic history, the final image-enabled case set produced four successful assistant records (keyword, mention, private, image) and two user error records (exception, timeout). Six OneBot sends comprise four successful replies and two error notices. The other-user mention, ordinary group text and unrelated burst produce no replies. The baseline sent 37 replies for the original seven cases plus the 30-message burst; the extra image case is a final-version-only persistence check, not part of the matched response comparison.

The monitoring workload adds 64 historical pending records without an execution owner or lease, each with approximately 256 KiB of inline data, only to the isolated database. Three authenticated session-list and SSE snapshot requests measure the historical-payload path. These raw inserts represent pre-contract history, not a supported new-write API.

The baseline exposes all 64 records as active; the final version exposes zero. Baseline session-list median was 387.7 ms and snapshot median 61.4 ms. The initial final-version comparison measured 243.5 ms and 21.4 ms respectively. This is a small local sample, not a general throughput claim.

## Safety and limitations

The first run, before this follow-up, accidentally triggered SDK Box cleanup on the shared Docker daemon. The incident and exact container events were delivered separately in LANG-17. The member explicitly cleared the pause. Follow-up runtime tests block shared Docker access; the PostgreSQL test manages only its explicitly recorded container.

A browser run with the development frontend crossed the preselected 2 GiB aggregate RSS limit and was automatically terminated and cleaned up. That browser attempt is not a pass. Other setup attempts lacked the matching browser binary or were redirected to first-run onboarding; neither is counted as a product failure or a passed acceptance run. The final fixture marks onboarding skipped via the public API before browser navigation and waits for the real execution response and a rendered record before taking the acceptance screenshot. The subsequent browser run uses the production frontend and a task-local Chromium headless shell.

Resource limits are 2 GiB aggregate RSS, 200% aggregate CPU for five consecutive samples, and 150 seconds maximum per runtime run. Process ownership is recorded; shutdown checks the Multica daemon PID before terminating any owned process. Evidence distinguishes Core, RT, plugin worker, frontend and browser processes. Cold-start peaks and browser overhead must not be interpreted as a steady-state Core memory leak.

The merged author implementation enforces group response rules after all explicit Pipeline routes, including filtered routes. This differs from the earlier LANG-16 patch, which retained an override for explicitly filtered bindings. No routing semantics were changed by this follow-up; do not blindly cherry-pick the earlier response-rule patch over the merged design.

This PR covers portions of LANG-16 monitoring/resource usage, group triggering and Groq request construction. It does not independently deliver the parent's migration-network diagnostics, plugin fault-isolation work or Box demand-creation fixes. Groq service calls remain deferred. No overnight real-model history growth, mainland-China network test, real Dify callback or multi-platform live acceptance is claimed. The bounded runs do not prove the absence of long-term leaks.

## Reproduction

Use an independent task worktree and the pinned dependencies. The attached evidence archive supplies `tests/manual/lang17_live.py`, `lang17_onebot.py`, `lang17_fixture.py`, `lang17_ui.mjs`, and `lang17_postgres.py`. Preserve their relative locations when reproducing.

Build `web/` first and install the Playwright Chromium headless shell under the task's `evidence/playwright-browsers`. Run the live supervisor with the task virtualenv. For baseline comparison, set `LANG17_SOURCE` to a separate worktree at the baseline SHA. Do not reuse production configuration, credentials, databases, plugin directories or ports. The scripts intentionally avoid real model credentials.
