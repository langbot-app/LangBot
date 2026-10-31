"""Unit tests for processor workspace operations authorization and catalog (LANG-226)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.application.api import ApplicationAPI
from langbot.pkg.api.application.contracts import ApplicationAPIException
from langbot.pkg.api.application.tool_grants import (
    get_workspace_operations_catalog,
    validate_grant_change,
)
from langbot.pkg.api.authz import Permission, permissions_for_role
from langbot.pkg.api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from langbot.pkg.api.http.service.pipeline import PipelineService
from langbot.pkg.pipeline.extension_preferences import normalize_extension_preferences


def make_context(role: str, permissions: frozenset[str] | None = None) -> RequestContext:
    if permissions is None:
        permissions = permissions_for_role(role)
    return RequestContext(
        instance_uuid='test-instance',
        placement_generation=1,
        request_id='req-1',
        auth_type='cookie',
        principal=PrincipalContext(
            principal_type=PrincipalType.ACCOUNT,
            account_uuid='acc-1',
        ),
        workspace=WorkspaceContext(
            workspace_uuid='ws-1',
            membership_uuid='mem-1',
            role=role,
            permissions=permissions,
        ),
    )


@pytest.fixture
def test_host(monkeypatch):
    monkeypatch.setattr('langbot.pkg.api.application.api.get_workspace_language', AsyncMock(return_value='en_US'))
    host = SimpleNamespace(
        logger=Mock(),
        workspace_service=SimpleNamespace(
            get_execution_binding=AsyncMock(
                return_value=SimpleNamespace(instance_uuid='test-instance', placement_generation=1)
            )
        ),
        persistence_mgr=SimpleNamespace(),
    )
    host.application_api = ApplicationAPI(host)
    return host


# 1. Admin 可以勾选 provider_secret.manage 级别的操作，member 不能
def test_admin_can_grant_provider_secret_manage_and_member_cannot(test_host):
    admin_ctx = make_context('admin')
    # model.llm.create requires provider_secret.manage and has exposure == 'all'
    granted = validate_grant_change(test_host, admin_ctx, [], ['model.llm.create'])
    assert granted == ['model.llm.create']

    member_ctx = make_context('viewer')
    with pytest.raises(ApplicationAPIException) as exc_info:
        validate_grant_change(test_host, member_ctx, [], ['model.llm.create'])
    assert exc_info.value.error.code == 'permission_denied'
    assert exc_info.value.error.status_code == 403
    assert 'model.llm.create' in exc_info.value.error.details['operations']


# 2. Member 修改一个已经包含高权限勾选项的流水线的其他字段时，可以保存
def test_member_can_save_pipeline_with_existing_high_privilege_grants(test_host):
    # Member only has RESOURCE_VIEW and RESOURCE_MANAGE, NOT provider_secret.manage
    member_ctx = make_context(
        'operator',
        frozenset({Permission.RESOURCE_VIEW.value, Permission.RESOURCE_MANAGE.value}),
    )

    old_ids = ['model.llm.create', 'bot.list']
    # Same operations kept, no new operations added
    new_ids = ['bot.list', 'model.llm.create']

    result = validate_grant_change(test_host, member_ctx, old_ids, new_ids)
    assert result == ['bot.list', 'model.llm.create']

    # Member removing one operation also succeeds
    reduced = validate_grant_change(test_host, member_ctx, old_ids, ['bot.list'])
    assert reduced == ['bot.list']


# 3. Member 新增高权限勾选项时被拒绝
def test_member_adding_high_privilege_grant_is_rejected(test_host):
    member_ctx = make_context(
        'developer',
        frozenset({Permission.RESOURCE_VIEW.value, Permission.RESOURCE_MANAGE.value}),
    )

    old_ids = ['bot.list']
    # Tries to add model.llm.create which requires provider_secret.manage
    new_ids = ['bot.list', 'model.llm.create']

    with pytest.raises(ApplicationAPIException) as exc_info:
        validate_grant_change(test_host, member_ctx, old_ids, new_ids)
    assert exc_info.value.error.code == 'permission_denied'
    assert exc_info.value.error.status_code == 403
    assert 'model.llm.create' in exc_info.value.error.details['operations']


# 4. 勾选 exposure != 'all' 的操作被拒绝
def test_granting_non_all_exposure_or_invalid_operations_rejected(test_host):
    admin_ctx = make_context('admin')

    # pipeline.migration.preview has exposure == 'assistant'
    with pytest.raises(ApplicationAPIException) as exc_info:
        validate_grant_change(test_host, admin_ctx, [], ['pipeline.migration.preview'])
    assert exc_info.value.error.code == 'invalid_input'
    assert exc_info.value.error.status_code == 400
    assert 'pipeline.migration.preview' in exc_info.value.error.details['operations']

    # agent.debug.stream is streaming / exposure == 'none'
    with pytest.raises(ApplicationAPIException) as exc_info:
        validate_grant_change(test_host, admin_ctx, [], ['agent.debug.stream'])
    assert exc_info.value.error.code == 'invalid_input'
    assert exc_info.value.error.status_code == 400

    # Non-existent operation
    with pytest.raises(ApplicationAPIException) as exc_info:
        validate_grant_change(test_host, admin_ctx, [], ['unknown.nonexistent.op'])
    assert exc_info.value.error.code == 'invalid_input'

    # Wildcard notation rejected
    with pytest.raises(ApplicationAPIException) as exc_info:
        validate_grant_change(test_host, admin_ctx, [], ['bot.*'])
    assert exc_info.value.error.code == 'invalid_input'

    # Non-string item rejected
    with pytest.raises(ApplicationAPIException) as exc_info:
        validate_grant_change(test_host, admin_ctx, [], [123])
    assert exc_info.value.error.code == 'invalid_input'


# 5. 复制流水线时的权限检查
@pytest.mark.asyncio
async def test_copy_pipeline_permission_check(test_host):
    # Setup mock pipeline service
    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(),
        instance_config=SimpleNamespace(data={'system': {'limitation': {'max_pipelines': -1}}}),
        pipeline_mgr=SimpleNamespace(load_pipeline=AsyncMock()),
        ver_mgr=SimpleNamespace(get_current_version=Mock(return_value='1.0.0')),
        application_api=test_host.application_api,
    )

    original_pipeline = SimpleNamespace(
        name='Source Pipeline',
        description='Source description',
        stages=['Stage1'],
        config={},
        extensions_preferences={
            'enable_all_plugins': True,
            'plugins': [],
            'workspace_operations': ['model.llm.create'],
        },
    )

    service = PipelineService(ap)
    service.get_pipelines = AsyncMock(return_value=[])
    ap.persistence_mgr.execute_async = AsyncMock(
        return_value=SimpleNamespace(first=Mock(return_value=original_pipeline))
    )
    service.get_pipeline = AsyncMock(return_value={'uuid': 'copy-123', 'name': 'Source Pipeline (Copy)'})

    # 1) Admin copies: succeeds
    admin_ctx = make_context('admin')
    copy_uuid = await service.copy_pipeline(admin_ctx, 'orig-uuid')
    assert copy_uuid is not None

    # 2) Member without provider_secret.manage copies: raises ApplicationAPIException (permission_denied)
    member_ctx = make_context(
        'operator',
        frozenset({Permission.RESOURCE_VIEW.value, Permission.RESOURCE_MANAGE.value}),
    )
    with pytest.raises(ApplicationAPIException) as exc_info:
        await service.copy_pipeline(member_ctx, 'orig-uuid')
    assert exc_info.value.error.code == 'permission_denied'
    assert exc_info.value.error.status_code == 403


# 6. enable_all_plugins=True 时，工作区操作仍然是空的
def test_enable_all_plugins_does_not_enable_workspace_operations():
    prefs = normalize_extension_preferences({'enable_all_plugins': True})
    assert prefs['enable_all_plugins'] is True
    assert prefs['workspace_operations'] == []

    prefs_with_ops = normalize_extension_preferences(
        {
            'enable_all_plugins': True,
            'workspace_operations': ['bot.list'],
        }
    )
    assert prefs_with_ops['enable_all_plugins'] is True
    assert prefs_with_ops['workspace_operations'] == ['bot.list']


# 7. 目录接口与 grantable 标记
def test_workspace_operations_catalog_and_grantable_flags(test_host):
    admin_ctx = make_context('admin')
    admin_catalog = get_workspace_operations_catalog(test_host, admin_ctx)

    ops = admin_catalog['workspace_operations']
    domains = admin_catalog['domains']

    assert len(ops) > 0
    assert len(domains) > 0

    # Every item has {id, domain, label, summary, risk, permission, grantable}
    for item in ops:
        assert 'id' in item
        assert 'domain' in item
        assert 'label' in item
        assert 'summary' in item
        assert 'risk' in item
        assert 'permission' in item
        assert 'grantable' in item

    # Admin has permission for provider_secret.manage ops
    admin_secret_ops = [op for op in ops if op['permission'] == Permission.PROVIDER_SECRET_MANAGE.value]
    assert len(admin_secret_ops) > 0
    for op in admin_secret_ops:
        assert op['grantable'] is True

    # Member without provider_secret.manage sees grantable == False for secret ops
    member_ctx = make_context('viewer')
    member_catalog = get_workspace_operations_catalog(test_host, member_ctx)
    member_secret_ops = [
        op
        for op in member_catalog['workspace_operations']
        if op['permission'] == Permission.PROVIDER_SECRET_MANAGE.value
    ]
    for op in member_secret_ops:
        assert op['grantable'] is False

    # Read-only operations requiring only RESOURCE_VIEW are grantable for viewer
    viewer_view_ops = [
        op for op in member_catalog['workspace_operations'] if op['permission'] == Permission.RESOURCE_VIEW.value
    ]
    for op in viewer_view_ops:
        assert op['grantable'] is True
