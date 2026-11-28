# Harness key rotation on PostgreSQL workers

This acceptance path checks the persisted rotation protocol across two separate
Core processes sharing PostgreSQL. It covers the two-worker `key_acked` race,
the 500 ms WebSocket serving-key recheck, and emergency retirement. It is not a
general multi-process acceptance test for other Core subsystems.

## Disposable database setup

Use a local throwaway PostgreSQL database, never a development, staging, or
production database. Create a dedicated unprivileged login and database owned
by that role; the test creates and drops a uniquely named schema for each case.
For example, with PostgreSQL binaries available locally:

```sql
CREATE ROLE harness_test LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE DATABASE harness_rotation_test OWNER harness_test;
```

The test connects directly as `harness_test`, creates schema
`harness_rpc_<random UUID>`, and uses that schema as `search_path` for both
worker processes. It creates only the Harness/account/workspace tables needed
by the fixture, then drops the isolated schema with `CASCADE` in teardown. The
login needs ownership of its disposable database so it can create/drop schemas;
do not grant it elevated privileges on any shared database.

Build the adjacent LangBot Harness Core package, then run from the LangBot root:

```bash
pnpm --dir ../LangBot-Harness/packages/core build
export HARNESS_TEST_POSTGRES_URL=postgresql+asyncpg://harness_test@127.0.0.1:56492/harness_rotation_test
export HARNESS_TS_RPC_TRANSPORT="$PWD/../LangBot-Harness/packages/core/dist/rpc-transport.js"
export HARNESS_TS_TRANSPORT="$PWD/../LangBot-Harness/packages/core/dist/transport.js"
uv run --frozen pytest -q -s tests/unit_tests/harness tests/integration/harness
```

All environment variables above are test-only. Without the PostgreSQL URL the
rotation fixture uses SQLite and does not establish cross-process PostgreSQL
behavior; without the built transport modules, the cross-component tests skip.

The test starts two HTTPS worker processes with distinct PIDs against the same
schema. It enrolls two devices, plans a rotation, concurrently submits both
encrypted ACKs through different workers, and asserts exactly one ACK first
reports `retired=false`, the other reports `retired=true`, and the old key's
private ciphertext is erased. It also checks that the idle WSS connections on
both workers are closed after the database reports retirement. The emergency
case asserts old and overlap keys are retired and idle WSS connections close.

On the acceptance run, the clients received WebSocket close code **1008** for
retired-key sessions. Hypercorn also emitted
`ssl.SSLError: [SSL: APPLICATION_DATA_AFTER_CLOSE_NOTIFY] application data after close notify`
while tearing down some WebSocket connections. This server-side shutdown log
did not change the client result: both the code-1008 assertion and the bounded
500 ms retirement-check assertions passed. Expected observed closure times in
the local run were approximately 200–492 ms after the ACK/retirement event.
