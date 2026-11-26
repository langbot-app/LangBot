# Harness Bot cardinality (LANG-714)

## Decision boundary

The issue asks for Bot rows not to grow with processor count. The approved v4.0 attachment (§0 item 11, §7.2, §13.6 and G4) explicitly requires a persisted Bot and route per processor, including a processor-specific `monitoring_sessions.bot_id`. Both cannot hold for new processors. The current branch still follows the v4.0 projection; the design below is a proposed revision, not a runtime change.

The conflict is local to LangBot and can be tested without the Harness repository. The Harness client and its cross-repository protocol tests are not available in this workspace. The live WS route also lacks provisioned device lookup and encrypted account/Workspace context resolution. Neither a mocked transport nor the projection baseline is network acceptance.

## Smallest viable replacement

1. Provision one deterministic managed Harness Bot per enabled Workspace. Reuse the existing Bot lifecycle, adapter and logger. Provisioning must be idempotent under concurrent retries and must not depend on processor listing or grants. Keep its ordinary `event_bindings` and plugin subscriptions empty. Stop the old per-processor writer at cutover; do not run both provisioning paths.
2. On `message.received`, resolve the selected processor in the authenticated Workspace, recheck its access before dispatch (including on an established connection), and bind the resulting route to that message. Do not accept target kind, synthetic route data or authority from the client. Add a narrow internal RuntimeBot Harness ingress entry, checked against adapter identity and active placement, that invokes the existing processor dispatch with an explicit resolved route. Leave normal EBA filter selection unchanged. Do not mutate shared Bot config to switch targets. `can_use_processor` currently resolves Agents only; keep Pipeline targets denied until their Workspace access check is implemented and tested.
3. Keep the wire conversation ID unchanged. Internally partition connection, event, aggregation, interaction, and history keys by Workspace, account, processor kind/ID and conversation ID. Use a versioned opaque encoding for the internal session ID. Bind replies to the originating connection generation rather than looking up a client-supplied conversation alone. Repeated IDs from different processors or accounts must not share history or reply delivery.
4. For new writes, `monitoring_sessions.bot_id` identifies the shared Bot; record the processor separately in the session summary and use it for processor filtering and labels. Update `SessionSummaryWriter` in the source transaction and read through `SessionSummaryReader`, not request-time joins over raw messages. Preserve existing per-processor Bot IDs and their historical references during cutover: disable legacy projections, keep their history readable, and measure retained rows separately. For a fresh install the bound is one row per enabled Workspace. On upgrade it is the fixed retained legacy baseline plus that bound; no new legacy rows are created.

## Acceptance

**Runnable baseline** (repository root):

```sh
uv run pytest tests/unit_tests/platform/test_harness_bindings.py -q
```

`test_v4_projection_adds_one_bot_for_each_new_processor` measures 1 then 100 projected rows using the in-memory service double; removing 99 processors disables those rows but does not remove them. It does not measure real database writes.

**Required for the replacement** (test cases to implement):

| Fixture and action | Pass condition |
| --- | --- |
| Fresh database, two Workspaces; enable Harness in each, vary processor count from 1 to 100, rerun provisioning concurrently and restart Core. Count `SELECT workspace_uuid, COUNT(*) FROM bots WHERE adapter = 'harness' GROUP BY workspace_uuid`. | Exactly one row per Workspace and one active Harness runtime per placement at each count. Processor grants, revocation and deletion do not add Bot rows. |
| Two authorized processors, two accounts and two Workspaces send messages concurrently with the same client conversation ID. Then revoke access while a connection remains open. | Each message runs exactly once against its intended processor; the next revoked message is denied before dispatch. A foreign or missing processor is denied. Replies, interactions and history stay in the originating scope. |
| Upgrade a database with legacy projected Bots and nonempty histories. Enable the shared route, replay provisioning, then add more processors. | Legacy histories remain readable under their old IDs; no new legacy Bot rows or handlers appear. New histories list and filter by processor under the shared Bot ID. |

Run the database cases on SQLite and PostgreSQL, and run `uv run pytest --required-suite session_summary -q` with all required backends active. Exercise the real RuntimeBot with the in-tree SDK and an installed representative Runner. When the Harness checkout and runtime identity dependencies are available, repeat the routing, revocation and reply cases over real encrypted WebSockets. These replacement checks have not been run.
