"""add monitoring traces and spans

Revision ID: 0006_monitoring_traces
Revises: 0005_add_llm_context_length
Create Date: 2026-06-16
"""

import sqlalchemy as sa
from alembic import op

revision = '0006_monitoring_traces'
down_revision = '0005_add_llm_context_length'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if 'monitoring_traces' not in tables:
        op.create_table(
            'monitoring_traces',
            sa.Column('trace_id', sa.String(length=255), nullable=False),
            sa.Column('started_at', sa.DateTime(), nullable=False),
            sa.Column('ended_at', sa.DateTime(), nullable=True),
            sa.Column('duration', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('bot_id', sa.String(length=255), nullable=True),
            sa.Column('bot_name', sa.String(length=255), nullable=True),
            sa.Column('pipeline_id', sa.String(length=255), nullable=True),
            sa.Column('pipeline_name', sa.String(length=255), nullable=True),
            sa.Column('session_id', sa.String(length=255), nullable=True),
            sa.Column('message_id', sa.String(length=255), nullable=True),
            sa.Column('query_id', sa.String(length=255), nullable=True),
            sa.Column('attributes', sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint('trace_id'),
        )
        op.create_index('ix_monitoring_traces_started_at', 'monitoring_traces', ['started_at'])
        op.create_index('ix_monitoring_traces_ended_at', 'monitoring_traces', ['ended_at'])
        op.create_index('ix_monitoring_traces_status', 'monitoring_traces', ['status'])
        op.create_index('ix_monitoring_traces_bot_id', 'monitoring_traces', ['bot_id'])
        op.create_index('ix_monitoring_traces_pipeline_id', 'monitoring_traces', ['pipeline_id'])
        op.create_index('ix_monitoring_traces_session_id', 'monitoring_traces', ['session_id'])
        op.create_index('ix_monitoring_traces_message_id', 'monitoring_traces', ['message_id'])
        op.create_index('ix_monitoring_traces_query_id', 'monitoring_traces', ['query_id'])

    if 'monitoring_spans' not in tables:
        op.create_table(
            'monitoring_spans',
            sa.Column('span_id', sa.String(length=255), nullable=False),
            sa.Column('trace_id', sa.String(length=255), nullable=False),
            sa.Column('parent_span_id', sa.String(length=255), nullable=True),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('kind', sa.String(length=80), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('started_at', sa.DateTime(), nullable=False),
            sa.Column('ended_at', sa.DateTime(), nullable=True),
            sa.Column('duration', sa.Integer(), nullable=True),
            sa.Column('message_id', sa.String(length=255), nullable=True),
            sa.Column('session_id', sa.String(length=255), nullable=True),
            sa.Column('bot_id', sa.String(length=255), nullable=True),
            sa.Column('pipeline_id', sa.String(length=255), nullable=True),
            sa.Column('attributes', sa.Text(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint('span_id'),
        )
        op.create_index('ix_monitoring_spans_trace_id', 'monitoring_spans', ['trace_id'])
        op.create_index('ix_monitoring_spans_parent_span_id', 'monitoring_spans', ['parent_span_id'])
        op.create_index('ix_monitoring_spans_kind', 'monitoring_spans', ['kind'])
        op.create_index('ix_monitoring_spans_status', 'monitoring_spans', ['status'])
        op.create_index('ix_monitoring_spans_started_at', 'monitoring_spans', ['started_at'])
        op.create_index('ix_monitoring_spans_message_id', 'monitoring_spans', ['message_id'])
        op.create_index('ix_monitoring_spans_session_id', 'monitoring_spans', ['session_id'])
        op.create_index('ix_monitoring_spans_bot_id', 'monitoring_spans', ['bot_id'])
        op.create_index('ix_monitoring_spans_pipeline_id', 'monitoring_spans', ['pipeline_id'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if 'monitoring_spans' in tables:
        op.drop_table('monitoring_spans')
    if 'monitoring_traces' in tables:
        op.drop_table('monitoring_traces')
