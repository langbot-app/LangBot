"""Disable the superseded shared Harness Bot while retaining its history."""

import uuid

import sqlalchemy as sa
from alembic import op

revision = '0064_harness_processor_bots'
down_revision = '0063_oauth_grants'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table('bots'):
        return
    # A legacy bots table can predate the enable/adapter columns, exactly as 0059
    # guards for; without this the select below fails instead of being a no-op.
    present = {column['name'] for column in inspector.get_columns('bots')}
    if not {'uuid', 'workspace_uuid', 'enable', 'adapter'}.issubset(present):
        return
    bots = sa.table('bots', sa.column('uuid'), sa.column('workspace_uuid'), sa.column('enable'), sa.column('adapter'))
    shared_namespace = uuid.UUID('51b0ec5e-b015-5ad0-bd7e-41405bcd0fa5')
    candidates = conn.execute(
        sa.select(bots.c.uuid, bots.c.workspace_uuid).where(
            bots.c.enable.is_(True), bots.c.adapter.in_(['harness', 'harness-omni'])
        )
    ).all()
    for bot_uuid, workspace in candidates:
        if bot_uuid == str(uuid.uuid5(shared_namespace, f'workspace/{workspace}')):
            conn.execute(
                bots.update().where(bots.c.uuid == bot_uuid, bots.c.workspace_uuid == workspace).values(enable=False)
            )


def downgrade():
    # Do not reactivate an obsolete or intentionally disabled route.
    pass
