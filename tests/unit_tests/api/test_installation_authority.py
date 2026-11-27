"""Read current installation authority from real persisted rows, without service mocks."""

import logging
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from langbot_plugin.entities.io.context import InstallationBinding

from langbot.pkg.api.application import ApplicationAPI, ApplicationAPIException
from langbot.pkg.api.application.plugin_permissions import installation_context
from langbot.pkg.api.context import PrincipalType
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.plugin import PluginSetting
from langbot.pkg.entity.persistence.workspace import Workspace
from langbot.pkg.persistence.mgr import PersistenceManager


@pytest.fixture
async def authority(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "authority.db"}')
    ap = SimpleNamespace(logger=logging.getLogger('authority'), instance_config=SimpleNamespace(data={}))
    ap.persistence_mgr = PersistenceManager(ap)
    ap.persistence_mgr.db = SimpleNamespace(get_engine=lambda: engine)
    ap.application_api = ApplicationAPI(ap)
    binding = InstallationBinding(
        instance_uuid='instance',
        workspace_uuid='workspace-a',
        placement_generation=7,
        installation_uuid='installation-a',
        runtime_revision=3,
        artifact_digest='a' * 64,
    )
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            for workspace in ('workspace-a', 'workspace-b'):
                await conn.execute(
                    sa.insert(Workspace).values(
                        uuid=workspace,
                        instance_uuid='instance',
                        name=workspace,
                        slug=workspace,
                        source='cloud_projection',
                    )
                )
            await conn.execute(
                sa.insert(PluginSetting).values(
                    workspace_uuid='workspace-a',
                    plugin_author='authority',
                    plugin_name='probe',
                    installation_uuid=binding.installation_uuid,
                    runtime_revision=3,
                    artifact_digest='a' * 64,
                    enabled=True,
                    permission_declaration={'workspace_operations': ['stats.basic'], 'capabilities': ['models.invoke']},
                    permission_grants={'workspace_operations': ['stats.basic'], 'capabilities': ['models.invoke']},
                )
            )
        yield ap, binding
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_context_preserves_the_authenticated_binding_and_exact_grants(authority):
    ap, binding = authority
    async with ap.persistence_mgr.tenant_scope('workspace-a'):
        context = await installation_context(ap, binding, run_id='run-a')
    assert (context.instance_uuid, context.workspace_uuid, context.placement_generation) == (
        'instance',
        'workspace-a',
        7,
    )
    assert context.auth_type == 'plugin' and context.request_id
    assert context.principal.principal_type == PrincipalType.PLUGIN
    assert context.principal.installation_uuid == 'installation-a' and context.principal.run_id == 'run-a'
    assert context.allowed_operation_ids == frozenset({'stats.basic'})
    assert context.workspace.permissions == frozenset({'resource.view', 'runtime.operate'})
    assert context.workspace.membership_uuid is None and context.workspace.role is None
    async with ap.persistence_mgr.tenant_scope('workspace-a'):
        other = await installation_context(ap, binding)
    assert other.principal.run_id is None and other.request_id != context.request_id


@pytest.mark.asyncio
@pytest.mark.parametrize('change', [dict(enabled=False), dict(runtime_revision=4), dict(artifact_digest='b' * 64)])
async def test_disabled_or_replaced_installation_rejects_the_captured_binding(authority, change):
    ap, binding = authority
    async with ap.persistence_mgr.tenant_uow('workspace-a') as uow:
        await uow.execute(
            sa.update(PluginSetting).where(PluginSetting.workspace_uuid == 'workspace-a').values(**change)
        )
    async with ap.persistence_mgr.tenant_scope('workspace-a'):
        with pytest.raises(ApplicationAPIException) as denied:
            await installation_context(ap, binding)
    assert denied.value.error.code == 'permission_denied'
    assert isinstance(denied.value.error.message, str) and denied.value.error.message


@pytest.mark.asyncio
async def test_revocation_is_read_again_and_foreign_installation_is_not_disclosed(authority):
    ap, binding = authority
    async with ap.persistence_mgr.tenant_uow('workspace-a') as uow:
        await uow.execute(
            sa.update(PluginSetting)
            .where(PluginSetting.workspace_uuid == 'workspace-a')
            .values(
                permission_grants={'workspace_operations': [], 'capabilities': []},
            )
        )
    async with ap.persistence_mgr.tenant_scope('workspace-a'):
        current = await installation_context(ap, binding)
    assert current.allowed_operation_ids == frozenset() and current.workspace.permissions == frozenset()
    async with ap.persistence_mgr.tenant_scope('workspace-b'):
        with pytest.raises(ApplicationAPIException) as denied:
            await installation_context(ap, binding.model_copy(update={'workspace_uuid': 'workspace-b'}))
    assert denied.value.error.code == 'not_found'
