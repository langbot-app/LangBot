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
    app.user_service.verify_jwt_token = AsyncMock(return_value={'email': 'test@example.com'})
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
    app.provider_service.create_provider = AsyncMock(return_value={'uuid': 'new-provider-uuid'})
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

    # Rerank model service
    app.rerank_models_service = Mock()
    app.rerank_models_service.get_rerank_models = AsyncMock(return_value=[])

    # Model manager
    app.model_mgr = Mock()
    app.model_mgr.load_provider = AsyncMock()
    app.model_mgr.unload_provider = AsyncMock()

    return app


@pytest.fixture(scope='module')
async def quart_test_client(fake_provider_app):
    """Create Quart test client (module scope to avoid route re-registration)."""
    from langbot.pkg.api.http.controller.main import HTTPController

    controller = HTTPController(fake_provider_app)
    await controller.initialize()

    client = controller.quart_app.test_client()
    yield client


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestProviderEndpoints:
    """Tests for /api/v1/provider endpoints."""

    @pytest.mark.asyncio
    async def test_get_providers_success(self, quart_test_client):
        """GET /api/v1/provider/providers returns provider list."""
        response = await quart_test_client.get(
            '/api/v1/provider/providers',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'data' in data

    @pytest.mark.asyncio
    async def test_get_single_provider_success(self, quart_test_client):
        """GET /api/v1/provider/providers/{uuid} returns provider."""
        response = await quart_test_client.get(
            '/api/v1/provider/providers/test-provider-uuid',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0

    @pytest.mark.asyncio
    async def test_create_provider_success(self, quart_test_client):
        """POST /api/v1/provider/providers creates new provider."""
        response = await quart_test_client.post(
            '/api/v1/provider/providers',
            headers={'Authorization': 'Bearer test_token'},
            json={'name': 'New Provider', 'requester': 'chatcmpl'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'uuid' in data['data']

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