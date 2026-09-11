"""Scope monitoring sessions by bot without changing runtime session IDs.

Revision ID: 0023_bot_scoped_sessions
Revises: 0022_codex_credentials
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite

revision = '0023_bot_scoped_sessions'
down_revision = '0022_codex_credentials'
branch_labels = None
depends_on = None

_TABLE = 'monitoring_sessions'
_KEY = ['workspace_uuid', 'bot_id', 'session_id']


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    pk = inspector.get_pk_constraint(_TABLE)
    if pk['constrained_columns'] == _KEY:
        return
    # PostgreSQL alters in place, retaining indexes, grants, policies and RLS.
    # SQLite batch reflection retains all existing indexes and foreign keys.
    with op.batch_alter_table(_TABLE, naming_convention={'pk': 'pk_%(table_name)s'}) as batch:
        batch.drop_constraint(pk['name'] or f'pk_{_TABLE}', type_='primary')
        batch.create_primary_key(f'pk_{_TABLE}', _KEY)

    metadata = sa.MetaData()
    sessions = sa.Table(_TABLE, metadata, autoload_with=conn)
    messages = sa.Table('monitoring_messages', metadata, autoload_with=conn)
    m = messages.c
    collisions = (
        sa.select(m.workspace_uuid, m.session_id)
        .group_by(m.workspace_uuid, m.session_id)
        .having(sa.func.count(sa.distinct(m.bot_id)) > 1)
        .subquery()
    )
    partition = [m.workspace_uuid, m.bot_id, m.session_id]
    # Repair only demonstrable collisions. Retention may have removed earlier
    # evidence; these summaries describe surviving messages, never invented text.
    ranked = (
        sa.select(
            *[m[name] for name in _KEY],
            m.bot_name,
            m.pipeline_id,
            m.pipeline_name,
            m.platform,
            m.user_id,
            m.user_name,
            sa.func.sum(sa.case((sa.or_(m.role == 'user', m.role.is_(None)), 1), else_=0))
            .over(partition_by=partition)
            .label('message_count'),
            sa.func.min(m.timestamp).over(partition_by=partition).label('start_time'),
            sa.func.max(m.timestamp).over(partition_by=partition).label('last_activity'),
            sa.func.row_number().over(partition_by=partition, order_by=[m.timestamp.desc(), m.id.desc()]).label('rank'),
        )
        .join(
            collisions,
            sa.and_(m.workspace_uuid == collisions.c.workspace_uuid, m.session_id == collisions.c.session_id),
        )
        .subquery()
    )
    columns = _KEY + [
        'bot_name',
        'pipeline_id',
        'pipeline_name',
        'platform',
        'user_id',
        'user_name',
        'message_count',
        'start_time',
        'last_activity',
        'is_active',
    ]
    select = sa.select(*[ranked.c[name] for name in columns[:-1]], sa.literal(True)).where(ranked.c.rank == 1)
    insert = postgresql.insert if conn.dialect.name == 'postgresql' else sqlite.insert
    statement = insert(sessions).from_select(columns, select)
    conn.execute(
        statement.on_conflict_do_update(
            index_elements=_KEY,
            set_={name: statement.excluded[name] for name in columns if name not in _KEY and name != 'is_active'},
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    collisions = conn.execute(
        sa.text('SELECT 1 FROM monitoring_sessions GROUP BY workspace_uuid, session_id HAVING COUNT(*) > 1 LIMIT 1')
    ).first()
    if collisions:
        raise RuntimeError('Cannot downgrade bot-scoped sessions without losing colliding bot records')
    pk = sa.inspect(conn).get_pk_constraint(_TABLE)
    with op.batch_alter_table(_TABLE, naming_convention={'pk': 'pk_%(table_name)s'}) as batch:
        batch.drop_constraint(pk['name'] or f'pk_{_TABLE}', type_='primary')
        batch.create_primary_key(f'pk_{_TABLE}', ['workspace_uuid', 'session_id'])
