"""Persist installation permission declarations and grants."""

from alembic import op
import sqlalchemy as sa

revision = '0044_plugin_permissions'
down_revision = '0043_speech_models'
branch_labels = None
depends_on = None

# Frozen from api/application/plugin_capabilities.py for pre-permission installations.
LEGACY_CAPABILITIES = [
    'bot.message.send',
    'bot.platform_api',
    'bot.read',
    'config.read',
    'knowledge.parser',
    'knowledge.read',
    'knowledge.vector',
    'langbot.info',
    'mcp',
    'models.invoke',
    'models.read',
    'plugin.read',
    'plugin_tools',
    'sandbox',
    'storage.plugin',
    'storage.workspace',
]


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('plugin_settings'):
        return
    existing = {column['name'] for column in inspector.get_columns('plugin_settings')}
    for name in ('permission_declaration', 'permission_grants', 'permission_snapshot'):
        if name not in existing:
            op.add_column('plugin_settings', sa.Column(name, sa.JSON(), nullable=True))
    settings = sa.table(
        'plugin_settings',
        sa.column('permission_grants', sa.JSON()),
        sa.column('permission_snapshot', sa.JSON()),
    )
    legacy = {'workspace_operations': [], 'capabilities': LEGACY_CAPABILITIES}
    op.get_bind().execute(
        settings.update()
        .where(
            sa.or_(settings.c.permission_grants.is_(None), sa.cast(settings.c.permission_grants, sa.String) == 'null')
        )
        .values(permission_grants=legacy, permission_snapshot=legacy)
    )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('plugin_settings'):
        return
    existing = {column['name'] for column in inspector.get_columns('plugin_settings')}
    for name in ('permission_snapshot', 'permission_grants', 'permission_declaration'):
        if name in existing:
            op.drop_column('plugin_settings', name)
