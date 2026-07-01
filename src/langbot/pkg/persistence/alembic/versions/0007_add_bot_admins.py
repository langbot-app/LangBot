"""add bot_admins table and migrate config admins

Revision ID: 0007_add_bot_admins
Revises: 0006_normalize_mcp_remote_mode
Create Date: 2026-06-26
"""

import sqlalchemy as sa
from alembic import op

revision = '0007_add_bot_admins'
down_revision = '0006_normalize_mcp_remote_mode'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if 'bot_admins' in sa.inspect(conn).get_table_names():
        return
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

    import json

    try:
        cfg = json.loads(meta_row[0])
    except Exception:
        return

    admins = cfg.get('admins', [])
    for entry in admins:
        parts = entry.split('_', 1)
        if len(parts) != 2:
            continue
        launcher_type, launcher_id = parts
        try:
            conn.execute(
                sa.text(
                    'INSERT OR IGNORE INTO bot_admins (bot_uuid, launcher_type, launcher_id) VALUES (:bu, :lt, :li)'
                ),
                {'bu': first_bot_uuid, 'lt': launcher_type, 'li': launcher_id},
            )
        except Exception:
            pass

    # Remove admins key from stored config
    if 'admins' in cfg:
        del cfg['admins']
        conn.execute(
            sa.text("UPDATE metadata SET value = :v WHERE key = 'instance_config'"),
            {'v': json.dumps(cfg)},
        )


def downgrade() -> None:
    op.drop_table('bot_admins')
