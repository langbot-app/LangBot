"""
API integration tests for knowledge base endpoints.

Tests real HTTP API behavior for knowledge base management.

Run: uv run pytest tests/integration/api/test_knowledge.py -q
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
        'langbot.pkg.api.http.controller.groups.knowledge',
        'langbot.pkg.api.http.controller.groups.knowledge.base',
        'langbot.pkg.api.http.controller.groups.knowledge.engines',
        'langbot.pkg.api.http.controller.groups.knowledge.parsers',
        'langbot.pkg.api.http.controller.main',
    ]

    with isolated_sys_modules(
        mocks={
            'langbot.pkg.core.app': mock_app,
            'langbot.pkg.core.entities': mock_entities,
        },
        clear=clear,
    ):
        import langbot.pkg.api.http.controller.groups.knowledge.base as _knowledge  # noqa: E402, F401
        yield


@pytest.fixture(scope='module')
def fake_knowledge_app():
    """Create FakeApp with knowledge services (module scope for reuse)."""
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

    # Knowledge service
    app.knowledge_service = Mock()
    app.knowledge_service.get_knowledge_bases = AsyncMock(return_value=[
        {
            'uuid': 'test-kb-uuid',
            'name': 'Test Knowledge Base',
            'description': 'Test KB description',
            'engine_plugin_id': 'test/engine',
            'created_at': '2024-01-01T00:00:00',
            'updated_at': '2024-01-01T00:00:00',
        }
    ])
    app.knowledge_service.get_knowledge_base = AsyncMock(return_value={
        'uuid': 'test-kb-uuid',
        'name': 'Test Knowledge Base',
        'description': 'Test KB description',
        'engine_plugin_id': 'test/engine',
    })
    app.knowledge_service.create_knowledge_base = AsyncMock(return_value={'uuid': 'new-kb-uuid'})
    app.knowledge_service.update_knowledge_base = AsyncMock(return_value={})
    app.knowledge_service.delete_knowledge_base = AsyncMock()
    app.knowledge_service.get_files_by_knowledge_base = AsyncMock(return_value=[
        {'uuid': 'test-file-uuid', 'filename': 'test.pdf'}
    ])
    app.knowledge_service.store_file = AsyncMock(return_value={'task_id': 'test-task-id'})
    app.knowledge_service.delete_file = AsyncMock()
    app.knowledge_service.retrieve_knowledge_base = AsyncMock(return_value=[
        {'content': 'test result', 'score': 0.95}
    ])

    # RAG manager
    app.rag_mgr = Mock()

    return app


@pytest.fixture(scope='module')
async def quart_test_client(fake_knowledge_app, http_controller_cls):
    """Create Quart test client (module scope to avoid route re-registration)."""
    controller = http_controller_cls(fake_knowledge_app)
    await controller.initialize()

    client = controller.quart_app.test_client()
    yield client


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestKnowledgeBaseEndpoints:
    """Tests for /api/v1/knowledge/bases endpoints."""

    @pytest.mark.asyncio
    async def test_get_knowledge_bases_success(self, quart_test_client):
        """GET /api/v1/knowledge/bases returns knowledge base list."""
        response = await quart_test_client.get(
            '/api/v1/knowledge/bases',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'data' in data
        assert 'bases' in data['data']

    @pytest.mark.asyncio
    async def test_create_knowledge_base_success(self, quart_test_client):
        """POST /api/v1/knowledge/bases creates new knowledge base."""
        response = await quart_test_client.post(
            '/api/v1/knowledge/bases',
            headers={'Authorization': 'Bearer test_token'},
            json={'name': 'New KB', 'engine_plugin_id': 'test/engine'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'uuid' in data['data']

    @pytest.mark.asyncio
    async def test_get_single_knowledge_base_success(self, quart_test_client):
        """GET /api/v1/knowledge/bases/{uuid} returns knowledge base."""
        response = await quart_test_client.get(
            '/api/v1/knowledge/bases/test-kb-uuid',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'base' in data['data']

    @pytest.mark.asyncio
    async def test_update_knowledge_base_success(self, quart_test_client):
        """PUT /api/v1/knowledge/bases/{uuid} updates knowledge base."""
        response = await quart_test_client.put(
            '/api/v1/knowledge/bases/test-kb-uuid',
            headers={'Authorization': 'Bearer test_token'},
            json={'name': 'Updated KB'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0

    @pytest.mark.asyncio
    async def test_delete_knowledge_base_success(self, quart_test_client):
        """DELETE /api/v1/knowledge/bases/{uuid} deletes knowledge base."""
        response = await quart_test_client.delete(
            '/api/v1/knowledge/bases/test-kb-uuid',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestKnowledgeBaseFilesEndpoints:
    """Tests for knowledge base files endpoints."""

    @pytest.mark.asyncio
    async def test_get_files_success(self, quart_test_client):
        """GET /api/v1/knowledge/bases/{uuid}/files returns files."""
        response = await quart_test_client.get(
            '/api/v1/knowledge/bases/test-kb-uuid/files',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'files' in data['data']

    @pytest.mark.asyncio
    async def test_add_file_to_knowledge_base(self, quart_test_client):
        """POST /api/v1/knowledge/bases/{uuid}/files adds file."""
        response = await quart_test_client.post(
            '/api/v1/knowledge/bases/test-kb-uuid/files',
            headers={'Authorization': 'Bearer test_token'},
            json={'file_id': 'test-file-id', 'parser_plugin_id': 'test/parser'}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'task_id' in data['data']

    @pytest.mark.asyncio
    async def test_delete_file_from_knowledge_base(self, quart_test_client):
        """DELETE /api/v1/knowledge/bases/{uuid}/files/{file_id}."""
        response = await quart_test_client.delete(
            '/api/v1/knowledge/bases/test-kb-uuid/files/test-file-uuid',
            headers={'Authorization': 'Bearer test_token'}
        )

        assert response.status_code == 200


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestKnowledgeBaseRetrieveEndpoint:
    """Tests for knowledge base retrieval endpoint."""

    @pytest.mark.asyncio
    async def test_retrieve_knowledge_success(self, quart_test_client):
        """POST /api/v1/knowledge/bases/{uuid}/retrieve."""
        response = await quart_test_client.post(
            '/api/v1/knowledge/bases/test-kb-uuid/retrieve',
            headers={'Authorization': 'Bearer test_token'},
            json={'query': 'test query', 'retrieval_settings': {'top_k': 5}}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert data['code'] == 0
        assert 'results' in data['data']

    @pytest.mark.asyncio
    async def test_retrieve_without_query_returns_error(self, quart_test_client):
        """POST retrieve without query returns 400."""
        response = await quart_test_client.post(
            '/api/v1/knowledge/bases/test-kb-uuid/retrieve',
            headers={'Authorization': 'Bearer test_token'},
            json={}
        )

        assert response.status_code == 400
        data = await response.get_json()
        assert data['code'] == -1
