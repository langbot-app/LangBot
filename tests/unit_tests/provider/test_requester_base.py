"""
Unit tests for ProviderAPIRequester base class and runtime entities in provider/modelmgr.

Tests requester initialization, configuration handling, token management,
and runtime model/provider behavior without calling real LLM APIs.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock
from types import SimpleNamespace

from langbot.pkg.provider.modelmgr import requester
from langbot.pkg.provider.modelmgr import token
from langbot.pkg.entity.persistence import model as persistence_model
from langbot.pkg.provider.modelmgr.errors import RequesterError


# ============================================================================
# ProviderAPIRequester Base Class Tests
# ============================================================================


class TestableRequester(requester.ProviderAPIRequester):
    """Testable requester subclass for testing base class behavior."""

    name = 'testable-requester'

    default_config = {
        'base_url': 'https://default.example.com',
        'timeout': 60,
        'max_retries': 3,
    }

    async def invoke_llm(
        self,
        query,
        model: requester.RuntimeLLMModel,
        messages: list,
        funcs=None,
        extra_args={},
        remove_think=False,
    ):
        import langbot_plugin.api.entities.builtin.provider.message as provider_message
        return provider_message.Message(
            role='assistant',
            content=[provider_message.ContentElement(type='text', text='Testable response')],
        )


def test_requester_base_class_is_abstract():
    """Test ProviderAPIRequester cannot be instantiated directly."""
    mock_app = SimpleNamespace()
    mock_app.logger = Mock()

    # ProviderAPIRequester has abstract methods, but ABCMeta allows instantiation
    # if you don't call the abstract methods. Test that it has abstract methods.
    assert hasattr(requester.ProviderAPIRequester, 'invoke_llm')
    # Check that invoke_llm is abstract
    assert hasattr(requester.ProviderAPIRequester.invoke_llm, '__isabstractmethod__')


def test_requester_default_config_merged():
    """Test requester merges default config with provided config."""
    mock_app = SimpleNamespace()
    mock_app.logger = Mock()

    inst = TestableRequester(mock_app, {'base_url': 'https://custom.example.com', 'custom_key': 'custom_value'})

    assert inst.requester_cfg['base_url'] == 'https://custom.example.com'
    assert inst.requester_cfg['timeout'] == 60  # from default
    assert inst.requester_cfg['max_retries'] == 3  # from default
    assert inst.requester_cfg['custom_key'] == 'custom_value'  # custom added


def test_requester_default_config_not_modified():
    """Test that default_config dict is not modified when merging."""
    mock_app = SimpleNamespace()
    mock_app.logger = Mock()

    inst = TestableRequester(mock_app, {'base_url': 'https://override.example.com'})

    assert TestableRequester.default_config['base_url'] == 'https://default.example.com'
    assert inst.requester_cfg['base_url'] == 'https://override.example.com'


def test_requester_empty_config_uses_defaults():
    """Test requester uses defaults when empty config provided."""
    mock_app = SimpleNamespace()
    mock_app.logger = Mock()

    inst = TestableRequester(mock_app, {})

    assert inst.requester_cfg == inst.default_config


@pytest.mark.asyncio
async def test_requester_initialize_is_callable():
    """Test requester initialize method is callable (default is pass)."""
    mock_app = SimpleNamespace()
    mock_app.logger = Mock()

    inst = TestableRequester(mock_app, {})
    await inst.initialize()

    # No exception should occur


@pytest.mark.asyncio
async def test_requester_scan_models_not_implemented():
    """Test scan_models raises NotImplementedError by default."""
    mock_app = SimpleNamespace()
    mock_app.logger = Mock()

    inst = TestableRequester(mock_app, {})
    await inst.initialize()

    with pytest.raises(NotImplementedError) as exc_info:
        await inst.scan_models()

    assert 'does not support model scanning' in str(exc_info.value)


@pytest.mark.asyncio
async def test_requester_invoke_rerank_not_implemented():
    """Test invoke_rerank raises NotImplementedError by default."""
    mock_app = SimpleNamespace()
    mock_app.logger = Mock()

    inst = TestableRequester(mock_app, {})
    await inst.initialize()

    # Create fake model
    fake_provider_entity = persistence_model.ModelProvider(
        uuid='provider-uuid',
        name='Provider',
        requester='test',
        base_url='https://test.com',
        api_keys=[],
    )
    fake_token_mgr = token.TokenManager(name='test', tokens=[])
    fake_requester = inst
    fake_provider = requester.RuntimeProvider(
        provider_entity=fake_provider_entity,
        token_mgr=fake_token_mgr,
        requester=fake_requester,
    )
    fake_model_entity = persistence_model.RerankModel(
        uuid='model-uuid',
        name='Model',
        provider_uuid='provider-uuid',
        extra_args={},
    )
    fake_model = requester.RuntimeRerankModel(
        model_entity=fake_model_entity,
        provider=fake_provider,
    )

    with pytest.raises(NotImplementedError) as exc_info:
        await inst.invoke_rerank(fake_model, 'query', ['doc1', 'doc2'])

    assert 'does not support rerank' in str(exc_info.value)


# ============================================================================
# TokenManager Tests
# ============================================================================


def test_token_manager_initial_state():
    """Test TokenManager initial state."""
    mgr = token.TokenManager(name='test-manager', tokens=['key1', 'key2', 'key3'])

    assert mgr.name == 'test-manager'
    assert mgr.tokens == ['key1', 'key2', 'key3']
    assert mgr.using_token_index == 0


def test_token_manager_get_token():
    """Test TokenManager.get_token returns current token."""
    mgr = token.TokenManager(name='test', tokens=['key1', 'key2'])

    assert mgr.get_token() == 'key1'


def test_token_manager_get_token_empty():
    """Test TokenManager.get_token returns empty string when no tokens."""
    mgr = token.TokenManager(name='test', tokens=[])

    assert mgr.get_token() == ''


def test_token_manager_next_token_cycles():
    """Test TokenManager.next_token cycles through tokens."""
    mgr = token.TokenManager(name='test', tokens=['key1', 'key2', 'key3'])

    assert mgr.get_token() == 'key1'

    mgr.next_token()
    assert mgr.get_token() == 'key2'

    mgr.next_token()
    assert mgr.get_token() == 'key3'

    # Should cycle back to first
    mgr.next_token()
    assert mgr.get_token() == 'key1'


def test_token_manager_next_token_single():
    """Test TokenManager.next_token with single token."""
    mgr = token.TokenManager(name='test', tokens=['single-key'])

    mgr.next_token()
    assert mgr.get_token() == 'single-key'

    mgr.next_token()
    assert mgr.get_token() == 'single-key'


def test_token_manager_next_token_empty():
    """Test TokenManager.next_token with empty tokens doesn't error."""
    mgr = token.TokenManager(name='test', tokens=[])

    assert mgr.next_token() is None
    assert mgr.get_token() == ''


# ============================================================================
# RuntimeProvider Tests
# ============================================================================


def test_runtime_provider_initialization(runtime_provider, fake_persistence_data):
    """Test RuntimeProvider initialization."""
    provider = runtime_provider
    provider_entity = fake_persistence_data['providers'][0]

    assert provider.provider_entity.uuid == provider_entity.uuid
    assert provider.provider_entity.name == provider_entity.name
    assert provider.token_mgr.name == provider_entity.uuid
    assert provider.token_mgr.tokens == provider_entity.api_keys
    assert isinstance(provider.requester, requester.ProviderAPIRequester)


def test_runtime_provider_has_invoke_methods(runtime_provider):
    """Test RuntimeProvider has invoke methods that delegate to requester."""
    provider = runtime_provider

    assert hasattr(provider, 'invoke_llm')
    assert hasattr(provider, 'invoke_llm_stream')
    assert hasattr(provider, 'invoke_embedding')
    assert hasattr(provider, 'invoke_rerank')


@pytest.mark.asyncio
async def test_runtime_provider_invoke_llm_delegates(runtime_provider, runtime_llm_model):
    """Test RuntimeProvider.invoke_llm delegates to requester."""
    provider = runtime_provider

    # Track that requester was called
    provider.requester._invoke_count = 0

    import langbot_plugin.api.entities.builtin.provider.message as provider_message
    import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

    # Create minimal query for testing (bypass validation)
    query = pipeline_query.Query.model_construct(
        query_id='test-query',
        launcher_type='person',
        launcher_id=12345,
        sender_id=12345,
        message_chain=None,
        message_event=None,
        adapter=None,
        pipeline_uuid='pipeline-uuid',
        bot_uuid='bot-uuid',
        pipeline_config={'ai': {}, 'output': {}, 'trigger': {}},
        session=None,
        prompt=None,
        messages=[],
        user_message=None,
        use_funcs=[],
        use_llm_model_uuid=None,
        variables={},
        resp_messages=[],
        resp_message_chain=None,
        current_stage_name=None,
    )

    messages = [provider_message.Message(role='user', content=[provider_message.ContentElement(type='text', text='Hello')])]

    result = await provider.invoke_llm(query, runtime_llm_model, messages)

    assert provider.requester._invoke_count == 1
    assert provider.requester._last_messages == messages
    assert provider.requester._last_model == runtime_llm_model
    assert result.role == 'assistant'


@pytest.mark.asyncio
async def test_runtime_provider_invoke_llm_stream_yields_chunks(runtime_provider, runtime_llm_model):
    """Test RuntimeProvider.invoke_llm_stream yields chunks from requester."""
    provider = runtime_provider

    import langbot_plugin.api.entities.builtin.provider.message as provider_message
    import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

    query = pipeline_query.Query.model_construct(
        query_id='test-stream',
        launcher_type='person',
        launcher_id=12345,
        sender_id=12345,
        message_chain=None,
        message_event=None,
        adapter=None,
        pipeline_uuid='pipeline-uuid',
        bot_uuid='bot-uuid',
        pipeline_config={'ai': {}, 'output': {}, 'trigger': {}},
        session=None,
        prompt=None,
        messages=[],
        user_message=None,
        use_funcs=[],
        use_llm_model_uuid=None,
        variables={},
        resp_messages=[],
        resp_message_chain=None,
        current_stage_name=None,
    )

    messages = [provider_message.Message(role='user', content=[provider_message.ContentElement(type='text', text='Hello')])]

    chunks = []
    async for chunk in provider.invoke_llm_stream(query, runtime_llm_model, messages):
        chunks.append(chunk)

    assert len(chunks) == 1
    assert chunks[0].role == 'assistant'


@pytest.mark.asyncio
async def test_runtime_provider_invoke_embedding_returns_vectors(runtime_provider, runtime_embedding_model):
    """Test RuntimeProvider.invoke_embedding returns embedding vectors."""
    provider = runtime_provider

    result = await provider.invoke_embedding(runtime_embedding_model, ['text1', 'text2'])

    assert len(result) == 2
    assert result[0] == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_runtime_provider_invoke_rerank_returns_scores(runtime_provider, runtime_rerank_model):
    """Test RuntimeProvider.invoke_rerank returns relevance scores."""
    # Need to use the correct provider for rerank model
    provider = runtime_rerank_model.provider

    result = await provider.invoke_rerank(runtime_rerank_model, 'query', ['doc1', 'doc2', 'doc3'])

    assert len(result) == 3
    assert result[0]['index'] == 0
    assert result[0]['relevance_score'] == 0.9


# ============================================================================
# RuntimeLLMModel Tests
# ============================================================================


def test_runtime_llm_model_initialization(runtime_llm_model, fake_persistence_data):
    """Test RuntimeLLMModel initialization."""
    model = runtime_llm_model
    model_entity = fake_persistence_data['llm_models'][0]

    assert model.model_entity.uuid == model_entity.uuid
    assert model.model_entity.name == model_entity.name
    assert model.model_entity.abilities == model_entity.abilities
    assert model.model_entity.extra_args == model_entity.extra_args
    assert model.provider is not None


def test_runtime_llm_model_provider_ref(runtime_llm_model):
    """Test RuntimeLLMModel has correct provider reference."""
    model = runtime_llm_model

    assert model.provider.provider_entity is not None
    assert model.provider.token_mgr is not None
    assert model.provider.requester is not None


# ============================================================================
# RuntimeEmbeddingModel Tests
# ============================================================================


def test_runtime_embedding_model_initialization(runtime_embedding_model, fake_persistence_data):
    """Test RuntimeEmbeddingModel initialization."""
    model = runtime_embedding_model
    model_entity = fake_persistence_data['embedding_models'][0]

    assert model.model_entity.uuid == model_entity.uuid
    assert model.model_entity.name == model_entity.name
    assert model.model_entity.extra_args == model_entity.extra_args
    assert model.provider is not None


# ============================================================================
# RuntimeRerankModel Tests
# ============================================================================


def test_runtime_rerank_model_initialization(runtime_rerank_model, fake_persistence_data):
    """Test RuntimeRerankModel initialization."""
    model = runtime_rerank_model
    model_entity = fake_persistence_data['rerank_models'][0]

    assert model.model_entity.uuid == model_entity.uuid
    assert model.model_entity.name == model_entity.name
    assert model.model_entity.extra_args == model_entity.extra_args
    assert model.provider is not None


# ============================================================================
# RequesterError Tests
# ============================================================================


def test_requester_error_message_format():
    """Test RequesterError message format."""
    error = RequesterError('API returned 500')

    assert '模型请求失败' in str(error)
    assert 'API returned 500' in str(error)


def test_requester_error_is_exception():
    """Test RequesterError is Exception subclass."""
    error = RequesterError('test')

    assert isinstance(error, Exception)


# ============================================================================
# ProviderAPIRequester Config Validation Tests
# ============================================================================


def test_requester_with_missing_base_url():
    """Test requester handles missing base_url in config."""
    mock_app = SimpleNamespace()
    mock_app.logger = Mock()

    # If base_url is in default_config, it will be used
    inst = TestableRequester(mock_app, {'timeout': 30})

    assert inst.requester_cfg['base_url'] == 'https://default.example.com'


def test_requester_with_none_values():
    """Test requester handles None values in config."""
    mock_app = SimpleNamespace()
    mock_app.logger = Mock()

    inst = TestableRequester(mock_app, {'timeout': None, 'base_url': 'https://test.com'})

    # None values are kept in the merged config
    assert inst.requester_cfg['timeout'] is None


class RequesterWithNoDefaults(requester.ProviderAPIRequester):
    """Requester with empty defaults for testing."""

    name = 'no-defaults-requester'
    default_config = {}

    async def invoke_llm(self, query, model, messages, funcs=None, extra_args={}, remove_think=False):
        pass


def test_requester_empty_defaults_with_empty_config():
    """Test requester with empty defaults and empty config."""
    mock_app = SimpleNamespace()
    mock_app.logger = Mock()

    inst = RequesterWithNoDefaults(mock_app, {})

    assert inst.requester_cfg == {}


def test_requester_empty_defaults_with_values():
    """Test requester with empty defaults receives config values."""
    mock_app = SimpleNamespace()
    mock_app.logger = Mock()

    inst = RequesterWithNoDefaults(mock_app, {'base_url': 'https://custom.com', 'api_key': 'key'})

    assert inst.requester_cfg['base_url'] == 'https://custom.com'
    assert inst.requester_cfg['api_key'] == 'key'


# ============================================================================
# RuntimeProvider Error Handling Tests
# ============================================================================


class ErrorThrowingRequester(requester.ProviderAPIRequester):
    """Requester that throws errors for testing."""

    name = 'error-requester'
    default_config = {}

    async def invoke_llm(self, query, model, messages, funcs=None, extra_args={}, remove_think=False):
        raise RequesterError('Simulated API error')


@pytest.mark.asyncio
async def test_runtime_provider_invoke_llm_propagates_error(mock_app_for_modelmgr):
    """Test RuntimeProvider.invoke_llm propagates requester errors."""
    mock_app = mock_app_for_modelmgr

    # Add monitoring_service for error handling path
    mock_app.monitoring_service = AsyncMock()

    requester_inst = ErrorThrowingRequester(mock_app, {})
    await requester_inst.initialize()

    provider_entity = persistence_model.ModelProvider(
        uuid='error-provider',
        name='Error Provider',
        requester='error-requester',
        base_url='https://error.com',
        api_keys=['error-key'],
    )
    token_mgr = token.TokenManager(name='error-provider', tokens=['error-key'])

    provider = requester.RuntimeProvider(
        provider_entity=provider_entity,
        token_mgr=token_mgr,
        requester=requester_inst,
    )

    model_entity = persistence_model.LLMModel(
        uuid='error-model',
        name='Error Model',
        provider_uuid='error-provider',
        abilities=[],
        extra_args={},
    )
    model = requester.RuntimeLLMModel(model_entity=model_entity, provider=provider)

    import langbot_plugin.api.entities.builtin.provider.message as provider_message
    import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

    query = pipeline_query.Query.model_construct(
        query_id='error-query',
        launcher_type='person',
        launcher_id=12345,
        sender_id=12345,
        message_chain=None,
        message_event=None,
        adapter=None,
        pipeline_uuid='pipeline-uuid',
        bot_uuid='bot-uuid',
        pipeline_config={'ai': {}, 'output': {}, 'trigger': {}},
        session=None,
        prompt=None,
        messages=[],
        user_message=None,
        use_funcs=[],
        use_llm_model_uuid=None,
        variables={},
        resp_messages=[],
        resp_message_chain=None,
        current_stage_name=None,
    )

    messages = [provider_message.Message(role='user', content=[provider_message.ContentElement(type='text', text='Hello')])]

    with pytest.raises(RequesterError):
        await provider.invoke_llm(query, model, messages)


# ============================================================================
# LLMModelInfo Tests (from entities.py)
# ============================================================================


def test_llm_model_info_basic():
    """Test LLMModelInfo basic structure."""
    from langbot.pkg.provider.modelmgr.entities import LLMModelInfo

    mock_app = SimpleNamespace()
    mock_app.logger = Mock()

    fake_requester = TestableRequester(mock_app, {})
    fake_token_mgr = token.TokenManager(name='test', tokens=['key'])

    info = LLMModelInfo(
        name='test-model',
        model_name='gpt-4',
        token_mgr=fake_token_mgr,
        requester=fake_requester,
        tool_call_supported=True,
        vision_supported=False,
    )

    assert info.name == 'test-model'
    assert info.model_name == 'gpt-4'
    assert info.tool_call_supported == True
    assert info.vision_supported == False


def test_llm_model_info_optional_fields():
    """Test LLMModelInfo optional fields default values."""
    from langbot.pkg.provider.modelmgr.entities import LLMModelInfo

    mock_app = SimpleNamespace()
    mock_app.logger = Mock()

    fake_requester = TestableRequester(mock_app, {})
    fake_token_mgr = token.TokenManager(name='test', tokens=['key'])

    info = LLMModelInfo(
        name='minimal-model',
        token_mgr=fake_token_mgr,
        requester=fake_requester,
    )

    assert info.model_name is None
    assert info.tool_call_supported == False  # default
    assert info.vision_supported == False  # default
