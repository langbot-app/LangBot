"""Persist Skill publications and immutable database/S3 content.

Revision ID: 0048_skill_persistence
Revises: 0047_workspace_alerts
"""

import sqlalchemy as sa
from alembic import op


revision = '0048_skill_persistence'
down_revision = '0047_workspace_alerts'
branch_labels = None
depends_on = None

_TABLES = ('content_objects', 'content_aliases', 'skill_registry', 'skill_versions')


def _workspace(*, primary_key=False):
    return sa.Column(
        'workspace_uuid',
        sa.String(36),
        sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
        primary_key=primary_key,
    )


def _created():
    return sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now())


def upgrade():
    conn = op.get_bind()
    existing = set(sa.inspect(conn).get_table_names())
    if 'workspaces' not in existing:
        return
    if 'content_objects' not in existing:
        op.create_table(
            'content_objects',
            sa.Column('ref', sa.String(80), primary_key=True),
            _workspace(),
            sa.Column('public_media', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('public_key', sa.String(255), nullable=True),
            sa.Column('owner_type', sa.String(64), nullable=False),
            sa.Column('owner', sa.String(255), nullable=False),
            sa.Column('key', sa.Text(), nullable=False),
            sa.Column('digest', sa.String(64), nullable=False),
            sa.Column('size', sa.BigInteger(), nullable=False),
            sa.Column('backend', sa.String(128), nullable=False),
            sa.Column('locator', sa.JSON(), nullable=True),
            sa.Column('value', sa.LargeBinary(), nullable=True),
            _created(),
            sa.UniqueConstraint('workspace_uuid', 'ref', name='uq_content_objects_workspace_ref'),
            sa.CheckConstraint('size >= 0', name='ck_content_objects_size'),
        )
        op.create_index('ix_content_objects_workspace', 'content_objects', ['workspace_uuid'])
        op.create_index('ix_content_objects_public_key', 'content_objects', ['public_key'])
    if 'content_aliases' not in existing:
        op.create_table(
            'content_aliases',
            _workspace(primary_key=True),
            sa.Column('key', sa.String(512), primary_key=True),
            sa.Column('content_ref', sa.String(80), nullable=False),
            sa.ForeignKeyConstraint(
                ['workspace_uuid', 'content_ref'],
                ['content_objects.workspace_uuid', 'content_objects.ref'],
                name='fk_content_alias_workspace_ref',
            ),
        )
    if 'skill_registry' not in existing:
        op.create_table(
            'skill_registry',
            sa.Column('uuid', sa.String(36), primary_key=True),
            _workspace(),
            sa.Column('instance_uuid', sa.String(255), nullable=False),
            sa.Column('name', sa.String(64), nullable=False),
            sa.Column('current_revision', sa.String(71), nullable=False),
            sa.Column('skill_json', sa.JSON(), nullable=False),
            _created(),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('workspace_uuid', 'instance_uuid', 'name', name='uq_skill_registry_scope_name'),
        )
    if 'skill_versions' not in existing:
        op.create_table(
            'skill_versions',
            sa.Column('uuid', sa.String(36), primary_key=True),
            _workspace(),
            sa.Column('instance_uuid', sa.String(255), nullable=False),
            sa.Column('name', sa.String(64), nullable=False),
            sa.Column('revision', sa.String(71), nullable=False),
            sa.Column('manifest_json', sa.JSON(), nullable=False),
            sa.Column('skill_json', sa.JSON(), nullable=False),
            sa.Column('content_ref', sa.String(80), nullable=False),
            _created(),
            sa.ForeignKeyConstraint(
                ['workspace_uuid', 'content_ref'],
                ['content_objects.workspace_uuid', 'content_objects.ref'],
                ondelete='RESTRICT',
                name='fk_skill_versions_content_scope',
            ),
            sa.UniqueConstraint(
                'workspace_uuid',
                'instance_uuid',
                'name',
                'revision',
                name='uq_skill_versions_scope_name_revision',
            ),
        )
    if conn.dialect.name == 'postgresql':
        tenant = "workspace_uuid::text = NULLIF(current_setting('langbot.workspace_uuid', true), '')"
        for table in _TABLES:
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'DROP POLICY IF EXISTS langbot_workspace_isolation ON "{table}"'))
            op.execute(
                sa.text(
                    f'CREATE POLICY langbot_workspace_isolation ON "{table}" USING ({tenant}) WITH CHECK ({tenant})'
                )
            )
        op.execute(sa.text('DROP POLICY IF EXISTS langbot_public_media_read ON content_objects'))
        op.execute(
            sa.text(
                'CREATE POLICY langbot_public_media_read ON content_objects FOR SELECT USING ('
                "public_media = true AND public_key::text = NULLIF(current_setting('langbot.public_media_key', true), ''))"
            )
        )


def downgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    for table in reversed(_TABLES):
        if table in existing:
            op.drop_table(table)
