"""add bot_admins table and migrate config admins

Revision ID: 0007_add_bot_admins
Revises: 0006_normalize_mcp_remote_mode
Create Date: 2026-06-26
"""

import json

import sqlalchemy as sa
from alembic import op

revision = '0007_add_bot_admins'
down_revision = '0006_normalize_mcp_remote_mode'
branch_labels = None
depends_on = None


_BOT_ADMINS = sa.table(
    'bot_admins',
    sa.column('bot_uuid', sa.String(255)),
    sa.column('launcher_type', sa.String(64)),
    sa.column('launcher_id', sa.String(255)),
)


def _upsert_admin(conn: sa.Connection, *, bot_uuid: str, launcher_type: str, launcher_id: str) -> None:
    values = {
        'bot_uuid': bot_uuid,
        'launcher_type': launcher_type,
        'launcher_id': launcher_id,
    }
    conflict_columns = [
        _BOT_ADMINS.c.bot_uuid,
        _BOT_ADMINS.c.launcher_type,
        _BOT_ADMINS.c.launcher_id,
    ]

    if conn.dialect.name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert

        statement = insert(_BOT_ADMINS).values(**values).on_conflict_do_nothing(index_elements=conflict_columns)
    elif conn.dialect.name == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert

        statement = insert(_BOT_ADMINS).values(**values).on_conflict_do_nothing(index_elements=conflict_columns)
    else:
        existing = conn.execute(
            sa.select(sa.literal(1))
            .select_from(_BOT_ADMINS)
            .where(
                _BOT_ADMINS.c.bot_uuid == bot_uuid,
                _BOT_ADMINS.c.launcher_type == launcher_type,
                _BOT_ADMINS.c.launcher_id == launcher_id,
            )
            .limit(1)
        ).first()
        if existing is not None:
            return
        statement = sa.insert(_BOT_ADMINS).values(**values)

    conn.execute(statement)


def upgrade() -> None:
    conn = op.get_bind()
    if 'bot_admins' not in sa.inspect(conn).get_table_names():
        op.create_table(
            'bot_admins',
            sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            sa.Column('bot_uuid', sa.String(255), nullable=False),
            sa.Column('launcher_type', sa.String(64), nullable=False),
            sa.Column('launcher_id', sa.String(255), nullable=False),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('bot_uuid', 'launcher_type', 'launcher_id', name='uq_bot_admin'),
        )

    # Migrate old config-based admins into the first bot (best-effort)
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'bots' not in tables:
        return

    # Read the first bot uuid
    row = conn.execute(sa.text('SELECT uuid FROM bots ORDER BY created_at LIMIT 1')).first()
    if row is None:
        return
    first_bot_uuid = row[0]

    # Read instance_config metadata key that holds the admins list
    if 'metadata' not in tables:
        return
    meta_row = conn.execute(sa.text("SELECT value FROM metadata WHERE key = 'instance_config'")).first()
    if meta_row is None:
        return

    try:
        cfg = json.loads(meta_row[0])
    except (TypeError, json.JSONDecodeError):
        return

    admins = cfg.get('admins', [])
    if not isinstance(admins, list):
        return
    for entry in admins:
        if not isinstance(entry, str):
            continue
        parts = entry.split('_', 1)
        if len(parts) != 2:
            continue
        launcher_type, launcher_id = parts
        _upsert_admin(
            conn,
            bot_uuid=first_bot_uuid,
            launcher_type=launcher_type,
            launcher_id=launcher_id,
        )

    # Remove admins key from stored config
    if 'admins' in cfg:
        del cfg['admins']
        conn.execute(
            sa.text("UPDATE metadata SET value = :v WHERE key = 'instance_config'"),
            {'v': json.dumps(cfg)},
        )


def downgrade() -> None:
    if 'bot_admins' in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table('bot_admins')
