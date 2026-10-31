"""enforce one active owner per Workspace

Revision ID: 0019_single_workspace_owner
Revises: 0018_merge_launch_replay
Create Date: 2026-08-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0019_single_workspace_owner'
down_revision = '0018_merge_launch_replay'
branch_labels = None
depends_on = None

_INDEX_NAME = 'uq_workspace_memberships_one_active_owner'


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'workspace_memberships' not in inspector.get_table_names():
        return

    # Ownership transfer used to promote a second member without demoting the
    # original owner. Preserve the Workspace creator where possible and demote
    # every historical extra owner before installing the database invariant.
    op.execute(
        sa.text(
            """
            WITH ranked_owners AS (
                SELECT membership.uuid,
                       ROW_NUMBER() OVER (
                           PARTITION BY membership.workspace_uuid
                           ORDER BY
                               CASE
                                   WHEN membership.account_uuid = workspace.created_by_account_uuid THEN 0
                                   ELSE 1
                               END,
                               COALESCE(membership.joined_at, membership.created_at),
                               membership.uuid
                       ) AS owner_rank
                FROM workspace_memberships AS membership
                JOIN workspaces AS workspace
                  ON workspace.uuid = membership.workspace_uuid
                WHERE membership.role = 'owner'
                  AND membership.status = 'active'
            )
            UPDATE workspace_memberships
               SET role = 'admin'
             WHERE uuid IN (
                 SELECT uuid
                   FROM ranked_owners
                  WHERE owner_rank > 1
             )
            """
        )
    )
    # Fresh installations may already have this index because SQLAlchemy
    # metadata is created before Alembic advances the revision marker.
    op.execute(
        sa.text(
            'CREATE UNIQUE INDEX IF NOT EXISTS '
            'uq_workspace_memberships_one_active_owner '
            'ON workspace_memberships (workspace_uuid) '
            "WHERE role = 'owner' AND status = 'active'"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'workspace_memberships' not in inspector.get_table_names():
        return
    index_names = {index['name'] for index in inspector.get_indexes('workspace_memberships')}
    if _INDEX_NAME in index_names:
        op.drop_index(_INDEX_NAME, table_name='workspace_memberships')
