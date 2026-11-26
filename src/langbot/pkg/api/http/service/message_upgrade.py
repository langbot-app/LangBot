import json

import sqlalchemy as sa

from ....command.catalog import DESCRIPTIONS
from ....command.permissions import builtin_settings
from ....command.processor import command_name
from ....entity.persistence.bot import BotAdmin
from ....entity.persistence.metadata import WorkspaceMetadata
from ....entity.persistence.plugin import PluginSetting
from ....message_policy import schema
from ....message_policy.promotion import policy_promotion
from ....persistence.message_upgrade_report import REPORT_PREFIX
from ...application.contracts import ApplicationAPIError, ApplicationAPIException
from .tenant import require_workspace_uuid


ACK = REPORT_PREFIX + 'confirmed'
ESSENTIAL = 'langbot-team/EssentialCommands'


def conflict(code):
    return ApplicationAPIException(ApplicationAPIError(code, code, 409))


async def checks(service, context):
    ws = require_workspace_uuid(context)
    ap = service.ap
    execute = ap.persistence_mgr.execute_async
    records = {
        key: json.loads(value)
        for key, value in (
            await execute(
                sa.select(WorkspaceMetadata.key, WorkspaceMetadata.value).where(
                    WorkspaceMetadata.workspace_uuid == ws, WorkspaceMetadata.key.startswith(REPORT_PREFIX)
                )
            )
        ).all()
    }
    confirmed = set(records.get(ACK, []))
    items = []

    def add(code, params, actions=(), *identity):
        item_id = ':'.join((code, *identity))
        items.append(
            {'id': item_id, 'code': code, 'params': params, 'actions': list(actions), 'confirmed': item_id in confirmed}
        )

    plugins = {
        f'{author}/{name}'
        for author, name in (
            await execute(
                sa.select(PluginSetting.plugin_author, PluginSetting.plugin_name).where(
                    PluginSetting.workspace_uuid == ws
                )
            )
        ).all()
    }
    commands = []
    if plugins:
        await ap.plugin_connector.require_workspace_context(context)
        commands = [(cmd.owner, command_name(cmd)) for cmd in await ap.plugin_connector.list_commands()]
    conflicts = sorted({name for _, name in commands if name in DESCRIPTIONS or name == 'reset'})
    if ESSENTIAL in plugins or conflicts:
        add(
            'plugin_command_collision',
            {'essential_installed': ESSENTIAL in plugins, 'names': conflicts},
            ['uninstall_essential'] if ESSENTIAL in plugins else [],
        )
    admins = set(
        (
            await execute(
                sa.select(BotAdmin.bot_uuid).where(BotAdmin.workspace_uuid == ws, BotAdmin.launcher_type == 'person')
            )
        ).scalars()
    )
    overrides = records.get(REPORT_PREFIX + '0059', {}).get('route_overrides', [])
    enabled = records.get(REPORT_PREFIX + '0060', {}).get('enabled_plugins', {})
    prefixes = records.get(REPORT_PREFIX + 'commands', {}).get('original_prefixes', [])
    for bot in await service.get_bots(context):
        uuid = bot['uuid']
        settings = bot.get('command_settings') or {}
        default = bot.get('message_policy') or {}
        routes = bot.get('event_bindings') or []
        if any(p in prefixes and p not in settings.get('prefixes', ['/']) for p in ('!', '！')):
            add('command_prefix_changed', {'bot_uuid': uuid, 'original_prefixes': prefixes}, ['restore_prefixes'], uuid)
        admin_only = any(
            builtin_settings(settings, name)['enabled'] and builtin_settings(settings, name)['permission'] == 'admins'
            for name in DESCRIPTIONS
        )
        if (
            settings.get('enabled', True)
            and uuid not in admins
            and (admin_only or 'admins' in settings.get('plugin_permissions', {}).values())
        ):
            add('command_admin_missing', {'bot_uuid': uuid}, [], uuid)
        for plugin, scopes in enabled.get(uuid, {}).items():
            selections = {None: schema.enabled_plugins(schema.resolve_policy(default))}
            selections.update(
                {
                    route['id']: schema.enabled_plugins(schema.resolve_policy(default, route.get('policy')))
                    for route in routes
                }
            )
            scopes = [scope for scope in scopes if plugin in (selections.get(scope) or [])]
            if not scopes:
                continue
            add(
                'command_plugin_enabled',
                {'bot_uuid': uuid, 'plugin': plugin, 'scopes': scopes},
                ['remove_plugin'],
                uuid,
                plugin,
            )
        params = policy_promotion(uuid, default, routes)
        if params:
            add('equivalent_route_policies', params, ['promote_route_policy'], uuid)
        migrated = [route for route in overrides if route['bot_uuid'] == uuid]
        if migrated:
            add('chat_settings_moved', {'bot_uuid': uuid, 'routes': migrated}, [], uuid)
    return {
        'items': items,
        'reports': [
            dict(stage=key.removeprefix(REPORT_PREFIX), **value) for key, value in records.items() if key != ACK
        ],
    }


async def confirm(service, context, item_id):
    ws = require_workspace_uuid(context)
    available = [item['id'] for item in (await checks(service, context))['items']]
    if item_id is not None and item_id not in available:
        raise conflict('upgrade_check_not_current')
    ids = [item_id] if item_id is not None else available
    async with service.ap.persistence_mgr.tenant_write_uow(ws, operation='bot.upgrade.confirm') as uow:
        scoped = (WorkspaceMetadata.workspace_uuid == ws, WorkspaceMetadata.key == ACK)
        value = (
            await uow.execute(sa.select(WorkspaceMetadata.value).where(*scoped).with_for_update())
        ).scalar_one_or_none()
        confirmed = sorted(set(json.loads(value) if value else []) | set(ids))
        stmt = (
            sa.update(WorkspaceMetadata).where(*scoped)
            if value is not None
            else sa.insert(WorkspaceMetadata).values(workspace_uuid=ws, key=ACK)
        )
        await uow.execute(stmt.values(value=json.dumps(confirmed)))
    return {'confirmed': ids}


async def act(service, context, item_id, action):
    item = next((item for item in (await checks(service, context))['items'] if item['id'] == item_id), None)
    if item is None or action not in item['actions']:
        raise conflict(
            'policy_promotion_not_equivalent' if action == 'promote_route_policy' else 'upgrade_check_not_current'
        )
    params = item['params']
    if action == 'promote_route_policy':
        return await service.promote_route_policy(context, params['bot_uuid'])
    if action == 'uninstall_essential':
        await service.ap.plugin_connector.require_workspace_context(context)
        await service.ap.plugin_connector.delete_plugin(*ESSENTIAL.split('/'), delete_data=False)
    else:
        bot = await service.get_bot(context, params['bot_uuid'])
        if action == 'restore_prefixes':
            settings = bot['command_settings'] or {}
            change = {
                'command_settings': {
                    **settings,
                    'prefixes': list(dict.fromkeys([*settings.get('prefixes', ['/']), '!', '！'])),
                }
            }
        else:
            default = bot['message_policy'] or {}
            routes = bot['event_bindings'] or []
            plugin = params['plugin']

            def remove(policy):
                selection = policy['plugins']
                if not selection['enable_all']:
                    selection['plugins'] = [
                        entry for entry in selection['plugins'] if f'{entry["author"]}/{entry["name"]}' != plugin
                    ]

            old_default = schema.resolve_policy(default)
            if None in params['scopes']:
                remove(default)
            for route in routes:
                if route['id'] in params['scopes']:
                    effective = schema.resolve_policy(old_default, route.get('policy'))
                    remove(effective)
                    route.setdefault('policy', {})['plugins'] = effective['plugins']
            change = {'message_policy': default, 'event_bindings': routes}
        await service.update_bot(context, params['bot_uuid'], change)
    return {'id': item_id, 'action': action}
