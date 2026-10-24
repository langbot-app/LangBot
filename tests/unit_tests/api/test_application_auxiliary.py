"""Application operations exercised with SQLite, local files and real task ownership."""

from __future__ import annotations

import asyncio
import contextvars
import dataclasses
import logging
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
import sqlalchemy

from langbot.pkg.api.application import ApplicationAPI, ApplicationAPIException
from langbot.pkg.api.application.auxiliary import operations
from langbot.pkg.api.authz import Permission, permissions_for_role
from langbot.pkg.api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from langbot.pkg.core.taskmgr import AsyncTaskManager
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.workspace import WorkspaceInvitation, WorkspaceMembership
from langbot.pkg.operation_trace.service import WorkspaceSettingsService
from langbot.pkg.storage.mgr import StorageMgr
from langbot.pkg.storage.providers import localstorage

pytest_plugins = ['tests.unit_tests.workspace.test_workspace_collaboration']


@pytest.fixture
async def foundation(collaboration_context, tmp_path, monkeypatch):
    collaboration, workspace_service, session_factory, owner, workspace, membership = collaboration_context
    ap = collaboration.ap
    ap.workspace_service = workspace_service
    ap.workspace_collaboration_service = collaboration
    ap.instance_config = SimpleNamespace(data={})
    ap.logger = logging.getLogger('application-auxiliary-test')
    ap.event_loop = asyncio.get_running_loop()
    manager = ap.persistence_mgr
    current_session = contextvars.ContextVar('auxiliary_session', default=None)

    @asynccontextmanager
    async def tenant_scope(workspace_uuid):
        yield

    @asynccontextmanager
    async def tenant_uow(workspace_uuid):
        if current_session.get() is not None:
            yield SimpleNamespace(session=current_session.get(), execute=current_session.get().execute)
            return
        async with session_factory.begin() as session:
            token = current_session.set(session)
            try:
                yield SimpleNamespace(session=session, execute=session.execute)
            finally:
                current_session.reset(token)

    async def execute_async(statement):
        if current_session.get() is not None:
            connection = await current_session.get().connection()
            return await connection.execute(statement)
        async with manager.get_db_engine().begin() as connection:
            return await connection.execute(statement)

    async def get_user(account_uuid):
        async with session_factory() as session:
            return await session.get(User, account_uuid)

    manager.tenant_scope = tenant_scope
    manager.tenant_uow = tenant_uow
    manager.execute_async = execute_async
    manager.current_session = current_session.get
    ap.user_service = SimpleNamespace(get_user_by_uuid=get_user)
    ap.workspace_settings_service = WorkspaceSettingsService(ap)
    ap.task_mgr = AsyncTaskManager(ap)
    ap.storage_mgr = StorageMgr(ap)
    monkeypatch.setattr(localstorage, 'LOCAL_STORAGE_PATH', str(tmp_path / 'objects'))
    ap.storage_mgr.storage_provider = localstorage.LocalStorageProvider(ap)
    context = RequestContext(
        instance_uuid=workspace.instance_uuid,
        placement_generation=1,
        request_id='auxiliary-check',
        auth_type='user_token',
        principal=PrincipalContext(PrincipalType.ACCOUNT, account_uuid=owner.uuid),
        workspace=WorkspaceContext(workspace.uuid, membership.uuid, 'owner', permissions_for_role('owner')),
    )
    api = ApplicationAPI(ap, operations=operations())
    yield api, ap, context, session_factory
    await ap.workspace_settings_service.flush_pending()
    if ap.workspace_settings_service._writer_task is not None:
        ap.workspace_settings_service._writer_task.cancel()
        await asyncio.gather(ap.workspace_settings_service._writer_task, return_exceptions=True)
    for task in ap.task_mgr.tasks:
        if not task.task.done():
            task.task.cancel()
    await asyncio.gather(*(task.task for task in ap.task_mgr.tasks), return_exceptions=True)


@pytest.mark.asyncio
async def test_file_upload_round_trip_and_workspace_isolation(foundation):
    api, ap, context, _ = foundation
    content = b'\x89PNG\r\n\x1a\n' + '中文图片'.encode()
    uploaded = await api.execute('file.image.upload', context, {'filename': 'image.PNG', 'content': content})
    returned = await api.execute('file.image.get', context, uploaded)
    assert returned == {'content': content, 'media_type': 'image/png'}
    key = uploaded['file_key']
    assert localstorage._safe_resolve(localstorage.LOCAL_STORAGE_PATH, key)
    foreign_key = key.replace(context.workspace_uuid, '00000000-0000-0000-0000-000000000000')
    with pytest.raises(ApplicationAPIException):
        await api.execute('file.image.get', context, {'file_key': foreign_key})
    viewer = dataclasses.replace(
        context,
        workspace=dataclasses.replace(context.workspace, role='viewer', permissions=permissions_for_role('viewer')),
    )
    with pytest.raises(ApplicationAPIException) as denied:
        await api.execute('file.image.upload', viewer, {'filename': 'image.png', 'content': content})
    assert denied.value.error.status_code == 403
    for filename in ('../a.png', 'a\\b.png', 'a.svg', 'bad\x00.png'):
        with pytest.raises(ApplicationAPIException):
            await api.execute('file.image.upload', context, {'filename': filename, 'content': content})


@pytest.mark.asyncio
async def test_member_mutations_preserve_owner_and_invitation_secret(foundation):
    api, ap, context, sessions = foundation
    invite = await api.execute(
        'workspace.invitation.create', context, {'email': 'joined@example.com', 'role': 'viewer'}
    )
    assert invite['delivery']['status'] == 'link_only'
    assert 'token_hash' not in invite['invitation']
    async with sessions.begin() as session:
        stored = await session.get(WorkspaceInvitation, invite['invitation']['uuid'])
        assert stored.token_hash != invite['token']
        new_user = User(
            uuid='joined-account',
            user='joined',
            normalized_email='joined@example.com',
            password='test',
            account_type='local',
        )
        session.add(new_user)
    await ap.workspace_collaboration_service.accept_invitation(invite['token'], new_user.uuid)
    changed = await api.execute(
        'workspace.member.update', context, {'account_uuid': new_user.uuid, 'role': 'developer'}
    )
    assert changed['role'] == 'developer'
    members = await api.execute('workspace.member.list', context, {})
    assert {row['account_uuid'] for row in members} == {context.account_uuid, new_user.uuid}
    with pytest.raises(ApplicationAPIException):
        await api.execute('workspace.member.remove', context, {'account_uuid': context.account_uuid})
    await api.execute('workspace.member.remove', context, {'account_uuid': new_user.uuid})
    async with sessions() as session:
        row = await session.scalar(
            sqlalchemy.select(WorkspaceMembership).where(WorkspaceMembership.account_uuid == new_user.uuid)
        )
        assert row.status == 'removed'
    key_context = dataclasses.replace(
        context, principal=PrincipalContext(PrincipalType.API_KEY, api_key_uuid='key'), auth_type='api_key'
    )
    with pytest.raises(ApplicationAPIException):
        await api.execute('workspace.member.list', key_context, {})


@pytest.mark.asyncio
async def test_language_wizard_and_governance_persist_without_http(foundation):
    api, ap, context, _ = foundation
    assert (await api.execute('workspace.language.update', context, {'language': 'zh_Hans'}))['language'] == 'zh_Hans'
    assert (await api.execute('workspace.language.get', context, {}))['language'] == 'zh_Hans'
    await api.execute('system.wizard.progress.update', context, {'step': 2, 'bot_saved': True})
    assert (await api.execute('system.wizard.get', context, {}))['progress']['step'] == 2
    await api.execute('system.wizard.complete', context, {})
    assert await api.execute('system.wizard.get', context, {}) == {'status': 'completed', 'progress': None}
    updated = await api.execute('settings.governance.update', context, {'level': 1, 'retention_days': 30})
    assert updated['configured_level'] == 1
    assert updated['retention_days'] == 30
    await ap.workspace_settings_service.flush_pending()
    logs = await api.execute('settings.operation_logs.list', context, {})
    assert any(row['action'] == 'settings_update' for row in logs['records'])
    unauthorized_role = dataclasses.replace(
        context,
        workspace=dataclasses.replace(
            context.workspace, role='viewer', permissions=frozenset({Permission.AUDIT_VIEW.value})
        ),
    )
    with pytest.raises(ApplicationAPIException) as denied:
        await api.execute('settings.governance.update', unauthorized_role, {'level': 0})
    assert denied.value.error.status_code == 403


@pytest.mark.asyncio
async def test_task_selection_excludes_other_workspace_and_hides_api_key_logs(foundation):
    api, ap, context, _ = foundation

    async def work():
        return None

    owned = ap.task_mgr.create_user_task(
        work(), instance_uuid=context.instance_uuid, workspace_uuid=context.workspace_uuid, placement_generation=1
    )
    owned.task_context.trace('secret internal diagnostic')
    other = ap.task_mgr.create_user_task(
        work(), instance_uuid=context.instance_uuid, workspace_uuid='other-workspace', placement_generation=1
    )
    await asyncio.gather(owned.task, other.task)
    result = await api.execute('task.list', context, {})
    assert [task['id'] for task in result['tasks']] == [owned.id]
    key_context = dataclasses.replace(
        context, principal=PrincipalContext(PrincipalType.API_KEY, api_key_uuid='key'), auth_type='api_key'
    )
    public = await api.execute('task.get', key_context, {'task_id': owned.id})
    assert 'secret internal diagnostic' not in str(public)
    with pytest.raises(ApplicationAPIException):
        await api.execute('task.get', context, {'task_id': other.id})
