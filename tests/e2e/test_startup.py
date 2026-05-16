"""E2E tests for LangBot startup flow.

Tests the complete startup process including:
- boot.py startup orchestration
- stages/ (build_app, load_config, migrate, etc.)
- database initialization
- API availability

Run: uv run pytest tests/e2e/test_startup.py -v -m e2e
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


class TestStartupFlow:
    """Tests for LangBot startup process."""

    def test_process_is_running(self, langbot_process):
        """Verify LangBot process is running."""
        assert langbot_process.is_running()

    def test_health_check(self, langbot_process, e2e_port):
        """Verify LangBot API is responding."""
        assert langbot_process.health_check()

    def test_system_info_endpoint(self, e2e_client):
        """Test /api/v1/system/info endpoint."""
        response = e2e_client.get('/api/v1/system/info')
        assert response.status_code == 200

        data = response.json()
        assert data['code'] == 0
        assert 'data' in data
        # System info should contain version info
        assert 'version' in data['data'] or 'edition' in data['data']

    def test_database_initialized(self, e2e_db_path):
        """Verify SQLite database was created and initialized."""
        assert e2e_db_path.exists()

        # Database should have some tables after migration
        import sqlite3
        conn = sqlite3.connect(str(e2e_db_path))
        cursor = conn.cursor()

        # Check that core tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        # Core tables should be created by Alembic migrations
        # Note: table names may differ (legacy_pipelines instead of pipelines)
        expected_tables = ['legacy_pipelines', 'bots', 'model_providers', 'llm_models']
        for table in expected_tables:
            assert table in tables, f'Table {table} should exist. Available: {tables}'

        conn.close()

    def test_chroma_directory_created(self, e2e_tmpdir):
        """Verify Chroma vector database directory was created."""
        chroma_path = e2e_tmpdir / 'chroma'
        # Created by the E2E config factory before startup.
        assert chroma_path.exists()

    def test_pipelines_endpoint(self, e2e_client):
        """Test /api/v1/pipelines endpoint (requires auth)."""
        # Without auth, should return 401
        response = e2e_client.get('/api/v1/pipelines')
        assert response.status_code == 401

    def test_auth_endpoint(self, e2e_client, e2e_tmpdir):
        """Test auth endpoint."""
        # First startup may allow initial setup
        response = e2e_client.post('/api/v1/user/auth', json={
            'username': 'admin',
            'password': 'admin',
        })

        # Response could be:
        # - 200 if auth succeeds
        # - 400 if credentials wrong
        # - 401 if user not initialized
        assert response.status_code in [200, 400, 401]


class TestStartupStages:
    """Tests that verify individual startup stages worked correctly."""

    def test_config_loaded(self, e2e_client):
        """Verify config was loaded correctly by checking API port."""
        # If API responds on e2e_port, config was loaded
        assert e2e_client.get('/api/v1/system/info').status_code == 200

    def test_migrations_applied(self, e2e_db_path):
        """Verify database migrations were applied."""
        import sqlite3
        conn = sqlite3.connect(str(e2e_db_path))
        cursor = conn.cursor()

        # Check alembic_version table exists and has version
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version';")
        result = cursor.fetchone()
        assert result is not None, 'alembic_version table should exist'

        cursor.execute('SELECT version_num FROM alembic_version;')
        version = cursor.fetchone()
        assert version is not None, 'Migration version should be set'

        conn.close()

    def test_http_controller_initialized(self, e2e_client):
        """Verify HTTP controller was initialized."""
        # Multiple endpoints should be available
        endpoints = [
            '/api/v1/system/info',
            '/api/v1/pipelines',
            '/api/v1/provider/providers',
            '/api/v1/platform/bots',
        ]

        for endpoint in endpoints:
            response = e2e_client.get(endpoint)
            # Should get a real route response, even if auth is required.
            assert response.status_code in [200, 401, 403], f'{endpoint} should be registered'


class TestMinimalStartupNoLLM:
    """Tests verifying LangBot can start without LLM providers."""

    def test_api_available_without_llm(self, e2e_client):
        """API should be available even without LLM providers configured."""
        response = e2e_client.get('/api/v1/system/info')
        assert response.status_code == 200

    def test_pipeline_metadata_available(self, e2e_client):
        """Pipeline metadata endpoint should work without LLM."""
        # Requires auth, but endpoint should exist
        response = e2e_client.get('/api/v1/pipelines/_/metadata')
        assert response.status_code in [200, 401]  # Not 404 or 500
