"""Keep the previous Harness refresh hash so reuse revokes the grant family."""

import sqlalchemy as sa
from alembic import op


revision = '0062_harness_refresh_reuse'
down_revision = '0061_harness_oauth'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column['name'] for column in inspector.get_columns('harness_oauth_grants')}
    if 'previous_refresh_token_hash' not in columns:
        op.add_column(
            'harness_oauth_grants',
            sa.Column('previous_refresh_token_hash', sa.String(64), nullable=True),
        )
        op.create_index(
            'ix_harness_oauth_grants_previous_refresh_token_hash',
            'harness_oauth_grants',
            ['previous_refresh_token_hash'],
        )


def downgrade():
    op.drop_index('ix_harness_oauth_grants_previous_refresh_token_hash', table_name='harness_oauth_grants')
    op.drop_column('harness_oauth_grants', 'previous_refresh_token_hash')
