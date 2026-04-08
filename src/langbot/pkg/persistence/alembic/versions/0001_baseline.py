"""baseline: stamp existing schema (db version 25)

This is a no-op migration that marks the starting point for Alembic.
All tables already exist via create_all() + legacy DBMigration system.

Revision ID: 0001_baseline
Revises: None
Create Date: 2026-04-08
"""

revision = '0001_baseline'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op: existing schema is already at database_version=25
    # This revision serves as the Alembic baseline.
    pass


def downgrade() -> None:
    pass
