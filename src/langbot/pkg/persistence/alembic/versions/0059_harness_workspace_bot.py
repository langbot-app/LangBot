"""Retire per-processor Harness projections without deleting history references."""

import uuid

import sqlalchemy as sa
from alembic import op

revision = '0059_harness_workspace_bot'
down_revision = '0058_harness_instance_keys'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    if not sa.inspect(conn).has_table('bots'):
        return
    bots = sa.Table('bots', sa.MetaData(), autoload_with=conn)
    if not {'adapter', 'workspace_uuid', 'uuid', 'enable'}.issubset(bots.c.keys()):
        return
    candidates = conn.execute(sa.select(bots).where(bots.c.adapter.in_(['harness', 'harness-omni']))).mappings().all()
    for workspace in sorted({row['workspace_uuid'] for row in candidates}):
        shared = str(uuid.uuid5(uuid.UUID('51b0ec5e-b015-5ad0-bd7e-41405bcd0fa5'), f'workspace/{workspace}'))
        retired = [row for row in candidates if row['workspace_uuid'] == workspace and row['uuid'] != shared]
        if not retired:
            continue
        existing = conn.execute(sa.select(bots.c.adapter, bots.c.workspace_uuid).where(bots.c.uuid == shared)).first()
        if existing is not None and (existing.adapter != 'harness-omni' or existing.workspace_uuid != workspace):
            raise RuntimeError('Workspace Harness Bot UUID collision')
        if existing is None and any(row['enable'] for row in retired):
            conn.execute(
                bots.insert().values(
                    uuid=shared,
                    workspace_uuid=workspace,
                    adapter='harness-omni',
                    name='LangBot Harness',
                    description='Managed by LangBot Harness.',
                    adapter_config={},
                    event_bindings=[],
                    plugin_processors=[],
                    enable=True,
                )
            )
        conn.execute(
            bots.update()
            .where(bots.c.uuid.in_([row['uuid'] for row in retired]))
            .values(
                enable=False,
                event_bindings=[],
                plugin_processors=[],
            )
        )


def downgrade():
    # Do not recreate revoked routes or delete Bots now referenced by history.
    pass
