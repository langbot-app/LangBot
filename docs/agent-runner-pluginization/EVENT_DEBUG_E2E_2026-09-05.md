# Event debug end-to-end regression — 2026-09-05

Environment: Windows, Vite :3000, Core :5300, standalone Plugin Runtime :5400/:5401, standalone Box :5410, Docker backend. Tests use browser controls in Edge and an isolated unbound Agent `E2E Debug 0905` (`49e52ae0-6a99-46ce-975e-70164b2786ec`). Local plugin maintenance uses the authenticated localhost management API because Edge file upload is disabled.

## Coverage inventory

- Message input: empty input, plain text, multi-turn context, draft edits during streaming.
- Structured events: group join/leave/ban, friend request/add, feedback, bot state, message edit/delete/reaction, platform and custom events.
- Payload validation: invalid JSON, non-object JSON, Unicode and nested fields.
- Execution trace: intermediate/final text, returned thinking, tool arguments/results, tool failure, no-output failure, completion without duplication.
- Lifecycle: save-and-run, provider failure and recovery, long output/autoscroll, switch Agent during run, reconnect.
- Visual checks: scroll containment, long tool JSON, error card, narrow viewport.

## Findings and fixes

1. Synthetic debug Query omitted public Workspace fields. Native tools failed during skill mount lookup. Project trusted ExecutionContext fields onto synthetic queries; real Docker exec returned `E2E_TOOL_OK` after repair.
2. LocalAgent context assembly omitted structured event data. Add a bounded user-role event facts message before current input, preserving ordinary empty-data message behavior. Browser join/leave/friend/feedback returned unique JSON probes after installing the patched local plugin.
3. A model failure before visible output left an empty Agent card. Hide output entries with no visible execution steps.
4. A completed message request cleared a newly edited draft. Clear only the submitted input value; the browser retained `NEXT_DRAFT_SHOULD_REMAIN`.
5. Tool transport completion was shown as success even with `result.ok=false`. Treat explicit failed tool results as failure; real exec exit 7/stderr is preserved.
6. Native file tools resolved a Core host path before selecting remote Box execution. Choose Box first for remote/no-host-root deployments, validate virtual path boundaries, and cover all five file tools.
7. This local legacy config had no `box.local.host_root`, so Docker had no writable `/workspace` mount. Add an explicit local development root and keep the read-only root filesystem enabled.

8. LocalAgent repeats previous turns in cumulative chunks after tools. Strip the already displayed prefix for those chunks; real thought text now appears once across write/read.
9. Remote grep generated Python `include = null` when no filter was supplied. Serialize it as a Python literal and test optional/quoted values.

## External configuration observations

`gpt-4.1-mini` under LangBot Models returned no available channel; NewAPI rockchin returned invalid token. These are reported by the trace; tests continued with working `claude-opus-4-8` and `deepseek-v4-flash` models. The test Agent now uses the latter. No credentials were changed.

## Results

### Browser outcomes

All 15 preset event types and one named custom event were executed through the UI. These exercise synthetic debug event dispatch, not delivery from real messaging platforms.

| Events | Observed outcome |
| --- | --- |
| `message.received` | Plain text marker, multi-turn tool execution and recovery succeeded. |
| `message.edited`, `message.deleted`, `message.reaction` | Returned `EDIT_10`, `DELETE_11`, `REACTION_12`. |
| `group.member_joined`, `group.member_left`, `group.member_banned` | Returned Unicode member data/`JOIN_42`, `LEFT_7`, `BANNED_20`. |
| `friend.request_received`, `friend.added` | Returned `FRIEND_8`, `ADDED_19`. |
| `bot.muted`, `bot.unmuted`, `bot.invited_to_group`, `bot.removed_from_group` | Returned `MUTED_13`, `UNMUTED_16`, `INVITED_17`, `REMOVED_18`. |
| `feedback.received` | Returned `FEEDBACK_9` and numeric rating from JSON. |
| `platform.specific`, `custom.e2e_probe` | Read nested JSON; returned `PLATFORM_14` and custom event type/`CUSTOM_15`. |

- Empty message, malformed JSON and non-object JSON did not start execution. Unicode, nested arrays/objects and an empty event object were exercised. Empty custom event name validation was not conclusively verified.
- Real Docker `exec`, `write`, `read`, `edit`, `glob`, and `grep` all succeeded after fixes. Files were limited to `/workspace/e2e-debug-0905`. Final grep without `include` returned `probe.txt`, line 1, `E2E_EDIT_OK`, total 1.
- Nonzero exec exit preserved exit code 7/stderr and displayed failure. `sleep 3` with `timeout_sec=1` returned `timed_out`, `ok=false`, about 1037 ms, and displayed failure with the actual timeout message.
- Provider-returned thinking, intermediate text, tool arguments/results and final text appeared in order. A repeated prior thought appeared once after the cumulative-prefix fix. Models that do not return thinking are not expected to display it.
- Two browser tabs ran independent debug sessions without mixed transcripts. While `exec sleep 30` showed running, switching Agents cleared the old transcript/running state. Returning and sending a new request produced `AFTER_CANCEL_OK`. This verifies UI cancellation/recovery; termination timing of the already launched container command was not independently measured.
- Core restart and standalone Plugin Runtime reconnection recovered successfully. The development services remain running.
- At the 1280 x 800 test viewport, the final transcript measured height 315, scroll height 5203, distance from bottom 0, and client/scroll widths both 333: automatic scrolling and horizontal containment passed. Screenshot inspected; viewport override reset afterward.

### Automated verification

- Core: 130 passed, 24 skipped across orchestrator, execution context, debug controller/service, native tools and skill tools. Skips are POSIX secure-host-filesystem cases unavailable on Windows; they still require Linux verification. Remote Box routing is covered on both capability branches.
- LocalAgent full suite: 185 passed with `PYTHONUTF8=1`.
- Frontend trace reducer: 5 passed; TypeScript `tsc --noEmit` passed.
- Ruff checks on changed Python implementation/tests and Git whitespace checks passed. Existing Pydantic deprecation warnings remain.

The isolated unbound Agent `E2E Debug 0905` is retained for reproduction. No real platform messages were sent. This run does not claim coverage of every provider, model fallback policy, Linux host file operations, or live platform adapter ingress.

## Follow-up: mock platform actions

The original run did not verify platform action tools: the synthetic envelope had no supported platform APIs or reply target. This was a coverage gap. Debug now supplies mock adapter capabilities and a synthetic reply target while retaining tool selection, event compatibility and parameter validation. Event targets remain frozen by the Host. Only platform operations are simulated; native tools still execute normally.

Verified in the browser on the user's `localagent test` Agent (`0dc5d7d3-07b2-4c4c-bb2b-a4f8e40e3a76`) without changing its welcome system prompt: `group.member_joined` caused a real `event_reply` tool call with `text: Hello，Debug User`. Its mock result contained `api: send_message`, `target_type: group`, `target_id: debug-group`, `mock: true`, and `delivery: simulated`. The UI labels this as mock execution rather than text output or real delivery, and shows the tool count after completion.

Mock platform responses are deterministic fixtures, not evidence of real adapter support or delivery. Read operations return synthetic information; list operations return empty fixture lists. Service/platform-tool regressions: 44 passed, including mock reply, explicit-target send, identity/group lookup, request rejection, validation and assertions that the real bot manager is never accessed. TypeScript and Ruff checks passed.

The same browser run subsequently exposed repeated `event_reply` calls after successful mock results, and one invalid `event_get_actor` call with an unexpected `_call` parameter. The invalid call was rejected and shown as failure. The run was cancelled by switching Agents. Therefore this verifies the mock call/result path, but does not establish that this configured model completes the welcome workflow exactly once. At this checkpoint the cause had not been determined.

For the subsequent investigation, updated SDK-shaped Mock fixtures (including non-empty default lists), cancellation fix, complete event matrix, Linux verification and remaining provider/stream-pressure limits, see [the full follow-up report](./EVENT_DEBUG_FULL_QA_2026-09-05.md). Its results supersede the checkpoint counts and fixture description above.
