"""allow Core-owned collaboration writes on Cloud Workspaces

Revision ID: 0015_cloud_core_collab
Revises: 0014_cloud_directory
Create Date: 2026-07-26

Cloud-projected Workspace identity remains projected by the directory
boundary, but membership role/remove and invitation acceptance are now owned
by Core tenant scope.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0015_cloud_core_collab'
down_revision = '0014_cloud_directory'
branch_labels = None
depends_on = None


_TABLE_NAME = 'workspace_memberships'
_POLICY_NAME = 'langbot_workspace_local_directory_write'
_TENANT_SETTING = 'langbot.workspace_uuid'


def _setting(name: str) -> str:
    return f"NULLIF(current_setting('{name}', true), '')"


def _quote(conn: sa.Connection, identifier: str) -> str:
    return conn.dialect.identifier_preparer.quote(identifier)


def _drop_policy(conn: sa.Connection) -> None:
    table = _quote(conn, _TABLE_NAME)
    policy = _quote(conn, _POLICY_NAME)
    op.execute(sa.text(f'DROP POLICY IF EXISTS {policy} ON {table}'))


def _create_policy(conn: sa.Connection, expression: str) -> None:
    table = _quote(conn, _TABLE_NAME)
    policy = _quote(conn, _POLICY_NAME)
    op.execute(
        sa.text(
            f'CREATE POLICY {policy} ON {table} AS PERMISSIVE FOR ALL TO PUBLIC '
            f'USING ({expression}) WITH CHECK ({expression})'
        )
    )


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql':
        return
    expression = f'workspace_uuid::text = {_setting(_TENANT_SETTING)}'
    _drop_policy(conn)
    _create_policy(conn, expression)


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql':
        return
    expression = (
        f'workspace_uuid::text = {_setting(_TENANT_SETTING)} AND EXISTS ('
        'SELECT 1 FROM workspaces AS local_workspace '
        'WHERE local_workspace.uuid = workspace_memberships.workspace_uuid '
        "AND local_workspace.source = 'local'"
        ')'
    )
    _drop_policy(conn)
    _create_policy(conn, expression)
