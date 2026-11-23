# Historical schema fixtures

These JSON files contain **DDL compiled from historical ORM modules**, not the
current models with a historical revision stamped over them. `source_commit`,
`source_path`, and `revision` in each file record provenance.

- `baseline_schema.json`: the first Alembic baseline (database version 25),
  commit `9cd3544d59600fcb88700d05e4b211f59ac00445`.
- `master_schema.json`: commit `9b7ba0d64708496ace30a82866f6dbc185f089dc`,
  published head `0024_passkey_credentials`.
- `beta_schema.json`: commit `03854b5d33d8b66fec4c86a77714e0e7512a31bd`,
  published head `0025_bot_plugin_processors`.

`test_migration_branch_convergence.py` loads the appropriate SQLite/PostgreSQL
DDL into an empty database, executes the real ancestors to the exact historical
revision, seeds representative rows, then upgrades to the unified head. There
is no version stamping in these regression tests. Historical ORM startup used
`create_all` before Alembic; executing ancestors also installs PostgreSQL RLS
and pgvector objects absent from the ORM snapshots.

The baseline PostgreSQL case follows the application's staged legacy startup:
upgrade to `0010_scope_resources`, create deferred tenant tables, then upgrade
to head. Bare Alembic against a completely empty PostgreSQL database is **not**
the product's fresh-install contract; the fresh case explicitly starts empty,
creates current ORM metadata, and executes all migrations. Existing-table
columns and populated baseline data still undergo real migrations.

The data probes preserve account/owner membership, bot routes, pipelines,
providers, messages, colliding bot sessions, beta Agent/Runner state and plugin
processor subscriptions, and master Codex/passkey rows. PostgreSQL checks RLS
flags/policies; SQLite checks foreign-key integrity. This is representative
migration coverage, not a production database clone or exhaustive data fuzzing.

PostgreSQL tests require `TEST_POSTGRES_URL` to an expendable test service. Each
case creates and drops only its own UUID-named schema. Prefer a disposable
`pgvector/pgvector:pg16` container with loopback-only port binding, CPU/memory
limits, and tmpfs storage. Do not point the suite at production.

The only downgrade exercised with populated branch data removes the no-op
merge and leaves **both** parent heads. Older feature downgrades can destroy
credentials, agents, or colliding bot sessions and are not claimed safe.

## Regeneration

Run `generate_schema_fixtures.py` with the repository's locked Python environment
and `PYTHONPATH=src` from the repository root. It reads historical objects with
`git show` into a temporary package and compiles each historical metadata set
using SQLAlchemy's SQLite/PostgreSQL dialects; it never modifies migrations or
connects to a database. Keep these fixed historical snapshots when adding new
migrations; do not regenerate from current models.
