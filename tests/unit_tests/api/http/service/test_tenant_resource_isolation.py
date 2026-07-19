from __future__ import annotations

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.service.bot import BotService
from langbot.pkg.api.http.service.model import LLMModelsService
from langbot.pkg.api.http.service.pipeline import PipelineService
from langbot.pkg.api.http.service.provider import ModelProviderService
from langbot.pkg.api.http.service.tenant import require_workspace_uuid
from langbot.pkg.api.http.authz import WorkspaceRequiredError
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.bot import Bot
from langbot.pkg.entity.persistence.model import LLMModel, ModelProvider
from langbot.pkg.entity.persistence.pipeline import LegacyPipeline
from langbot.pkg.entity.persistence.workspace import Workspace
from langbot.pkg.workspace.errors import WorkspaceNotFoundError


pytestmark = pytest.mark.asyncio

WORKSPACE_A = '00000000-0000-0000-0000-00000000000a'
WORKSPACE_B = '00000000-0000-0000-0000-00000000000b'


class _PersistenceManager:
    def __init__(self, engine):
        self.engine = engine

    async def execute_async(self, *args, **kwargs):
        async with self.engine.connect() as connection:
            result = await connection.execute(*args, **kwargs)
            await connection.commit()
            return result

    @staticmethod
    def serialize_model(model, data, masked_columns=None):
        masked_columns = masked_columns or []
        return {
            column.name: (
                getattr(data, column.name).isoformat()
                if isinstance(getattr(data, column.name), datetime.datetime)
                else getattr(data, column.name)
            )
            for column in model.__table__.columns
            if column.name not in masked_columns
        }


@pytest.fixture
async def tenant_services(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "tenant-resources.db"}')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(
            sqlalchemy.insert(Workspace),
            [
                {
                    'uuid': WORKSPACE_A,
                    'instance_uuid': 'instance-a',
                    'name': 'Workspace A',
                    'slug': 'workspace-a',
                    'source': 'cloud_projection',
                },
                {
                    'uuid': WORKSPACE_B,
                    'instance_uuid': 'instance-b',
                    'name': 'Workspace B',
                    'slug': 'workspace-b',
                    'source': 'cloud_projection',
                },
            ],
        )
        await connection.execute(
            sqlalchemy.insert(ModelProvider),
            [
                {
                    'uuid': 'provider-a',
                    'workspace_uuid': WORKSPACE_A,
                    'name': 'Same Provider',
                    'requester': 'chatcmpl',
                    'base_url': 'https://a.invalid',
                    'api_keys': ['secret-a'],
                },
                {
                    'uuid': 'provider-b',
                    'workspace_uuid': WORKSPACE_B,
                    'name': 'Same Provider',
                    'requester': 'chatcmpl',
                    'base_url': 'https://b.invalid',
                    'api_keys': ['secret-b'],
                },
            ],
        )
        await connection.execute(
            sqlalchemy.insert(LLMModel),
            [
                {
                    'uuid': 'model-a',
                    'workspace_uuid': WORKSPACE_A,
                    'name': 'Same Model',
                    'provider_uuid': 'provider-a',
                    'abilities': [],
                    'extra_args': {},
                    'prefered_ranking': 0,
                },
                {
                    'uuid': 'model-b',
                    'workspace_uuid': WORKSPACE_B,
                    'name': 'Same Model',
                    'provider_uuid': 'provider-b',
                    'abilities': [],
                    'extra_args': {},
                    'prefered_ranking': 0,
                },
            ],
        )
        await connection.execute(
            sqlalchemy.insert(LegacyPipeline),
            [
                {
                    'uuid': 'pipeline-a',
                    'workspace_uuid': WORKSPACE_A,
                    'name': 'Same Pipeline',
                    'description': 'A',
                    'for_version': 'test',
                    'is_default': False,
                    'stages': [],
                    'config': {},
                    'extensions_preferences': {},
                },
                {
                    'uuid': 'pipeline-b',
                    'workspace_uuid': WORKSPACE_B,
                    'name': 'Same Pipeline',
                    'description': 'B',
                    'for_version': 'test',
                    'is_default': False,
                    'stages': [],
                    'config': {},
                    'extensions_preferences': {},
                },
            ],
        )
        await connection.execute(
            sqlalchemy.insert(Bot),
            [
                {
                    'uuid': 'bot-a',
                    'workspace_uuid': WORKSPACE_A,
                    'name': 'Same Bot',
                    'description': 'A',
                    'adapter': 'test',
                    'adapter_config': {},
                    'enable': False,
                    'use_pipeline_uuid': 'pipeline-a',
                    'use_pipeline_name': 'Same Pipeline',
                    'pipeline_routing_rules': [],
                },
                {
                    'uuid': 'bot-b',
                    'workspace_uuid': WORKSPACE_B,
                    'name': 'Same Bot',
                    'description': 'B',
                    'adapter': 'test',
                    'adapter_config': {},
                    'enable': False,
                    'use_pipeline_uuid': 'pipeline-b',
                    'use_pipeline_name': 'Same Pipeline',
                    'pipeline_routing_rules': [],
                },
            ],
        )

    runtime_provider_a = SimpleNamespace(provider_entity=SimpleNamespace(uuid='provider-a'))
    runtime_provider_b = SimpleNamespace(provider_entity=SimpleNamespace(uuid='provider-b'))
    application = SimpleNamespace(
        persistence_mgr=_PersistenceManager(engine),
        instance_config=SimpleNamespace(data={'system': {'limitation': {}}, 'api': {}}),
        ver_mgr=SimpleNamespace(get_current_version=lambda: 'test'),
        platform_mgr=SimpleNamespace(
            load_bot=AsyncMock(return_value=SimpleNamespace(enable=False)),
            remove_bot=AsyncMock(),
            get_bot_by_uuid=AsyncMock(return_value=None),
        ),
        pipeline_mgr=SimpleNamespace(
            load_pipeline=AsyncMock(),
            remove_pipeline=AsyncMock(),
        ),
        model_mgr=SimpleNamespace(
            provider_dict={'provider-a': runtime_provider_a, 'provider-b': runtime_provider_b},
            llm_models=[],
            embedding_models=[],
            rerank_models=[],
            load_provider=AsyncMock(),
            cache_provider=AsyncMock(),
            get_provider_by_uuid=AsyncMock(return_value=runtime_provider_a),
            reload_provider=AsyncMock(),
            remove_provider=AsyncMock(),
            load_llm_model_with_provider=AsyncMock(return_value=SimpleNamespace()),
            cache_llm_model=AsyncMock(),
            remove_llm_model=AsyncMock(),
        ),
        sess_mgr=SimpleNamespace(session_list=[]),
    )
    application.provider_service = ModelProviderService(application)
    application.llm_model_service = LLMModelsService(application)
    application.pipeline_service = PipelineService(application)
    application.bot_service = BotService(application)

    yield application, engine
    await engine.dispose()


async def test_context_is_mandatory_and_fails_closed(tenant_services):
    application, _engine = tenant_services

    with pytest.raises(WorkspaceRequiredError):
        require_workspace_uuid(None)
    with pytest.raises(WorkspaceRequiredError):
        await application.bot_service.get_bots(None)
    with pytest.raises(WorkspaceRequiredError):
        await application.provider_service.get_providers(None)
    with pytest.raises(WorkspaceRequiredError):
        await application.pipeline_service.get_pipelines(None)
    with pytest.raises(WorkspaceRequiredError):
        await application.llm_model_service.get_llm_models(None)


async def test_lists_and_same_names_are_isolated(tenant_services):
    application, _engine = tenant_services

    assert [item['uuid'] for item in await application.bot_service.get_bots(WORKSPACE_A)] == ['bot-a']
    assert [item['uuid'] for item in await application.pipeline_service.get_pipelines(WORKSPACE_A)] == ['pipeline-a']
    assert [item['uuid'] for item in await application.provider_service.get_providers(WORKSPACE_A)] == ['provider-a']
    assert [item['uuid'] for item in await application.llm_model_service.get_llm_models(WORKSPACE_A)] == ['model-a']


async def test_cross_workspace_uuid_guessing_cannot_read_update_or_delete(tenant_services):
    application, engine = tenant_services

    assert await application.bot_service.get_bot(WORKSPACE_A, 'bot-b') is None
    assert await application.pipeline_service.get_pipeline(WORKSPACE_A, 'pipeline-b') is None
    assert await application.provider_service.get_provider(WORKSPACE_A, 'provider-b') is None
    assert await application.llm_model_service.get_llm_model(WORKSPACE_A, 'model-b') is None

    with pytest.raises(WorkspaceNotFoundError):
        await application.bot_service.update_bot(WORKSPACE_A, 'bot-b', {'name': 'stolen'})
    with pytest.raises(WorkspaceNotFoundError):
        await application.pipeline_service.update_pipeline(
            WORKSPACE_A,
            'pipeline-b',
            {'description': 'stolen'},
        )
    with pytest.raises(WorkspaceNotFoundError):
        await application.provider_service.update_provider(WORKSPACE_A, 'provider-b', {'name': 'stolen'})
    with pytest.raises(WorkspaceNotFoundError):
        await application.llm_model_service.update_llm_model(
            WORKSPACE_A,
            'model-b',
            {'name': 'stolen'},
        )

    with pytest.raises(WorkspaceNotFoundError):
        await application.bot_service.delete_bot(WORKSPACE_A, 'bot-b')
    with pytest.raises(WorkspaceNotFoundError):
        await application.pipeline_service.delete_pipeline(WORKSPACE_A, 'pipeline-b')
    with pytest.raises(WorkspaceNotFoundError):
        await application.provider_service.delete_provider(WORKSPACE_A, 'provider-b')
    with pytest.raises(WorkspaceNotFoundError):
        await application.llm_model_service.delete_llm_model(WORKSPACE_A, 'model-b')

    async with engine.connect() as connection:
        assert await connection.scalar(sqlalchemy.select(Bot.name).where(Bot.uuid == 'bot-b')) == 'Same Bot'
        assert (
            await connection.scalar(sqlalchemy.select(LegacyPipeline.uuid).where(LegacyPipeline.uuid == 'pipeline-b'))
            == 'pipeline-b'
        )
        assert (
            await connection.scalar(sqlalchemy.select(ModelProvider.name).where(ModelProvider.uuid == 'provider-b'))
            == 'Same Provider'
        )
        assert await connection.scalar(sqlalchemy.select(LLMModel.uuid).where(LLMModel.uuid == 'model-b')) == 'model-b'


async def test_cross_workspace_parent_references_are_rejected(tenant_services):
    application, _engine = tenant_services

    with pytest.raises(WorkspaceNotFoundError):
        await application.bot_service.update_bot(
            WORKSPACE_A,
            'bot-a',
            {'use_pipeline_uuid': 'pipeline-b'},
        )

    with pytest.raises(WorkspaceNotFoundError):
        await application.llm_model_service.create_llm_model(
            WORKSPACE_A,
            {
                'name': 'Cross reference',
                'provider_uuid': 'provider-b',
                'abilities': [],
                'extra_args': {},
                'prefered_ranking': 0,
            },
            auto_set_to_default_pipeline=False,
        )


async def test_created_resources_are_bound_to_callers_workspace(tenant_services):
    application, engine = tenant_services

    runtime_provider = SimpleNamespace(provider_entity=SimpleNamespace(uuid='provider-created'))
    application.model_mgr.load_provider.return_value = runtime_provider
    provider_uuid = await application.provider_service.create_provider(
        WORKSPACE_A,
        {
            'name': 'Created Provider',
            'requester': 'chatcmpl',
            'base_url': 'https://created.invalid',
            'api_keys': [],
        },
    )
    pipeline_uuid = await application.pipeline_service.create_pipeline(
        WORKSPACE_A,
        {'name': 'Created Pipeline', 'description': 'created'},
    )
    bot_uuid = await application.bot_service.create_bot(
        WORKSPACE_A,
        {
            'name': 'Created Bot',
            'description': 'created',
            'adapter': 'test',
            'adapter_config': {},
            'enable': False,
            'pipeline_routing_rules': [],
        },
    )
    model_uuid = await application.llm_model_service.create_llm_model(
        WORKSPACE_A,
        {
            'name': 'Created Model',
            'provider_uuid': 'provider-a',
            'abilities': [],
            'extra_args': {},
            'prefered_ranking': 0,
        },
        auto_set_to_default_pipeline=False,
    )

    async with engine.connect() as connection:
        assert (
            await connection.scalar(
                sqlalchemy.select(ModelProvider.workspace_uuid).where(ModelProvider.uuid == provider_uuid)
            )
            == WORKSPACE_A
        )
        assert (
            await connection.scalar(
                sqlalchemy.select(LegacyPipeline.workspace_uuid).where(LegacyPipeline.uuid == pipeline_uuid)
            )
            == WORKSPACE_A
        )
        assert await connection.scalar(sqlalchemy.select(Bot.workspace_uuid).where(Bot.uuid == bot_uuid)) == WORKSPACE_A
        assert (
            await connection.scalar(sqlalchemy.select(LLMModel.workspace_uuid).where(LLMModel.uuid == model_uuid))
            == WORKSPACE_A
        )
