"""Add tenant-scoped Artifact metadata and retention references.

Revision ID: 0049_artifacts
Revises: 0048_skill_persistence
"""

import sqlalchemy as sa
from alembic import op


revision = '0049_artifacts'
down_revision = '0048_skill_persistence'
branch_labels = None
depends_on = None

_TABLES = ('artifacts', 'artifact_references')


def upgrade():
    conn = op.get_bind()
    existing = set(sa.inspect(conn).get_table_names())
    if 'workspaces' not in existing:
        return
    if 'artifacts' not in existing:
        op.create_table(
            'artifacts',
            sa.Column('id', sa.String(40), primary_key=True),
            sa.Column(
                'workspace_uuid',
                sa.String(36),
                sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
                nullable=False,
            ),
            sa.Column('owner_type', sa.String(16), nullable=False),
            sa.Column('owner_id', sa.String(36), nullable=False),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('mime_type', sa.String(255), nullable=False),
            sa.Column('size', sa.BigInteger(), nullable=False),
            sa.Column('digest', sa.String(64), nullable=False),
            sa.Column('content_ref', sa.String(80), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.UniqueConstraint('workspace_uuid', 'id', name='uq_artifacts_workspace_id'),
            sa.ForeignKeyConstraint(
                ['workspace_uuid', 'content_ref'],
                ['content_objects.workspace_uuid', 'content_objects.ref'],
                ondelete='RESTRICT',
                name='fk_artifacts_content_scope',
            ),
            sa.CheckConstraint('size >= 0', name='ck_artifacts_size'),
        )
        op.create_index('ix_artifacts_expiration', 'artifacts', ['workspace_uuid', 'deleted_at', 'expires_at'])
    if 'artifact_references' not in existing:
        op.create_table(
            'artifact_references',
            sa.Column(
                'workspace_uuid',
                sa.String(36),
                sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
                primary_key=True,
            ),
            sa.Column('artifact_id', sa.String(40), primary_key=True),
            sa.Column('holder_type', sa.String(64), primary_key=True),
            sa.Column('holder_id', sa.String(255), primary_key=True),
            sa.ForeignKeyConstraint(
                ['workspace_uuid', 'artifact_id'],
                ['artifacts.workspace_uuid', 'artifacts.id'],
                ondelete='RESTRICT',
                name='fk_artifact_references_scope',
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


def downgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    for table in reversed(_TABLES):
        if table in existing:
            op.drop_table(table)
