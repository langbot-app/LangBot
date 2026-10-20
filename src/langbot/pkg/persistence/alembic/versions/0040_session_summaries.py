"""Persist idempotent conversation summaries independently of message history."""

import contextlib

from alembic import op
import sqlalchemy as sa

revision = '0040_session_summaries'
down_revision = '0039_execution_lease_indexes'
branch_labels = None
depends_on = None

TABLE = 'monitoring_session_receipts'
TIME_INDEX = 'ix_monitoring_messages_workspace_timestamp'
INDEXES = (
    ('monitoring_messages', 'ix_monitoring_messages_summary_event', ['workspace_uuid', 'bot_id', 'event_id', 'role']),
    ('agent_run', 'ix_agent_run_summary_event', ['workspace_id', 'bot_id', 'event_id', 'id']),
    (
        'monitoring_messages',
        'ix_monitoring_messages_execution_filter',
        ['workspace_uuid', 'status', 'role', 'bot_id', 'id', 'session_id', 'parent_message_id', 'run_id'],
    ),
    (
        'monitoring_messages',
        TIME_INDEX,
        [
            'workspace_uuid',
            'timestamp',
            'id',
            'status',
            'role',
            'bot_id',
            'session_id',
            'parent_message_id',
            'run_id',
            'pipeline_id',
        ],
    ),
)


@contextlib.contextmanager
def _suspend_summary_forced_rls(connection):
    """Let the table-owning migrator mark history without a Workspace scope."""
    if connection.dialect.name != 'postgresql':
        yield
        return
    tables = (
        connection.execute(
            sa.text(
                'SELECT relname FROM pg_class WHERE relnamespace = current_schema()::regnamespace '
                'AND relname IN :tables AND relforcerowsecurity'
            ).bindparams(sa.bindparam('tables', expanding=True)),
            {'tables': ('workspaces', 'workspace_metadata', 'monitoring_sessions', 'monitoring_messages', 'event_log')},
        )
        .scalars()
        .all()
    )
    quote = connection.dialect.identifier_preparer.quote
    try:
        for table in tables:
            connection.execute(sa.text(f'ALTER TABLE {quote(table)} NO FORCE ROW LEVEL SECURITY'))
        yield
    finally:
        for table in tables:
            connection.execute(sa.text(f'ALTER TABLE {quote(table)} FORCE ROW LEVEL SECURITY'))


def upgrade():
    connection = op.get_bind()
    for table, index, fields in INDEXES:
        if not sa.inspect(connection).has_table(table):
            continue
        existing = {item['name']: item['column_names'] for item in sa.inspect(connection).get_indexes(table)}
        if existing.get(index) == fields:
            continue
        if index in existing:
            op.drop_index(index, table_name=table)
        op.create_index(index, table, fields)
    # Bare Alembic and partial-schema upgrades rely on ORM bootstrap for core tables.
    if not sa.inspect(connection).has_table('monitoring_sessions'):
        return
    columns = {column['name'] for column in sa.inspect(connection).get_columns('monitoring_sessions')}
    for name, type_ in [
        ('metadata_timestamp', sa.DateTime()),
        ('metadata_role', sa.String(50)),
        ('metadata_source_key', sa.String(512)),
        ('base_snapshot', sa.Text()),
    ]:
        if name not in columns:
            op.add_column('monitoring_sessions', sa.Column(name, type_, nullable=True))
    if 'source_count' not in columns:
        op.add_column(
            'monitoring_sessions', sa.Column('source_count', sa.Integer(), nullable=False, server_default='0')
        )
    # Legacy metadata provenance is unknown. Keep existing display values, but
    # leave provenance and the base snapshot NULL until bounded projection.
    if not sa.inspect(connection).has_table(TABLE):
        op.create_table(
            TABLE,
            sa.Column(
                'workspace_uuid', sa.String(36), sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'), primary_key=True
            ),
            sa.Column('bot_id', sa.String(255), primary_key=True),
            sa.Column('source_key', sa.String(512), primary_key=True),
            sa.Column('session_id', sa.String(255), nullable=True),
            sa.Column('event_id', sa.String(255), nullable=True),
            sa.Column('role', sa.String(50), nullable=False),
            sa.Column('covered', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('timestamp', sa.DateTime(), nullable=False),
            sa.Column('candidate_snapshot', sa.Text(), nullable=True),
            sa.Column('source_timestamp', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ['workspace_uuid', 'bot_id', 'session_id'],
                ['monitoring_sessions.workspace_uuid', 'monitoring_sessions.bot_id', 'monitoring_sessions.session_id'],
                ondelete='CASCADE',
            ),
        )
        op.create_index('ix_session_receipts_session', TABLE, ['workspace_uuid', 'bot_id', 'session_id'])
        op.create_index('ix_session_receipts_expiry', TABLE, ['workspace_uuid', 'timestamp', 'bot_id', 'source_key'])
        # Historical receipts must be initialized offline before live projection.
        if sa.inspect(connection).has_table('workspace_metadata'):
            sources = ['EXISTS (SELECT 1 FROM monitoring_sessions s WHERE s.workspace_uuid=w.uuid)']
            if sa.inspect(connection).has_table('monitoring_messages'):
                sources.append('EXISTS (SELECT 1 FROM monitoring_messages m WHERE m.workspace_uuid=w.uuid)')
            if sa.inspect(connection).has_table('event_log'):
                sources.append('EXISTS (SELECT 1 FROM event_log e WHERE e.workspace_id=w.uuid)')
            with _suspend_summary_forced_rls(connection):
                connection.execute(
                    sa.text(
                        'INSERT INTO workspace_metadata (workspace_uuid, key, value) '
                        "SELECT w.uuid, 'session_summary_backfill_v1', :cursor FROM workspaces w WHERE ("
                        + ' OR '.join(sources)
                        + ') ON CONFLICT (workspace_uuid, key) DO UPDATE SET value=excluded.value'
                    ),
                    {'cursor': '{"source": "messages"}'},
                )
    collation = '"C"' if connection.dialect.name == 'postgresql' else 'BINARY'
    op.execute(
        sa.text(
            f'CREATE INDEX IF NOT EXISTS ix_session_receipts_candidate ON {TABLE} '
            '(workspace_uuid, bot_id, session_id, source_timestamp DESC, '
            f'source_key COLLATE {collation} DESC) WHERE candidate_snapshot IS NOT NULL'
        )
    )
    if connection.dialect.name == 'postgresql':
        predicate = "workspace_uuid::text = NULLIF(current_setting('langbot.workspace_uuid', true), '')"
        op.execute(sa.text(f'ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'DROP POLICY IF EXISTS langbot_workspace_isolation ON {TABLE}'))
        op.execute(
            sa.text(
                f'CREATE POLICY langbot_workspace_isolation ON {TABLE} AS PERMISSIVE FOR ALL TO PUBLIC '
                f'USING ({predicate}) WITH CHECK ({predicate})'
            )
        )


def downgrade():
    connection = op.get_bind()
    for table, index, _ in reversed(INDEXES):
        if sa.inspect(connection).has_table(table):
            if index in {item['name'] for item in sa.inspect(connection).get_indexes(table)}:
                op.drop_index(index, table_name=table)
            if index == TIME_INDEX:
                op.create_index(index, table, ['workspace_uuid', 'timestamp'])
    if sa.inspect(connection).has_table(TABLE):
        op.drop_table(TABLE)
    if sa.inspect(connection).has_table('monitoring_sessions'):
        columns = {item['name'] for item in sa.inspect(connection).get_columns('monitoring_sessions')}
        for column in (
            'base_snapshot',
            'metadata_source_key',
            'metadata_role',
            'metadata_timestamp',
            'source_count',
        ):
            if column in columns:
                op.drop_column('monitoring_sessions', column)
