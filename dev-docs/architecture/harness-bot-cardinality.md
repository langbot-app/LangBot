# Harness Bot cardinality (LANG-714)

## Runtime contract

Authenticated ingress rechecks active Workspace membership and Agent access before provisioning and dispatch. Each authorized message targets a deterministic `harness-omni` Bot for its `(workspace_uuid, processor_uuid)` pair. The first message creates the row on demand and loads the runtime; concurrent or repeated messages reuse the identity. Opening or redeeming a registration link does not create a Bot. The route is owned by Harness and generic Bot creation does not provision it. Pipelines and event processors are not accepted as Harness targets.

Conversation IDs remain namespaced internally by Workspace, account, Agent and client conversation ID. Replies go back to the originating connection, with the original conversation and Agent IDs. A reconnect can reuse conversation state but does not inherit late replies from its predecessor. New monitoring records use the processor Bot ID.

Migration `0064_harness_processor_bots` disables the old shared row created by `0059_harness_workspace_bot` or by older servers. It preserves historical Bot IDs and monitoring records. The new processor projections are not backfilled. Downgrading the revision marker does not restore old routes.

## HTS1 wire contract

The TS and Python peers share `tests/unit_tests/harness/protocol-vectors.json` (copied byte-for-byte from Harness core commit `4cca441`; SHA-256 `c324325bfc280f9fc4bdb2e20bac78611976314c8cb769b728d15d0460f11aee`). HS1 signs the server-visible fields as `HTS1/HS1\n{v}\n{kid}\n{ts}\n{nonce_s}\n{e_h}`. HS2 signs `HTS1/HS2\n` plus the HS1 transcript and `\n{e_c}`. Three DH values are ordered ephemeral-ephemeral, client-ephemeral/server-static, client-static/server-ephemeral. Confirmation is HMAC-SHA256 over `langbot-harness-hts1 || full_transcript`. Frame sequence numbers are canonical decimal strings representing uint64; replay state advances only after successful AEAD authentication.

The Runner acceptance below redeems the link and enrolls a client device over HTTPS, obtains an OAuth grant via encrypted HTTP RPC password login, and authenticates the chat channel inside HTS1 (`auth.kind: oauth`). It does not exercise browser 2FA handoff.

Assistant chat replies include `{ execution: { source: 'agent', id } }` from the active Runner trace context. Inspector uses the explicit encrypted RPC method `monitoring.execution.detail` through `Hts1HttpRpcTransport.getExecutionDetail()`. Required params are `access_token`, `workspace_uuid`, `processor_uuid`, `conversation_id`, and `execution_id`; optional params are `section`, `offset`, and `limit` (maximum 50). The server revalidates grant, device and membership, checks live processor access, and matches the run to the deterministic processor Bot and the account/workspace/processor-scoped `person_` conversation before calling `MonitoringService.get_execution_detail()`. Cross-workspace requests return `workspace_forbidden`; unavailable or non-owned runs return `execution_not_found` (404) without disclosing their existence. This is deliberately not a generic Workspace API proxy.

## Reproduction

From the repository root:

```sh
uv run pytest tests/unit_tests/harness tests/unit_tests/platform/test_harness_adapter.py tests/unit_tests/agent/test_processor_policy.py tests/integration/persistence/test_migrations.py tests/unit_tests/api/service/test_bot_service.py -q
```

With Harness `6f3cf86` checked out as a sibling, run from the LangBot root (Node.js 26):

```sh
pnpm --dir ../LangBot-Harness install --frozen-lockfile
pnpm --dir ../LangBot-Harness/packages/core build
HARNESS_TS_TRANSPORT="$PWD/../LangBot-Harness/packages/core/dist/transport.js" \
HARNESS_TS_RPC_TRANSPORT="$PWD/../LangBot-Harness/packages/core/dist/rpc-transport.js" \
  uv run --frozen pytest -q tests/e2e/test_local_runner_fake_provider.py::test_harness_processor_bots_run_local_agent
```

The probe starts an isolated SQLite-backed LangBot server and the real SDK Plugin Runtime, installs the official LocalAgent Runner, and tests two Agents in a fresh Workspace over the actual HTS1 WebSocket route and TypeScript transport. Only the model provider is deterministic. The client verifies three assistant replies (`A → B → A`) and denial of a different Workspace and unknown processor. The server verifies two Bot rows and three completed Runner records across two stable conversation IDs.
