"""Persist installation permission declarations and grants."""

from alembic import op
import sqlalchemy as sa

revision = '0044_plugin_permissions'
down_revision = '0043_speech_models'
branch_labels = None
depends_on = None


def upgrade():
    existing = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('plugin_settings')}
    for name in ('permission_declaration', 'permission_grants', 'permission_snapshot'):
        if name not in existing:
            op.add_column('plugin_settings', sa.Column(name, sa.JSON(), nullable=True))


def downgrade():
    for name in ('permission_snapshot', 'permission_grants', 'permission_declaration'):
        op.drop_column('plugin_settings', name)
