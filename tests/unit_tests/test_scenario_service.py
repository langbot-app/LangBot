"""Exercise scenario creation and retry against a real SQLite transaction."""

import contextlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

# Initialize the application's existing import graph before individual services.
from langbot.pkg.core import app as app_module  # noqa: F401
from langbot.pkg.api.http.service import scenario
from langbot.pkg.entity.persistence.metadata import WorkspaceMetadata


class Persistence:
    def __init__(self, connection):
        self.connection = connection

    async def execute_async(self, statement):
        return await self.connection.execute(statement)

    @contextlib.asynccontextmanager
    async def tenant_uow(self, workspace):
        async with self.connection.begin():
            yield

    @staticmethod
    def serialize_model(model, row):
        return dict(row._mapping)


@pytest.mark.asyncio
async def test_import_disabled_remaps_routes_is_idempotent_and_workspace_scoped(monkeypatch):
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.connect() as connection:
        for model in (scenario.Bot, scenario.LegacyPipeline, scenario.Agent, WorkspaceMetadata):
            await connection.run_sync(lambda conn, model=model: model.__table__.create(conn))
        await connection.commit()
        ap = SimpleNamespace(
            persistence_mgr=Persistence(connection),
            bot_service=SimpleNamespace(_get_adapter_component=lambda name: SimpleNamespace(spec={'config': []})),
            ver_mgr=SimpleNamespace(get_current_version=lambda: 'test'),
            runner_registry=SimpleNamespace(
                get=AsyncMock(return_value=SimpleNamespace(plugin_version='1', config_schema=[]))
            ),
        )
        monkeypatch.setattr(scenario, 'workspace_limits', AsyncMock(return_value={}))
        monkeypatch.setattr(scenario, 'require_workspace_platform', AsyncMock())
        service = scenario.ScenarioPackService(ap)
        document = {
            'metadata': {'name': 'Support'},
            'resources': [
                {
                    'id': 'main',
                    'kind': 'bot',
                    'data': {
                        'name': 'Bot',
                        'adapter': 'test',
                        'adapter_config': {'token': ''},
                        'event_bindings': [
                            {'event_pattern': 'message.received', 'target_type': 'pipeline', 'target_uuid': 'flow'}
                        ],
                        'plugin_processors': [],
                    },
                },
                {
                    'id': 'flow',
                    'kind': 'pipeline',
                    'data': {
                        'name': 'Flow',
                        'config': {'ai': {'runner': {'id': 'runner'}, 'runner_config': {'runner': {}}}},
                        'extensions_preferences': {},
                    },
                },
            ],
            'dependencies': [{'kind': 'runner', 'id': 'runner', 'plugin_id': 'author/plugin', 'version': '1'}],
            'inputs': [
                {
                    'resource': 'main',
                    'path': ['adapter_config', 'token'],
                    'kind': 'credential',
                    'label': 'Token',
                    'required': True,
                }
            ],
        }
        request_id = 'a9758170-7e39-47fd-87fb-c101053d35dd'
        report = await service.import_package('workspace-a', document, request_id)
        assert report['inputs'][0]['status'] == 'missing'
        bot = (await connection.execute(sa.select(scenario.Bot))).first()
        flow = (await connection.execute(sa.select(scenario.LegacyPipeline))).first()
        assert bot.enable is False
        assert bot.event_bindings[0]['target_uuid'] == flow.uuid
        assert bot.workspace_uuid == flow.workspace_uuid == 'workspace-a'
        await connection.commit()
        again = await service.import_package('workspace-a', document, request_id)
        assert again['resources'] == report['resources']
        assert (await connection.execute(sa.select(sa.func.count()).select_from(scenario.Bot))).scalar() == 1
        assert await service._record('workspace-b', request_id) is None
        stored = (await connection.execute(sa.select(WorkspaceMetadata.value))).scalar()
        assert json.loads(stored)['mapping']['main'] == bot.uuid
        await connection.commit()
        original_execute = ap.persistence_mgr.execute_async

        async def fail_pipeline(statement):
            if isinstance(statement, sa.sql.dml.Insert) and statement.table.name == 'legacy_pipelines':
                raise RuntimeError('Simulated persistence failure')
            return await original_execute(statement)

        ap.persistence_mgr.execute_async = fail_pipeline
        with pytest.raises(RuntimeError, match='persistence failure'):
            await service.import_package('workspace-a', document, '9e8923bb-cf15-484d-a2de-56513c657721')
        assert (await connection.execute(sa.select(sa.func.count()).select_from(scenario.Bot))).scalar() == 1
    await engine.dispose()
