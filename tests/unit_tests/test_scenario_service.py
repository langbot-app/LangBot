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


@pytest.mark.asyncio
async def test_knowledge_configuration_roundtrip_excludes_documents_and_remaps_references(monkeypatch):
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.connect() as connection:
        for model in (
            scenario.Bot,
            scenario.Agent,
            scenario.KnowledgeBase,
            scenario.MCPServer,
            scenario.PluginSetting,
            WorkspaceMetadata,
        ):
            await connection.run_sync(lambda conn, model=model: model.__table__.create(conn))
        await connection.commit()
        descriptor = SimpleNamespace(
            plugin_version='1',
            config_schema=[
                {'name': 'knowledge', 'type': 'knowledge-base-multi-selector', 'required': True},
                {'name': 'prompt', 'type': 'string'},
            ],
            get_plugin_id=lambda: 'author/runner',
        )

        def plugin(name):
            return {
                'manifest': {
                    'manifest': {'metadata': {'author': 'author', 'name': name, 'version': '1'}, 'spec': {'config': []}}
                }
            }

        knowledge_service = SimpleNamespace(
            get_engine_creation_schema=AsyncMock(
                return_value={
                    'schema': [
                        {'name': 'chunk_size', 'type': 'integer'},
                        {'name': 'private_value', 'type': 'password', 'required': True},
                        {'name': 'embedding', 'type': 'llm-model-selector'},
                    ]
                }
            ),
            get_engine_retrieval_schema=AsyncMock(return_value=[{'name': 'top_k', 'type': 'integer'}]),
        )
        ap = SimpleNamespace(
            persistence_mgr=Persistence(connection),
            knowledge_service=knowledge_service,
            bot_service=SimpleNamespace(_get_adapter_component=lambda name: SimpleNamespace(spec={'config': []})),
            runner_registry=SimpleNamespace(get=AsyncMock(return_value=descriptor)),
            plugin_connector=SimpleNamespace(
                require_workspace_context=AsyncMock(),
                list_plugins=AsyncMock(return_value=[plugin('runner'), plugin('knowledge')]),
                install_plugin=AsyncMock(),
            ),
        )
        monkeypatch.setattr(scenario, 'workspace_limits', AsyncMock(return_value={}))
        monkeypatch.setattr(scenario, 'require_workspace_platform', AsyncMock())
        service = scenario.ScenarioPackService(ap)
        source = {
            ('bot', 'source-bot'): {
                'name': 'Support',
                'description': '',
                'adapter': 'test',
                'adapter_config': {},
                'event_bindings': [
                    {'event_pattern': 'message.received', 'target_type': 'agent', 'target_uuid': 'source-agent'}
                ],
                'plugin_processors': [],
            },
            ('agent', 'source-agent'): {
                'name': 'Answer agent',
                'description': '',
                'config': {
                    'runner': {'id': 'runner'},
                    'runner_config': {'runner': {'knowledge': ['source-kb'], 'prompt': 'Answer questions clearly'}},
                },
            },
            ('knowledge_base', 'source-kb'): {
                'name': 'Manual',
                'description': 'Company manual',
                'knowledge_engine_plugin_id': 'author/knowledge',
                'collection_id': 'private-collection',
                'creation_settings': {'chunk_size': 512, 'private_value': 'secret-value', 'embedding': 'source-model'},
                'retrieval_settings': {'top_k': 8},
                'files': ['private.pdf'],
                'initialized': True,
            },
            ('mcp_server', 'source-mcp'): {
                'name': 'Search',
                'mode': 'remote',
                'readme': '',
                'extra_args': {'url': 'https://example.test/mcp', 'headers': {'X-Custom': 'private-header'}},
            },
        }
        original_row = service._row
        service._row = AsyncMock(side_effect=lambda context, kind, identifier: source[(kind, identifier)])
        document = await service.export(
            'workspace-a',
            'source-bot',
            selection={
                'agent_uuids': ['source-agent'],
                'knowledge_base_uuids': ['source-kb'],
                'mcp_server_uuids': ['source-mcp'],
            },
        )
        service._row = original_row
        serialized = json.dumps(document)
        for forbidden in (
            'private.pdf',
            'private-collection',
            'secret-value',
            'source-model',
            'source-kb',
            'private-header',
        ):
            assert forbidden not in serialized
        kb_resource = next(item for item in document['resources'] if item['kind'] == 'knowledge_base')
        assert kb_resource['data']['creation_settings']['chunk_size'] == 512
        assert kb_resource['data']['retrieval_settings']['top_k'] == 8
        assert kb_resource['data']['creation_settings']['private_value'] == ''
        await connection.commit()
        report = await service.import_package('workspace-a', document, '7b204168-f5b0-47e8-b47f-10770f6ca3b8')
        kb = (await connection.execute(sa.select(scenario.KnowledgeBase))).first()
        agent = (await connection.execute(sa.select(scenario.Agent))).first()
        mcp = (await connection.execute(sa.select(scenario.MCPServer))).first()
        assert kb.initialized is False
        assert kb.collection_id == kb.uuid and kb.collection_id != 'private-collection'
        assert agent.config['runner_config']['runner']['knowledge'] == [kb.uuid]
        assert agent.config['runner_config']['runner']['prompt'] == 'Answer questions clearly'
        assert mcp.enable is False and mcp.extra_args['headers']['X-Custom'] == ''
        assert any(item['path'] == ['initialized'] and item['status'] == 'missing' for item in report['inputs'])
        assert all(item['status'] == 'ready' for item in report['dependencies'])
        await connection.commit()
        again = await service.import_package('workspace-a', document, report['id'])
        assert again['resources'] == report['resources']
        ap.plugin_connector.install_plugin.assert_not_awaited()
    await engine.dispose()


@pytest.mark.asyncio
async def test_missing_plugins_install_once_with_version_and_config(monkeypatch):
    ap = SimpleNamespace(
        plugin_connector=SimpleNamespace(
            require_workspace_context=AsyncMock(),
            install_plugin=AsyncMock(),
            set_plugin_config=AsyncMock(),
            get_plugin_info=AsyncMock(
                return_value={'manifest': {'manifest': {'spec': {'config': [{'name': 'mode', 'type': 'string'}]}}}}
            ),
        )
    )
    service = scenario.ScenarioPackService(ap)
    missing = {
        'kind': 'runner',
        'id': 'runner',
        'plugin_id': 'author/runner',
        'version': '1',
        'config': {'mode': 'precise'},
        'status': 'missing',
    }
    service._dependencies = AsyncMock(
        side_effect=[
            [missing, {**missing, 'kind': 'plugin', 'version': None}],
            [{**missing, 'status': 'ready'}],
        ]
    )
    monkeypatch.setattr(scenario, 'workspace_limits', AsyncMock(return_value={}))
    package = scenario.ScenarioPackage.model_construct(resources=[])
    await service._install_dependencies('workspace-a', package)
    ap.plugin_connector.install_plugin.assert_awaited_once_with(
        scenario.PluginInstallSource.MARKETPLACE,
        {'plugin_author': 'author', 'plugin_name': 'runner', 'plugin_version': '1'},
    )
    ap.plugin_connector.set_plugin_config.assert_awaited_once_with('author', 'runner', {'mode': 'precise'})


@pytest.mark.asyncio
async def test_plugin_install_failure_creates_no_resources(monkeypatch):
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.connect() as connection:
        for model in (scenario.Bot, WorkspaceMetadata):
            await connection.run_sync(lambda conn, model=model: model.__table__.create(conn))
        await connection.commit()
        service = scenario.ScenarioPackService(SimpleNamespace(persistence_mgr=Persistence(connection)))
        document = {
            'metadata': {'name': 'Broken'},
            'resources': [
                {'id': 'main', 'kind': 'bot', 'data': {'name': 'Bot', 'adapter': 'test', 'adapter_config': {}}}
            ],
        }
        service.preview = AsyncMock(return_value={'package': document})
        service._install_dependencies = AsyncMock(side_effect=RuntimeError('Marketplace unavailable'))
        with pytest.raises(RuntimeError, match='Marketplace unavailable'):
            await service.import_package('workspace-a', document, '0ae31eb1-8528-49a5-a038-bf995bf6b14b')
        assert (await connection.execute(sa.select(sa.func.count()).select_from(scenario.Bot))).scalar() == 0
        assert (await connection.execute(sa.select(sa.func.count()).select_from(WorkspaceMetadata))).scalar() == 0
    await engine.dispose()
