"""
Test fixtures for provider/modelmgr tests.

Provides fake persistence, mock requester registry, and test utilities
without calling real LLM APIs or network requests.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock
from types import SimpleNamespace

from langbot.pkg.provider.modelmgr import requester
from langbot.pkg.provider.modelmgr import token
from langbot.pkg.provider.modelmgr.modelmgr import ModelManager
from langbot.pkg.entity.persistence import model as persistence_model
from langbot.pkg.discover import engine as discover_engine


class FakeProviderAPIRequester(requester.ProviderAPIRequester):
    """Fake requester for testing that does not make real API calls."""

    name = 'fake-requester'

    default_config = {'base_url': 'https://fake-api.example.com', 'timeout': 30}

    def __init__(self, ap, config: dict):
        super().__init__(ap, config)
        self._invoke_count = 0
        self._last_messages = None
        self._last_model = None

    async def invoke_llm(
        self,
        query,
        model: requester.RuntimeLLMModel,
        messages: list,
        funcs=None,
        extra_args={},
        remove_think=False,
    ):
        """Return a fake message response."""
        self._invoke_count += 1
        self._last_messages = messages
        self._last_model = model

        # Import the message entity for response
        import langbot_plugin.api.entities.builtin.provider.message as provider_message

        return provider_message.Message(
            role='assistant',
            content=[provider_message.ContentElement(type='text', text='Fake LLM response')],
        )

    async def invoke_llm_stream(
        self,
        query,
        model: requester.RuntimeLLMModel,
        messages: list,
        funcs=None,
        extra_args={},
        remove_think=False,
    ):
        """Yield fake message chunks."""
        import langbot_plugin.api.entities.builtin.provider.message as provider_message

        yield provider_message.MessageChunk(
            role='assistant',
            content=[provider_message.ContentElement(type='text', text='Fake stream chunk')],
        )

    async def invoke_embedding(self, model, input_text: list, extra_args={}):
        """Return fake embedding vectors."""
        return [[0.1, 0.2, 0.3] for _ in input_text]

    async def invoke_rerank(self, model, query: str, documents: list, extra_args={}):
        """Return fake rerank results."""
        return [{'index': i, 'relevance_score': 0.9 - i * 0.1} for i in range(len(documents))]


class AnotherFakeRequester(requester.ProviderAPIRequester):
    """Another fake requester for multi-requester tests."""

    name = 'another-fake-requester'

    default_config = {'base_url': 'https://another-fake.example.com'}

    async def invoke_llm(self, query, model, messages, funcs=None, extra_args={}, remove_think=False):
        import langbot_plugin.api.entities.builtin.provider.message as provider_message
        return provider_message.Message(role='assistant', content=[provider_message.ContentElement(type='text', text='Another response')])

    async def invoke_rerank(self, model, query: str, documents: list, extra_args={}):
        """Return fake rerank results."""
        return [{'index': i, 'relevance_score': 0.9 - i * 0.1} for i in range(len(documents))]


def _create_fake_component(name: str, requester_class: type) -> Mock:
    """Create a fake Component mock for a requester."""
    # Use Mock to allow overriding get_python_component_class
    component = Mock(spec=discover_engine.Component)
    component.metadata = Mock()
    component.metadata.name = name
    component.get_python_component_class = Mock(return_value=requester_class)
    return component


def _make_mock_result(items: list = None, first_item=None):
    """Create a mock result object for persistence queries."""
    result = Mock()
    result.all = Mock(return_value=items or [])
    result.first = Mock(return_value=first_item)
    return result


def _make_row_mock(entity):
    """Create a mock Row-like object that can be unpacked via _mapping.

    Note: This function returns the actual entity directly since Mock objects
    don't pass isinstance(provider_info, sqlalchemy.Row) checks. The code
    in modelmgr.load_provider handles this via the else branch.
    """
    return entity


@pytest.fixture
def mock_app_for_modelmgr():
    """Provides a mock Application for ModelManager tests."""
    app = SimpleNamespace()
    app.logger = Mock()
    app.logger.debug = Mock()
    app.logger.info = Mock()
    app.logger.warning = Mock()
    app.logger.error = Mock()

    # Fake persistence manager - returns empty results by default
    app.persistence_mgr = SimpleNamespace()
    async def default_execute(query):
        return _make_mock_result([])
    app.persistence_mgr.execute_async = AsyncMock(side_effect=default_execute)

    # Fake discover engine
    app.discover = SimpleNamespace()
    app.discover.get_components_by_kind = Mock(return_value=[])

    # Fake instance config
    app.instance_config = SimpleNamespace()
    app.instance_config.data = {'space': {'disable_models_service': True}}

    # Other services (not used in basic tests)
    app.space_service = AsyncMock()
    app.llm_model_service = AsyncMock()
    app.embedding_models_service = AsyncMock()
    app.monitoring_service = AsyncMock()

    return app


@pytest.fixture
def fake_requester_registry(mock_app_for_modelmgr):
    """Provides a ModelManager with fake requester registry."""
    app = mock_app_for_modelmgr

    # Create fake components
    fake_component = _create_fake_component('fake-requester', FakeProviderAPIRequester)
    another_component = _create_fake_component('another-fake-requester', AnotherFakeRequester)

    app.discover.get_components_by_kind = Mock(
        return_value=[fake_component, another_component]
    )

    model_mgr = ModelManager(app)
    return model_mgr


@pytest.fixture
def fake_persistence_data():
    """Provides fake persistence data for models and providers."""
    provider_uuid = 'test-provider-uuid'
    provider_uuid2 = 'test-provider-uuid-2'

    providers = [
        persistence_model.ModelProvider(
            uuid=provider_uuid,
            name='Test Provider',
            requester='fake-requester',
            base_url='https://test.example.com',
            api_keys=['test-api-key-1', 'test-api-key-2'],
        ),
        persistence_model.ModelProvider(
            uuid=provider_uuid2,
            name='Test Provider 2',
            requester='another-fake-requester',
            base_url='https://test2.example.com',
            api_keys=['key-3'],
        ),
    ]

    llm_models = [
        persistence_model.LLMModel(
            uuid='test-llm-uuid-1',
            name='TestLLM-1',
            provider_uuid=provider_uuid,
            abilities=['func_call'],
            extra_args={'temperature': 0.7},
        ),
        persistence_model.LLMModel(
            uuid='test-llm-uuid-2',
            name='TestLLM-2',
            provider_uuid=provider_uuid,
            abilities=['vision'],
            extra_args={},
        ),
    ]

    embedding_models = [
        persistence_model.EmbeddingModel(
            uuid='test-embedding-uuid-1',
            name='TestEmbedding-1',
            provider_uuid=provider_uuid,
            extra_args={'dimensions': 768},
        ),
    ]

    rerank_models = [
        persistence_model.RerankModel(
            uuid='test-rerank-uuid-1',
            name='TestRerank-1',
            provider_uuid=provider_uuid2,
            extra_args={},
        ),
    ]

    return {
        'providers': providers,
        'llm_models': llm_models,
        'embedding_models': embedding_models,
        'rerank_models': rerank_models,
        'provider_uuid': provider_uuid,
        'provider_uuid2': provider_uuid2,
    }


@pytest.fixture
def runtime_provider(fake_persistence_data, mock_app_for_modelmgr):
    """Provides a RuntimeProvider instance for testing."""
    provider_entity = fake_persistence_data['providers'][0]
    token_mgr = token.TokenManager(name=provider_entity.uuid, tokens=provider_entity.api_keys or [])
    requester_inst = FakeProviderAPIRequester(mock_app_for_modelmgr, {'base_url': provider_entity.base_url})

    return requester.RuntimeProvider(
        provider_entity=provider_entity,
        token_mgr=token_mgr,
        requester=requester_inst,
    )


@pytest.fixture
def runtime_llm_model(fake_persistence_data, runtime_provider):
    """Provides a RuntimeLLMModel instance for testing."""
    model_entity = fake_persistence_data['llm_models'][0]
    return requester.RuntimeLLMModel(
        model_entity=model_entity,
        provider=runtime_provider,
    )


@pytest.fixture
def runtime_embedding_model(fake_persistence_data, runtime_provider):
    """Provides a RuntimeEmbeddingModel instance for testing."""
    model_entity = fake_persistence_data['embedding_models'][0]
    return requester.RuntimeEmbeddingModel(
        model_entity=model_entity,
        provider=runtime_provider,
    )


@pytest.fixture
def runtime_rerank_model(fake_persistence_data, mock_app_for_modelmgr):
    """Provides a RuntimeRerankModel instance for testing."""
    provider_entity = fake_persistence_data['providers'][1]
    token_mgr = token.TokenManager(name=provider_entity.uuid, tokens=provider_entity.api_keys or [])
    requester_inst = AnotherFakeRequester(mock_app_for_modelmgr, {'base_url': provider_entity.base_url})

    provider = requester.RuntimeProvider(
        provider_entity=provider_entity,
        token_mgr=token_mgr,
        requester=requester_inst,
    )

    model_entity = fake_persistence_data['rerank_models'][0]
    return requester.RuntimeRerankModel(
        model_entity=model_entity,
        provider=provider,
    )
