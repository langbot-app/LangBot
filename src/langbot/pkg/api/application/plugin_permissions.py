"""Installation-scoped plugin declarations, grants and request identities."""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy
from langbot_plugin.api.entities.permissions import PluginPermissions

from ...entity.persistence.plugin import PluginSetting
from ...utils import constants
from ..authz import Permission, has_permission, require_permission
from ..context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from .contracts import ApplicationAPIError, ApplicationAPIException
from .operation_docs import DOMAINS, get_operation_doc
from .plugin_capabilities import CAPABILITY_PERMISSIONS, DANGEROUS_CAPABILITIES, LEGACY_CAPABILITIES
from .tool_grants import validate_grant_change


def fail(code: str, message: str, **details: Any):
    from ...i18n import error_text

    raise ApplicationAPIException(
        ApplicationAPIError(
            code,
            error_text(code, message),
            403 if code == 'permission_denied' else 404 if code == 'not_found' else 400,
            details or None,
        )
    )


async def warn_compatibility(ap, workspace_uuid: str, plugin_id: str) -> None:
    from ...i18n import t
    from ...i18n.workspace import get_workspace_language

    locale = await get_workspace_language(ap, workspace_uuid)
    ap.logger.warning(
        t(
            'Plugin {plugin} has no permission declaration. Review compatibility access in plugin settings.',
            locale=locale,
            plugin=plugin_id,
        )
    )


def read_declaration(manifest: dict) -> dict | None:
    spec = manifest.get('spec', {})
    if 'permissions' not in spec:
        return None
    return PluginPermissions.model_validate(spec['permissions']).model_dump()


def expand_declaration(ap, declaration: dict | None) -> dict:
    if declaration is None:
        return {'workspace_operations': [], 'capabilities': sorted(LEGACY_CAPABILITIES)}
    parsed = PluginPermissions.model_validate(declaration)
    app_api = getattr(ap, 'application_api', None)
    if app_api is None:
        from .api import ApplicationAPI

        app_api = ApplicationAPI(ap)
    operations = app_api._operations
    expanded = set()
    for pattern in parsed.workspace_operations:
        if pattern.endswith('.*') and '*' not in pattern[:-2]:
            matching = [name for name in operations if name.startswith(pattern[:-1])]
            if not matching:
                fail('invalid_input', 'Unknown workspace operation domain', invalid_operations=[pattern])
            expanded.update(matching)
        elif '*' in pattern:
            fail('invalid_input', 'Invalid workspace operation wildcard', invalid_operations=[pattern])
        else:
            expanded.add(pattern)
    for name in sorted(expanded):
        operation = operations.get(name)
        if (
            operation is None
            or operation.streaming
            or (operation.principals is not None and PrincipalType.PLUGIN not in operation.principals)
            or get_operation_doc(name, side_effect=operation.side_effect).exposure != 'all'
        ):
            fail('invalid_input', 'Invalid plugin workspace operation', invalid_operations=[name])
    return {'workspace_operations': sorted(expanded), 'capabilities': sorted(set(parsed.capabilities))}


def effective_grants(ap, setting) -> dict:
    declaration = expand_declaration(ap, setting.permission_declaration)
    grants = setting.permission_grants
    if grants is None:
        grants = {'workspace_operations': [], 'capabilities': sorted(LEGACY_CAPABILITIES)}
    return {
        key: sorted(set(grants.get(key, ())) & set(declaration[key]))
        for key in ('workspace_operations', 'capabilities')
    }


def permission_status(ap, setting) -> dict:
    declaration = expand_declaration(ap, setting.permission_declaration)
    snapshot = setting.permission_snapshot
    return {
        'compatibility_mode': setting.permission_declaration is None,
        'pending_confirmation': snapshot is None
        or any(set(declaration[key]) - set(snapshot.get(key, ())) for key in declaration),
    }


async def workspace_operation_grants(ap, context) -> dict[str, list[str]]:
    result = await ap.persistence_mgr.execute_async(
        sqlalchemy.select(PluginSetting).where(PluginSetting.workspace_uuid == context.workspace_uuid)
    )
    grants = {}
    for row in result:
        setting = row[0] if isinstance(row[0], PluginSetting) else PluginSetting(**dict(row._mapping))
        grants[f'{setting.plugin_author}/{setting.plugin_name}'] = (
            effective_grants(ap, setting)['workspace_operations'] if setting.enabled else []
        )
    return grants


async def load_installation(ap, workspace_uuid: str, installation_uuid: str):
    result = await ap.persistence_mgr.execute_async(
        sqlalchemy.select(PluginSetting).where(
            PluginSetting.workspace_uuid == workspace_uuid,
            PluginSetting.installation_uuid == installation_uuid,
        )
    )
    row = result.first()
    if row is None:
        fail('not_found', 'Plugin installation not found')
    if isinstance(row[0], PluginSetting):
        return row[0]
    return PluginSetting(**dict(row._mapping))


async def installation_context(ap, binding, *, run_id: str | None = None) -> RequestContext:
    setting = await load_installation(ap, binding.workspace_uuid, binding.installation_uuid)
    if not setting.enabled:
        fail('permission_denied', 'Plugin installation is not enabled')
    if setting.runtime_revision != binding.runtime_revision or setting.artifact_digest != binding.artifact_digest:
        fail('permission_denied', 'Plugin installation binding is stale')
    grants = effective_grants(ap, setting)
    permissions = {ap.application_api._operations[name].permission for name in grants['workspace_operations']}
    for capability in grants['capabilities']:
        permissions.update(CAPABILITY_PERMISSIONS[capability])
    return RequestContext(
        instance_uuid=binding.instance_uuid,
        placement_generation=binding.placement_generation,
        request_id=str(uuid.uuid4()),
        auth_type='plugin',
        principal=PrincipalContext(
            principal_type=PrincipalType.PLUGIN,
            installation_uuid=binding.installation_uuid,
            run_id=run_id,
        ),
        workspace=WorkspaceContext(binding.workspace_uuid, None, None, frozenset(permissions)),
        allowed_operation_ids=frozenset(grants['workspace_operations']),
    )


async def authorize_action(ap, binding, action: str, data: dict) -> None:
    from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
    from .plugin_capabilities import ACTION_CAPABILITIES, APPLICATION_ACTIONS, BINARY_STORAGE_ACTIONS, CONTEXT_ACTIONS

    setting = await load_installation(ap, binding.workspace_uuid, binding.installation_uuid)
    if not setting.enabled:
        fail('permission_denied', 'Plugin installation is not enabled')
    if action in CONTEXT_ACTIONS or action in APPLICATION_ACTIONS:
        return
    if data.get('bot_uuid') == constants.WEBSOCKET_PROXY_BOT_UUID:
        # The debug proxy bot is in-memory only and never has a ``bots`` row;
        # it is available exactly when this Workspace has a live proxy.
        if not ap.platform_mgr.has_websocket_proxy_bot(binding.workspace_uuid):
            fail('permission_denied', 'Bot is not available in this Workspace')
    elif data.get('bot_uuid'):
        from ...entity.persistence.bot import Bot

        result = await ap.persistence_mgr.execute_async(
            sqlalchemy.select(Bot.uuid).where(
                Bot.uuid == data['bot_uuid'], Bot.workspace_uuid == binding.workspace_uuid
            )
        )
        if result.first() is None:
            fail('permission_denied', 'Bot is not available in this Workspace')
    if action == PluginToRuntimeAction.CALL_PLATFORM_API.value and data.get('run_id') and data.get('context_tool'):
        from ...agent.runner.platform_tools import PLATFORM_TOOLS_BY_NAME

        definition = PLATFORM_TOOLS_BY_NAME.get(data['context_tool'])
        if definition is not None and definition.scope == 'event':
            return
    capability = ACTION_CAPABILITIES.get(action)
    if action == PluginToRuntimeAction.CALL_PLATFORM_API.value and data.get('action') == 'send_message':
        capability = 'bot.message.send'
    if action == PluginToRuntimeAction.LIST_TOOLS.value:
        if not set(effective_grants(ap, setting)['capabilities']) & {'plugin_tools', 'mcp', 'sandbox'}:
            fail('permission_denied', 'No tool capabilities have been granted')
        return
    if action in BINARY_STORAGE_ACTIONS:
        capability = 'storage.workspace' if data.get('owner_type') == 'workspace' else 'storage.plugin'
    if action in {PluginToRuntimeAction.CALL_TOOL.value, PluginToRuntimeAction.GET_TOOL_DETAIL.value}:
        execution = ap.plugin_connector._runtime_handler()._execution_context(binding)
        catalog = await ap.tool_mgr.get_resolved_tool_catalog(execution, include_mcp_resource_tools=True)
        tool = next((item for item in catalog if item['name'] == data.get('tool_name')), None)
        if tool is None and data.get('run_id'):
            from ...agent.runner.platform_tools import PLATFORM_TOOLS_BY_NAME

            definition = PLATFORM_TOOLS_BY_NAME.get(data.get('tool_name'))
            if definition is not None:
                if definition.scope == 'event':
                    return
                capability = 'bot.message.send' if definition.api == 'send_message' else 'bot.platform_api'
                if capability not in effective_grants(ap, setting)['capabilities']:
                    fail(
                        'permission_denied', 'Plugin capability has not been granted', denied_capabilities=[capability]
                    )
                data['_permission_tool_source'] = {'source': 'platform', 'source_id': definition.name}
                return
        if tool is None:
            fail('not_found', 'Tool not found')
        # Native and builtin both name the sandbox tool loader (see ToolManager).
        capability = {
            'plugin': 'plugin_tools',
            'mcp': 'mcp',
            'builtin': 'sandbox',
            'native': 'sandbox',
            'skill': 'sandbox',
        }.get(tool['source'])
        data['_permission_tool_source'] = {key: tool[key] for key in ('source', 'source_id') if key in tool}
    if capability is None:
        fail('permission_denied', 'Plugin action has no capability mapping')
    if capability not in effective_grants(ap, setting)['capabilities']:
        fail('permission_denied', 'Plugin capability has not been granted', denied_capabilities=[capability])


def describe_permissions(ap, context, setting) -> dict:
    declaration = expand_declaration(ap, setting.permission_declaration)
    grants = effective_grants(ap, setting)
    snapshot = setting.permission_snapshot
    can_grant = context.principal.principal_type in {PrincipalType.ACCOUNT, PrincipalType.SUPPORT_ADMIN}
    rows = []
    domains = set()
    for category, names in declaration.items():
        for name in names:
            extra = {}
            if category == 'workspace_operations':
                spec = ap.application_api._operations[name]
                required = frozenset({spec.permission})
                doc = get_operation_doc(name, side_effect=spec.side_effect)
                risk = doc.risk
                label = doc.label
                extra = {'domain': doc.domain, 'summary': doc.summary}
                domains.add(doc.domain)
            else:
                label = None
                required = CAPABILITY_PERMISSIONS[name]
                risk = (
                    'dangerous' if name in DANGEROUS_CAPABILITIES else 'write' if name == 'bot.message.send' else 'read'
                )
            rows.append(
                {
                    'id': name,
                    'category': category,
                    'label': label,
                    'required_permissions': sorted(required),
                    'risk': risk,
                    'granted': name in grants[category],
                    'grantable': can_grant
                    and has_permission(context, Permission.RESOURCE_MANAGE)
                    and all(has_permission(context, permission) for permission in required),
                    **extra,
                }
            )
    return {
        'can_manage': has_permission(context, Permission.RESOURCE_MANAGE),
        'can_confirm': can_grant and has_permission(context, Permission.RESOURCE_MANAGE),
        'installation_uuid': setting.installation_uuid,
        'compatibility_mode': setting.permission_declaration is None,
        'pending_confirmation': snapshot is None
        or any(set(declaration[key]) - set(snapshot.get(key, ())) for key in declaration),
        'enabled': setting.enabled,
        'grants': grants,
        'permissions': rows,
        'domains': [
            {
                'domain': domain,
                'label': DOMAINS.get(domain, {}).get('label', {'zh_Hans': domain, 'en_US': domain.capitalize()}),
            }
            for domain in sorted(domains)
        ],
    }


async def change_permissions(ap, context, setting, *, workspace_operations, capabilities, confirm: bool) -> dict:
    require_permission(context, Permission.RESOURCE_MANAGE)
    declaration = expand_declaration(ap, setting.permission_declaration)
    old = effective_grants(ap, setting)
    requested = {'workspace_operations': workspace_operations, 'capabilities': capabilities}
    for key in requested:
        if not isinstance(requested[key], list) or any(not isinstance(item, str) for item in requested[key]):
            fail('invalid_input', 'Permission grants must be lists of strings')
        if set(requested[key]) - set(declaration[key]):
            fail('invalid_input', 'Permission is not declared by the plugin', **{f'invalid_{key}': requested[key]})
        if not confirm and set(requested[key]) - set(old[key]):
            fail('permission_denied', 'Adding grants requires confirmation')
    if confirm:
        if context.principal.principal_type not in {PrincipalType.ACCOUNT, PrincipalType.SUPPORT_ADMIN}:
            fail('permission_denied', 'Only a member can confirm plugin permissions')
        if setting.permission_declaration is None and any(
            set(requested[key]) != set(declaration[key]) for key in requested
        ):
            fail('invalid_input', 'Compatibility confirmation requires all legacy capabilities')
    validate_grant_change(
        ap,
        context,
        [] if confirm and setting.permission_declaration is None else old['workspace_operations'],
        workspace_operations,
        old_capabilities=[] if confirm and setting.permission_declaration is None else old['capabilities'],
        new_capabilities=capabilities,
        principal_type=PrincipalType.PLUGIN,
    )
    values = {'permission_grants': {key: sorted(set(value)) for key, value in requested.items()}}
    if confirm:
        values.update(permission_snapshot=declaration, enabled=True)
    result = await ap.persistence_mgr.execute_async(
        sqlalchemy.update(PluginSetting)
        .where(
            PluginSetting.workspace_uuid == context.workspace_uuid,
            PluginSetting.installation_uuid == setting.installation_uuid,
            PluginSetting.runtime_revision == setting.runtime_revision,
        )
        .values(**values)
    )
    if result.rowcount != 1:
        fail('invalid_input', 'Plugin changed; reload its permissions before confirming')
    for key, value in values.items():
        setattr(setting, key, value)
    if confirm:
        await ap.plugin_connector.activate_permission_installation(context, setting)
    return describe_permissions(ap, context, setting)


async def auto_confirm_declared(ap, context, setting) -> dict:
    declaration = expand_declaration(ap, setting.permission_declaration)
    validate_grant_change(
        ap,
        context,
        [],
        declaration['workspace_operations'],
        new_capabilities=declaration['capabilities'],
        principal_type=PrincipalType.PLUGIN,
    )
    return await change_permissions(ap, context, setting, **declaration, confirm=True)
