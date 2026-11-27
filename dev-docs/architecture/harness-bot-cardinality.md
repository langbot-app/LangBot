# Harness Bot cardinality (LANG-714)

## Runtime contract

LANG-714 replaces the v4.0 §7.2 per-processor projection with one deterministic `harness-omni` Bot per enabled Workspace. Standard Bot creation provisions it idempotently; it never creates processor bindings. The authenticated ingress rechecks active membership and Agent access for every message and passes a message-local route to the RuntimeBot. Pipelines and event processors are not accepted as Harness targets.

New conversation IDs are namespaced internally by Workspace, account, Agent and client conversation ID. Replies go back to the originating connection, with the original conversation and Agent IDs. A reconnect can reuse conversation state but does not inherit late replies from its predecessor. New monitoring records use the shared Bot ID; dedicated processor filtering in session summaries is not implemented.

Migration `0059_harness_workspace_bot` provisions a shared row for Workspaces with enabled legacy projections and disables all legacy Harness rows without deleting their identities or rewriting history. Upgraded Workspaces carry a fixed legacy baseline; fresh Workspaces have no such rows. Downgrading the revision marker does not restore old routes.

## Reproduction

From the repository root:

```sh
uv run pytest tests/unit_tests/harness tests/unit_tests/platform/test_harness_adapter.py tests/unit_tests/agent/test_processor_policy.py tests/integration/persistence/test_migrations.py tests/unit_tests/api/service/test_bot_service.py -q
```

The SQLite tests verify concurrent requests for 100 distinct processor-shaped configurations per Workspace still create one row each, and upgrading 101 legacy rows preserves all IDs and an existing session summary. The injected ingress test covers distinct routes, revocation on an established connection, account and processor isolation for identical wire conversation IDs, and rejection of late replies after disconnect.

End-to-end acceptance still needs an installed Runner, production device key registration and authenticated Workspace context on the WebSocket, plus repeat runs on PostgreSQL. Fixed crypto vectors and injected ingress are not network acceptance.
