"""Workspace governance and resource operations without transport dependencies."""

from __future__ import annotations

import datetime
import json
import mimetypes
import uuid
from contextlib import asynccontextmanager
from typing import Literal

import sqlalchemy
from pydantic import Field

from .contracts import Input, Operation
from ..authz import Permission, PermissionDeniedError
from ..context import ExecutionContext, PrincipalType
from ..secrets import redact_secrets
from ...entity.persistence.metadata import WorkspaceMetadata
from ...i18n import SUPPORTED_LANGUAGES
from ...i18n.workspace import get_workspace_language, set_workspace_language
from ...operation_trace import service as tracing
from ...pipeline.extension_preferences import normalize_extension_preferences
from ...utils import constants
from ...workspace.invitation_delivery import InvitationDeliveryService


class Empty(Input):
    pass


class Language(Input):
    language: str


class Member(Input):
    account_uuid: str


class MemberRole(Member):
    role: Literal['admin', 'developer', 'operator', 'viewer']


class Invite(Input):
    email: str
    role: Literal['admin', 'developer', 'operator', 'viewer'] = 'viewer'


class Invitation(Input):
    invitation_uuid: str


class Governance(Input):
    level: int | None = None
    retention_days: int | None = None
    max_rows: int | None = None
    dedupe_window_seconds: int | None = None


class LogFilters(Input):
    action: str | None = None
    resource_type: str | None = None
    actor_account_uuid: str | None = None
    level: int | None = None
    since: datetime.datetime | None = None
    until: datetime.datetime | None = None


class LogPage(LogFilters):
    limit: int = Field(default=100, ge=1)
    offset: int = Field(default=0, ge=0)
    integrity: str | None = None
    search: str | None = None


class TaskList(Input):
    task_type: str | None = None
    task_kind: str | None = None


class TaskGet(Input):
    task_id: int = Field(ge=0)


class Upload(Input):
    filename: str = Field(min_length=1)
    content: bytes = Field(max_length=10 * 1024 * 1024)


class ImageGet(Input):
    file_key: str


class ToolList(Input):
    pipeline_uuid: str | None = None


class ToolGet(ToolList):
    tool_name: str


class RequesterList(Input):
    model_type: str = ''


class RequesterGet(Input):
    requester_name: str


class AdapterGet(Input):
    adapter_name: str


class WizardStatus(Input):
    status: Literal['completed', 'skipped'] = 'completed'


class WizardProgress(Input):
    step: int = Field(ge=0)
    selected_scenario: str | None = None
    selected_adapter: str | None = None
    created_bot_uuid: str | None = None
    bot_saved: bool = False
    selected_runner: str | None = None


def _workspace(row):
    return {key: getattr(row, key) for key in ('uuid', 'instance_uuid', 'name', 'slug', 'type', 'status', 'source')}


def _membership(row, *, display_name='', email=''):
    value = {key: getattr(row, key) for key in ('uuid', 'workspace_uuid', 'account_uuid', 'role', 'status')}
    value.update(display_name=display_name, email=email)
    for key in ('joined_at', 'created_at'):
        timestamp = getattr(row, key)
        value[key] = timestamp.isoformat() if timestamp else None
    return value


def _invitation(row):
    value = {key: getattr(row, key) for key in ('uuid', 'workspace_uuid', 'normalized_email', 'role', 'status')}
    for key in ('expires_at', 'created_at'):
        timestamp = getattr(row, key)
        value[key] = timestamp.isoformat() if timestamp else None
    return value


@asynccontextmanager
async def _collaboration(ap, context):
    # Collaboration mutators require a tenant transaction in cloud runtime.
    if getattr(getattr(ap.persistence_mgr, 'mode', None), 'value', None) == 'cloud_runtime':
        async with ap.persistence_mgr.tenant_uow(context.workspace_uuid):
            yield
    else:
        yield


async def _actor(ap, context):
    if context.principal.principal_type != PrincipalType.ACCOUNT or not context.account_uuid:
        raise PermissionDeniedError('account_membership_required')
    access = await ap.workspace_collaboration_service.resolve_account_workspace(
        context.account_uuid, context.workspace_uuid
    )
    if access.membership.uuid != context.workspace.membership_uuid:
        raise PermissionDeniedError('account_membership_required')
    return access.membership


async def workspace_get(ap, context, payload):
    return _workspace(await ap.workspace_service.get_workspace(context.workspace_uuid))


async def workspace_current(ap, context, payload):
    workspace = await ap.workspace_service.get_workspace(context.workspace_uuid)
    result = {
        'workspace': _workspace(workspace),
        'permissions': sorted(context.workspace.permissions),
        'placement_generation': context.placement_generation,
        'membership': None,
        'plan_name': None,
        'current_plan': None,
        'limitation': None,
    }
    if context.principal.principal_type == PrincipalType.ACCOUNT:
        member = await _actor(ap, context)
        account = await ap.user_service.get_user_by_uuid(context.account_uuid)
        result['membership'] = _membership(member, display_name=account.user, email=account.normalized_email)
    resolver = getattr(ap, 'entitlement_resolver', None)
    if workspace.source == 'cloud_projection' and resolver is not None:
        from ..http.service.workspace_limits import LIMIT_KEYS

        entitlement = await resolver.resolve(workspace.uuid, minimum_revision=context.entitlement_revision)
        result['plan_name'] = entitlement.plan_name
        result['limitation'] = {key: entitlement.limit(value) for key, value in LIMIT_KEYS.items()}
        if entitlement.plan_revision is not None and entitlement.monthly_bonus_credits is not None:
            result['current_plan'] = {
                'name': entitlement.plan_name,
                'subscription_started_at': entitlement.subscription_started_at,
                'revision': entitlement.plan_revision,
                'monthly_bonus_credits': entitlement.monthly_bonus_credits,
                'limits': entitlement.limits,
                'entitlement_features': entitlement.features,
            }
    return result


async def language_get(ap, context, payload):
    return {
        'language': await get_workspace_language(ap, context.workspace_uuid, refresh=True),
        'supported_languages': list(SUPPORTED_LANGUAGES),
    }


async def language_update(ap, context, payload):
    return {'language': await set_workspace_language(ap, context.workspace_uuid, payload.language)}


async def members_list(ap, context, payload):
    async with _collaboration(ap, context):
        rows = await ap.workspace_collaboration_service.list_members(context.workspace_uuid, await _actor(ap, context))
    return [_membership(row.membership, display_name=row.display_name, email=row.email) for row in rows]


async def _record_change(ap, context, action, changes, resource_id=None):
    service = ap.workspace_settings_service
    rule = tracing.ACTION_RULES_BY_ACTION[action]
    await service.record(
        context.workspace_uuid,
        rule=rule,
        level=max(
            await service.effective_level(context.workspace_uuid, context.workspace.role),
            tracing.OPERATION_LEVEL_MUTATION,
        )
        if action == 'settings_update'
        else await service.effective_level(context.workspace_uuid, context.workspace.role),
        actor_account_uuid=context.account_uuid,
        actor_role=context.workspace.role,
        principal_type=context.principal.principal_type.value,
        api_key_uuid=context.principal.api_key_uuid,
        auth_type=context.auth_type,
        request_id=context.request_id,
        resource_id=resource_id,
        outcome='ok',
        summary=tracing.build_summary(rule, changes),
        changes=changes,
    )


async def member_update(ap, context, payload):
    async with _collaboration(ap, context):
        actor = await _actor(ap, context)
        members = await ap.workspace_collaboration_service.list_members(context.workspace_uuid, actor)
        before = next(
            (row.membership.role for row in members if row.membership.account_uuid == payload.account_uuid), None
        )
        member = await ap.workspace_collaboration_service.update_member_role(
            context.workspace_uuid, payload.account_uuid, payload.role, actor
        )
        account = await ap.user_service.get_user_by_uuid(member.account_uuid)
        result = _membership(
            member, display_name=account.user if account else '', email=account.normalized_email if account else ''
        )
    await _record_change(
        ap,
        context,
        'member_role_update',
        [{'field': 'role', 'before': before, 'after': member.role}],
        payload.account_uuid,
    )
    return result


async def member_remove(ap, context, payload):
    async with _collaboration(ap, context):
        actor = await _actor(ap, context)
        member = await ap.workspace_collaboration_service.remove_member(
            context.workspace_uuid, payload.account_uuid, actor
        )
    await _record_change(
        ap,
        context,
        'member_remove',
        [{'field': 'member', 'before': f'{member.account_uuid}:{member.role}', 'after': 'removed'}],
        member.account_uuid,
    )
    return {'account_uuid': member.account_uuid}


async def invitations_list(ap, context, payload):
    async with _collaboration(ap, context):
        rows = await ap.workspace_collaboration_service.list_invitations(
            context.workspace_uuid, await _actor(ap, context)
        )
    return [_invitation(row) for row in rows]


async def invitation_create(ap, context, payload):
    async with _collaboration(ap, context):
        created = await ap.workspace_collaboration_service.create_invitation(
            context.workspace_uuid, await _actor(ap, context), payload.email, payload.role
        )
    await _record_change(
        ap,
        context,
        'member_invite',
        [
            {
                'field': 'invitation',
                'before': None,
                'after': f'{created.invitation.normalized_email}:{created.invitation.role}',
            }
        ],
        created.invitation.uuid,
    )
    delivery_service = getattr(ap, 'invitation_delivery_service', None) or InvitationDeliveryService(ap)
    link = delivery_service.build_invitation_link(created.token)
    workspace = await ap.workspace_service.get_workspace(context.workspace_uuid)
    delivery = await delivery_service.deliver_invitation(
        recipient_email=created.invitation.normalized_email, workspace_name=workspace.name, invitation_link=link
    )
    return {
        'invitation': _invitation(created.invitation),
        'token': created.token,
        'link': link,
        'delivery': delivery.to_public_dict(),
    }


async def invitation_revoke(ap, context, payload):
    async with _collaboration(ap, context):
        row = await ap.workspace_collaboration_service.revoke_invitation(
            context.workspace_uuid, payload.invitation_uuid, await _actor(ap, context)
        )
    return _invitation(row)


async def governance_get(ap, context, payload):
    return await ap.workspace_settings_service.describe_governance(context.workspace_uuid)


async def governance_update(ap, context, payload):
    if not tracing.role_may_configure(context.workspace.role):
        raise PermissionDeniedError('workspace_owner_or_admin_required')
    service = ap.workspace_settings_service
    before = await service.describe_governance(context.workspace_uuid)
    options = payload.model_dump(exclude={'level'})
    result = await service.set_operation_level(
        context.workspace_uuid, payload.level if payload.level is not None else before['configured_level'], **options
    )
    keys = ('configured_level', 'retention_days', 'max_rows', 'dedupe_window_seconds')
    changes = tracing.changed_fields({key: before[key] for key in keys}, {key: result[key] for key in keys})
    if changes:
        await _record_change(ap, context, 'settings_update', changes)
    return result


def _log_filters(payload):
    values = payload.model_dump()
    for key in ('since', 'until'):
        if values[key] is not None and values[key].tzinfo is not None:
            values[key] = values[key].astimezone(datetime.UTC).replace(tzinfo=None)
    return values


async def logs_list(ap, context, payload):
    return await ap.workspace_settings_service.query_logs(context.workspace_uuid, **_log_filters(payload))


async def logs_export(ap, context, payload):
    return await ap.workspace_settings_service.export_logs(context.workspace_uuid, **_log_filters(payload))


async def logs_filters(ap, context, payload):
    options = await ap.workspace_settings_service.list_filter_options(context.workspace_uuid)
    options['governance'] = await ap.workspace_settings_service.describe_governance(context.workspace_uuid)
    return options


def _task_scope(context):
    return {
        'instance_uuid': context.instance_uuid,
        'workspace_uuid': context.workspace_uuid,
        'placement_generation': context.placement_generation,
    }


async def tasks_list(ap, context, payload):
    return ap.task_mgr.get_tasks_dict(
        payload.task_type or None,
        payload.task_kind or None,
        **_task_scope(context),
        public=context.principal.principal_type == PrincipalType.API_KEY,
    )


async def task_get(ap, context, payload):
    task = ap.task_mgr.get_task_by_id(payload.task_id, **_task_scope(context))
    if task is None:
        raise FileNotFoundError('Task not found')
    return task.to_public_dict() if context.principal.principal_type == PrincipalType.API_KEY else task.to_dict()


async def _upload(ap, context, payload, *, image):
    if '/' in payload.filename or '\\' in payload.filename or '\x00' in payload.filename:
        raise ValueError('File name contains invalid characters')
    extension = payload.filename.rsplit('.', 1)[1] if '.' in payload.filename else ''
    if image:
        extension = extension.lower()
        if extension not in {'jpg', 'jpeg', 'png', 'gif', 'webp'}:
            raise ValueError('Invalid image format')
    owner = (
        f'account:{context.account_uuid}'
        if context.account_uuid
        else f'api-key:{context.principal.api_key_uuid}'
        if context.principal.api_key_uuid
        else f'principal:{context.principal.principal_type.value}'
    )
    key = str(uuid.uuid4()) + (f'.{extension}' if extension else '')
    return await ap.storage_mgr.save_scoped(
        context, owner_type='upload_image' if image else 'upload_document', owner=owner, key=key, value=payload.content
    )


async def image_upload(ap, context, payload):
    return {'file_key': await _upload(ap, context, payload, image=True)}


async def document_upload(ap, context, payload):
    return {'file_id': await _upload(ap, context, payload, image=False)}


async def image_get(ap, context, payload):
    # The foundation reads only this Workspace, including keys otherwise publicly addressable.
    storage = ap.storage_mgr
    if storage.is_scoped_object_key(payload.file_key, expected_owner_type='upload_image'):
        owner_type = 'upload_image'
    elif storage.is_scoped_object_key(payload.file_key, expected_owner_type='bot_log'):
        owner_type = 'bot_log'
    else:
        raise FileNotFoundError('Image not found')
    content = await storage.load_scoped_object_key(context, payload.file_key, expected_owner_type=owner_type)
    return {'content': content, 'media_type': mimetypes.guess_type(payload.file_key)[0] or 'image/jpeg'}


async def box_status(ap, context, payload):
    status = await ap.box_service.get_status(context)
    return {**status, 'hidden': constants.edition == 'cloud' and status.get('enabled') is False}


async def box_sessions(ap, context, payload):
    return await ap.box_service.get_sessions(context)


async def box_errors(ap, context, payload):
    if ap.box_service.managed_admission_required:
        await ap.box_service.require_workspace_sandbox(context)
    return ap.box_service.get_recent_errors(context)


async def tools_list(ap, context, payload):
    bound_plugins = bound_mcp_servers = None
    if payload.pipeline_uuid:
        pipeline = await ap.pipeline_service.get_pipeline(context, payload.pipeline_uuid)
        if pipeline is None:
            raise FileNotFoundError('Pipeline not found')
        prefs = normalize_extension_preferences(pipeline.get('extensions_preferences'))
        if not prefs['enable_all_plugins']:
            bound_plugins = [f'{plugin["author"]}/{plugin["name"]}' for plugin in prefs['plugins']]
        if not prefs['enable_all_mcp_servers']:
            bound_mcp_servers = prefs['mcp_servers']
    return await ap.tool_mgr.get_resolved_tool_catalog(
        context, bound_plugins, bound_mcp_servers, include_skill_authoring=True
    )


async def tool_get(ap, context, payload):
    for tool in await tools_list(ap, context, payload):
        if tool.get('name') == payload.tool_name:
            return tool
    raise FileNotFoundError('Tool not found')


async def extensions_list(ap, context, payload):
    if ap.plugin_connector.is_enable_plugin:
        await ap.plugin_connector.require_workspace_context(context)
    # Keep failures visible to programmatic callers instead of returning a partial catalog.
    plugins = await ap.plugin_connector.list_plugins()
    servers = await ap.mcp_service.get_mcp_servers(context, contain_runtime_info=True)
    skills = await ap.skill_service.list_skills(context)
    extensions = [{'type': 'plugin', 'plugin': redact_secrets(plugin)} for plugin in plugins]
    extensions += [{'type': 'mcp', 'server': server} for server in servers]
    extensions += [{'type': 'skill', 'skill': skill} for skill in skills]
    return extensions


async def basic_stats(ap, context, payload):
    execution = ExecutionContext.from_request(context)
    sessions = [
        session
        for session in ap.sess_mgr.session_list
        if all(getattr(session, key, None) == value for key, value in _task_scope(context).items())
    ]
    return {
        'active_session_count': len(sessions),
        'conversation_count': sum(len(session.conversations or []) for session in sessions),
        'query_count': ap.query_pool.get_query_count(execution),
    }


async def _metadata_set(ap, context, key, value):
    condition = (WorkspaceMetadata.workspace_uuid == context.workspace_uuid, WorkspaceMetadata.key == key)
    result = await ap.persistence_mgr.execute_async(sqlalchemy.select(WorkspaceMetadata).where(*condition))
    statement = (
        sqlalchemy.update(WorkspaceMetadata).where(*condition).values(value=value)
        if result.first()
        else sqlalchemy.insert(WorkspaceMetadata).values(workspace_uuid=context.workspace_uuid, key=key, value=value)
    )
    await ap.persistence_mgr.execute_async(statement)


async def wizard_complete(ap, context, payload):
    await _metadata_set(ap, context, 'wizard_status', payload.status)
    await ap.persistence_mgr.execute_async(
        sqlalchemy.delete(WorkspaceMetadata).where(
            WorkspaceMetadata.workspace_uuid == context.workspace_uuid, WorkspaceMetadata.key == 'wizard_progress'
        )
    )
    return None


async def wizard_progress(ap, context, payload):
    await _metadata_set(ap, context, 'wizard_progress', json.dumps(payload.model_dump(), ensure_ascii=False))
    return None


async def recommended_model(ap, context, payload):
    return await ap.space_service.get_recommended_chat_model(context)


async def model_availability(ap, context, payload):
    return [model.model_dump(mode='json') for model in await ap.space_service.get_model_selection()]


async def requester_list(ap, context, payload):
    return ap.model_mgr.get_available_requesters_info(payload.model_type)


async def requester_get(ap, context, payload):
    result = ap.model_mgr.get_available_requester_info_by_name(payload.requester_name)
    if result is None:
        raise FileNotFoundError('Requester not found')
    return result


async def adapter_list(ap, context, payload):
    from ...cloud.plan_policy import workspace_entitlement, platform_feature_names

    snapshot = await workspace_entitlement(ap, context.workspace_uuid)
    adapters = ap.platform_mgr.get_available_adapters_info()
    if snapshot is not None:
        adapters = [
            adapter
            for adapter in adapters
            if not any(snapshot.features.get(feature) is False for feature in platform_feature_names(adapter['name']))
        ]
    return adapters


async def adapter_get(ap, context, payload):
    from ...cloud.plan_policy import require_workspace_platform

    await require_workspace_platform(ap, context.workspace_uuid, payload.adapter_name)
    result = ap.platform_mgr.get_available_adapter_info_by_name(payload.adapter_name)
    if result is None:
        raise FileNotFoundError('Adapter not found')
    return result


async def storage_analysis(ap, context, payload):
    return await ap.maintenance_service.get_storage_analysis(context)


async def wizard_get(ap, context, payload):
    result = await ap.persistence_mgr.execute_async(
        sqlalchemy.select(WorkspaceMetadata).where(
            WorkspaceMetadata.workspace_uuid == context.workspace_uuid,
            WorkspaceMetadata.key.in_(['wizard_status', 'wizard_progress']),
        )
    )
    values = {row.key: row.value for row in result.all()}
    return {
        'status': values.get('wizard_status'),
        'progress': json.loads(values['wizard_progress']) if values.get('wizard_progress') else None,
    }


async def plugin_status(ap, context, payload):
    await ap.plugin_connector.require_workspace_context(context)
    try:
        await ap.plugin_connector.ping_plugin_runtime()
    except Exception as exc:
        return {
            'is_enable': ap.plugin_connector.is_enable_plugin,
            'is_connected': False,
            'plugin_connector_error': str(exc),
        }
    return {'is_enable': ap.plugin_connector.is_enable_plugin, 'is_connected': True, 'plugin_connector_error': 'ok'}


def operations() -> list[Operation]:
    view, manage = Permission.RESOURCE_VIEW, Permission.RESOURCE_MANAGE
    account = frozenset({PrincipalType.ACCOUNT})
    return [
        Operation('workspace.get', Permission.WORKSPACE_VIEW, workspace_get, Empty, dict),
        Operation('workspace.current', Permission.WORKSPACE_VIEW, workspace_current, Empty, dict),
        Operation('workspace.language.get', Permission.WORKSPACE_VIEW, language_get, Empty, dict),
        Operation('workspace.language.update', Permission.WORKSPACE_UPDATE, language_update, Language, dict, True),
        Operation('workspace.member.list', Permission.MEMBER_VIEW, members_list, Empty, list[dict], principals=account),
        Operation(
            'workspace.member.update',
            Permission.MEMBER_UPDATE_ROLE,
            member_update,
            MemberRole,
            dict,
            True,
            principals=account,
        ),
        Operation(
            'workspace.member.remove', Permission.MEMBER_REMOVE, member_remove, Member, dict, True, principals=account
        ),
        Operation(
            'workspace.invitation.list',
            Permission.MEMBER_INVITE,
            invitations_list,
            Empty,
            list[dict],
            principals=account,
        ),
        Operation(
            'workspace.invitation.create',
            Permission.MEMBER_INVITE,
            invitation_create,
            Invite,
            dict,
            True,
            principals=account,
        ),
        Operation(
            'workspace.invitation.revoke',
            Permission.MEMBER_INVITE,
            invitation_revoke,
            Invitation,
            dict,
            True,
            principals=account,
        ),
        Operation('settings.governance.get', Permission.AUDIT_VIEW, governance_get, Empty, dict),
        Operation('settings.governance.update', Permission.AUDIT_VIEW, governance_update, Governance, dict, True),
        Operation('settings.operation_logs.list', Permission.AUDIT_VIEW, logs_list, LogPage, dict),
        Operation('settings.operation_logs.filters', Permission.AUDIT_VIEW, logs_filters, Empty, dict),
        Operation('settings.operation_logs.export', Permission.AUDIT_VIEW, logs_export, LogFilters, dict),
        Operation('task.list', view, tasks_list, TaskList, dict),
        Operation('task.get', view, task_get, TaskGet, dict),
        Operation('file.image.upload', manage, image_upload, Upload, dict[str, str], True),
        Operation('file.document.upload', manage, document_upload, Upload, dict[str, str], True),
        Operation('file.image.get', view, image_get, ImageGet, dict[str, bytes | str]),
        Operation('box.status', view, box_status, Empty, dict),
        Operation('box.sessions.list', Permission.AUDIT_VIEW, box_sessions, Empty, list[dict]),
        Operation('box.errors.list', Permission.AUDIT_VIEW, box_errors, Empty, list[dict]),
        Operation('tool.list', view, tools_list, ToolList, list[dict]),
        Operation('tool.get', view, tool_get, ToolGet, dict),
        Operation('extension.list', view, extensions_list, Empty, list[dict]),
        Operation('requester.list', view, requester_list, RequesterList, list[dict]),
        Operation('requester.get', view, requester_get, RequesterGet, dict),
        Operation('adapter.list', view, adapter_list, Empty, list[dict]),
        Operation('adapter.get', view, adapter_get, AdapterGet, dict),
        Operation('stats.basic', view, basic_stats, Empty, dict[str, int]),
        Operation('system.wizard.get', Permission.WORKSPACE_VIEW, wizard_get, Empty, dict),
        Operation('system.storage.analysis', Permission.AUDIT_VIEW, storage_analysis, Empty, dict),
        Operation(
            'system.wizard.complete', Permission.WORKSPACE_UPDATE, wizard_complete, WizardStatus, type(None), True
        ),
        Operation(
            'system.wizard.progress.update',
            Permission.WORKSPACE_UPDATE,
            wizard_progress,
            WizardProgress,
            type(None),
            True,
        ),
        Operation('system.model.recommended', manage, recommended_model, Empty, dict),
        Operation('system.model.availability', view, model_availability, Empty, list[dict]),
        Operation('system.plugin.status', view, plugin_status, Empty, dict),
    ]
