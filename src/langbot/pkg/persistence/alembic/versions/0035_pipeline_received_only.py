"""Narrow legacy Pipeline wildcard routes to incoming messages."""

import json

from alembic import op
import sqlalchemy as sa

revision = '0035_pipeline_received_only'
down_revision = '0034_monitoring_execution_links'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if not sa.inspect(connection).has_table('bots'):
        return
    bots = sa.table('bots', sa.column('uuid', sa.String()), sa.column('event_bindings', sa.JSON()))
    for bot_uuid, bindings in connection.execute(sa.select(bots.c.uuid, bots.c.event_bindings)).all():
        if isinstance(bindings, str):
            bindings = json.loads(bindings)
        if not isinstance(bindings, list):
            continue
        changed = False
        for binding in bindings:
            if (
                isinstance(binding, dict)
                and binding.get('target_type') == 'pipeline'
                and binding.get('event_pattern') == 'message.*'
            ):
                binding['event_pattern'] = 'message.received'
                changed = True
        if changed:
            connection.execute(bots.update().where(bots.c.uuid == bot_uuid).values(event_bindings=bindings))


def downgrade():
    # An exact incoming-message route remains valid with older versions.
    pass
