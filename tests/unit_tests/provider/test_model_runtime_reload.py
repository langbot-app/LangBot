"""Model runtime cache reload and cache-miss recovery (LANG-318).

A Cloud catalog sync reloads every Workspace. The reload used to empty all
runtime caches first, so any concurrent message failed with "No authorized
model" although its model was configured.
"""

from __future__ import annotations

import asyncio
import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.entity.persistence import model as persistence_model
from langbot.pkg.workspace.entities import WorkspaceExecutionBinding
from tests.unit_tests.provider.conftest import _make_mock_result

INSTANCE = 'instance-test'
WORKSPACES = ['ws-a', 'ws-b', 'ws-c']


def _binding(workspace_uuid: str, generation: int = 1) -> WorkspaceExecutionBinding:
    return WorkspaceExecutionBinding(
        instance_uuid=INSTANCE,
        workspace_uuid=workspace_uuid,
        placement_generation=generation,
        write_fenced=False,
        state='active',
    )


def _context(workspace_uuid: str) -> ExecutionContext:
    return ExecutionContext(instance_uuid=INSTANCE, workspace_uuid=workspace_uuid, placement_generation=1)


def _provider(workspace_uuid: str, api_keys=None) -> persistence_model.ModelProvider:
    return persistence_model.ModelProvider(
        workspace_uuid=workspace_uuid,
        uuid=f'provider-{workspace_uuid}',
        name='Provider',
        requester='fake-requester',
        base_url='https://example.com',
        api_keys=api_keys or ['key'],
    )


def _llm(workspace_uuid: str) -> persistence_model.LLMModel:
    return persistence_model.LLMModel(
        workspace_uuid=workspace_uuid,
        uuid=f'model-{workspace_uuid}',
        name='chat-model',
        provider_uuid=f'provider-{workspace_uuid}',
        abilities=[],
        extra_args={},
    )


class _FakeDB:
    """Workspace-scoped fake persistence for the Cloud loading path."""

    def __init__(self):
        self.providers = {ws: [_provider(ws)] for ws in WORKSPACES}
        self.llm_models = {ws: [_llm(ws)] for ws in WORKSPACES}
        self.active_workspace: str | None = None
        self.uow_delay = 0.0
        self.failing_workspaces: set[str] = set()

    @contextlib.asynccontextmanager
    async def tenant_uow(self, workspace_uuid):
        if workspace_uuid in self.failing_workspaces:
            raise RuntimeError('tenant transaction failed')
        await asyncio.sleep(self.uow_delay)
        previous, self.active_workspace = self.active_workspace, workspace_uuid
        try:
            yield SimpleNamespace()
        finally:
            self.active_workspace = previous

    def tenant_scope(self, workspace_uuid):
        return self.tenant_uow(workspace_uuid)

    async def execute_async(self, query):
        text = str(query)
        workspace = self.active_workspace
        params = query.compile().params
        workspace = next((v for k, v in params.items() if k.startswith('workspace_uuid')), workspace)
        uuid = next((v for k, v in params.items() if k.startswith('uuid')), None)
        if 'model_providers' in text:
            rows = self.providers.get(workspace, [])
        elif 'llm_models' in text:
            rows = self.llm_models.get(workspace, [])
        else:
            rows = []
        if uuid is not None:
            rows = [row for row in rows if row.uuid == uuid]
        return _make_mock_result(rows, first_item=rows[0] if rows else None)


@pytest.fixture
def cloud_mgr(fake_requester_registry):
    model_mgr = fake_requester_registry
    db = _FakeDB()
    persistence = model_mgr.ap.persistence_mgr
    persistence.mode = SimpleNamespace(value='cloud_runtime')
    persistence.tenant_uow = db.tenant_uow
    persistence.tenant_scope = db.tenant_scope
    persistence.execute_async = db.execute_async
    model_mgr.ap.workspace_service.list_active_execution_bindings = AsyncMock(
        return_value=[_binding(ws) for ws in WORKSPACES]
    )
    model_mgr.ap.workspace_service.get_execution_binding = AsyncMock(side_effect=lambda ws, **kwargs: _binding(ws))
    model_mgr.requester_components = model_mgr.ap.discover.get_components_by_kind('LLMAPIRequester')
    model_mgr.requester_dict = {
        component.metadata.name: component.get_python_component_class() for component in model_mgr.requester_components
    }
    return model_mgr, db


@pytest.mark.asyncio
async def test_configured_model_stays_resolvable_during_full_reload(cloud_mgr):
    model_mgr, db = cloud_mgr
    await model_mgr.load_models_from_db()
    target = _context('ws-c')
    before = await model_mgr.get_model_by_uuid(target, 'model-ws-c')

    db.uow_delay = 0.05
    reload_task = asyncio.create_task(model_mgr.load_models_from_db())
    await asyncio.sleep(0.02)
    assert not reload_task.done()
    during = await model_mgr.get_model_by_uuid(target, 'model-ws-c')
    await reload_task
    after = await model_mgr.get_model_by_uuid(target, 'model-ws-c')

    assert during is before
    assert after.model_entity.uuid == 'model-ws-c'
    # Unchanged providers are adopted instead of being retired and rebuilt.
    assert after.provider is before.provider


@pytest.mark.asyncio
async def test_reload_rebuilds_provider_when_configuration_changes(cloud_mgr):
    model_mgr, db = cloud_mgr
    await model_mgr.load_models_from_db()
    before = await model_mgr.get_model_by_uuid(_context('ws-a'), 'model-ws-a')

    db.providers['ws-a'] = [_provider('ws-a', api_keys=['rotated-key'])]
    await model_mgr.load_models_from_db()
    after = await model_mgr.get_model_by_uuid(_context('ws-a'), 'model-ws-a')

    assert after.provider is not before.provider
    assert after.provider.token_mgr.get_token() == 'rotated-key'


@pytest.mark.asyncio
async def test_one_failing_workspace_does_not_unload_the_others(cloud_mgr):
    model_mgr, db = cloud_mgr
    db.failing_workspaces = {'ws-a'}
    await model_mgr.load_models_from_db()

    assert (await model_mgr.get_model_by_uuid(_context('ws-b'), 'model-ws-b')).model_entity.uuid == 'model-ws-b'
    assert (await model_mgr.get_model_by_uuid(_context('ws-c'), 'model-ws-c')).model_entity.uuid == 'model-ws-c'
    model_mgr.ap.logger.error.assert_called()

    # Once the tenant recovers, its model is loaded on first use.
    db.failing_workspaces = set()
    assert (await model_mgr.get_model_by_uuid(_context('ws-a'), 'model-ws-a')).model_entity.uuid == 'model-ws-a'


@pytest.mark.asyncio
async def test_cache_miss_loads_persisted_model_and_missing_model_still_fails(cloud_mgr):
    model_mgr, db = cloud_mgr
    # Nothing loaded yet: e.g. written on another replica after startup.
    model = await model_mgr.get_model_by_uuid(_context('ws-b'), 'model-ws-b')
    assert model.model_entity.uuid == 'model-ws-b'
    assert await model_mgr.get_model_by_uuid(_context('ws-b'), 'model-ws-b') is model

    with pytest.raises(ValueError, match='not found'):
        await model_mgr.get_model_by_uuid(_context('ws-b'), 'deleted-model')
    # A model of another Workspace is never resolved through this scope.
    with pytest.raises(ValueError, match='not found'):
        await model_mgr.get_model_by_uuid(_context('ws-b'), 'model-ws-a')


@pytest.mark.asyncio
async def test_writes_racing_with_reload_are_not_overwritten_by_stale_rows(cloud_mgr):
    model_mgr, db = cloud_mgr
    await model_mgr.load_models_from_db()

    db.uow_delay = 0.05
    reload_task = asyncio.create_task(model_mgr.load_models_from_db())
    await asyncio.sleep(0.01)
    # The model is deleted while the reload is staging the previous rows.
    db.llm_models['ws-a'] = []
    await model_mgr.remove_llm_model(_context('ws-a'), 'model-ws-a')
    await reload_task

    with pytest.raises(ValueError, match='not found'):
        await model_mgr.get_model_by_uuid(_context('ws-a'), 'model-ws-a')
    assert (await model_mgr.get_model_by_uuid(_context('ws-b'), 'model-ws-b')).model_entity.uuid == 'model-ws-b'
