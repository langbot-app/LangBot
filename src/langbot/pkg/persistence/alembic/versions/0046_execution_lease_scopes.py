"""Index Host execution leases by (owner, Workspace) so maintenance never scans every Workspace."""

import contextlib

from alembic import op
import sqlalchemy as sa

revision = '0046_execution_lease_scopes'
down_revision = '0045_monitoring_handled_by'
branch_labels = None
depends_on = None

TABLE = 'execution_lease_scopes'
EXPIRY_INDEX = 'ix_execution_lease_scopes_expires_at'


@contextlib.contextmanager
def _suspend_forced_rls(connection, tables):
    """Let the table-owning migrator read leased rows without a Workspace scope."""
    if connection.dialect.name != 'postgresql':
        yield
        return
    forced = (
        connection.execute(
            sa.text(
                'SELECT relname FROM pg_class WHERE relnamespace = current_schema()::regnamespace '
                'AND relname IN :tables AND relforcerowsecurity'
            ).bindparams(sa.bindparam('tables', expanding=True)),
            {'tables': tuple(tables)},
        )
        .scalars()
        .all()
    )
    quote = connection.dialect.identifier_preparer.quote
    try:
        for table in forced:
            connection.execute(sa.text(f'ALTER TABLE {quote(table)} NO FORCE ROW LEVEL SECURITY'))
        yield
    finally:
        for table in forced:
            connection.execute(sa.text(f'ALTER TABLE {quote(table)} FORCE ROW LEVEL SECURITY'))


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table(TABLE):
        op.create_table(
            TABLE,
            sa.Column('owner_id', sa.String(36), primary_key=True),
            sa.Column('workspace_uuid', sa.String(255), primary_key=True),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('generation', sa.Integer(), nullable=False, server_default='0'),
        )
        op.create_index(EXPIRY_INDEX, TABLE, ['expires_at'])

    # Executions leased before this index existed must stay reapable after upgrade.
    sources = []
    if inspector.has_table('agent_run'):
        sources.append(
            'SELECT execution_owner_id AS owner_id, workspace_id AS workspace_uuid, '
            'execution_lease_expires_at AS expires_at FROM agent_run '
            "WHERE status = 'running' AND queue_name IS NULL AND claimed_by_runtime_id IS NULL "
            'AND execution_owner_id IS NOT NULL AND workspace_id IS NOT NULL '
            'AND execution_lease_expires_at IS NOT NULL'
        )
    if inspector.has_table('monitoring_messages'):
        sources.append(
            'SELECT execution_owner_id AS owner_id, workspace_uuid, '
            'execution_lease_expires_at AS expires_at FROM monitoring_messages '
            "WHERE status = 'pending' AND execution_owner_id IS NOT NULL "
            'AND execution_lease_expires_at IS NOT NULL'
        )
    if not sources:
        return
    with _suspend_forced_rls(connection, ('monitoring_messages',)):
        connection.execute(
            sa.text(
                f'INSERT INTO {TABLE} (owner_id, workspace_uuid, expires_at, generation) '
                'SELECT owner_id, workspace_uuid, MAX(expires_at), 0 FROM ('
                + ' UNION ALL '.join(sources)
                + ') leased GROUP BY owner_id, workspace_uuid '
                'ON CONFLICT (owner_id, workspace_uuid) DO NOTHING'
            )
        )


def downgrade():
    if sa.inspect(op.get_bind()).has_table(TABLE):
        op.drop_table(TABLE)
