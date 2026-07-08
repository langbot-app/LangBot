import langbot

semantic_version = f'v{langbot.__version__}'

required_database_version = 25
"""Tag the version of the legacy (3.x) database schema migration chain.

Frozen at 25: the legacy ``pkg/persistence/migrations`` system (DBMigration /
dbmXXX_*.py) is deprecated and no longer accepts new migrations. All schema
changes from here on are managed by Alembic (see
``pkg/persistence/alembic/versions``). This value only gates the one-time
upgrade of pre-existing 3.x databases up to the Alembic baseline."""

debug_mode = False

edition = 'community'

instance_id = ''

instance_create_ts = 0
"""Unix timestamp (seconds) of when this instance was first created.

Sourced from ``data/labels/instance_id.json``. Backfilled to the current
time for instances created before this field existed, so it is always a
positive value once load_config has run.
"""
