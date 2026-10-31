"""Add command_settings to bots table and migrate global command config.

Revision ID: 0043_bot_command_settings
Revises: 0042_sqlite_incremental_vacuum
Create Date: 2026-10-31
"""

from __future__ import annotations

import json
from alembic import op
import sqlalchemy as sa

revision = '0043_bot_command_settings'
down_revision = '0042_sqlite_incremental_vacuum'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'bots' not in tables:
        return

    existing_columns = {column['name'] for column in inspector.get_columns('bots')}
    if 'command_settings' not in existing_columns:
        with op.batch_alter_table('bots') as batch_op:
            batch_op.add_column(
                sa.Column(
                    'command_settings',
                    sa.JSON(),
                    nullable=False,
                    server_default='{"enabled": true, "prefixes": ["/"], "plugins": []}',
                )
            )

    # Read old global config from metadata.instance_config if available
    old_enabled = True
    old_prefixes = ['/']

    if 'metadata' in tables:
        meta_row = conn.execute(sa.text("SELECT value FROM metadata WHERE key = 'instance_config'")).first()
        if meta_row and meta_row[0]:
            try:
                cfg = json.loads(meta_row[0]) if isinstance(meta_row[0], str) else meta_row[0]
                if isinstance(cfg, dict) and 'command' in cfg:
                    command_cfg = cfg['command']
                    if isinstance(command_cfg, dict):
                        old_enabled = bool(command_cfg.get('enable', True))
                        raw_prefix = command_cfg.get('prefix')
                        if isinstance(raw_prefix, list):
                            clean = [str(p) for p in raw_prefix if isinstance(p, (str, int)) and str(p).strip()]
                            old_prefixes = clean if clean else ['/']
                        elif isinstance(raw_prefix, str) and raw_prefix.strip():
                            old_prefixes = [raw_prefix.strip()]
                        else:
                            old_prefixes = ['/']

                        # Remove command.enable and command.prefix from stored instance_config
                        command_cfg.pop('enable', None)
                        command_cfg.pop('prefix', None)
                        conn.execute(
                            sa.text("UPDATE metadata SET value = :v WHERE key = 'instance_config'"),
                            {'v': json.dumps(cfg, ensure_ascii=False)},
                        )
            except Exception:
                pass

    # Write old config values into every existing bot
    bots = sa.table(
        'bots',
        sa.column('uuid', sa.String()),
        sa.column('command_settings', sa.JSON()),
    )
    conn.execute(
        bots.update().values(
            command_settings={'enabled': old_enabled, 'prefixes': old_prefixes, 'plugins': []}
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'bots' not in tables:
        return

    existing_columns = {column['name'] for column in inspector.get_columns('bots')}
    if 'command_settings' not in existing_columns:
        return

    # Try to restore global configuration using values from the first bot
    bot_cols = {c['name'] for c in sa.inspect(conn).get_columns('bots')}
    order_clause = ' ORDER BY created_at' if 'created_at' in bot_cols else ''
    row = conn.execute(sa.text(f'SELECT command_settings FROM bots{order_clause} LIMIT 1')).first()
    first_settings = None
    if row and row[0]:
        try:
            first_settings = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        except Exception:
            pass

    if 'metadata' in tables and isinstance(first_settings, dict):
        meta_row = conn.execute(sa.text("SELECT value FROM metadata WHERE key = 'instance_config'")).first()
        if meta_row and meta_row[0]:
            try:
                cfg = json.loads(meta_row[0]) if isinstance(meta_row[0], str) else meta_row[0]
                if isinstance(cfg, dict):
                    cfg.setdefault('command', {})
                    if isinstance(cfg['command'], dict):
                        cfg['command']['enable'] = bool(first_settings.get('enabled', True))
                        prefixes = first_settings.get('prefixes', ['/'])
                        cfg['command']['prefix'] = prefixes if isinstance(prefixes, list) else ['/']
                    conn.execute(
                        sa.text("UPDATE metadata SET value = :v WHERE key = 'instance_config'"),
                        {'v': json.dumps(cfg, ensure_ascii=False)},
                    )
            except Exception:
                pass

    with op.batch_alter_table('bots') as batch_op:
        batch_op.drop_column('command_settings')
