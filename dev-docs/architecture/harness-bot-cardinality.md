# Harness Bot cardinality (LANG-714)

## Runtime contract

LANG-714 replaces the v4.0 §7.2 per-processor projection with one deterministic `harness-omni` Bot per enabled Workspace. Standard Bot creation provisions it idempotently; it never creates processor bindings. The authenticated ingress rechecks active membership and Agent access for every message and passes a message-local route to the RuntimeBot. Pipelines and event processors are not accepted as Harness targets.

New conversation IDs are namespaced internally by Workspace, account, Agent and client conversation ID. Replies go back to the originating connection, with the original conversation and Agent IDs. A reconnect can reuse conversation state but does not inherit late replies from its predecessor. New monitoring records use the shared Bot ID; dedicated processor filtering in session summaries is not implemented.

Migration `0059_harness_workspace_bot` provisions a shared row for Workspaces with enabled legacy projections and disables all legacy Harness rows without deleting their identities or rewriting history. Upgraded Workspaces carry a fixed legacy baseline; fresh Workspaces have no such rows. Downgrading the revision marker does not restore old routes.

## HTS1 wire contract

The TS and Python peers share `tests/unit_tests/harness/protocol-vectors.json` (copied byte-for-byte from Harness core commit `4cca441`; SHA-256 `c324325bfc280f9fc4bdb2e20bac78611976314c8cb769b728d15d0460f11aee`). HS1 signs the server-visible fields as `HTS1/HS1\n{v}\n{kid}\n{ts}\n{nonce_s}\n{e_h}`. HS2 signs `HTS1/HS2\n` plus the HS1 transcript and `\n{e_c}`. Three DH values are ordered ephemeral-ephemeral, client-ephemeral/server-static, client-static/server-ephemeral. Confirmation is HMAC-SHA256 over `langbot-harness-hts1 || full_transcript`. Frame sequence numbers are canonical decimal strings representing uint64; replay state advances only after successful AEAD authentication.

After the encrypted socket is established, the client sends its existing LangBot account JWT and Workspace ID inside an authenticated encrypted `authenticate` payload (`auth.kind: user_token`). Core resolves the token with `UserService`, resolves the Workspace via `WorkspaceCollaborationService`, and returns a random per-channel proof. Each message must present it. Membership, account token, placement generation and membership revision are checked again for each message, in addition to processor access. This bridges existing account login; it is not the whitepaper OAuth access/refresh token, registration-link or Cloud SSO flow.

## Reproduction

From the repository root:

```sh
uv run pytest tests/unit_tests/harness tests/unit_tests/platform/test_harness_adapter.py tests/unit_tests/agent/test_processor_policy.py tests/integration/persistence/test_migrations.py tests/unit_tests/api/service/test_bot_service.py -q
```

The TCP WebSocket smoke test uses the built TS transport from `LangBot-Harness` at `4cca441` (`agent/lang-714-client`). With both repositories checked out as siblings, run from the LangBot root (tested with Node.js 26):

```sh
git -C ../LangBot-Harness fetch origin agent/lang-714-client
git -C ../LangBot-Harness worktree add --detach ../LangBot-Harness-4cca441 4cca441
pnpm --dir ../LangBot-Harness-4cca441 install --frozen-lockfile
pnpm --dir ../LangBot-Harness-4cca441 test
HARNESS_TS_TRANSPORT="$PWD/../LangBot-Harness-4cca441/packages/core/dist/transport.js" \
  uv run pytest tests/integration/harness tests/unit_tests/harness -q
```

The SQLite tests verify concurrent requests for 100 distinct processor-shaped configurations per Workspace still create one row each, and upgrading 101 legacy rows preserves all IDs and an existing session summary. The injected ingress test covers distinct routes, revocation on an established connection, account and processor isolation for identical wire conversation IDs, and rejection of late replies after disconnect.

The smoke test uses the real Quart endpoint over TCP, TS HS1/HS2, persisted instance keys, account JWT validation, per-message processor denial, and encrypted replies. After the server closes the first socket, the same TS factory opens a fresh channel and reauthenticates. The same conversation keeps its internal chat ID but receives a new connection ID and channel proof. The fixture supplies device lookup, Workspace context and the Runner reply callback; production device registration, installed Runner execution, and PostgreSQL acceptance are separate.
