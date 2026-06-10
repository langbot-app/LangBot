"""
API integration tests for provider/model endpoints.

Tests real HTTP API behavior for provider and model management.

Run: uv run pytest tests/integration/api/test_providers.py -q
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, Mock

from tests.factories import FakeApp


pytestmark = pytest.mark.integration


@pytest.fixture(scope='module')
def mock_circular_import_chain():
    """Break circular import chain for API controller."""
    from tests.utils.import_isolation import isolated_sys_modules, MockLifecycleControlScope

    class FakeMinimalApplication:
        pass

    mock_app = MagicMock()
    mock_app.Application = FakeMinimalApplication

    mock_entities = MagicMock()
    mock_entities.LifecycleControlScope = MockLifecycleControlScope

    clear = [
        'langbot.pkg.api.http.controller.group',
        'langbot.pkg.api.http.controller.groups',
        'langbot.pkg.api.http.controller.groups.provider',
        'langbot.pkg.api.http.controller.groups.provider.providers',
        'langbot.pkg.api.http.controller.groups.provider.models',
        'langbot.pkg.api.http.controller.main',
    ]

    with isolated_sys_modules(
        mocks={
            'langbot.pkg.core.app': mock_app,
            'langbot.pkg.core.entities': mock_entities,
        },
        clear=clear,
    ):
        import langbot.pkg.api.http.controller.groups.provider.providers as _providers  # noqa: E402, F401
        import langbot.pkg.api.http.controller.groups.provider.models as _models  # noqa: E402, F401
        yield


@pytest.fixture(scope='module')
def fake_provider_app():
    """Create FakeApp with provider/model services (module scope for reuse)."""
    app = FakeApp()

    app.instance_config.data.update({
        'api': {'port': 5300},
        'system': {'allow_modify_login_info': True, 'limitation': {}},
    })

    # Auth services
    app.user_service = Mock()
    app.user_service.is_initialized = AsyncMock(return_value=True)
    app.user_service.verify_jwt_token = AsyncMock(return_value='test@example.com')
    app.user_service.get_user_by_email = AsyncMock(return_value=Mock(email='test@example.com'))
    app.apikey_service = Mock()
    app.apikey_service.verify_api_key = AsyncMock(return_value=True)

    # Provider service
    app.provider_service = Mock()
    app.provider_service.get_providers = AsyncMock(return_value=[
        {'uuid': 'test-provider-uuid', 'name': 'OpenAI', 'requester': 'chatcmpl'}
    ])
    app.provider_service.get_provider = AsyncMock(return_value={
        'uuid': 'test-provider-uuid', 'name': 'OpenAI', 'requester': 'chatcmpl'
    })
    app.provider_service.create_provider = AsyncMock(return_value='new-provider-uuid')
    app.provider_service.update_provider = AsyncMock(return_value={})
    app.provider_service.delete_provider = AsyncMock()
    app.provider_service.get_provider_model_counts = AsyncMock(return_value={
        'llm_count': 2, 'embedding_count': 1, 'rerank_count': 0
    })

    # LLM model service
    app.llm_model_service = Mock()
    app.llm_model_service.get_llm_models = AsyncMock(return_value=[
        {'uuid': 'test-model-uuid', 'name': 'gpt-4'}
    ])
    app.llm_model_service.get_llm_model = AsyncMock(return_value={
        'uuid': 'test-model-uuid', 'name': 'gpt-4'
    })
    app.llm_model_service.create_llm_model = AsyncMock(return_value={'uuid': 'new-model-uuid'})
    app.llm_model_service.update_llm_model = AsyncMock(return_value={})
    app.llm_model_service.delete_llm_model = AsyncMock()

    # Embedding model service
    app.embedding_models_service = Mock()
    app.embedding_models_service.get_embedding_models = AsyncMock(return_value=[])
    app.embedding_models_service.create_embedding_model = AsyncMock(return_value={'uuid': 'new-embedding-uuid'})

    # Rerank model service
    app.rerank_models_service = Mock()
    app.rerank_models_service.get_rerank_models = AsyncMock(return_value=[])
    app.rerank_models_service.create_rerank_model = AsyncMock(return_value={'uuid': 'new-rerank-uuid'})

    # Model manager
    app.model_mgr = Mock()
    app.model_mgr.load_provider = AsyncMock()
    app.model_mgr.unload_provider = AsyncMock()

    return app


@pytest.fixture(scope='module')
async def quart_test_client(fake_provider_app, http_controller_cls):
    """Create Quart test client (module scope to avoid route re-registration)."""
    controller = http_controller_cls(fake_provider_app)
    await controller.initialize()

    client = controller.quart_app.test_client()
    yield client


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestProviderEndpoints:
    """Tests for /api/v1/provider endpoints."""

    @pytest.mark.asyncio
    async def test_get_providers_success(self, quart_test_client):
        """GET /api/v1/provider/providers returns provider list with complete structure."""
        response = await quart_test_client.get(
            '/api/v1/provider/providers',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'data' in data
        # Verify response structure completeness
        providers = data['data']['providers']
        assert isinstance(providers, list)
        assert len(providers) == 1
        # Verify required fields in provider object
        provider = providers[0]
        assert 'uuid' in provider
        assert 'name' in provider
        assert 'requester' in provider
        assert provider['uuid'] == 'test-provider-uuid'
        assert provider['name'] == 'OpenAI'

    @pytest.mark.asyncio
    async def test_get_single_provider_success(self, quart_test_client):
        """GET /api/v1/provider/providers/{uuid} returns complete provider structure."""
        response = await quart_test_client.get(
            '/api/v1/provider/providers/test-provider-uuid',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        # Verify response structure
        provider = data['data']['provider']
        assert 'uuid' in provider
        assert 'name' in provider
        assert 'requester' in provider
        assert provider['uuid'] == 'test-provider-uuid'

    @pytest.mark.asyncio
    async def test_create_provider_success(self, quart_test_client):
        """POST /api/v1/provider/providers creates new provider with uuid returned."""
        response = await quart_test_client.post(
            '/api/v1/provider/providers',
            headers={'Authorization': 'Bearer test_token'},
            json={'name': 'New Provider', 'requester': 'chatcmpl'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        # Verify uuid is present and matches expected
        assert 'data' in data
        assert 'uuid' in data['data']
        assert data['data']['uuid'] == 'new-provider-uuid'

    @pytest.mark.asyncio
    async def test_update_provider_success(self, quart_test_client):
        """PUT /api/v1/provider/providers/{uuid} updates provider."""
        response = await quart_test_client.put(
            '/api/v1/provider/providers/test-provider-uuid',
            headers={'Authorization': 'Bearer test_token'},
            json={'name': 'Updated Provider'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0

    @pytest.mark.asyncio
    async def test_delete_provider_success(self, quart_test_client):
        """DELETE /api/v1/provider/providers/{uuid} deletes provider."""
        response = await quart_test_client.delete(
            '/api/v1/provider/providers/test-provider-uuid',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_provider_includes_model_counts(self, quart_test_client):
        """GET provider response includes model counts."""
        response = await quart_test_client.get(
            '/api/v1/provider/providers/test-provider-uuid',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        # Model counts are embedded in provider response
        provider_data = data['data']['provider']
        assert 'llm_count' in provider_data
        assert 'embedding_count' in provider_data
        assert 'rerank_count' in provider_data


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestModelEndpoints:
    """Tests for /api/v1/provider/models endpoints."""

    @pytest.mark.asyncio
    async def test_get_llm_models_success(self, quart_test_client):
        """GET /api/v1/provider/models/llm returns model list."""
        response = await quart_test_client.get(
            '/api/v1/provider/models/llm',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'data' in data

    @pytest.mark.asyncio
    async def test_get_single_llm_model_success(self, quart_test_client):
        """GET /api/v1/provider/models/llm/{uuid} returns model."""
        response = await quart_test_client.get(
            '/api/v1/provider/models/llm/test-model-uuid',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0

    @pytest.mark.asyncio
    async def test_create_llm_model_success(self, quart_test_client):
        """POST /api/v1/provider/models/llm creates new model."""
        response = await quart_test_client.post(
            '/api/v1/provider/models/llm',
            headers={'Authorization': 'Bearer test_token'},
            json={'name': 'New Model', 'provider_uuid': 'test-provider-uuid'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'uuid' in data['data']

    @pytest.mark.asyncio
    async def test_delete_llm_model_success(self, quart_test_client):
        """DELETE /api/v1/provider/models/llm/{uuid} deletes model."""
        response = await quart_test_client.delete(
            '/api/v1/provider/models/llm/test-model-uuid',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestEmbeddingModelEndpoints:
    """Tests for /api/v1/provider/models/embedding endpoints."""

    @pytest.mark.asyncio
    async def test_get_embedding_models_success(self, quart_test_client):
        """GET /api/v1/provider/models/embedding returns model list."""
        response = await quart_test_client.get(
            '/api/v1/provider/models/embedding',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'models' in data['data']

    @pytest.mark.asyncio
    async def test_create_embedding_model_success(self, quart_test_client):
        """POST /api/v1/provider/models/embedding creates new model."""
        response = await quart_test_client.post(
            '/api/v1/provider/models/embedding',
            headers={'Authorization': 'Bearer test_token'},
            json={'name': 'New Embedding Model', 'provider_uuid': 'test-provider-uuid'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'uuid' in data['data']


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestRerankModelEndpoints:
    """Tests for /api/v1/provider/models/rerank endpoints."""

    @pytest.mark.asyncio
    async def test_get_rerank_models_success(self, quart_test_client):
        """GET /api/v1/provider/models/rerank returns model list."""
        response = await quart_test_client.get(
            '/api/v1/provider/models/rerank',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'models' in data['data']

    @pytest.mark.asyncio
    async def test_create_rerank_model_success(self, quart_test_client):
        """POST /api/v1/provider/models/rerank creates new model."""
        response = await quart_test_client.post(
            '/api/v1/provider/models/rerank',
            headers={'Authorization': 'Bearer test_token'},
            json={'name': 'New Rerank Model', 'provider_uuid': 'test-provider-uuid'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'uuid' in data['data']
