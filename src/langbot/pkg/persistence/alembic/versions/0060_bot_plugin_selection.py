"""Move listener and command selection to bot and route policies."""

import json
import logging

from alembic import op
import sqlalchemy as sa

from langbot.pkg.command.processor import COMMAND_PROCESSOR_KIND, plugin_id_from_component_ref
from langbot.pkg.pipeline.extension_preferences import normalize_extension_preferences
from langbot.pkg.persistence.message_upgrade_report import write_report

revision = '0060_bot_plugin_selection'
down_revision = '0059_bot_message_policy'
branch_labels = None
depends_on = None


def _json(value):
    return json.loads(value) if isinstance(value, (str, bytes)) else value


def _workspace(table):
    return table.c.get('workspace_uuid', sa.literal('').label('workspace_uuid'))


def _same_row(table, row):
    condition = table.c.uuid == row['uuid']
    if 'workspace_uuid' in table.c:
        condition &= table.c.workspace_uuid == row['workspace_uuid']
    return condition


def _selection(all_plugins, names):
    return {'enable_all': all_plugins, 'plugins': [dict(zip(('author', 'name'), name.split('/', 1))) for name in names]}


def _migrate(bot, preferences, instances):
    routes = _json(bot['event_bindings']) or []
    commands = {}
    settings = _json(bot['command_settings']) or {}
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
    added = {}

    def selection(all_plugins, names, route_id):
        if not all_plugins:
            for plugin in commands.keys() - names.keys():
                added.setdefault(plugin, []).append(route_id)
            names = names | commands
        return _selection(all_plugins, names)

    default = selection(enable_all, union, None)
    for route, all_plugins, names in route_sets:
        override = selection(all_plugins, names, route.get('id'))
        if override != default:
            route.setdefault('policy', {})['plugins'] = override
    if added:
        logging.getLogger(__name__).info('Bot %s enabled command plugins: %s', bot['uuid'], ', '.join(sorted(added)))
    return {**(_json(bot['message_policy']) or {}), 'plugins': default}, routes, added


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
            sa.select(_workspace(agents), agents.c.uuid, agents.c.component_ref).where(
                agents.c.kind == COMMAND_PROCESSOR_KIND
            )
        )
    }
    preferences = {
        (workspace, uuid): normalize_extension_preferences(_json(prefs))
        for workspace, uuid, prefs in bind.execute(
            sa.select(
                _workspace(pipelines),
                pipelines.c.uuid,
                pipelines.c.get('extensions_preferences', sa.literal({}, type_=sa.JSON())),
            )
        )
    }
    reports = {}
    for row in (
        bind.execute(
            sa.select(
                bots.c.uuid,
                _workspace(bots),
                bots.c.event_bindings,
                bots.c.command_settings,
                bots.c.message_policy,
            )
        )
        .mappings()
        .all()
    ):
        policy, routes, added = _migrate(row, preferences, instances)
        if added:
            reports.setdefault(row['workspace_uuid'], {}).setdefault('enabled_plugins', {})[row['uuid']] = added
        bind.execute(bots.update().where(_same_row(bots, row)).values(message_policy=policy, event_bindings=routes))
    write_report(bind, '0060', reports)


def downgrade():
    bind = op.get_bind()
    if not sa.inspect(bind).has_table('bots'):
        return
    bots = sa.Table('bots', sa.MetaData(), autoload_with=bind)
    for row in (
        bind.execute(sa.select(bots.c.uuid, _workspace(bots), bots.c.message_policy, bots.c.event_bindings))
        .mappings()
        .all()
    ):
        policy = _json(row['message_policy']) or {}
        policy.pop('plugins', None)
        routes = _json(row['event_bindings']) or []
        for route in routes:
            override = route.get('policy')
            if isinstance(override, dict) and 'plugins' in override:
                del override['plugins']
                if not override:
                    del route['policy']
        bind.execute(bots.update().where(_same_row(bots, row)).values(message_policy=policy, event_bindings=routes))
