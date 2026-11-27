"""Keep run origins private while allowing named managers and expiring read leases.

Revision ID: 0050_artifact_managers
Revises: 0049_artifacts
"""

import sqlalchemy as sa
from alembic import op


revision = '0050_artifact_managers'
down_revision = '0049_artifacts'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    if 'artifacts' in tables:
        columns = {column['name'] for column in sa.inspect(conn).get_columns('artifacts')}
        for name, length in (('manager_type', 16), ('manager_id', 36)):
            if name not in columns:
                op.add_column('artifacts', sa.Column(name, sa.String(length), nullable=True))
    if 'artifact_references' in tables:
        columns = {column['name'] for column in sa.inspect(conn).get_columns('artifact_references')}
        if 'expires_at' not in columns:
            op.add_column('artifact_references', sa.Column('expires_at', sa.DateTime(), nullable=True))
        constraints = {
            constraint['name'] for constraint in sa.inspect(conn).get_check_constraints('artifact_references')
        }
        if 'ck_artifact_reference_lease_kind' not in constraints:
            with op.batch_alter_table('artifact_references') as batch:
                batch.create_check_constraint(
                    'ck_artifact_reference_lease_kind', "expires_at IS NULL OR holder_type = 'read_lease'"
                )
    # Legacy run-output commits retain their private origin and pin; no manager can be inferred safely.


def downgrade():
    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    if 'artifact_references' in tables:
        columns = {column['name'] for column in sa.inspect(conn).get_columns('artifact_references')}
        constraints = {
            constraint['name'] for constraint in sa.inspect(conn).get_check_constraints('artifact_references')
        }
        if 'ck_artifact_reference_lease_kind' in constraints:
            with op.batch_alter_table('artifact_references') as batch:
                batch.drop_constraint('ck_artifact_reference_lease_kind', type_='check')
        if 'expires_at' in columns:
            op.drop_column('artifact_references', 'expires_at')
    if 'artifacts' in tables:
        columns = {column['name'] for column in sa.inspect(conn).get_columns('artifacts')}
        for name in ('manager_id', 'manager_type'):
            if name in columns:
                op.drop_column('artifacts', name)
