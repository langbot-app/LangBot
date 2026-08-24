"""Merge AgentRunner and Workspace heads and scope Agents to a Workspace.

Revision ID: 0016_agent_workspace
Revises: 0015_official_runner_ids, 0015_cloud_core_collab
Create Date: 2026-07-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0016_agent_workspace'
down_revision = ('0015_official_runner_ids', '0015_cloud_core_collab')
branch_labels = None
depends_on = None


_TABLE = 'agents'
_POLICY = 'langbot_workspace_isolation'
_TENANT_SETTING = 'langbot.workspace_uuid'


def _inspector(conn: sa.Connection) -> sa.Inspector:
    return sa.inspect(conn)


def _columns(conn: sa.Connection) -> dict[str, dict]:
    return {
        column['name']: column
        for column in _inspector(conn).get_columns(_TABLE)
    }


def _default_workspace_uuid(conn: sa.Connection) -> str | None:
    metadata = sa.table(
        'metadata',
        sa.column('key', sa.String(255)),
        sa.column('value', sa.String(255)),
    )
    workspaces = sa.table(
        'workspaces',
        sa.column('uuid', sa.String(36)),
        sa.column('instance_uuid', sa.String(255)),
        sa.column('source', sa.String(32)),
    )
    instance_uuid = conn.execute(
        sa.select(metadata.c.value).where(metadata.c.key == 'instance_uuid')
    ).scalar_one_or_none()
    query = sa.select(workspaces.c.uuid).where(workspaces.c.source == 'local')
    if isinstance(instance_uuid, str) and instance_uuid.strip():
        query = query.where(workspaces.c.instance_uuid == instance_uuid.strip())
    rows = conn.execute(query.order_by(workspaces.c.uuid)).scalars().all()
    if len(rows) > 1:
        raise RuntimeError('Cannot backfill Agents: multiple local Workspaces exist')
    return rows[0] if rows else None


def _foreign_key_exists(conn: sa.Connection) -> bool:
    return any(
        tuple(foreign_key.get('constrained_columns') or ())
        == ('workspace_uuid',)
        and foreign_key.get('referred_table') == 'workspaces'
        and tuple(foreign_key.get('referred_columns') or ()) == ('uuid',)
        for foreign_key in _inspector(conn).get_foreign_keys(_TABLE)
    )


def _enable_postgres_rls(conn: sa.Connection) -> None:
    if conn.dialect.name != 'postgresql':
        return
    table = conn.dialect.identifier_preparer.quote(_TABLE)
    policy = conn.dialect.identifier_preparer.quote(_POLICY)
    op.execute(sa.text(f'DROP POLICY IF EXISTS {policy} ON {table}'))
    op.execute(sa.text(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY'))
    expression = (
        "workspace_uuid::text = "
        f"NULLIF(current_setting('{_TENANT_SETTING}', true), '')"
    )
    op.execute(
        sa.text(
            f'CREATE POLICY {policy} ON {table} AS PERMISSIVE FOR ALL TO PUBLIC '
            f'USING ({expression}) WITH CHECK ({expression})'
        )
    )


def upgrade() -> None:
    conn = op.get_bind()
    table_names = set(_inspector(conn).get_table_names())
    if _TABLE not in table_names or 'workspaces' not in table_names:
        return

    columns = _columns(conn)
    if 'workspace_uuid' not in columns:
        op.add_column(
            _TABLE,
            sa.Column('workspace_uuid', sa.String(36), nullable=True),
        )

    agents = sa.table(
        _TABLE,
        sa.column('workspace_uuid', sa.String(36)),
    )
    null_count = conn.scalar(
        sa.select(sa.func.count())
        .select_from(agents)
        .where(agents.c.workspace_uuid.is_(None))
    )
    if null_count:
        workspace_uuid = _default_workspace_uuid(conn)
        if workspace_uuid is None:
            raise RuntimeError(
                'Cannot backfill Agents: the instance has no unique local Workspace'
            )
        conn.execute(
            agents.update()
            .where(agents.c.workspace_uuid.is_(None))
            .values(workspace_uuid=workspace_uuid)
        )

    columns = _columns(conn)
    needs_contract = columns['workspace_uuid']['nullable'] or not _foreign_key_exists(conn)
    if needs_contract:
        with op.batch_alter_table(_TABLE) as batch_op:
            if columns['workspace_uuid']['nullable']:
                batch_op.alter_column(
                    'workspace_uuid',
                    existing_type=columns['workspace_uuid']['type'],
                    nullable=False,
                )
            if not _foreign_key_exists(conn):
                batch_op.create_foreign_key(
                    'fk_agents_workspace',
                    'workspaces',
                    ['workspace_uuid'],
                    ['uuid'],
                    ondelete='CASCADE',
                )

    index_names = {
        index['name'] for index in _inspector(conn).get_indexes(_TABLE)
    }
    if 'ix_agents_workspace_name' not in index_names:
        op.create_index(
            'ix_agents_workspace_name',
            _TABLE,
            ['workspace_uuid', 'name'],
        )
    if 'ix_agents_workspace_updated' not in index_names:
        op.create_index(
            'ix_agents_workspace_updated',
            _TABLE,
            ['workspace_uuid', 'updated_at'],
        )

    _enable_postgres_rls(conn)


def downgrade() -> None:
    conn = op.get_bind()
    if _TABLE not in _inspector(conn).get_table_names():
        return
    if 'workspace_uuid' not in _columns(conn):
        return
    if conn.dialect.name == 'postgresql':
        table = conn.dialect.identifier_preparer.quote(_TABLE)
        policy = conn.dialect.identifier_preparer.quote(_POLICY)
        op.execute(sa.text(f'DROP POLICY IF EXISTS {policy} ON {table}'))
        op.execute(sa.text(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY'))

    index_names = {
        index['name'] for index in _inspector(conn).get_indexes(_TABLE)
    }
    for index_name in ('ix_agents_workspace_updated', 'ix_agents_workspace_name'):
        if index_name in index_names:
            op.drop_index(index_name, table_name=_TABLE)

    foreign_keys = _inspector(conn).get_foreign_keys(_TABLE)
    workspace_fk = next(
        (
            foreign_key
            for foreign_key in foreign_keys
            if tuple(foreign_key.get('constrained_columns') or ())
            == ('workspace_uuid',)
            and foreign_key.get('referred_table') == 'workspaces'
        ),
        None,
    )
    with op.batch_alter_table(_TABLE) as batch_op:
        if workspace_fk is not None and workspace_fk.get('name'):
            batch_op.drop_constraint(workspace_fk['name'], type_='foreignkey')
        batch_op.drop_column('workspace_uuid')
