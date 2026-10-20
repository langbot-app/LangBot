# Message routing acceptance

Use an isolated worktree, data directory, ports and Plugin Runtime. Preserve the
member's database and bot configuration. Back up SQLite with its backup API before
repairing data; do not copy a live WAL database with a plain file copy.

## Reproduction and repair

The product processor form sends `POST /api/v1/agents` with `kind=pipeline`.
Previously `AgentService` forwarded `config={}`, bypassing the Pipeline service's
default-config branch. The row was inserted, then stage initialization raised
`KeyError: safety`. Repeated failed creates could leave empty-config rows.

Pipeline creation now omits this empty override and the Pipeline service also
handles explicit `{}` as a request for defaults. Existing non-empty configs are
not replaced. For affected historical rows, back up first, inspect their config,
and repair only rows whose entire config is exactly `{}` with the version's
default Pipeline template. Preserve UUID, name and all other columns. Do not
silently reset partial or non-empty configurations.

New bots previously had no routes if there was no Pipeline. First-bot setup now
creates one default Pipeline and reuses it, serialized within the instance.
Existing bots are never rewritten. The old message preset added one unfiltered
route; it now adds separate private and group-mention routes, with an explicit
boolean mention condition in the editor. Reapplying preserves manual targets and
disabled routes.

## Acceptance sequence

1. Use the real WebUI to create a Pipeline, verify success, refresh its page, and
   inspect persisted `trigger`, `safety`, `ai`, `output` sections. Correlate the
   creation request with the HTTP access log.
2. Create a separate test bot. Confirm that the two message routes already
   exist. Expand conditions and verify the private/group split and boolean
   `is_at_bot=true`.
3. On the test bot only, remove the generated routes, use the message template,
   save, wait for success, then refresh. Click the template again and check that
   it neither duplicates conditions nor replaces manual targets.
4. Connect a local OneBot Universal protocol simulator using its own token and
   fake bot/group/user IDs. Never attach the simulator to a real QQ account.
5. Send a bounded sequence: unmentioned group, mention of another user, private,
   mention of the bot. Capture per-case task counters, Core logs, and the WebUI
   bot log/matching records. The first two must create no Pipeline tasks; the
   latter two must route to the selected Pipeline.
6. Verify actual replies separately with an authorized model. A matched route
   followed by a missing-model error proves routing, not successful AI replies.
   Label local protocol simulation separately from real-platform acceptance.
7. Confirm original member rows/configs are unchanged, capture service ownership
   and health, and keep the isolated dev services available for manual review.

Use existing `skills/.env` conventions for machine-specific URLs. Apply resource
stop thresholds before bounded tests; do not treat a short idle sample as a soak
test or a health endpoint as feature acceptance.
