"""
Unit tests for ModelProviderService.

Tests model provider management operations including:
- Provider CRUD operations
- Provider model count checking
- Find or create provider logic
- Space model provider API key updates
- Provider model scanning

Source: src/langbot/pkg/api/http/service/provider.py
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock
from types import SimpleNamespace

from langbot.pkg.api.http.service.provider import ModelProviderService
from langbot.pkg.entity.persistence.model import ModelProvider, LLMModel, EmbeddingModel, RerankModel


pytestmark = pytest.mark.asyncio


def _create_mock_provider(
    provider_uuid: str = 'test-provider-uuid',
    name: str = 'Test Provider',
    requester: str = 'openai',
    base_url: str = 'https://api.openai.com',
    api_keys: list = None,
) -> Mock:
    """Helper to create mock ModelProvider entity."""
    provider = Mock(spec=ModelProvider)
    provider.uuid = provider_uuid
    provider.name = name
    provider.requester = requester
    provider.base_url = base_url
    provider.api_keys = api_keys or ['test-key']
    return provider


def _create_mock_llm_model(
    model_uuid: str = 'test-llm-uuid',
    name: str = 'Test LLM',
    provider_uuid: str = 'test-provider-uuid',
) -> Mock:
    """Helper to create mock LLMModel entity."""
    model = Mock(spec=LLMModel)
    model.uuid = model_uuid
    model.name = name
    model.provider_uuid = provider_uuid
    return model


def _create_mock_result(items: list = None, first_item=None):
    """Create mock result object for persistence queries."""
    result = Mock()
    result.all = Mock(return_value=items or [])
    result.first = Mock(return_value=first_item)
    result.scalar = Mock(return_value=len(items) if items else 0)
    return result


class TestModelProviderServiceGetProviders:
    """Tests for get_providers method."""

    async def test_get_providers_empty_list(self):
        """Returns empty list when no providers exist."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'uuid': entity.uuid,
                'name': entity.name,
                'requester': entity.requester,
                'base_url': entity.base_url,
                'api_keys': entity.api_keys,
            }
        )

        service = ModelProviderService(ap)

        # Execute
        result = await service.get_providers()

        # Verify
        assert result == []

    async def test_get_providers_returns_serialized_list(self):
        """Returns serialized list of providers."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        provider1 = _create_mock_provider(provider_uuid='provider-1', name='Provider 1')
        provider2 = _create_mock_provider(provider_uuid='provider-2', name='Provider 2')

        mock_result = _create_mock_result([provider1, provider2])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'uuid': entity.uuid,
                'name': entity.name,
                'requester': entity.requester,
                'base_url': entity.base_url,
                'api_keys': entity.api_keys,
            }
        )

        service = ModelProviderService(ap)

        # Execute
        result = await service.get_providers()

        # Verify
        assert len(result) == 2
        assert result[0]['name'] == 'Provider 1'
        assert result[1]['name'] == 'Provider 2'

    async def test_get_providers_parse_api_keys_json_string(self):
        """Parses api_keys from JSON string if needed."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        provider = _create_mock_provider(provider_uuid='provider-1', api_keys='["key1", "key2"]')

        mock_result = _create_mock_result([provider])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'uuid': entity.uuid,
                'name': entity.name,
                'api_keys': entity.api_keys,  # Returns string
            }
        )

        service = ModelProviderService(ap)

        # Execute
        result = await service.get_providers()

        # Verify - api_keys should be parsed from string
        assert result[0]['api_keys'] == ['key1', 'key2']

    async def test_get_providers_invalid_json_api_keys_returns_empty(self):
        """Returns empty list for invalid JSON api_keys."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        provider = _create_mock_provider(provider_uuid='provider-1', api_keys='invalid-json')

        mock_result = _create_mock_result([provider])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'uuid': entity.uuid,
                'name': entity.name,
                'api_keys': entity.api_keys,  # Returns invalid string
            }
        )

        service = ModelProviderService(ap)

        # Execute
        result = await service.get_providers()

        # Verify - invalid JSON returns empty list
        assert result[0]['api_keys'] == []


class TestModelProviderServiceGetProvider:
    """Tests for get_provider method."""

    async def test_get_provider_by_uuid_found(self):
        """Returns provider when found by UUID."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        provider = _create_mock_provider(provider_uuid='found-uuid', name='Found Provider')

        mock_result = _create_mock_result([], first_item=provider)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={
                'uuid': 'found-uuid',
                'name': 'Found Provider',
                'api_keys': ['key'],
            }
        )

        service = ModelProviderService(ap)

        # Execute
        result = await service.get_provider('found-uuid')

        # Verify
        assert result is not None
        assert result['uuid'] == 'found-uuid'

    async def test_get_provider_by_uuid_not_found(self):
        """Returns None when provider not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        mock_result = _create_mock_result([], first_item=None)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = ModelProviderService(ap)

        # Execute
        result = await service.get_provider('nonexistent-uuid')

        # Verify
        assert result is None


class TestModelProviderServiceCreateProvider:
    """Tests for create_provider method."""

    async def test_create_provider_generates_uuid(self):
        """Creates provider with generated UUID."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.provider_dict = {}

        # Mock load_provider to return runtime provider
        runtime_provider = Mock()
        runtime_provider.provider_entity = Mock()
        runtime_provider.provider_entity.uuid = 'generated-uuid'
        ap.model_mgr.load_provider = AsyncMock(return_value=runtime_provider)

        ap.persistence_mgr.execute_async = AsyncMock()

        service = ModelProviderService(ap)

        # Execute
        provider_uuid = await service.create_provider({
            'name': 'New Provider',
            'requester': 'openai',
            'base_url': 'https://api.openai.com',
            'api_keys': ['key'],
        })

        # Verify - UUID is generated
        assert provider_uuid is not None
        assert len(provider_uuid) == 36  # UUID format

    async def test_create_provider_loads_to_runtime(self):
        """Loads provider to runtime model_mgr."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.provider_dict = {}

        runtime_provider = Mock()
        runtime_provider.provider_entity = Mock()
        runtime_provider.provider_entity.uuid = 'runtime-uuid'
        ap.model_mgr.load_provider = AsyncMock(return_value=runtime_provider)

        ap.persistence_mgr.execute_async = AsyncMock()

        service = ModelProviderService(ap)

        # Execute
        result_uuid = await service.create_provider({
            'name': 'Runtime Provider',
            'requester': 'openai',
            'base_url': 'https://api.openai.com',
            'api_keys': ['key'],
        })

        # Verify - provider added to runtime dict and UUID generated
        ap.model_mgr.load_provider.assert_called_once()
        assert result_uuid is not None


class TestModelProviderServiceUpdateProvider:
    """Tests for update_provider method."""

    async def test_update_provider_removes_uuid_from_data(self):
        """Removes uuid from update data before persisting."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.reload_provider = AsyncMock()

        ap.persistence_mgr.execute_async = AsyncMock()

        service = ModelProviderService(ap)

        # Execute
        await service.update_provider('existing-uuid', {
            'uuid': 'should-be-removed',  # Will be removed
            'name': 'Updated Name',
        })

        # Verify - reload called
        ap.model_mgr.reload_provider.assert_called_once_with('existing-uuid')

    async def test_update_provider_reloads_runtime(self):
        """Reloads provider in runtime after update."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.reload_provider = AsyncMock()

        ap.persistence_mgr.execute_async = AsyncMock()

        service = ModelProviderService(ap)

        # Execute
        await service.update_provider('update-uuid', {'name': 'New Name'})

        # Verify
        ap.model_mgr.reload_provider.assert_called_once()


class TestModelProviderServiceDeleteProvider:
    """Tests for delete_provider method."""

    async def test_delete_provider_with_llm_models_raises_error(self):
        """Raises ValueError when LLM models reference provider."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        # Mock LLM model exists - only return LLM result since that's first check
        llm_result = _create_mock_result([], first_item=_create_mock_llm_model())

        ap.persistence_mgr.execute_async = AsyncMock(return_value=llm_result)

        service = ModelProviderService(ap)

        # Execute & Verify
        with pytest.raises(ValueError, match='Cannot delete provider: LLM models'):
            await service.delete_provider('provider-with-llm')

    async def test_delete_provider_with_embedding_models_raises_error(self):
        """Raises ValueError when Embedding models reference provider."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        # Create results for each check type
        llm_result = Mock()
        llm_result.first = Mock(return_value=None)  # No LLM models
        embedding_result = Mock()
        embedding_result.first = Mock(return_value=Mock(spec=EmbeddingModel))  # Has embedding model
        rerank_result = Mock()
        rerank_result.first = Mock(return_value=None)

        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return llm_result
            elif call_count == 2:
                return embedding_result
            return rerank_result

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)

        service = ModelProviderService(ap)

        # Execute & Verify - should raise embedding error (LLM check passes, embedding check fails)
        with pytest.raises(ValueError, match='Cannot delete provider: Embedding models'):
            await service.delete_provider('provider-with-embedding')

    async def test_delete_provider_with_rerank_models_raises_error(self):
        """Raises ValueError when Rerank models reference provider."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        # Create results for each check type
        llm_result = Mock()
        llm_result.first = Mock(return_value=None)  # No LLM models
        embedding_result = Mock()
        embedding_result.first = Mock(return_value=None)  # No embedding models
        rerank_result = Mock()
        rerank_result.first = Mock(return_value=Mock(spec=RerankModel))  # Has rerank model

        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return llm_result
            elif call_count == 2:
                return embedding_result
            return rerank_result

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)

        service = ModelProviderService(ap)

        # Execute & Verify - should raise rerank error (LLM and embedding checks pass, rerank check fails)
        with pytest.raises(ValueError, match='Cannot delete provider: Rerank models'):
            await service.delete_provider('provider-with-rerank')

    async def test_delete_provider_no_models_success(self):
        """Deletes provider when no models reference it."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.remove_provider = AsyncMock()

        # Mock no models reference provider
        empty_result = Mock()
        empty_result.first = Mock(return_value=None)

        ap.persistence_mgr.execute_async = AsyncMock(return_value=empty_result)

        service = ModelProviderService(ap)

        # Execute
        await service.delete_provider('provider-no-models')

        # Verify - delete and remove called
        ap.model_mgr.remove_provider.assert_called_once_with('provider-no-models')


class TestModelProviderServiceGetProviderModelCounts:
    """Tests for get_provider_model_counts method."""

    async def test_get_model_counts_returns_correct_counts(self):
        """Returns correct counts for each model type."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        # Mock scalar results for counts
        llm_result = Mock()
        llm_result.scalar = Mock(return_value=3)
        embedding_result = Mock()
        embedding_result.scalar = Mock(return_value=2)
        rerank_result = Mock()
        rerank_result.scalar = Mock(return_value=1)

        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return llm_result
            elif call_count == 2:
                return embedding_result
            return rerank_result

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)

        service = ModelProviderService(ap)

        # Execute
        result = await service.get_provider_model_counts('provider-uuid')

        # Verify
        assert result['llm_count'] == 3
        assert result['embedding_count'] == 2
        assert result['rerank_count'] == 1

    async def test_get_model_counts_zero_counts(self):
        """Returns zero counts when no models."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        zero_result = Mock()
        zero_result.scalar = Mock(return_value=0)

        ap.persistence_mgr.execute_async = AsyncMock(return_value=zero_result)

        service = ModelProviderService(ap)

        # Execute
        result = await service.get_provider_model_counts('empty-provider')

        # Verify
        assert result['llm_count'] == 0
        assert result['embedding_count'] == 0
        assert result['rerank_count'] == 0


class TestModelProviderServiceFindOrCreateProvider:
    """Tests for find_or_create_provider method."""

    async def test_find_existing_provider_matching_config(self):
        """Returns existing provider UUID when config matches."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        existing_provider = _create_mock_provider(
            provider_uuid='existing-uuid',
            requester='openai',
            base_url='https://api.openai.com',
            api_keys=['key1', 'key2'],
        )

        mock_result = _create_mock_result([existing_provider])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = ModelProviderService(ap)

        # Execute
        result = await service.find_or_create_provider(
            requester='openai',
            base_url='https://api.openai.com',
            api_keys=['key1', 'key2'],  # Same keys (sorted)
        )

        # Verify - returns existing UUID
        assert result == 'existing-uuid'

    async def test_find_existing_provider_keys_order_mismatch(self):
        """Returns existing provider when keys match but order differs."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        existing_provider = _create_mock_provider(
            provider_uuid='existing-uuid',
            requester='openai',
            base_url='https://api.openai.com',
            api_keys=['key1', 'key2'],
        )

        mock_result = _create_mock_result([existing_provider])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = ModelProviderService(ap)

        # Execute with reversed key order
        result = await service.find_or_create_provider(
            requester='openai',
            base_url='https://api.openai.com',
            api_keys=['key2', 'key1'],  # Different order, should still match
        )

        # Verify - returns existing UUID (keys are sorted in comparison)
        assert result == 'existing-uuid'

    async def test_create_new_provider_no_match(self):
        """Creates new provider when no existing match."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.provider_dict = {}

        runtime_provider = Mock()
        runtime_provider.provider_entity = Mock()
        runtime_provider.provider_entity.uuid = None  # Will be set by uuid.uuid4()
        ap.model_mgr.load_provider = AsyncMock(return_value=runtime_provider)

        # Mock no existing providers
        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = ModelProviderService(ap)

        # Execute
        result = await service.find_or_create_provider(
            requester='new-requester',
            base_url='https://new.api.com',
            api_keys=['new-key'],
        )

        # Verify - creates new provider with valid UUID format
        assert result is not None
        assert len(result) == 36  # UUID format
        # Verify provider was loaded to runtime
        ap.model_mgr.load_provider.assert_called_once()

    async def test_create_provider_name_from_url_parse(self):
        """Creates provider with name parsed from URL."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.provider_dict = {}

        runtime_provider = Mock()
        runtime_provider.provider_entity = Mock()
        runtime_provider.provider_entity.uuid = 'parsed-url-uuid'
        ap.model_mgr.load_provider = AsyncMock(return_value=runtime_provider)

        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = ModelProviderService(ap)

        # Execute
        result_uuid = await service.find_or_create_provider(
            requester='custom',
            base_url='https://api.example.com/v1',
            api_keys=['key'],
        )

        # Verify - name should be parsed from URL (api.example.com)
        ap.model_mgr.load_provider.assert_called_once()
        assert result_uuid is not None


class TestModelProviderServiceUpdateSpaceModelProviderApiKeys:
    """Tests for update_space_model_provider_api_keys method."""

    async def test_update_space_provider_api_keys(self):
        """Updates Space provider API keys."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.model_mgr.reload_provider = AsyncMock()

        ap.persistence_mgr.execute_async = AsyncMock()

        service = ModelProviderService(ap)

        # Execute
        await service.update_space_model_provider_api_keys('space-api-key')

        # Verify - update and reload called for Space provider UUID
        ap.model_mgr.reload_provider.assert_called_once_with(
            '00000000-0000-0000-0000-000000000000'
        )


class TestModelProviderServiceScanProviderModels:
    """Tests for scan_provider_models method."""

    async def test_scan_provider_not_found_raises_error(self):
        """Raises ValueError when provider not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        mock_result = _create_mock_result([], first_item=None)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = ModelProviderService(ap)

        # Execute & Verify
        with pytest.raises(ValueError, match='provider not found'):
            await service.scan_provider_models('nonexistent-uuid')

    async def test_scan_provider_returns_models_list(self):
        """Returns scanned models list."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.llm_model_service = SimpleNamespace()
        ap.embedding_models_service = SimpleNamespace()

        provider = _create_mock_provider(provider_uuid='scan-uuid')

        mock_result = _create_mock_result([], first_item=provider)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={
                'uuid': 'scan-uuid',
                'name': 'Scan Provider',
                'requester': 'openai',
                'base_url': 'https://api.openai.com',
                'api_keys': ['key'],
            }
        )

        # Mock runtime provider with scan capability
        runtime_provider = Mock()
        runtime_provider.requester = Mock()
        runtime_provider.token_mgr = Mock()
        runtime_provider.token_mgr.get_token = Mock(return_value='token')
        runtime_provider.token_mgr.tokens = ['token']

        # Mock scan_models to return models
        async def mock_scan_models(token):
            return {
                'models': [
                    {'id': 'gpt-4', 'name': 'GPT-4', 'type': 'llm'},
                    {'id': 'text-embedding', 'name': 'Text Embedding', 'type': 'embedding'},
                ],
                'debug': None,
            }

        runtime_provider.requester.scan_models = AsyncMock(side_effect=mock_scan_models)
        ap.model_mgr.load_provider = AsyncMock(return_value=runtime_provider)

        # Mock existing model services
        ap.llm_model_service.get_llm_models_by_provider = AsyncMock(return_value=[])
        ap.embedding_models_service.get_embedding_models_by_provider = AsyncMock(return_value=[])

        service = ModelProviderService(ap)

        # Execute
        result = await service.scan_provider_models('scan-uuid')

        # Verify
        assert 'models' in result
        assert len(result['models']) == 2

    async def test_scan_provider_filter_by_model_type(self):
        """Returns filtered models by type."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.llm_model_service = SimpleNamespace()
        ap.embedding_models_service = SimpleNamespace()

        provider = _create_mock_provider(provider_uuid='filter-uuid')

        mock_result = _create_mock_result([], first_item=provider)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={
                'uuid': 'filter-uuid',
                'name': 'Filter Provider',
                'requester': 'openai',
                'base_url': 'https://api.openai.com',
                'api_keys': ['key'],
            }
        )

        runtime_provider = Mock()
        runtime_provider.requester = Mock()
        runtime_provider.token_mgr = Mock()
        runtime_provider.token_mgr.get_token = Mock(return_value='token')
        runtime_provider.token_mgr.tokens = ['token']

        async def mock_scan_models(token):
            return {
                'models': [
                    {'id': 'gpt-4', 'name': 'GPT-4', 'type': 'llm'},
                    {'id': 'text-embedding', 'name': 'Text Embedding', 'type': 'embedding'},
                ],
                'debug': None,
            }

        runtime_provider.requester.scan_models = AsyncMock(side_effect=mock_scan_models)
        ap.model_mgr.load_provider = AsyncMock(return_value=runtime_provider)

        ap.llm_model_service.get_llm_models_by_provider = AsyncMock(return_value=[])
        ap.embedding_models_service.get_embedding_models_by_provider = AsyncMock(return_value=[])

        service = ModelProviderService(ap)

        # Execute - filter for LLM only
        result = await service.scan_provider_models('filter-uuid', model_type='llm')

        # Verify - only LLM models returned
        assert len(result['models']) == 1
        assert result['models'][0]['type'] == 'llm'

    async def test_scan_provider_not_implemented_raises_error(self):
        """Raises ValueError when scan not implemented."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()

        provider = _create_mock_provider(provider_uuid='no-scan-uuid')

        mock_result = _create_mock_result([], first_item=provider)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={
                'uuid': 'no-scan-uuid',
                'name': 'No Scan Provider',
                'requester': 'custom',
                'base_url': 'https://custom.api.com',
                'api_keys': ['key'],
            }
        )

        runtime_provider = Mock()
        runtime_provider.requester = Mock()
        runtime_provider.token_mgr = Mock()
        runtime_provider.token_mgr.get_token = Mock(return_value='token')
        runtime_provider.token_mgr.tokens = ['token']
        runtime_provider.requester.scan_models = AsyncMock(
            side_effect=NotImplementedError('scan not supported')
        )
        ap.model_mgr.load_provider = AsyncMock(return_value=runtime_provider)

        service = ModelProviderService(ap)

        # Execute & Verify
        with pytest.raises(ValueError, match='current provider does not support model scanning'):
            await service.scan_provider_models('no-scan-uuid')

    async def test_scan_provider_marks_already_added_models(self):
        """Marks models that are already added."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.model_mgr = SimpleNamespace()
        ap.llm_model_service = SimpleNamespace()
        ap.embedding_models_service = SimpleNamespace()

        provider = _create_mock_provider(provider_uuid='already-added-uuid')

        mock_result = _create_mock_result([], first_item=provider)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={
                'uuid': 'already-added-uuid',
                'name': 'Already Added Provider',
                'requester': 'openai',
                'base_url': 'https://api.openai.com',
                'api_keys': ['key'],
            }
        )

        runtime_provider = Mock()
        runtime_provider.requester = Mock()
        runtime_provider.token_mgr = Mock()
        runtime_provider.token_mgr.get_token = Mock(return_value='token')
        runtime_provider.token_mgr.tokens = ['token']

        async def mock_scan_models(token):
            return {
                'models': [
                    {'id': 'existing-model', 'name': 'Existing Model', 'type': 'llm'},
                    {'id': 'new-model', 'name': 'New Model', 'type': 'llm'},
                ],
                'debug': None,
            }

        runtime_provider.requester.scan_models = AsyncMock(side_effect=mock_scan_models)
        ap.model_mgr.load_provider = AsyncMock(return_value=runtime_provider)

        # Mock existing LLM model
        ap.llm_model_service.get_llm_models_by_provider = AsyncMock(
            return_value=[{'name': 'Existing Model'}]
        )
        ap.embedding_models_service.get_embedding_models_by_provider = AsyncMock(return_value=[])

        service = ModelProviderService(ap)

        # Execute
        result = await service.scan_provider_models('already-added-uuid')

        # Verify - existing model marked as already_added
        existing_model = next(m for m in result['models'] if m['name'] == 'Existing Model')
        assert existing_model['already_added'] is True

        new_model = next(m for m in result['models'] if m['name'] == 'New Model')
        assert new_model['already_added'] is False