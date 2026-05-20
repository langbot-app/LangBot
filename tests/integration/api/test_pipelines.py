"""
API integration tests for pipeline endpoints.

Tests real HTTP API behavior using Quart test client with mocked services.
Extends test_smoke.py coverage for pipeline-related endpoints.

Run: uv run pytest tests/integration/api/test_pipelines.py -q
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, Mock

from tests.factories import FakeApp


pytestmark = pytest.mark.integration


# ============== FIXTURE FOR SYS.MODULES ISOLATION ==============

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
        'langbot.pkg.api.http.controller.groups.pipelines',
        'langbot.pkg.api.http.controller.groups.pipelines.pipelines',
        'langbot.pkg.api.http.controller.groups.pipelines.embed',
        'langbot.pkg.api.http.controller.groups.pipelines.websocket_chat',
        'langbot.pkg.api.http.controller.main',
    ]

    with isolated_sys_modules(
        mocks={
            'langbot.pkg.core.app': mock_app,
            'langbot.pkg.core.entities': mock_entities,
        },
        clear=clear,
    ):
        # Import groups after mocking to populate preregistered_groups
        import langbot.pkg.api.http.controller.groups.pipelines.pipelines as _pipelines  # noqa: E402, F401
        yield


# ============== FAKE APPLICATION WITH PIPELINE SERVICES ==============

@pytest.fixture(scope='module')
def fake_pipeline_app():
    """Create FakeApp with pipeline-specific services (module scope for reuse)."""
    app = FakeApp()

    # Pipeline config
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

    # Pipeline service
    app.pipeline_service = Mock()
    app.pipeline_service.get_pipeline_metadata = AsyncMock(return_value=[
        {'name': 'trigger', 'stages': []},
        {'name': 'ai', 'stages': []},
    ])
    app.pipeline_service.get_pipelines = AsyncMock(return_value=[
        {
            'uuid': 'test-pipeline-uuid',
            'name': 'Test Pipeline',
            'description': 'Test description',
            'created_at': '2024-01-01T00:00:00',
            'updated_at': '2024-01-01T00:00:00',
            'is_default': False,
        }
    ])
    app.pipeline_service.get_pipeline = AsyncMock(return_value={
        'uuid': 'test-pipeline-uuid',
        'name': 'Test Pipeline',
        'config': {},
    })
    app.pipeline_service.create_pipeline = AsyncMock(return_value={'uuid': 'new-pipeline-uuid'})
    app.pipeline_service.update_pipeline = AsyncMock(return_value={})
    app.pipeline_service.delete_pipeline = AsyncMock()
    app.pipeline_service.copy_pipeline = AsyncMock(return_value={'uuid': 'copied-pipeline-uuid'})

    # Bot service
    app.bot_service = Mock()
    app.bot_service.get_bots = AsyncMock(return_value=[])
    app.bot_service.create_bot = AsyncMock(return_value={'uuid': 'new-bot-uuid'})

    # MCP service (for extensions endpoint)
    app.mcp_service = Mock()
    app.mcp_service.get_mcp_servers = AsyncMock(return_value=[])

    # Plugin connector (for extensions endpoint)
    app.plugin_connector.list_plugins = AsyncMock(return_value=[])

    return app


@pytest.fixture(scope='module')
async def quart_test_client(fake_pipeline_app, http_controller_cls):
    """Create Quart test client (module scope to avoid route re-registration)."""
    controller = http_controller_cls(fake_pipeline_app)
    await controller.initialize()

    client = controller.quart_app.test_client()
    yield client


# ============== PIPELINE ENDPOINT TESTS ==============

@pytest.mark.usefixtures('mock_circular_import_chain')
class TestPipelineMetadataEndpoint:
    """Tests for /api/v1/pipelines/_/metadata endpoint."""

    @pytest.mark.asyncio
    async def test_get_pipeline_metadata_success(self, quart_test_client):
        """GET /api/v1/pipelines/_/metadata returns metadata list."""
        response = await quart_test_client.get(
            '/api/v1/pipelines/_/metadata',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'data' in data
        assert isinstance(data['data'], dict)

    @pytest.mark.asyncio
    async def test_get_pipeline_metadata_requires_auth(self, quart_test_client):
        """Pipeline metadata endpoint requires authentication."""
        response = await quart_test_client.get('/api/v1/pipelines/_/metadata')
        assert response.status_code == 401


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestPipelinesListEndpoint:
    """Tests for /api/v1/pipelines endpoint."""

    @pytest.mark.asyncio
    async def test_get_pipelines_success(self, quart_test_client):
        """GET /api/v1/pipelines returns pipeline list."""
        response = await quart_test_client.get(
            '/api/v1/pipelines',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'data' in data

    @pytest.mark.asyncio
    async def test_get_pipelines_with_sort_param(self, quart_test_client):
        """GET pipelines with sort parameter."""
        response = await quart_test_client.get(
            '/api/v1/pipelines?sort_by=created_at&sort_order=DESC',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestPipelinesCRUDEndpoints:
    """Tests for pipeline CRUD operations."""

    @pytest.mark.asyncio
    async def test_get_single_pipeline_success(self, quart_test_client):
        """GET /api/v1/pipelines/{uuid} returns pipeline."""
        response = await quart_test_client.get(
            '/api/v1/pipelines/test-pipeline-uuid',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'data' in data

    @pytest.mark.asyncio
    async def test_create_pipeline_success(self, quart_test_client):
        """POST /api/v1/pipelines creates new pipeline."""
        response = await quart_test_client.post(
            '/api/v1/pipelines',
            headers={'Authorization': 'Bearer test_token'},
            json={'name': 'New Pipeline', 'config': {}}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'uuid' in data['data']

    @pytest.mark.asyncio
    async def test_update_pipeline_success(self, quart_test_client):
        """PUT /api/v1/pipelines/{uuid} updates pipeline."""
        response = await quart_test_client.put(
            '/api/v1/pipelines/test-pipeline-uuid',
            headers={'Authorization': 'Bearer test_token'},
            json={'name': 'Updated Pipeline'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0

    @pytest.mark.asyncio
    async def test_delete_pipeline_success(self, quart_test_client):
        """DELETE /api/v1/pipelines/{uuid} deletes pipeline."""
        response = await quart_test_client.delete(
            '/api/v1/pipelines/test-pipeline-uuid',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0

    @pytest.mark.asyncio
    async def test_copy_pipeline_success(self, quart_test_client):
        """POST /api/v1/pipelines/{uuid}/copy copies pipeline."""
        response = await quart_test_client.post(
            '/api/v1/pipelines/test-pipeline-uuid/copy',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'uuid' in data['data']


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestPipelineExtensionsEndpoint:
    """Tests for pipeline extensions."""

    @pytest.mark.asyncio
    async def test_get_extensions(self, quart_test_client):
        """GET /api/v1/pipelines/{uuid}/extensions."""
        response = await quart_test_client.get(
            '/api/v1/pipelines/test-pipeline-uuid/extensions',
            headers={'Authorization': 'Bearer test_token'}
        )

        # Should return 200 if pipeline found
        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
