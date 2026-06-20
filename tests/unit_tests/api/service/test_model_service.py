"""
Unit tests for LLMModelsService, EmbeddingModelsService, and RerankModelsService.

Tests model management operations including:
- Model CRUD operations
- Model with provider info
- Provider auto-creation on model create/update
- Runtime model loading/unloading
- Model deletion

Source: src/langbot/pkg/api/http/service/model.py
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.agent.runner.default_config import AgentRunnerDefaultConfigService
from langbot.pkg.agent.runner.descriptor import AgentRunnerDescriptor
from langbot.pkg.api.http.service.model import (
    LLMModelsService,
    EmbeddingModelsService,
    RerankModelsService,
    _parse_provider_api_keys,
    _runtime_model_data,
    _validate_provider_supports,
)
from langbot.pkg.entity.persistence.model import LLMModel, EmbeddingModel, RerankModel, ModelProvider


pytestmark = pytest.mark.asyncio
RUNNER_ID = 'plugin:test/runner/default'


def _create_mock_llm_model(
    model_uuid: str = 'llm-uuid',
    name: str = 'Test LLM',
    provider_uuid: str = 'provider-uuid',
    abilities: list = None,
    context_length: int | None = None,
    extra_args: dict = None,
) -> Mock:
    """Helper to create mock LLMModel entity."""
    model = Mock(spec=LLMModel)
    model.uuid = model_uuid
    model.name = name
    model.provider_uuid = provider_uuid
    model.abilities = abilities or []
    model.context_length = context_length
    model.extra_args = extra_args or {}
    return model


def _create_mock_embedding_model(
    model_uuid: str = 'embedding-uuid',
    name: str = 'Test Embedding',
    provider_uuid: str = 'provider-uuid',
) -> Mock:
    """Helper to create mock EmbeddingModel entity."""
    model = Mock(spec=EmbeddingModel)
    model.uuid = model_uuid
    model.name = name
    model.provider_uuid = provider_uuid
    model.extra_args = {}
    return model


def _create_mock_rerank_model(
    model_uuid: str = 'rerank-uuid',
    name: str = 'Test Rerank',
    provider_uuid: str = 'provider-uuid',
) -> Mock:
    """Helper to create mock RerankModel entity."""
    model = Mock(spec=RerankModel)
    model.uuid = model_uuid
    model.name = name
    model.provider_uuid = provider_uuid
    model.extra_args = {}
    return model


def _create_mock_provider(
    provider_uuid: str = 'provider-uuid',
    name: str = 'Test Provider',
    api_keys: list = None,
) -> Mock:
    """Helper to create mock ModelProvider entity."""
    provider = Mock(spec=ModelProvider)
    provider.uuid = provider_uuid
    provider.name = name
    provider.requester = 'openai'
    provider.base_url = 'https://api.openai.com'
    provider.api_keys = api_keys or ['key']
    return provider


def _create_mock_result(items: list = None, first_item=None):
    """Create mock result object for persistence queries."""
    result = Mock()
    result.all = Mock(return_value=items or [])
    result.first = Mock(return_value=first_item)
    return result


class FakeAgentRunnerRegistry:
    async def get(self, runner_id, bound_plugins=None):
        return AgentRunnerDescriptor(
            id=runner_id,
            source='plugin',
            label={'en_US': 'Test Runner'},
            plugin_author='test',
            plugin_name='runner',
            runner_name='default',
            config_schema=[
                {'name': 'model', 'type': 'model-fallback-selector', 'default': {'primary': '', 'fallbacks': []}},
            ],
            permissions={'models': ['invoke']},
        )


class TestParseProviderApiKeys:
    """Tests for _parse_provider_api_keys helper function."""

    def test_parse_valid_json_string(self):
        """Parses valid JSON string to list."""
        provider_dict = {'api_keys': '["key1", "key2"]'}
        result = _parse_provider_api_keys(provider_dict)
        assert result['api_keys'] == ['key1', 'key2']

    def test_parse_invalid_json_returns_empty(self):
        """Returns empty list for invalid JSON."""
        provider_dict = {'api_keys': 'invalid json'}
        result = _parse_provider_api_keys(provider_dict)
        assert result['api_keys'] == []

    def test_parse_already_list(self):
        """Returns unchanged if already a list."""
        provider_dict = {'api_keys': ['key1', 'key2']}
        result = _parse_provider_api_keys(provider_dict)
        assert result['api_keys'] == ['key1', 'key2']

    def test_parse_missing_key(self):
        """Handles missing api_keys key."""
        provider_dict = {'name': 'Provider'}
        result = _parse_provider_api_keys(provider_dict)
        assert 'api_keys' not in result


class TestRuntimeModelData:
    """Tests for _runtime_model_data helper function."""

    def test_runtime_data_preserves_uuid(self):
        """Preserves UUID in runtime data."""
        update_payload = {'name': 'Updated', 'provider_uuid': 'provider'}
        result = _runtime_model_data('model-uuid', update_payload)
        assert result['uuid'] == 'model-uuid'
        assert result['name'] == 'Updated'

    def test_runtime_data_copies_all_fields(self):
        """Copies all fields from payload."""
        update_payload = {
            'name': 'Model',
            'provider_uuid': 'provider',
            'abilities': ['vision'],
            'context_length': 128000,
            'extra_args': {'temp': 0.7},
        }
        result = _runtime_model_data('uuid', update_payload)
        assert result['abilities'] == ['vision']
        assert result['context_length'] == 128000
        assert result['extra_args'] == {'temp': 0.7}


class TestLLMModelsServiceGetLLMModels:
    """Tests for LLMModelsService.get_llm_models method."""

    async def test_get_llm_models_empty_list(self):
        """Returns empty list when no models exist."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        mock_result = _create_mock_result([])
        mock_provider_result = _create_mock_result([])

        call_count = 0

        async def mock_execute(query):
            return mock_result if call_count == 0 else mock_provider_result

        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'uuid': entity.uuid,
                'name': entity.name,
                'provider_uuid': entity.provider_uuid,
            }
        )

        service = LLMModelsService(ap)

        # Execute
        result = await service.get_llm_models()

        # Verify
        assert result == []

    async def test_get_llm_models_with_provider_info(self):
        """Returns models with provider info."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        model = _create_mock_llm_model(context_length=128000)
        provider = _create_mock_provider()

        mock_model_result = _create_mock_result([model])
        mock_provider_result = _create_mock_result([provider])

        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            return mock_model_result if call_count == 1 else mock_provider_result

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'uuid': entity.uuid,
                'name': entity.name,
                'provider_uuid': entity.provider_uuid if hasattr(entity, 'provider_uuid') else None,
                'context_length': getattr(entity, 'context_length', None),
                'api_keys': entity.api_keys if hasattr(entity, 'api_keys') else None,
            }
        )

        service = LLMModelsService(ap)

        # Execute
        result = await service.get_llm_models()

        # Verify
        assert len(result) == 1
        assert result[0]['name'] == 'Test LLM'
        assert result[0]['context_length'] == 128000

    async def test_get_llm_models_hide_secret_keys(self):
        """Hides secret API keys when include_secret=False."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        model = _create_mock_llm_model()
        provider = _create_mock_provider(api_keys=['secret-key-1', 'secret-key-2'])

        mock_model_result = _create_mock_result([model])
        mock_provider_result = _create_mock_result([provider])

        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            return mock_model_result if call_count == 1 else mock_provider_result

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'uuid': entity.uuid,
                'name': entity.name,
                'provider_uuid': entity.provider_uuid if hasattr(entity, 'provider_uuid') else None,
                'api_keys': entity.api_keys if hasattr(entity, 'api_keys') else None,
            }
        )

        service = LLMModelsService(ap)

        # Execute
        result = await service.get_llm_models(include_secret=False)

        # Verify - keys should be masked
        assert result[0]['provider']['api_keys'] == ['***', '***']


class TestLLMModelsServiceGetLLMModel:
    """Tests for LLMModelsService.get_llm_model method."""

    async def test_get_llm_model_found(self):
        """Returns model when found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        model = _create_mock_llm_model(model_uuid='found-uuid', context_length=128000)
        provider = _create_mock_provider()

        mock_model_result = _create_mock_result([], first_item=model)
        mock_provider_result = _create_mock_result([], first_item=provider)

        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            return mock_model_result if call_count == 1 else mock_provider_result

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'uuid': entity.uuid,
                'name': entity.name,
                'provider_uuid': getattr(entity, 'provider_uuid', None),
                'context_length': getattr(entity, 'context_length', None),
                'api_keys': getattr(entity, 'api_keys', None),
            }
        )

        service = LLMModelsService(ap)

        # Execute
        result = await service.get_llm_model('found-uuid')

        # Verify
        assert result is not None
        assert result['uuid'] == 'found-uuid'
        assert result['context_length'] == 128000

    async def test_get_llm_model_not_found(self):
        """Returns None when model not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        mock_result = _create_mock_result([], first_item=None)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = LLMModelsService(ap)

        # Execute
        result = await service.get_llm_model('nonexistent-uuid')

        # Verify
        assert result is None


class TestLLMModelsServiceGetLLMModelsByProvider:
    """Tests for LLMModelsService.get_llm_models_by_provider method."""

    async def test_get_models_by_provider_uuid(self):
        """Returns models for specific provider."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        model1 = _create_mock_llm_model(model_uuid='model-1', provider_uuid='target-provider')
        model2 = _create_mock_llm_model(model_uuid='model-2', provider_uuid='target-provider')

        mock_result = _create_mock_result([model1, model2])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(return_value={'uuid': 'model-1', 'name': 'Model 1'})

        service = LLMModelsService(ap)

        # Execute
        result = await service.get_llm_models_by_provider('target-provider')

        # Verify
        assert len(result) == 2


class TestLLMModelsServiceCreateLLMModel:
    """Tests for LLMModelsService.create_llm_model method."""

    async def test_create_llm_model_generates_uuid(self):
        """Creates LLM model with generated UUID."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.provider_dict = {'provider-uuid': Mock()}
        ap.model_mgr.llm_models = []
        ap.model_mgr.load_llm_model_with_provider = AsyncMock(return_value=Mock())
        ap.pipeline_service = SimpleNamespace()
        ap.pipeline_service.update_pipeline = AsyncMock()

        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = LLMModelsService(ap)

        # Execute
        model_uuid = await service.create_llm_model(
            {
                'name': 'New LLM',
                'provider_uuid': 'provider-uuid',
                'abilities': [],
                'extra_args': {},
            }
        )

        # Verify
        assert model_uuid is not None
        assert len(model_uuid) == 36  # UUID format

    async def test_create_llm_model_preserve_uuid(self):
        """Creates LLM model preserving provided UUID."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.provider_dict = {'provider-uuid': Mock()}
        ap.model_mgr.llm_models = []
        ap.model_mgr.load_llm_model_with_provider = AsyncMock(return_value=Mock())
        ap.pipeline_service = SimpleNamespace()
        ap.pipeline_service.update_pipeline = AsyncMock()

        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = LLMModelsService(ap)

        # Execute
        model_uuid = await service.create_llm_model(
            {
                'uuid': 'preserved-uuid',
                'name': 'Preserved UUID Model',
                'provider_uuid': 'provider-uuid',
                'abilities': [],
                'extra_args': {},
            },
            preserve_uuid=True,
        )

        # Verify
        assert model_uuid == 'preserved-uuid'

    async def test_create_llm_model_persists_context_length_as_column(self):
        """Creates LLM model with context_length outside extra_args."""
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.provider_dict = {'provider-uuid': Mock()}
        ap.model_mgr.llm_models = []
        ap.model_mgr.load_llm_model_with_provider = AsyncMock(return_value=Mock())
        ap.pipeline_service = SimpleNamespace(update_pipeline=AsyncMock())

        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = LLMModelsService(ap)

        await service.create_llm_model(
            {
                'uuid': 'model-with-context',
                'name': 'Context Model',
                'provider_uuid': 'provider-uuid',
                'abilities': ['func_call'],
                'context_length': 128000,
                'extra_args': {'temperature': 0.2},
            },
            preserve_uuid=True,
            auto_set_to_default_pipeline=False,
        )

        runtime_entity = ap.model_mgr.load_llm_model_with_provider.await_args.args[0]
        assert runtime_entity.context_length == 128000
        assert runtime_entity.extra_args == {'temperature': 0.2}
        assert 'context_length' not in runtime_entity.extra_args

    async def test_create_llm_model_auto_sets_schema_defined_default_pipeline_model(self):
        """Auto-default model selection should use runner schema, not legacy field names."""
        ap = SimpleNamespace()
        ap.logger = Mock()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.provider_dict = {'provider-uuid': Mock()}
        ap.model_mgr.llm_models = []
        ap.model_mgr.load_llm_model_with_provider = AsyncMock(return_value=Mock())
        ap.pipeline_service = SimpleNamespace(update_pipeline=AsyncMock())
        ap.agent_runner_registry = FakeAgentRunnerRegistry()
        ap.agent_runner_default_config_service = AgentRunnerDefaultConfigService(ap)

        pipeline = SimpleNamespace(
            uuid='pipeline-uuid',
            config={
                'ai': {
                    'runner': {'id': RUNNER_ID},
                    'runner_config': {
                        RUNNER_ID: {
                            'model': {'primary': '', 'fallbacks': []},
                        },
                    },
                },
            },
        )
        ap.persistence_mgr.execute_async = AsyncMock(return_value=_create_mock_result(first_item=pipeline))

        service = LLMModelsService(ap)

        model_uuid = await service.create_llm_model({
            'uuid': 'new-model-uuid',
            'name': 'New LLM',
            'provider_uuid': 'provider-uuid',
            'abilities': [],
            'extra_args': {},
        }, preserve_uuid=True)

        assert model_uuid == 'new-model-uuid'
        ap.pipeline_service.update_pipeline.assert_awaited_once()
        updated_config = ap.pipeline_service.update_pipeline.await_args.args[1]['config']
        assert updated_config['ai']['runner_config'][RUNNER_ID]['model'] == {
            'primary': 'new-model-uuid',
            'fallbacks': [],
        }

    async def test_create_llm_model_provider_not_found_raises_error(self):
        """Raises Exception when provider not found in runtime."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.provider_dict = {}  # Empty - no provider

        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = LLMModelsService(ap)

        # Execute & Verify
        with pytest.raises(Exception, match='provider not found'):
            await service.create_llm_model(
                {
                    'name': 'No Provider Model',
                    'provider_uuid': 'nonexistent-provider',
                    'abilities': [],
                    'extra_args': {},
                }
            )

    async def test_create_llm_model_with_provider_data(self):
        """Creates provider when provider data provided."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.provider_dict = {}
        ap.model_mgr.llm_models = []
        ap.model_mgr.load_llm_model_with_provider = AsyncMock(return_value=Mock())
        ap.provider_service = SimpleNamespace()
        ap.provider_service.find_or_create_provider = AsyncMock(return_value='new-provider-uuid')
        ap.pipeline_service = SimpleNamespace()
        ap.pipeline_service.update_pipeline = AsyncMock()

        # Create runtime provider
        runtime_provider = Mock()
        ap.model_mgr.provider_dict['new-provider-uuid'] = runtime_provider

        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = LLMModelsService(ap)

        # Execute - with provider data (no UUID)
        result_uuid = await service.create_llm_model(
            {
                'name': 'Model with New Provider',
                'provider': {
                    'requester': 'openai',
                    'base_url': 'https://api.openai.com',
                    'api_keys': ['key'],
                },
                'abilities': [],
                'extra_args': {},
            }
        )

        # Verify - provider_service was called and UUID generated
        ap.provider_service.find_or_create_provider.assert_called_once()
        assert result_uuid is not None


class TestLLMModelsServiceUpdateLLMModel:
    """Tests for LLMModelsService.update_llm_model method."""

    async def test_update_llm_model_removes_uuid_from_data(self):
        """Removes uuid from update data before persisting."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.provider_dict = {'provider-uuid': Mock()}
        ap.model_mgr.llm_models = []
        ap.model_mgr.remove_llm_model = AsyncMock()
        ap.model_mgr.load_llm_model_with_provider = AsyncMock(return_value=Mock())

        ap.persistence_mgr.execute_async = AsyncMock()

        service = LLMModelsService(ap)

        # Execute
        await service.update_llm_model(
            'existing-uuid',
            {
                'uuid': 'should-be-removed',
                'name': 'Updated Name',
                'provider_uuid': 'provider-uuid',
            },
        )

        # Verify - remove and load called
        ap.model_mgr.remove_llm_model.assert_called_once_with('existing-uuid')

    async def test_update_llm_model_provider_not_found_raises_error(self):
        """Raises Exception when provider not found after update."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.provider_dict = {}  # Empty
        ap.model_mgr.remove_llm_model = AsyncMock()

        ap.persistence_mgr.execute_async = AsyncMock()

        service = LLMModelsService(ap)

        # Execute & Verify
        with pytest.raises(Exception, match='provider not found'):
            await service.update_llm_model(
                'model-uuid',
                {
                    'name': 'Update',
                    'provider_uuid': 'nonexistent-provider',
                },
            )

    async def test_update_llm_model_reloads_context_length_as_column(self):
        """Updates runtime model with context_length outside extra_args."""
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace(execute_async=AsyncMock())
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.provider_dict = {'provider-uuid': Mock()}
        ap.model_mgr.llm_models = []
        ap.model_mgr.remove_llm_model = AsyncMock()
        ap.model_mgr.load_llm_model_with_provider = AsyncMock(return_value=Mock())

        service = LLMModelsService(ap)

        await service.update_llm_model(
            'existing-uuid',
            {
                'name': 'Updated Name',
                'provider_uuid': 'provider-uuid',
                'abilities': ['vision'],
                'context_length': 64000,
                'extra_args': {'temperature': 0.4},
            },
        )

        runtime_entity = ap.model_mgr.load_llm_model_with_provider.await_args.args[0]
        assert runtime_entity.uuid == 'existing-uuid'
        assert runtime_entity.context_length == 64000
        assert runtime_entity.extra_args == {'temperature': 0.4}
        assert 'context_length' not in runtime_entity.extra_args


class TestLLMModelsServiceDeleteLLMModel:
    """Tests for LLMModelsService.delete_llm_model method."""

    async def test_delete_llm_model_success(self):
        """Deletes LLM model successfully."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.remove_llm_model = AsyncMock()

        ap.persistence_mgr.execute_async = AsyncMock()

        service = LLMModelsService(ap)

        # Execute
        await service.delete_llm_model('delete-uuid')

        # Verify
        ap.persistence_mgr.execute_async.assert_called_once()
        ap.model_mgr.remove_llm_model.assert_called_once_with('delete-uuid')


class TestEmbeddingModelsServiceGetEmbeddingModels:
    """Tests for EmbeddingModelsService.get_embedding_models method."""

    async def test_get_embedding_models_empty_list(self):
        """Returns empty list when no models exist."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(return_value={'uuid': 'embedding-uuid', 'name': 'Test'})

        service = EmbeddingModelsService(ap)

        # Execute
        result = await service.get_embedding_models()

        # Verify
        assert result == []

    async def test_get_embedding_models_with_provider(self):
        """Returns embedding models with provider info."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        model = _create_mock_embedding_model()
        provider = _create_mock_provider()

        mock_model_result = _create_mock_result([model])
        mock_provider_result = _create_mock_result([provider])

        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            return mock_model_result if call_count == 1 else mock_provider_result

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'uuid': entity.uuid,
                'name': entity.name,
                'provider_uuid': getattr(entity, 'provider_uuid', None),
                'api_keys': getattr(entity, 'api_keys', ['key']),
            }
        )

        service = EmbeddingModelsService(ap)

        # Execute
        result = await service.get_embedding_models()

        # Verify
        assert len(result) == 1


class TestEmbeddingModelsServiceGetEmbeddingModel:
    """Tests for EmbeddingModelsService.get_embedding_model method."""

    async def test_get_embedding_model_found(self):
        """Returns embedding model when found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        model = _create_mock_embedding_model(model_uuid='found-embedding')
        provider = _create_mock_provider()

        mock_model_result = _create_mock_result([], first_item=model)
        mock_provider_result = _create_mock_result([], first_item=provider)

        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            return mock_model_result if call_count == 1 else mock_provider_result

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={
                'uuid': 'found-embedding',
                'name': 'Found Embedding',
                'provider': {'uuid': 'provider-uuid'},
            }
        )

        service = EmbeddingModelsService(ap)

        # Execute
        result = await service.get_embedding_model('found-embedding')

        # Verify
        assert result is not None

    async def test_get_embedding_model_not_found(self):
        """Returns None when model not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        mock_result = _create_mock_result([], first_item=None)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = EmbeddingModelsService(ap)

        # Execute
        result = await service.get_embedding_model('nonexistent-embedding')

        # Verify
        assert result is None


class TestEmbeddingModelsServiceCreateEmbeddingModel:
    """Tests for EmbeddingModelsService.create_embedding_model method."""

    async def test_create_embedding_model_success(self):
        """Creates embedding model successfully."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.provider_dict = {'provider-uuid': Mock()}
        ap.model_mgr.embedding_models = []
        ap.model_mgr.load_embedding_model_with_provider = AsyncMock(return_value=Mock())

        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = EmbeddingModelsService(ap)

        # Execute
        model_uuid = await service.create_embedding_model(
            {
                'name': 'New Embedding',
                'provider_uuid': 'provider-uuid',
                'extra_args': {},
            }
        )

        # Verify
        assert model_uuid is not None
        assert len(model_uuid) == 36

    async def test_create_embedding_model_provider_not_found_raises(self):
        """Raises Exception when provider not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.provider_dict = {}  # Empty

        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = EmbeddingModelsService(ap)

        # Execute & Verify
        with pytest.raises(Exception, match='provider not found'):
            await service.create_embedding_model(
                {
                    'name': 'No Provider Embedding',
                    'provider_uuid': 'nonexistent',
                    'extra_args': {},
                }
            )


class TestEmbeddingModelsServiceDeleteEmbeddingModel:
    """Tests for EmbeddingModelsService.delete_embedding_model method."""

    async def test_delete_embedding_model_success(self):
        """Deletes embedding model successfully."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.remove_embedding_model = AsyncMock()

        ap.persistence_mgr.execute_async = AsyncMock()

        service = EmbeddingModelsService(ap)

        # Execute
        await service.delete_embedding_model('delete-embedding-uuid')

        # Verify
        ap.model_mgr.remove_embedding_model.assert_called_once()


class TestRerankModelsServiceGetRerankModels:
    """Tests for RerankModelsService.get_rerank_models method."""

    async def test_get_rerank_models_empty_list(self):
        """Returns empty list when no models exist."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = RerankModelsService(ap)

        # Execute
        result = await service.get_rerank_models()

        # Verify
        assert result == []

    async def test_get_rerank_models_with_provider(self):
        """Returns rerank models with provider info."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        model = _create_mock_rerank_model()
        provider = _create_mock_provider()

        mock_model_result = _create_mock_result([model])
        mock_provider_result = _create_mock_result([provider])

        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            return mock_model_result if call_count == 1 else mock_provider_result

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'uuid': entity.uuid,
                'name': entity.name,
                'provider_uuid': getattr(entity, 'provider_uuid', None),
                'api_keys': getattr(entity, 'api_keys', ['key']),
            }
        )

        service = RerankModelsService(ap)

        # Execute
        result = await service.get_rerank_models()

        # Verify
        assert len(result) == 1


class TestRerankModelsServiceGetRerankModel:
    """Tests for RerankModelsService.get_rerank_model method."""

    async def test_get_rerank_model_found(self):
        """Returns rerank model when found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        model = _create_mock_rerank_model(model_uuid='found-rerank')
        provider = _create_mock_provider()

        mock_model_result = _create_mock_result([], first_item=model)
        mock_provider_result = _create_mock_result([], first_item=provider)

        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            return mock_model_result if call_count == 1 else mock_provider_result

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={
                'uuid': 'found-rerank',
                'name': 'Found Rerank',
                'provider': {'uuid': 'provider-uuid'},
            }
        )

        service = RerankModelsService(ap)

        # Execute
        result = await service.get_rerank_model('found-rerank')

        # Verify
        assert result is not None

    async def test_get_rerank_model_not_found(self):
        """Returns None when model not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        mock_result = _create_mock_result([], first_item=None)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = RerankModelsService(ap)

        # Execute
        result = await service.get_rerank_model('nonexistent-rerank')

        # Verify
        assert result is None


class TestRerankModelsServiceCreateRerankModel:
    """Tests for RerankModelsService.create_rerank_model method."""

    async def test_create_rerank_model_success(self):
        """Creates rerank model successfully."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.provider_dict = {'provider-uuid': Mock()}
        ap.model_mgr.rerank_models = []
        ap.model_mgr.load_rerank_model_with_provider = AsyncMock(return_value=Mock())

        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = RerankModelsService(ap)

        # Execute
        model_uuid = await service.create_rerank_model(
            {
                'name': 'New Rerank',
                'provider_uuid': 'provider-uuid',
                'extra_args': {},
            }
        )

        # Verify
        assert model_uuid is not None

    async def test_create_rerank_model_provider_not_found_raises(self):
        """Raises Exception when provider not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.provider_dict = {}

        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = RerankModelsService(ap)

        # Execute & Verify
        with pytest.raises(Exception, match='provider not found'):
            await service.create_rerank_model(
                {
                    'name': 'No Provider Rerank',
                    'provider_uuid': 'nonexistent',
                    'extra_args': {},
                }
            )


class TestRerankModelsServiceDeleteRerankModel:
    """Tests for RerankModelsService.delete_rerank_model method."""

    async def test_delete_rerank_model_success(self):
        """Deletes rerank model successfully."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.remove_rerank_model = AsyncMock()

        ap.persistence_mgr.execute_async = AsyncMock()

        service = RerankModelsService(ap)

        # Execute
        await service.delete_rerank_model('delete-rerank-uuid')

        # Verify
        ap.model_mgr.remove_rerank_model.assert_called_once()


class TestEmbeddingModelsServiceGetEmbeddingModelsByProvider:
    """Tests for EmbeddingModelsService.get_embedding_models_by_provider method."""

    async def test_get_embedding_models_by_provider_uuid(self):
        """Returns embedding models for specific provider."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        model1 = _create_mock_embedding_model(model_uuid='emb-1', provider_uuid='provider-uuid')
        model2 = _create_mock_embedding_model(model_uuid='emb-2', provider_uuid='provider-uuid')

        mock_result = _create_mock_result([model1, model2])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(return_value={'uuid': 'emb-1', 'name': 'Embedding 1'})

        service = EmbeddingModelsService(ap)

        # Execute
        result = await service.get_embedding_models_by_provider('provider-uuid')

        # Verify
        assert len(result) == 2


class TestRerankModelsServiceGetRerankModelsByProvider:
    """Tests for RerankModelsService.get_rerank_models_by_provider method."""

    async def test_get_rerank_models_by_provider_uuid(self):
        """Returns rerank models for specific provider."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        model1 = _create_mock_rerank_model(model_uuid='rerank-1', provider_uuid='provider-uuid')
        model2 = _create_mock_rerank_model(model_uuid='rerank-2', provider_uuid='provider-uuid')

        mock_result = _create_mock_result([model1, model2])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(return_value={'uuid': 'rerank-1', 'name': 'Rerank 1'})

        service = RerankModelsService(ap)

        # Execute
        result = await service.get_rerank_models_by_provider('provider-uuid')

        # Verify
        assert len(result) == 2


class TestValidateProviderSupports:
    """Tests for _validate_provider_supports guard."""

    @staticmethod
    def _make_ap(requester_name: str, support_type):
        """Build a fake ap whose model_mgr resolves a manifest with support_type."""
        manifest = SimpleNamespace(spec={'support_type': support_type})
        runtime_provider = SimpleNamespace(provider_entity=SimpleNamespace(requester=requester_name))
        model_mgr = SimpleNamespace(
            provider_dict={'p1': runtime_provider},
            get_available_requester_manifest_by_name=lambda name: manifest if name == requester_name else None,
        )
        return SimpleNamespace(model_mgr=model_mgr)

    async def test_allows_supported_type(self):
        ap = self._make_ap('cohere-rerank', ['rerank'])
        # Should not raise
        await _validate_provider_supports(ap, 'p1', 'rerank')

    async def test_rejects_unsupported_type(self):
        ap = self._make_ap('cohere-rerank', ['rerank'])
        with pytest.raises(ValueError, match='does not support llm'):
            await _validate_provider_supports(ap, 'p1', 'llm')

    async def test_allows_when_support_type_missing(self):
        # Manifest without support_type must not block (backward compatible)
        manifest = SimpleNamespace(spec={})
        runtime_provider = SimpleNamespace(provider_entity=SimpleNamespace(requester='legacy'))
        model_mgr = SimpleNamespace(
            provider_dict={'p1': runtime_provider},
            get_available_requester_manifest_by_name=lambda name: manifest,
        )
        ap = SimpleNamespace(model_mgr=model_mgr)
        await _validate_provider_supports(ap, 'p1', 'rerank')

    async def test_allows_when_provider_unknown(self):
        ap = self._make_ap('cohere-rerank', ['rerank'])
        # Unknown provider uuid -> no entry -> no block
        await _validate_provider_supports(ap, 'missing', 'llm')

    async def test_degrades_when_model_mgr_incomplete(self):
        # A bare ap without a usable model_mgr must not raise (defensive)
        ap = SimpleNamespace(model_mgr=SimpleNamespace())
        await _validate_provider_supports(ap, 'p1', 'llm')
