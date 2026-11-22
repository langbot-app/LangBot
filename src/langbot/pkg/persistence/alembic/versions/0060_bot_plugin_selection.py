"""Move listener and command selection to bot and route policies."""

import logging

from alembic import op
import sqlalchemy as sa

from langbot.pkg.command.processor import COMMAND_PROCESSOR_KIND, plugin_id_from_component_ref
from langbot.pkg.pipeline.extension_preferences import normalize_extension_preferences

revision = '0060_bot_plugin_selection'
down_revision = '0059_bot_message_policy'
branch_labels = None
depends_on = None


def _selection(all_plugins, names):
    return {'enable_all': all_plugins, 'plugins': [dict(zip(('author', 'name'), name.split('/', 1))) for name in names]}


def _migrate(bot, preferences, instances):
    routes = bot['event_bindings'] or []
    commands = {}
    settings = bot['command_settings'] or {}
    for item in [*settings.get('plugins', []), *settings.get('processors', [])]:
        plugin = item.get('plugin_id') or instances.get((bot['workspace_uuid'], item.get('processor_uuid')))
        if not plugin and item.get('author') and item.get('name'):
            plugin = f'{item["author"]}/{item["name"]}'
        if plugin:
            commands[plugin] = None
    route_sets = []
    union = {}
    enable_all = False
    for route in routes:
        key = (bot['workspace_uuid'], route.get('target_uuid'))
        if route.get('target_type') != 'pipeline' or key not in preferences:
            continue
        prefs = preferences[key]
        names = dict.fromkeys(f'{item["author"]}/{item["name"]}' for item in prefs['plugins'])
        route_sets.append((route, prefs['enable_all_plugins'], names))
        enable_all |= prefs['enable_all_plugins']
        union.update(names)
    added = set()

    def selection(all_plugins, names):
        if not all_plugins:
            added.update(commands.keys() - names.keys())
            names = names | commands
        return _selection(all_plugins, names)

    default = selection(enable_all, union)
    for route, all_plugins, names in route_sets:
        override = selection(all_plugins, names)
        if override != default:
            route.setdefault('policy', {})['plugins'] = override
    if added:
        logging.getLogger(__name__).info('Bot %s enabled command plugins: %s', bot['uuid'], ', '.join(sorted(added)))
    return {**(bot['message_policy'] or {}), 'plugins': default}, routes


def upgrade():
    bind = op.get_bind()
    metadata = sa.MetaData()
    if not sa.inspect(bind).has_table('bots'):
        return
    bots = sa.Table('bots', metadata, autoload_with=bind)
    agents = sa.Table('agents', metadata, autoload_with=bind)
    pipelines = sa.Table('legacy_pipelines', metadata, autoload_with=bind)
    instances = {
        (workspace, uuid): plugin_id_from_component_ref(ref)
        for workspace, uuid, ref in bind.execute(
            sa.select(agents.c.workspace_uuid, agents.c.uuid, agents.c.component_ref).where(
                agents.c.kind == COMMAND_PROCESSOR_KIND
            )
        )
    }
    preferences = {
        (workspace, uuid): normalize_extension_preferences(prefs)
        for workspace, uuid, prefs in bind.execute(
            sa.select(
                pipelines.c.workspace_uuid,
                pipelines.c.uuid,
                pipelines.c.get('extensions_preferences', sa.literal({}, type_=sa.JSON())),
            )
        )
    }
    for row in (
        bind.execute(
            sa.select(
                bots.c.uuid,
                bots.c.workspace_uuid,
                bots.c.event_bindings,
                bots.c.command_settings,
                bots.c.message_policy,
            )
        )
        .mappings()
        .all()
    ):
        policy, routes = _migrate(row, preferences, instances)
        bind.execute(
            bots.update()
            .where(bots.c.uuid == row['uuid'], bots.c.workspace_uuid == row['workspace_uuid'])
            .values(message_policy=policy, event_bindings=routes)
        )


def downgrade():
    bind = op.get_bind()
    if not sa.inspect(bind).has_table('bots'):
        return
    bots = sa.Table('bots', sa.MetaData(), autoload_with=bind)
    for row in (
        bind.execute(sa.select(bots.c.uuid, bots.c.workspace_uuid, bots.c.message_policy, bots.c.event_bindings))
        .mappings()
        .all()
    ):
        policy = row['message_policy'] or {}
        policy.pop('plugins', None)
        routes = row['event_bindings'] or []
        for route in routes:
            override = route.get('policy')
            if isinstance(override, dict) and 'plugins' in override:
                del override['plugins']
                if not override:
                    del route['policy']
        bind.execute(
            bots.update()
            .where(bots.c.uuid == row['uuid'], bots.c.workspace_uuid == row['workspace_uuid'])
            .values(message_policy=policy, event_bindings=routes)
        )
