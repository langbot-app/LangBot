# v4.10.11 database upgrade audit

Baseline: `v4.10.11`, commit `273b8839b91cb74dfd083644efea18849a3fcee1`.
Audited target: `48c6a1f536bab421cbaab98a1e880fe767034463`.

## Changes covered

- Agent definitions, run ledger, interactions/delivery results, event logs and transcripts.
- Bot legacy pipeline routing to event bindings, followed by legacy-column removal; plugin processors.
- Workspace tenancy/ownership repairs and migration branch merges.
- Unified runner state, assistant conversations and pipeline migration snapshots.
- Passkey and TOTP credentials.
- Knowledge-base initialization/drafts and engine document identity.
- Operation traceability, monitoring links/tool calls, execution host leases and metadata text storage.

The existing migration chain covers the audited ORM changes. No additional runtime migration was required by the exercised upgrade paths.

## Added regression

`release_4_10_11_schema.json` contains immutable dialect-specific DDL exported from the tagged release ORM, rather than current metadata. The test applies historical migrations through `0023_bot_scoped_sessions` to include migration-owned objects such as pgvector, seeds representative legacy records, then runs the current persistence schema initialization twice.

Assertions cover legacy bot/pipeline preservation, converted bot event bindings, default plugin processors, initialized knowledge bases, SQLite foreign-key consistency, and missing tables/columns/indexes/constraints or column type/nullability differences against current metadata. Equivalent existing index/constraint column sets are accepted; extra migration-owned objects and removed-object diffs are not treated as missing schema. This is representative upgrade coverage, not an exhaustive test of every possible historical data value.

## Executed verification

Disposable SQLite files and an isolated PostgreSQL/pgvector container were used; no business database was changed.

- New tagged-release upgrade test: **2 passed** (SQLite and PostgreSQL), including repeated initialization.
- Existing PostgreSQL migration / release-migration / RAG identity suite: **85 passed, 4 failed** on the first completed run. The four failures were release configuration validation because the test URL omitted the required port.
- Release-migration suite rerun with explicit `:5432`: **5 passed**.
- Ruff check and format: passed for the new regression test.

Reproduce the new regression with `TEST_POSTGRES_URL` pointing to a disposable PostgreSQL/pgvector instance whose test role can create/drop databases:

```sh
pytest tests/integration/persistence/test_release_41011_upgrade.py -q
```

Without `TEST_POSTGRES_URL`, PostgreSQL is explicitly skipped rather than reported as tested.
