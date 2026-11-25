"""Pin immutable Skill versions without copying or owning their package bytes."""

import sqlalchemy as sa
from alembic import op

revision = '0052_artifact_skill_sources'
down_revision = '0051_artifact_publications'
branch_labels = None
depends_on = None

_SOURCE_CHECK = (
    '(source_version_id IS NULL AND source_revision IS NULL AND source_path IS NULL) OR '
    '(source_version_id IS NOT NULL AND source_revision IS NOT NULL AND source_path IS NOT NULL)'
)


def upgrade():
    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    if 'artifacts' not in tables:
        return
    columns = {column['name'] for column in sa.inspect(conn).get_columns('artifacts')}
    with op.batch_alter_table('artifacts') as batch:
        for name, length in (('source_version_id', 36), ('source_revision', 71), ('source_path', 1024)):
            if name not in columns:
                batch.add_column(sa.Column(name, sa.String(length), nullable=True))
        checks = {item['name'] for item in sa.inspect(conn).get_check_constraints('artifacts')}
        if 'ck_artifact_skill_source' not in checks:
            batch.create_check_constraint('ck_artifact_skill_source', _SOURCE_CHECK)
        if 'skill_versions' in tables:
            foreign_keys = {item['name'] for item in sa.inspect(conn).get_foreign_keys('artifacts')}
            if 'fk_artifact_skill_version' not in foreign_keys:
                batch.create_foreign_key(
                    'fk_artifact_skill_version', 'skill_versions', ['source_version_id'], ['uuid'], ondelete='RESTRICT'
                )


def downgrade():
    conn = op.get_bind()
    if 'artifacts' not in sa.inspect(conn).get_table_names():
        return
    columns = {column['name'] for column in sa.inspect(conn).get_columns('artifacts')}
    if 'source_version_id' in columns:
        # Old readers interpret content_ref as file bytes. Never silently downgrade live package refs.
        if conn.execute(sa.text('SELECT 1 FROM artifacts WHERE source_version_id IS NOT NULL LIMIT 1')).first():
            raise RuntimeError('Release and collect Skill source artifacts before downgrade')
    checks = {item['name'] for item in sa.inspect(conn).get_check_constraints('artifacts')}
    foreign_keys = {item['name'] for item in sa.inspect(conn).get_foreign_keys('artifacts')}
    with op.batch_alter_table('artifacts') as batch:
        if 'ck_artifact_skill_source' in checks:
            batch.drop_constraint('ck_artifact_skill_source', type_='check')
        if 'fk_artifact_skill_version' in foreign_keys:
            batch.drop_constraint('fk_artifact_skill_version', type_='foreignkey')
        for name in ('source_path', 'source_revision', 'source_version_id'):
            if name in columns:
                batch.drop_column(name)
