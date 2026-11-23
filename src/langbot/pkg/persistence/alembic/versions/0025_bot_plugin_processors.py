"""Separate plugin processor subscriptions from exclusive bot event routes."""

from alembic import op
import sqlalchemy as sa

revision = '0025_bot_plugin_processors'
down_revision = '0024_unify_runner_state'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('bots'):
        return
    if 'plugin_processors' not in {column['name'] for column in inspector.get_columns('bots')}:
        op.add_column('bots', sa.Column('plugin_processors', sa.JSON(), nullable=False, server_default='[]'))
    bots = sa.table(
        'bots',
        sa.column('uuid', sa.String()),
        sa.column('event_bindings', sa.JSON()),
        sa.column('plugin_processors', sa.JSON()),
    )
    for row in bind.execute(sa.select(bots)).mappings():
        routes = []
        subscriptions = {item['processor_uuid']: dict(item) for item in (row['plugin_processors'] or [])}
        for route in row['event_bindings'] or []:
            if route.get('target_type') != 'event_processor':
                routes.append(route)
                continue
            processor_uuid = route.get('target_uuid')
            if not processor_uuid:
                continue
            if processor_uuid not in subscriptions:
                subscriptions[processor_uuid] = {'processor_uuid': processor_uuid, 'enabled': False}
            subscriptions[processor_uuid]['enabled'] |= bool(route.get('enabled', True))
        bind.execute(
            bots.update()
            .where(bots.c.uuid == row['uuid'])
            .values(
                event_bindings=routes,
                plugin_processors=list(subscriptions.values()),
            )
        )


def downgrade():
    # A subscription may match several events. Represent it as a wildcard route
    # when reverting, while retaining the target and enabled state.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('bots') or 'plugin_processors' not in {
        column['name'] for column in inspector.get_columns('bots')
    }:
        return
    bots = sa.table(
        'bots',
        sa.column('uuid', sa.String()),
        sa.column('event_bindings', sa.JSON()),
        sa.column('plugin_processors', sa.JSON()),
    )
    for row in bind.execute(sa.select(bots)).mappings():
        routes = list(row['event_bindings'] or [])
        for item in row['plugin_processors'] or []:
            routes.append(
                {
                    'id': f'plugin_processor:{item["processor_uuid"]}',
                    'event_pattern': '*',
                    'target_type': 'event_processor',
                    'target_uuid': item['processor_uuid'],
                    'enabled': item['enabled'],
                    'filters': [],
                    'priority': 0,
                    'order': len(routes),
                }
            )
        bind.execute(bots.update().where(bots.c.uuid == row['uuid']).values(event_bindings=routes))
    op.drop_column('bots', 'plugin_processors')
