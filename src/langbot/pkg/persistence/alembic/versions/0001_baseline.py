"""baseline: stamp the supported 4.x schema

This is a no-op migration that marks the starting point for Alembic.
Current tables already exist via SQLAlchemy metadata create_all().

Revision ID: 0001_baseline
Revises: None
Create Date: 2026-04-08
"""

revision = '0001_baseline'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op: this revision serves as the Alembic baseline.
    pass


def downgrade() -> None:
    pass
