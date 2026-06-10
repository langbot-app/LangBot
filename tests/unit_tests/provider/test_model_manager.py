"""
Unit tests for ModelManager in provider/modelmgr.

Tests model configuration management, requester selection, provider loading,
and error handling without calling real LLM APIs.
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock

from langbot.pkg.provider.modelmgr.modelmgr import ModelManager
from langbot.pkg.provider.modelmgr import requester
from langbot.pkg.entity.persistence import model as persistence_model
from langbot.pkg.entity.errors import provider as provider_errors
from langbot.pkg.provider.modelmgr import token
from tests.unit_tests.provider.conftest import _make_mock_result, _make_row_mock


# ============================================================================
# ModelManager Initialization Tests
# ============================================================================


@pytest.mark.asyncio
async def test_model_manager_initialize_with_fake_requesters(fake_requester_registry):
    """Test ModelManager initializes with fake requester registry."""
    model_mgr = fake_requester_registry

    await model_mgr.initialize()

    assert 'fake-requester' in model_mgr.requester_dict
    assert 'another-fake-requester' in model_mgr.requester_dict
    assert model_mgr.requester_dict['fake-requester'] is not None
    assert len(model_mgr.requester_components) == 2


@pytest.mark.asyncio
async def test_model_manager_initialize_empty_registry(mock_app_for_modelmgr):
    """Test ModelManager handles empty requester registry."""
    app = mock_app_for_modelmgr
    app.discover.get_components_by_kind = Mock(return_value=[])

    model_mgr = ModelManager(app)
    await model_mgr.initialize()

    assert model_mgr.requester_dict == {}
    assert len(model_mgr.requester_components) == 0


@pytest.mark.asyncio
async def test_model_manager_skips_space_sync_when_disabled(mock_app_for_modelmgr):
    """Test ModelManager skips space sync when disabled in config."""
    app = mock_app_for_modelmgr
    app.instance_config.data = {'space': {'disable_models_service': True}}

    model_mgr = ModelManager(app)
    await model_mgr.initialize()

    # Should not call space_service if disabled
    app.space_service.get_models.assert_not_called()


# ============================================================================
# Model Loading Tests
# ============================================================================


@pytest.mark.asyncio
async def test_model_manager_load_models_from_db(fake_requester_registry, fake_persistence_data):
    """Test ModelManager loads models from database correctly."""
    model_mgr = fake_requester_registry

    # Setup fake persistence responses - return entities directly (code handles non-Row entities)
    async def fake_execute(query):
        query_str = str(query)
        if 'model_providers' in query_str:
            return _make_mock_result(fake_persistence_data['providers'])
        elif 'llm_models' in query_str:
            return _make_mock_result(fake_persistence_data['llm_models'])
        elif 'embedding_models' in query_str:
            return _make_mock_result(fake_persistence_data['embedding_models'])
        elif 'rerank_models' in query_str:
            return _make_mock_result(fake_persistence_data['rerank_models'])
        return _make_mock_result([])

    model_mgr.ap.persistence_mgr.execute_async = fake_execute

    await model_mgr.initialize()

    # Check providers loaded
    assert len(model_mgr.provider_dict) == 2
    assert fake_persistence_data['provider_uuid'] in model_mgr.provider_dict
    assert fake_persistence_data['provider_uuid2'] in model_mgr.provider_dict

    # Check models loaded
    assert len(model_mgr.llm_models) == 2
    assert len(model_mgr.embedding_models) == 1
    assert len(model_mgr.rerank_models) == 1


@pytest.mark.asyncio
async def test_model_manager_load_provider_unknown_requester(mock_app_for_modelmgr):
    """Test ModelManager raises RequesterNotFoundError for unknown requester."""
    app = mock_app_for_modelmgr
    app.discover.get_components_by_kind = Mock(return_value=[])

    model_mgr = ModelManager(app)
    await model_mgr.initialize()

    provider_info = {
        'uuid': 'unknown-provider',
        'name': 'Unknown Provider',
        'requester': 'non-existent-requester',
        'base_url': 'https://unknown.com',
        'api_keys': [],
    }

    with pytest.raises(provider_errors.RequesterNotFoundError) as exc_info:
        await model_mgr.load_provider(provider_info)

    assert exc_info.value.requester_name == 'non-existent-requester'


@pytest.mark.asyncio
async def test_model_manager_load_provider_from_dict(fake_requester_registry):
    """Test ModelManager loads provider from dict correctly."""
    model_mgr = fake_requester_registry
    await model_mgr.initialize()

    provider_info = {
        'uuid': 'dict-provider-uuid',
        'name': 'Dict Provider',
        'requester': 'fake-requester',
        'base_url': 'https://dict.example.com',
        'api_keys': ['dict-key'],
    }

    runtime_provider = await model_mgr.load_provider(provider_info)

    assert runtime_provider.provider_entity.uuid == 'dict-provider-uuid'
    assert runtime_provider.provider_entity.name == 'Dict Provider'
    assert runtime_provider.token_mgr.name == 'dict-provider-uuid'
    assert runtime_provider.token_mgr.tokens == ['dict-key']
    assert isinstance(runtime_provider.requester, requester.ProviderAPIRequester)


@pytest.mark.asyncio
async def test_model_manager_load_provider_from_entity(fake_requester_registry, fake_persistence_data):
    """Test ModelManager loads provider from persistence entity."""
    model_mgr = fake_requester_registry
    await model_mgr.initialize()

    provider_entity = fake_persistence_data['providers'][0]

    runtime_provider = await model_mgr.load_provider(provider_entity)

    assert runtime_provider.provider_entity.uuid == provider_entity.uuid
    assert runtime_provider.requester is not None


# ============================================================================
# Model Query Tests
# ============================================================================


@pytest.mark.asyncio
async def test_model_manager_get_model_by_uuid(fake_requester_registry, fake_persistence_data):
    """Test ModelManager.get_model_by_uuid returns correct model."""
    model_mgr = fake_requester_registry

    async def fake_execute(query):
        query_str = str(query)
        if 'model_providers' in query_str:
            return _make_mock_result(fake_persistence_data['providers'])
        elif 'llm_models' in query_str:
            return _make_mock_result(fake_persistence_data['llm_models'])
        return _make_mock_result([])

    model_mgr.ap.persistence_mgr.execute_async = fake_execute
    await model_mgr.initialize()

    model = await model_mgr.get_model_by_uuid('test-llm-uuid-1')

    assert model.model_entity.uuid == 'test-llm-uuid-1'
    assert model.model_entity.name == 'TestLLM-1'


@pytest.mark.asyncio
async def test_model_manager_get_model_by_uuid_not_found(fake_requester_registry):
    """Test ModelManager.get_model_by_uuid raises ValueError for unknown model."""
    model_mgr = fake_requester_registry
    await model_mgr.initialize()

    with pytest.raises(ValueError) as exc_info:
        await model_mgr.get_model_by_uuid('unknown-model-uuid')

    assert 'unknown-model-uuid' in str(exc_info.value)


@pytest.mark.asyncio
async def test_model_manager_get_embedding_model_by_uuid(fake_requester_registry, fake_persistence_data):
    """Test ModelManager.get_embedding_model_by_uuid returns correct model."""
    model_mgr = fake_requester_registry

    async def fake_execute(query):
        query_str = str(query)
        if 'model_providers' in query_str:
            return _make_mock_result(fake_persistence_data['providers'])
        elif 'embedding_models' in query_str:
            return _make_mock_result(fake_persistence_data['embedding_models'])
        return _make_mock_result([])

    model_mgr.ap.persistence_mgr.execute_async = fake_execute
    await model_mgr.initialize()

    model = await model_mgr.get_embedding_model_by_uuid('test-embedding-uuid-1')

    assert model.model_entity.uuid == 'test-embedding-uuid-1'


@pytest.mark.asyncio
async def test_model_manager_get_embedding_model_by_uuid_not_found(fake_requester_registry):
    """Test ModelManager.get_embedding_model_by_uuid raises ValueError."""
    model_mgr = fake_requester_registry
    await model_mgr.initialize()

    with pytest.raises(ValueError):
        await model_mgr.get_embedding_model_by_uuid('unknown-embedding-uuid')


@pytest.mark.asyncio
async def test_model_manager_get_rerank_model_by_uuid(fake_requester_registry, fake_persistence_data):
    """Test ModelManager.get_rerank_model_by_uuid returns correct model."""
    model_mgr = fake_requester_registry

    async def fake_execute(query):
        query_str = str(query)
        if 'model_providers' in query_str:
            return _make_mock_result(fake_persistence_data['providers'])
        elif 'rerank_models' in query_str:
            return _make_mock_result(fake_persistence_data['rerank_models'])
        return _make_mock_result([])

    model_mgr.ap.persistence_mgr.execute_async = fake_execute
    await model_mgr.initialize()

    model = await model_mgr.get_rerank_model_by_uuid('test-rerank-uuid-1')

    assert model.model_entity.uuid == 'test-rerank-uuid-1'


@pytest.mark.asyncio
async def test_model_manager_get_rerank_model_by_uuid_not_found(fake_requester_registry):
    """Test ModelManager.get_rerank_model_by_uuid raises ValueError."""
    model_mgr = fake_requester_registry
    await model_mgr.initialize()

    with pytest.raises(ValueError):
        await model_mgr.get_rerank_model_by_uuid('unknown-rerank-uuid')


# ============================================================================
# Model Removal Tests
# ============================================================================


@pytest.mark.asyncio
async def test_model_manager_remove_llm_model(fake_requester_registry, fake_persistence_data):
    """Test ModelManager.remove_llm_model removes model correctly."""
    model_mgr = fake_requester_registry

    async def fake_execute(query):
        query_str = str(query)
        if 'model_providers' in query_str:
            return _make_mock_result(fake_persistence_data['providers'])
        elif 'llm_models' in query_str:
            return _make_mock_result(fake_persistence_data['llm_models'])
        return _make_mock_result([])

    model_mgr.ap.persistence_mgr.execute_async = fake_execute
    await model_mgr.initialize()

    assert len(model_mgr.llm_models) == 2

    await model_mgr.remove_llm_model('test-llm-uuid-1')

    assert len(model_mgr.llm_models) == 1
    assert model_mgr.llm_models[0].model_entity.uuid == 'test-llm-uuid-2'


@pytest.mark.asyncio
async def test_model_manager_remove_llm_model_not_found(fake_requester_registry, fake_persistence_data):
    """Test ModelManager.remove_llm_model handles unknown model gracefully."""
    model_mgr = fake_requester_registry

    async def fake_execute(query):
        query_str = str(query)
        if 'model_providers' in query_str:
            return _make_mock_result(fake_persistence_data['providers'])
        elif 'llm_models' in query_str:
            return _make_mock_result(fake_persistence_data['llm_models'])
        return _make_mock_result([])

    model_mgr.ap.persistence_mgr.execute_async = fake_execute
    await model_mgr.initialize()

    original_count = len(model_mgr.llm_models)

    # Removing unknown model should do nothing (no error)
    await model_mgr.remove_llm_model('unknown-model-uuid')

    assert len(model_mgr.llm_models) == original_count


@pytest.mark.asyncio
async def test_model_manager_remove_embedding_model(fake_requester_registry, fake_persistence_data):
    """Test ModelManager.remove_embedding_model removes model correctly."""
    model_mgr = fake_requester_registry

    async def fake_execute(query):
        query_str = str(query)
        if 'model_providers' in query_str:
            return _make_mock_result(fake_persistence_data['providers'])
        elif 'embedding_models' in query_str:
            return _make_mock_result(fake_persistence_data['embedding_models'])
        return _make_mock_result([])

    model_mgr.ap.persistence_mgr.execute_async = fake_execute
    await model_mgr.initialize()

    assert len(model_mgr.embedding_models) == 1

    await model_mgr.remove_embedding_model('test-embedding-uuid-1')

    assert len(model_mgr.embedding_models) == 0


@pytest.mark.asyncio
async def test_model_manager_remove_rerank_model(fake_requester_registry, fake_persistence_data):
    """Test ModelManager.remove_rerank_model removes model correctly."""
    model_mgr = fake_requester_registry

    async def fake_execute(query):
        query_str = str(query)
        if 'model_providers' in query_str:
            return _make_mock_result(fake_persistence_data['providers'])
        elif 'rerank_models' in query_str:
            return _make_mock_result(fake_persistence_data['rerank_models'])
        return _make_mock_result([])

    model_mgr.ap.persistence_mgr.execute_async = fake_execute
    await model_mgr.initialize()

    assert len(model_mgr.rerank_models) == 1

    await model_mgr.remove_rerank_model('test-rerank-uuid-1')

    assert len(model_mgr.rerank_models) == 0


@pytest.mark.asyncio
async def test_model_manager_remove_provider(fake_requester_registry, fake_persistence_data):
    """Test ModelManager.remove_provider removes provider correctly."""
    model_mgr = fake_requester_registry

    async def fake_execute(query):
        query_str = str(query)
        if 'model_providers' in query_str:
            return _make_mock_result(fake_persistence_data['providers'])
        elif 'llm_models' in query_str:
            return _make_mock_result(fake_persistence_data['llm_models'])
        return _make_mock_result([])

    model_mgr.ap.persistence_mgr.execute_async = fake_execute
    await model_mgr.initialize()

    assert fake_persistence_data['provider_uuid'] in model_mgr.provider_dict

    await model_mgr.remove_provider(fake_persistence_data['provider_uuid'])

    assert fake_persistence_data['provider_uuid'] not in model_mgr.provider_dict


# ============================================================================
# Requester Info Tests
# ============================================================================


def test_model_manager_get_available_requesters_info(fake_requester_registry):
    """Test ModelManager.get_available_requesters_info returns correct info."""
    model_mgr = fake_requester_registry
    model_mgr.requester_components = []

    info = model_mgr.get_available_requesters_info('')

    assert info == []


def test_model_manager_get_available_requesters_info_with_type_filter(fake_requester_registry):
    """Test ModelManager.get_available_requesters_info filters by model type."""
    model_mgr = fake_requester_registry

    from langbot.pkg.discover import engine as discover_engine

    manifest = {
        'apiVersion': 'v1',
        'kind': 'LLMAPIRequester',
        'metadata': {'name': 'test-req', 'label': {'en_US': 'Test'}, 'description': {'en_US': 'Test'}},
        'spec': {'support_type': ['chat', 'embedding']},
        'execution': {'python': {'path': 'fake', 'attr': 'FakeClass'}},
    }
    component = discover_engine.Component(owner='test', manifest=manifest, rel_path='fake.yaml')
    model_mgr.requester_components = [component]

    # Filter by chat type
    info = model_mgr.get_available_requesters_info('chat')
    assert len(info) == 1
    assert info[0]['name'] == 'test-req'

    # Filter by unsupported type
    info = model_mgr.get_available_requesters_info('rerank')
    assert len(info) == 0


def test_model_manager_get_available_requester_info_by_name(fake_requester_registry):
    """Test ModelManager.get_available_requester_info_by_name returns correct info."""
    model_mgr = fake_requester_registry

    from langbot.pkg.discover import engine as discover_engine

    manifest = {
        'apiVersion': 'v1',
        'kind': 'LLMAPIRequester',
        'metadata': {'name': 'named-req', 'label': {'en_US': 'Named'}, 'description': {'en_US': 'Named'}},
        'spec': {'support_type': ['chat']},
        'execution': {'python': {'path': 'fake', 'attr': 'FakeClass'}},
    }
    component = discover_engine.Component(owner='test', manifest=manifest, rel_path='fake.yaml')
    model_mgr.requester_components = [component]

    info = model_mgr.get_available_requester_info_by_name('named-req')
    assert info is not None
    assert info['name'] == 'named-req'

    info = model_mgr.get_available_requester_info_by_name('unknown-req')
    assert info is None


def test_model_manager_get_available_requester_manifest_by_name(fake_requester_registry):
    """Test ModelManager.get_available_requester_manifest_by_name returns component."""
    model_mgr = fake_requester_registry

    from langbot.pkg.discover import engine as discover_engine

    manifest = {
        'apiVersion': 'v1',
        'kind': 'LLMAPIRequester',
        'metadata': {'name': 'manifest-req', 'label': {'en_US': 'Manifest'}, 'description': {'en_US': 'Manifest'}},
        'spec': {'support_type': ['chat']},
        'execution': {'python': {'path': 'fake', 'attr': 'FakeClass'}},
    }
    component = discover_engine.Component(owner='test', manifest=manifest, rel_path='fake.yaml')
    model_mgr.requester_components = [component]

    comp = model_mgr.get_available_requester_manifest_by_name('manifest-req')
    assert comp is not None
    assert comp.metadata.name == 'manifest-req'

    comp = model_mgr.get_available_requester_manifest_by_name('unknown-req')
    assert comp is None


# ============================================================================
# Temporary Runtime Model Tests
# ============================================================================


@pytest.mark.asyncio
async def test_model_manager_init_temporary_runtime_llm_model(fake_requester_registry):
    """Test ModelManager.init_temporary_runtime_llm_model creates model correctly."""
    model_mgr = fake_requester_registry
    await model_mgr.initialize()

    model_info = {
        'uuid': 'temp-model-uuid',
        'name': 'TempModel',
        'provider': {
            'uuid': 'temp-provider-uuid',
            'name': 'Temp Provider',
            'requester': 'fake-requester',
            'base_url': 'https://temp.example.com',
            'api_keys': ['temp-key'],
        },
        'abilities': ['func_call'],
        'extra_args': {'temperature': 0.5},
    }

    runtime_model = await model_mgr.init_temporary_runtime_llm_model(model_info)

    assert runtime_model.model_entity.uuid == 'temp-model-uuid'
    assert runtime_model.model_entity.name == 'TempModel'
    assert runtime_model.provider.provider_entity.uuid == 'temp-provider-uuid'
    assert runtime_model.provider.token_mgr.tokens == ['temp-key']


@pytest.mark.asyncio
async def test_model_manager_init_temporary_runtime_embedding_model(fake_requester_registry):
    """Test ModelManager.init_temporary_runtime_embedding_model creates model correctly."""
    model_mgr = fake_requester_registry
    await model_mgr.initialize()

    model_info = {
        'uuid': 'temp-embedding-uuid',
        'name': 'TempEmbedding',
        'provider': {
            'uuid': 'temp-provider-uuid',
            'name': 'Temp Provider',
            'requester': 'fake-requester',
            'base_url': 'https://temp.example.com',
            'api_keys': [],
        },
        'extra_args': {'dimensions': 512},
    }

    runtime_model = await model_mgr.init_temporary_runtime_embedding_model(model_info)

    assert runtime_model.model_entity.uuid == 'temp-embedding-uuid'
    assert runtime_model.model_entity.name == 'TempEmbedding'


@pytest.mark.asyncio
async def test_model_manager_init_temporary_runtime_rerank_model(fake_requester_registry):
    """Test ModelManager.init_temporary_runtime_rerank_model creates model correctly."""
    model_mgr = fake_requester_registry
    await model_mgr.initialize()

    model_info = {
        'uuid': 'temp-rerank-uuid',
        'name': 'TempRerank',
        'provider': {
            'uuid': 'temp-provider-uuid',
            'name': 'Temp Provider',
            'requester': 'fake-requester',
            'base_url': 'https://temp.example.com',
            'api_keys': [],
        },
        'extra_args': {},
    }

    runtime_model = await model_mgr.init_temporary_runtime_rerank_model(model_info)

    assert runtime_model.model_entity.uuid == 'temp-rerank-uuid'
    assert runtime_model.model_entity.name == 'TempRerank'


# ============================================================================
# Provider Reload Tests
# ============================================================================


@pytest.mark.asyncio
async def test_model_manager_reload_provider(fake_requester_registry, fake_persistence_data):
    """Test ModelManager.reload_provider reloads provider and updates model refs."""
    model_mgr = fake_requester_registry

    async def fake_execute(query):
        query_str = str(query)
        if 'model_providers' in query_str:
            # For initial load - return all providers
            rows = [_make_row_mock(p) for p in fake_persistence_data['providers']]
            return _make_mock_result(rows)
        elif 'llm_models' in query_str:
            rows = [_make_row_mock(m) for m in fake_persistence_data['llm_models']]
            return _make_mock_result(rows)
        elif 'embedding_models' in query_str:
            rows = [_make_row_mock(m) for m in fake_persistence_data['embedding_models']]
            return _make_mock_result(rows)
        elif 'rerank_models' in query_str:
            rows = [_make_row_mock(m) for m in fake_persistence_data['rerank_models']]
            return _make_mock_result(rows)
        return _make_mock_result([])

    model_mgr.ap.persistence_mgr.execute_async = fake_execute
    await model_mgr.initialize()

    original_provider = model_mgr.provider_dict[fake_persistence_data['provider_uuid']]
    original_base_url = original_provider.provider_entity.base_url

    # Setup for reload - return updated provider
    async def reload_execute(query):
        updated_provider = persistence_model.ModelProvider(
            uuid=fake_persistence_data['provider_uuid'],
            name='Updated Provider',
            requester='fake-requester',
            base_url='https://updated.example.com',
            api_keys=['updated-key'],
        )
        return _make_mock_result([_make_row_mock(updated_provider)], first_item=_make_row_mock(updated_provider))

    model_mgr.ap.persistence_mgr.execute_async = reload_execute

    await model_mgr.reload_provider(fake_persistence_data['provider_uuid'])

    updated_provider = model_mgr.provider_dict[fake_persistence_data['provider_uuid']]
    assert updated_provider.provider_entity.base_url == 'https://updated.example.com'
    assert updated_provider.provider_entity.base_url != original_base_url


@pytest.mark.asyncio
async def test_model_manager_reload_provider_not_found(fake_requester_registry):
    """Test ModelManager.reload_provider raises ProviderNotFoundError."""
    model_mgr = fake_requester_registry
    await model_mgr.initialize()

    async def fake_execute(query):
        return _make_mock_result([], first_item=None)

    model_mgr.ap.persistence_mgr.execute_async = fake_execute

    with pytest.raises(provider_errors.ProviderNotFoundError) as exc_info:
        await model_mgr.reload_provider('unknown-provider-uuid')

    assert exc_info.value.provider_name == 'unknown-provider-uuid'


# ============================================================================
# Model Load with Provider Tests
# ============================================================================


@pytest.mark.asyncio
async def test_model_manager_load_llm_model_with_provider(fake_requester_registry, fake_persistence_data, runtime_provider):
    """Test ModelManager.load_llm_model_with_provider creates RuntimeLLMModel."""
    model_mgr = fake_requester_registry

    model_entity = fake_persistence_data['llm_models'][0]

    runtime_model = await model_mgr.load_llm_model_with_provider(model_entity, runtime_provider)

    assert runtime_model.model_entity.uuid == model_entity.uuid
    assert runtime_model.provider is runtime_provider


@pytest.mark.asyncio
async def test_model_manager_load_llm_model_with_provider_from_row(fake_requester_registry, fake_persistence_data, runtime_provider):
    """Test ModelManager.load_llm_model_with_provider handles Row objects."""
    model_mgr = fake_requester_registry

    model_entity = fake_persistence_data['llm_models'][0]
    row_mock = _make_row_mock(model_entity)

    runtime_model = await model_mgr.load_llm_model_with_provider(row_mock, runtime_provider)

    assert runtime_model.model_entity.uuid == model_entity.uuid


@pytest.mark.asyncio
async def test_model_manager_load_embedding_model_with_provider(fake_requester_registry, fake_persistence_data, runtime_provider):
    """Test ModelManager.load_embedding_model_with_provider creates RuntimeEmbeddingModel."""
    model_mgr = fake_requester_registry

    model_entity = fake_persistence_data['embedding_models'][0]

    runtime_model = await model_mgr.load_embedding_model_with_provider(model_entity, runtime_provider)

    assert runtime_model.model_entity.uuid == model_entity.uuid
    assert runtime_model.provider is runtime_provider


@pytest.mark.asyncio
async def test_model_manager_load_rerank_model_with_provider(fake_requester_registry, fake_persistence_data):
    """Test ModelManager.load_rerank_model_with_provider creates RuntimeRerankModel."""
    model_mgr = fake_requester_registry
    await model_mgr.initialize()

    provider_entity = fake_persistence_data['providers'][1]
    token_mgr = token.TokenManager(name=provider_entity.uuid, tokens=provider_entity.api_keys or [])
    requester_inst = model_mgr.requester_dict['another-fake-requester'](
        ap=model_mgr.ap, config={'base_url': provider_entity.base_url}
    )
    await requester_inst.initialize()
    provider = requester.RuntimeProvider(
        provider_entity=provider_entity,
        token_mgr=token_mgr,
        requester=requester_inst,
    )

    model_entity = fake_persistence_data['rerank_models'][0]

    runtime_model = await model_mgr.load_rerank_model_with_provider(model_entity, provider)

    assert runtime_model.model_entity.uuid == model_entity.uuid
    assert runtime_model.provider is provider


# ============================================================================
# Missing Provider Warning Tests
# ============================================================================


@pytest.mark.asyncio
async def test_model_manager_logs_warning_for_missing_provider(fake_requester_registry):
    """Test ModelManager logs warning when model's provider is missing."""
    model_mgr = fake_requester_registry

    async def fake_execute(query):
        query_str = str(query)
        if 'model_providers' in query_str:
            # Return empty providers
            return _make_mock_result([])
        elif 'llm_models' in query_str:
            # Return model with missing provider
            fake_model = persistence_model.LLMModel(
                uuid='model-with-missing-provider',
                name='MissingProviderModel',
                provider_uuid='missing-provider-uuid',
                abilities=[],
                extra_args={},
            )
            return _make_mock_result([_make_row_mock(fake_model)])
        return _make_mock_result([])

    model_mgr.ap.persistence_mgr.execute_async = fake_execute
    await model_mgr.initialize()

    # Should have logged warning and skipped the model
    assert len(model_mgr.llm_models) == 0
    model_mgr.ap.logger.warning.assert_called()


@pytest.mark.asyncio
async def test_model_manager_handles_requester_not_found_gracefully(fake_requester_registry):
    """Test ModelManager handles RequesterNotFoundError during provider load."""
    model_mgr = fake_requester_registry

    async def fake_execute(query):
        query_str = str(query)
        if 'model_providers' in query_str:
            # Return provider with unknown requester
            fake_provider = persistence_model.ModelProvider(
                uuid='provider-with-unknown-requester',
                name='Unknown Requester Provider',
                requester='unknown-requester-name',
                base_url='https://unknown.com',
                api_keys=[],
            )
            return _make_mock_result([_make_row_mock(fake_provider)])
        elif 'llm_models' in query_str:
            fake_model = persistence_model.LLMModel(
                uuid='model-uuid',
                name='Model',
                provider_uuid='provider-with-unknown-requester',
                abilities=[],
                extra_args={},
            )
            return _make_mock_result([_make_row_mock(fake_model)])
        return _make_mock_result([])

    model_mgr.ap.persistence_mgr.execute_async = fake_execute
    await model_mgr.initialize()

    # Provider should be skipped
    assert len(model_mgr.provider_dict) == 0
    assert len(model_mgr.llm_models) == 0
    model_mgr.ap.logger.warning.assert_called()


# ============================================================================
# Error Classes Tests
# ============================================================================


def test_requester_not_found_error_str():
    """Test RequesterNotFoundError string representation."""
    error = provider_errors.RequesterNotFoundError('test-requester')

    assert str(error) == 'Requester test-requester not found'
    assert error.requester_name == 'test-requester'


def test_provider_not_found_error_str():
    """Test ProviderNotFoundError string representation."""
    error = provider_errors.ProviderNotFoundError('test-provider')

    assert str(error) == 'Provider test-provider not found'
    assert error.provider_name == 'test-provider'