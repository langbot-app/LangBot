"""add explicit Workspace membership source

Revision ID: 0020_membership_source
Revises: 001a_pgvector_dimension_3072
Create Date: 2026-08-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0020_membership_source'
down_revision = '001a_pgvector_dimension_3072'
branch_labels = None
depends_on = None

_CONSTRAINT_NAME = 'ck_workspace_memberships_source'


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'workspace_memberships' not in inspector.get_table_names():
        return
    if 'source' in {column['name'] for column in inspector.get_columns('workspace_memberships')}:
        return

    # No durable historical field distinguishes Directory-created revision-zero
    # rows from Core invitations. Protect every existing row; production can
    # reclassify separately after UUIDs have been verified against Space.
    with op.batch_alter_table('workspace_memberships') as batch_op:
        batch_op.add_column(sa.Column('source', sa.String(length=32), nullable=False, server_default='local'))
        batch_op.create_check_constraint(
            _CONSTRAINT_NAME,
            "source IN ('local', 'cloud_projection')",
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'workspace_memberships' not in inspector.get_table_names():
        return
    if 'source' not in {column['name'] for column in inspector.get_columns('workspace_memberships')}:
        return
    with op.batch_alter_table('workspace_memberships') as batch_op:
        batch_op.drop_constraint(_CONSTRAINT_NAME, type_='check')
        batch_op.drop_column('source')
