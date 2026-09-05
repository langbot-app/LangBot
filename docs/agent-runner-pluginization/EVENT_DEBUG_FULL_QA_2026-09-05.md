# Event debug full QA and release verification — 2026-09-05

## Scope and inventory

This follow-up investigates repeated welcome actions, verifies the debug surface with standalone Box/Plugin Runtime, and checks the changes before committing/pushing Core, SDK, and LocalAgent. Real messaging-platform effects must remain isolated from debug runs.

| Area | Required checks | Evidence |
| --- | --- | --- |
| Root cause | Follow-up messages/tool IDs preserved; direct model replay before/after mock guidance; original welcome prompt | Sanitized local traces, browser tool count |
| Events | All 15 built-in event types plus custom; nested/Unicode data and identity/target mapping | Browser results and parameterized service tests |
| Platform actions | Every catalog tool; frozen and explicit targets; permission/event/API intersection | Parameterized host boundary tests, browser reply/query/moderation/request cases |
| Mock scenarios | Success, error, query fixture, unsupported API; malformed options rejected | Browser and service tests |
| Input | Empty message/name, invalid/non-object JSON, unsupported event, actor/subject validation | Browser and request tests |
| Trace | Thinking/text/tool ordering, final snapshot deduplication, status/error correctness, no-call summary | Browser and reducer tests |
| Lifecycle | Cancel retains partial record; rerun; tabs/Agent switching; provider failure/fallback; reconnect | Browser and transport/runner tests |
| Native tools | Exec/file operations, nonzero exit, timeout and path escape | Browser and native-tool tests |
| Layout | Long output/parameters, automatic bottom scroll, narrow view, KB card spacing | DOM geometry and screenshots |
| Release | Python/SDK suites, frontend build/lint, whitespace checks, change review, commit and push | Commands, counts and remote SHAs |

## Investigation

The real follow-up request contained the assistant tool call and successful tool result with matching IDs. No loss occurred at the LocalAgent → SDK → Host model boundary. Direct replay to the configured provider, bypassing the runner, reproduced `event_reply` after success. Adding explicit mock completion semantics stopped further calls in two direct replays. The previous LocalAgent system context omitted the debug/mock semantics although the tool result said no real platform operation occurred.

The configured upstream `claude-opus-4-8` also returned an unsolicited CLI identity statement in direct replay. This originates in the provider response, not the debug renderer. It is separate from preserving tool results; it must not be presented as normal LangBot-generated status.

## Final results

### Browser event matrix

Executed through the real Edge WebUI, against Core `:5300`, Vite `:3000`, standalone Plugin Runtime `:5400/:5401`, and Docker-backed standalone Box `:5410`. The unbound `E2E Debug 0905` Agent uses `deepseek-v4-flash`; the user's original Agent and welcome prompt remain unchanged and use `claude-opus-4-8`.

| Event | Observed result in this pass |
| --- | --- |
| `bot.invited_to_group` | Actor/group queries and `event_respond_group_invite(approve=true)` succeeded; request ID frozen to `debug-group-request`. |
| `bot.muted`, `bot.removed_from_group` | One `event_get_group` call each, correct group target. |
| `bot.unmuted` | One actor query; correct user target. |
| `feedback.received` | One mock reply, `FEEDBACK_MOCK_OK`, person target. |
| `friend.added` | One mock reply, `FRIEND_ADDED_OK`, person target. |
| `friend.request_received` | Acceptance and separate explicit rejection exercised; rejection preserved `approve=false`, Unicode remark and frozen request ID. |
| `group.member_banned` | One member lookup, SDK-compatible nested `user` and `group_id`. |
| `group.member_left` | One group lookup, SDK-compatible `id`/`name`. |
| `group.member_joined` | Welcome reply, configured failure, query fixture, unsupported API, and mute/unmute/kick scenarios. Original-model repeat caveat below. |
| `message.deleted` | One actor lookup, SDK-compatible `id`/`nickname`. |
| `message.edited` | One simulated deletion; frozen group, chat and message IDs. |
| `message.reaction` | One reply, `REACTION_OK`, and correct `👍` event data. |
| `message.received` | Real six-tool file/exec chain, plain-text recovery, cancellation, draft retention, nonzero exit and timeout. |
| `platform.specific` | Preserved nested arrays, booleans, null and `测试🙂`; no tools called. |
| `custom.event`, `custom.e2e` | Empty object and named custom event with `CUSTOM_中文🙂`; no tools called. |

The first invitation/default friend-request runs submitted the preset text; they are recorded as default-behavior cases, not as explicit one-call/rejection tests. The rejection was separately rerun with the actual submitted instruction verified. Browser automation reads the controlled input after filling before treating a scenario as submitted.

### Mock and execution behavior

- Platform Mock runs the actual model/tool selection, authorization, parameter validation and frozen-target resolution; only the adapter boundary is simulated. Tests assert that mock execution never accesses the real bot manager. Native tools retain real Box behavior.
- The platform catalog contains 24 tools. Parameterized tests exercise success and configured failure for all 24, plus permission/event/API filtering, explicit/frozen targets, SDK fixture shapes and invalid options. This is full catalog contract coverage, not 24 separate browser clicks or proof of live adapter support.
- `errors.event_reply = "E2E permission denied"` produced one failed call and the **模拟执行失败 · Mock** status. The model reported the actual error without retrying in this scenario.
- `results.event_get_actor` returned the configured `fixture-user-77` / `测试用户🙂`; the model used these values instead of the original event identity. Default query results now serialize SDK platform models; default lists contain one synthetic entry and can be overridden with `[]`.
- Disabling `send_message` removed `event_reply` from the model's available tools. It returned `REPLY_UNAVAILABLE`, with the explicit no-tool-call summary. Clearing Mock options restored action availability; the three moderation calls succeeded with the correct group/member IDs.
- Mock `[]`, unknown tool names, whitespace-only message/custom name, malformed event JSON and event JSON `[]` were rejected. Browser transcript counts did not increase for client-side validation failures. Backend tests additionally cover falsey/non-object actor, subject and data values, conflicting outcomes and invalid API names.
- Thinking returned by the provider, intermediate text, tool parameters, results and final text remain distinct and ordered. Missing thinking is not fabricated. Cumulative final snapshots and prior tool-turn prefixes are deduplicated without hiding actual repeated tool calls.

### Lifecycle, native tools and layout

- A browser cancellation regression exposed a stuck **停止调试** button: the `finally` block skipped resetting state for aborted requests. It now clears the matching controller and resets running state even after user cancellation. Retest retained partial thinking/tool arguments, marked the unfinished call **未返回结果**, showed the cancellation notice and restored **运行测试**.
- Two subsequent recovery requests encountered the bounded-stream error below. A later request in the same tab/session returned `42` successfully; further real tool runs also completed. Cancellation and recovery are therefore verified, but immediate model success after cancellation is not guaranteed.
- Editing `NEXT_DRAFT_FINAL_0905` while a `sleep 5` run was still awaiting its final response preserved the draft after completion.
- Real `write → read → edit → glob → grep → exec` succeeded. `final.txt` changed from `FINAL_WRITE` to `FINAL_EDIT`; grep without `include` found one match; exec returned `FINAL_EXEC` with exit code 0. Writes stayed under `/workspace/e2e-debug-0905`.
- `printf E2E_ERROR >&2; exit 7` preserved stderr and exit code 7 and displayed failure. `sleep 3` with `timeout_sec=1` returned `timed_out` in 1025 ms and displayed failure. Neither was retried.
- Separate tabs retained separate transcripts during concurrent runs. Agent switching reset the debug surface. File workspace sharing remains intentional; transcript isolation does not mean separate Box filesystems.
- The final transcript measured 674 px high with 16,630 px scroll height, distance from bottom 0, and equal client/scroll widths of 468 px. Visual inspection confirmed contained parameters/results and accessible input controls. The earlier pass also verified 1280 × 800; the final attempted viewport override did not change this tab, so that attempt is not counted as an additional narrow-screen result. Temporary overrides were reset.
- Knowledge-base card geometry: retrieval card bottom 1413 px, danger card top 1437 px, giving the expected **24 px** gap. Both adjacent card gaps measured 24 px.
- Core health check returned `ok`; Plugin Runtime was connected and all development service ports remained listening. Previous restart/reconnect evidence is in the earlier report.

### Automated checks

| Suite | Result |
| --- | --- |
| Core agent unit directory plus debug service/controller, native/skill tools and model conversion | 659 passed, 24 Windows-only skips |
| Final changed platform/debug service/controller checks | 133 passed |
| Linux Docker: native tools, skill tools and all platform tools | 150 passed, 0 skipped; includes the 24 POSIX cases skipped on Windows |
| SDK API suite plus runtime I/O handler | 411 passed |
| LocalAgent full suite (`PYTHONUTF8=1`) | 187 passed |
| Frontend unit suite | 69 passed |
| Skills CLI suite | 122 passed |
| Frontend TypeScript/Vite build and changed-file ESLint | Passed; existing large-bundle advisory remains |
| Changed Python Ruff; Git whitespace checks | Passed |
| Skills index generation, validate and index consistency | Passed |

Counts overlap where a final focused/Linux run repeats an earlier suite; do not add them as unique tests. Existing Pydantic deprecation warnings remain. This is the relevant subsystem regression set, not the entire repository/integration matrix. Provider fallback has deterministic LocalAgent tests; live fallback after a partially emitted response is deliberately unsupported and was not claimed as a successful browser fallback.

The full regression also found Windows portability problems in the skills tooling: LF-only frontmatter parsing, `/cases/` detection and native path separators in generated references. These are fixed and covered by the CLI suite. Two frontend source-contract expectations were stale after the existing three-tab workbench/layout changes; they were updated to the actual product structure.

### Remaining limits and reproduction

1. **Original provider is still nondeterministic.** With the latest LocalAgent guidance, one rerun made exactly one successful `event_reply`; another made repeated successful replies before stopping. The trace faithfully records each call. Earlier invalid `_call` arguments were rejected. Direct provider replay proved that repeated calls can originate upstream even with a valid matching tool result. Prompt guidance reduces ambiguity but does not establish exactly-once actions. No silent deduplication or fabricated success was added.
2. **Bounded stream pressure can fail long responses.** Two recovery runs emitted thinking and then `Streaming action consumer is too slow; response buffer full`; later recovery and six-tool runs succeeded. The error originates in the SDK's existing 128-frame response queue and is preserved in the UI. It is not a missing-tool-result or 30-second HTTP timeout. Full end-to-end flow control under sustained overload remains open; queue limits were not removed to conceal the failure.
3. Mock results verify debug behavior, not real platform credentials, permissions, delivery, or every adapter/event Cartesian combination. Already launched external tool termination timing was not independently measured. A development-branch push does not mean these remaining production release gates passed.

For reproduction, use the retained test Agent, the Mock examples in [AGENT_RUNNER_QA_GUIDE.md](./AGENT_RUNNER_QA_GUIDE.md), and the original welcome Agent. Local diagnostic traces and fixture artifacts are excluded from Git; they contain model responses and local runtime state. This report contains outcomes rather than raw provider reasoning or secrets.
