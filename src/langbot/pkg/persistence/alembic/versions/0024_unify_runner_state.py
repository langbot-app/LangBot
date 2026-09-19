"""Rename the persisted Runner state table without discarding development data.

Revision ID: 0024_unify_runner_state
Revises: 0023_drop_agent_enabled
"""

from alembic import op
import sqlalchemy as sa

revision = '0024_unify_runner_state'
down_revision = '0023_drop_agent_enabled'
branch_labels = None
depends_on = None


def _rename(source, target):
    tables = sa.inspect(op.get_bind()).get_table_names()
    if source in tables:
        if target in tables:
            metadata = sa.MetaData()
            source_table = sa.Table(source, metadata, autoload_with=op.get_bind())
            target_table = sa.Table(target, metadata, autoload_with=op.get_bind())
            target_count = op.get_bind().scalar(sa.select(sa.func.count()).select_from(target_table))
            source_count = op.get_bind().scalar(sa.select(sa.func.count()).select_from(source_table))
            if not target_count:
                # Startup may already have created the empty current model table.
                op.drop_table(target)
            elif not source_count:
                op.drop_table(source)
                return
            else:
                raise RuntimeError(f'Both {source} and {target} contain state; reconcile before migrating')
        op.rename_table(source, target)


def upgrade():
    _rename('agent_runner_state', 'runner_state')


def downgrade():
    _rename('runner_state', 'agent_runner_state')
