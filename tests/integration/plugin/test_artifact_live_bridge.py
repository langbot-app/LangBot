"""Real SQLite Artifact ownership and read leases through the secured SDK bridge."""

# ruff: noqa: F811
import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
import sqlalchemy as sa

from langbot.pkg.entity.persistence.artifact import ArtifactReference
from langbot.pkg.entity.persistence.plugin import PluginSetting
from langbot.pkg.plugin.handler import RuntimeConnectionHandler
from langbot_plugin.api.proxies.langbot_api import LangBotAPIProxy
from langbot_plugin.api.proxies.artifacts import ArtifactOperationError
from langbot_plugin.entities.io.context import InstallationBinding
from langbot_plugin.entities.io.errors import ActionCallError
from tests.integration.storage.test_plugin_artifacts import plugin_context, OPERATIONS
from tests.integration.storage.test_artifacts import artifact_replicas, replicas  # noqa: F401
from tests.integration.skill import test_persistent_skill_replicas as storage_tests

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.sdk_core,
    pytest.mark.contract('artifact_workspace_live'),
]

# sdk_core is account-free. PG/S3 remain covered by the opt-in Artifact storage matrix.
persistence_case = pytest.fixture(params=['sqlite-database'])(storage_tests.persistence_case.__wrapped__)


async def test_live_sdk_bridge_revocation_and_cancel_release_read_lease(artifact_replicas, monkeypatch):
    case = artifact_replicas
    context = await plugin_context(case)
    async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        await uow.execute(sa.update(PluginSetting).values(runtime_revision=1, artifact_digest='a' * 64))
    binding = InstallationBinding(
        instance_uuid=context.instance_uuid,
        workspace_uuid=context.workspace_uuid,
        placement_generation=context.placement_generation,
        installation_uuid=context.principal.installation_uuid,
        runtime_revision=1,
        artifact_digest='a' * 64,
    )
    handler = RuntimeConnectionHandler(Mock(), AsyncMock(return_value=True), case.a.app)
    handler.register_installation_binding(binding, plugin_author='artifact-test', plugin_name='one')
    handler._current_action_context.set(binding)

    class Bridge:
        async def call_action(self, action, data, timeout=180, **kwargs):
            response = await handler.actions[action.value](data)
            if response.code:
                raise ActionCallError(response.message, response.data)
            return response.data

    proxy = LangBotAPIProxy(Bridge()).artifacts
    item = await proxy.create('bytes.bin', b'\x00\xff')
    assert (await proxy.read(item.id)).content == b'\x00\xff'
    entered, release = asyncio.Event(), asyncio.Event()
    store = case.a.app.storage_mgr.content_store
    original = store._read

    async def slow(*args, **kwargs):
        entered.set()
        await release.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(store, '_read', slow)
    reading = asyncio.create_task(proxy.read(item.id))
    await asyncio.wait_for(entered.wait(), 10)
    reading.cancel()
    with pytest.raises(asyncio.CancelledError):
        await reading
    async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        assert not (await uow.execute(sa.select(ArtifactReference.artifact_id))).first()
    entered.clear()
    reading = asyncio.create_task(proxy.read(item.id))
    await asyncio.wait_for(entered.wait(), 10)
    async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        await uow.execute(
            sa.update(PluginSetting).values(
                permission_grants={'workspace_operations': sorted(OPERATIONS - {'artifact.read'}), 'capabilities': []}
            )
        )
    release.set()
    with pytest.raises(ArtifactOperationError) as error:
        await reading
    assert error.value.code == 'permission_denied'
