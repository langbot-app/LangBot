# Legacy migrations (DEPRECATED — do not add new files here)

This directory holds the **legacy 3.x database migration system**
(`DBMigration` subclasses in `dbmXXX_*.py`, registered via
`@migration.migration_class(N)` and run from `pkg/persistence/mgr.py`).

**This system is frozen. Do not add new `dbmXXX_*.py` migrations.**

The chain is capped at version 25 (`required_database_version = 25` in
`pkg/utils/constants.py`). These files exist only to upgrade pre-existing
3.x databases up to the Alembic baseline (`0001_baseline`). Removing them
would break in-place upgrades from old installations, so they are kept
read-only.

## All new schema changes use Alembic

Migrations now live in `pkg/persistence/alembic/versions/`. To create one:

```bash
uv run python -m langbot.pkg.persistence.alembic_runner autogenerate "description of your change"
```

(requires `data/config.yaml` to exist). Review and edit the generated
script before committing — Alembic migrations run automatically on startup
and must be idempotent and guard against missing tables (the test suite
runs them against empty databases).

### Rules for Alembic revision ids

- Keep the revision id **≤ 32 characters** — PostgreSQL stores
  `alembic_version.version_num` as `varchar(32)` and will raise
  `StringDataRightTruncationError` on overflow.
- Guard every `op` call against a missing table / missing column
  (`inspector.get_table_names()` / `inspector.get_columns()`); fresh
  installs create the schema via `create_all()` and stamp the baseline,
  so migrations may run against tables that already match or do not exist.
