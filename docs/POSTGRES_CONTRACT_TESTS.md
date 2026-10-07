# Disposable PostgreSQL contract tests

The fast integration suite deliberately runs without an external database. At
the current baseline, 83 cases in three persistence modules require PostgreSQL:

| Module | PostgreSQL cases | Contract |
| --- | ---: | --- |
| `test_pipeline_admission_postgres.py` | 27 | Real row-lock admission, tenant isolation, rollback, cancellation and commit reconciliation |
| `test_rag_document_identity.py` | 34 | Persisted engine document identity, scoped deletion and migration convergence |
| `test_rag_interrupted_ingestion.py` | 22 | Interrupted/cancelled ingestion, delayed SDK writes, recovery and retained uploads |

Another 39 PostgreSQL cases are marked slow and deselected by Fast Integration
Tests rather than reported as skipped:

| Module | PostgreSQL cases | Contract |
| --- | ---: | --- |
| `test_migration_branch_convergence.py` | 7 | Real historical/populated upgrade branches, certification backfill and merge-only downgrade |
| `test_runner_timestamps_postgres.py` | 32 | Non-superuser timestamp/lease/retention contracts against both metadata and published-migration schemas |

The PostgreSQL Contract Tests job in `.github/workflows/run-tests.yml` provisions
a dedicated `pgvector/pgvector:pg16` service, sets both required URL variables,
and runs all 122 PostgreSQL cases. Admission uses a separate database from RAG,
convergence and timestamp tests: its populated `public` schema must not affect
other fixtures' schema discovery through their `schema,public` search path.
Its JUnit check requires each module's baseline
case count and rejects skips, failures and errors. Results are uploaded even when
the job fails. SQLite variants continue running in Fast Integration Tests.

## Run locally

Use a new disposable database. The admission fixture drops and recreates the
entire `public` schema and creates a test runtime role. Never use a development,
staging or production database, or a shared database containing useful data.

For example, start an isolated container bound only to the local loopback address:

```bash
docker run --rm -d --name langbot-contract-pg \
  -e POSTGRES_USER=postgres -e POSTGRES_DB=langbot_test \
  -e POSTGRES_HOST_AUTH_METHOD=trust \
  -p 127.0.0.1:55432:5432 pgvector/pgvector:pg16
docker exec langbot-contract-pg pg_isready -U postgres -d langbot_test
```

Wait until `pg_isready` reports that the server is accepting connections, then:

```bash
docker exec langbot-contract-pg psql -U postgres -d postgres \
  -v ON_ERROR_STOP=1 -c 'CREATE DATABASE langbot_admission_test;'
uv sync --dev --frozen
export TEST_POSTGRES_URL=postgresql+asyncpg://postgres@localhost:55432/langbot_test
export LANGBOT_ADMISSION_TEST_URL=postgresql+asyncpg://postgres@localhost:55432/langbot_admission_test
uv run pytest \
  tests/integration/persistence/test_pipeline_admission_postgres.py \
  tests/integration/persistence/test_rag_document_identity.py \
  tests/integration/persistence/test_rag_interrupted_ingestion.py \
  tests/integration/persistence/test_migration_branch_convergence.py \
  tests/integration/persistence/test_runner_timestamps_postgres.py \
  -k postgres -q --tb=short -rs --durations=10 \
  --junitxml=postgres-contract-results.xml
docker stop langbot-contract-pg
```

Trust authentication is limited to this throwaway, loopback-bound service. The
admission fixture needs the literal `postgres@` URL to derive a separate
unprivileged runtime-role connection. RAG fixtures create and clean up their own
unique schemas, as do convergence fixtures. Timestamp fixtures create a unique
non-superuser, non-RLS-bypass role and owned schema for each case and remove both
afterward. The admin connection therefore needs role/schema creation privileges.
These settings do not belong in an application configuration.

## Other skip categories

- The monitoring PostgreSQL unit regression is separately selected by the
  Migrations (PostgreSQL) job in `.github/workflows/test-migrations.yml`
- Eight legacy-identity cross-repository cases require a sibling plugin-source
  checkout named `langbot-plugins-411-migration`
- The compiled CLI HTTP contract needs `LANGBOT_CLI_BIN` pointing to a real
  `lbctl` binary from the separate `langbot-cli` repository
- Embedded SeekDB has two slow tests and an optional `pyseekdb` dependency; a
  missing dependency appears as one module-level skip before marker filtering

These remaining prerequisites should be reported explicitly rather than treated
as passing tests. The four chat-handler logging tests now initialize the normal
application import graph before importing the handler and no longer skip.
