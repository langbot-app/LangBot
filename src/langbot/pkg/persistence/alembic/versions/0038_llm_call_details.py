"""Persist additive LLM timing, usage and structured failure diagnostics."""

from alembic import op
import sqlalchemy as sa

revision = '0038_llm_call_details'
down_revision = '0037_metadata_text'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('monitoring_llm_calls'):
        columns = {column['name'] for column in inspector.get_columns('monitoring_llm_calls')}
        if 'details' not in columns:
            op.add_column('monitoring_llm_calls', sa.Column('details', sa.JSON(), nullable=True))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('monitoring_llm_calls'):
        columns = {column['name'] for column in inspector.get_columns('monitoring_llm_calls')}
        if 'details' in columns:
            op.drop_column('monitoring_llm_calls', 'details')
