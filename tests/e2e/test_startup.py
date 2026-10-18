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


@pytest.fixture(scope='session')
def e2e_tmpdir(tmp_path_factory):
    # Initial registration is global; keep this module independent of other E2E accounts.
    return tmp_path_factory.mktemp('langbot_startup')


@pytest.fixture(scope='session')
def e2e_port():
    import socket

    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


@pytest.fixture(scope='session')
def langbot_process(e2e_tmpdir, e2e_port):
    from tests.e2e.utils.config_factory import create_minimal_config, create_test_directories
    from tests.e2e.utils.process_manager import LangBotProcess, find_project_root

    create_minimal_config(e2e_tmpdir, port=e2e_port)
    create_test_directories(e2e_tmpdir)
    process = LangBotProcess(
        project_root=find_project_root(),
        work_dir=e2e_tmpdir,
        port=e2e_port,
        timeout=180,
        collect_coverage=True,
    )
    try:
        assert process.start(), process.get_logs()
        yield process
    finally:
        process.stop()
        coverage_file = process.get_coverage_file()
        if coverage_file is not None and coverage_file.exists():
            import shutil

            shutil.copy(coverage_file, find_project_root() / '.coverage.e2e.startup')


@pytest.fixture(scope='session')
def e2e_db_path(e2e_tmpdir):
    return e2e_tmpdir / 'data/langbot.db'


@pytest.fixture
def startup_credentials(e2e_client):
    credentials = {'user': 'startup-e2e@example.com', 'password': 'startup-local-test-password'}
    state = e2e_client.get('/api/v1/user/init')
    assert state.status_code == 200
    if not state.json()['data']['initialized']:
        response = e2e_client.post('/api/v1/user/init', json=credentials)
        assert response.status_code == 200, response.text
        assert response.json()['code'] == 0
    return credentials


@pytest.fixture
def startup_headers(e2e_client, startup_credentials):
    response = e2e_client.post('/api/v1/user/auth', json=startup_credentials)
    assert response.status_code == 200, response.text
    headers = {'Authorization': f'Bearer {response.json()["data"]["token"]}'}
    bootstrap = e2e_client.get('/api/v1/workspaces/bootstrap', headers=headers)
    assert bootstrap.status_code == 200, bootstrap.text
    headers['X-Workspace-Id'] = bootstrap.json()['data']['workspaces'][0]['workspace']['uuid']
    return headers


class TestStartupFlow:
    """Tests for LangBot startup process."""

    def test_process_is_running(self, langbot_process):
        """Verify LangBot process is running."""
        assert langbot_process.is_running()

    def test_health_check(self, langbot_process, e2e_port):
        """Verify LangBot API is responding."""
        assert langbot_process.health_check()

    def test_health_check_exposes_bounded_blocking_executor(self, e2e_client):
        """The production startup path installs blocking-work admission."""
        response = e2e_client.get('/healthz')

        assert response.status_code == 200
        executor = response.json()['resources']['blocking_executor']
        assert executor['max_workers'] == 8
        assert executor['max_pending'] == 128
        assert executor['max_inflight_per_scope'] == 4
        assert executor['inflight'] >= 0
        assert executor['rejected_total'] >= 0
        event_loop = response.json()['resources']['event_loop']
        assert event_loop['running'] is True
        assert event_loop['recent_max_lag_ms'] >= 0

    def test_system_info_endpoint(self, e2e_client):
        """Test /api/v1/system/info endpoint."""
        response = e2e_client.get('/api/v1/system/info')
        assert response.status_code == 200

        data = response.json()
        assert data['code'] == 0
        assert 'data' in data
        # System info should contain version info
        assert 'version' in data['data'] or 'edition' in data['data']

    def test_database_initialized(self, langbot_process, e2e_db_path):
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

    def test_auth_endpoint(self, e2e_client, startup_credentials):
        """A controlled local account can sign in and use its token."""
        response = e2e_client.post('/api/v1/user/auth', json=startup_credentials)
        assert response.status_code == 200, response.text
        assert response.json()['code'] == 0
        token = response.json()['data']['token']
        assert isinstance(token, str) and token
        bootstrap = e2e_client.get('/api/v1/workspaces/bootstrap', headers={'Authorization': f'Bearer {token}'})
        assert bootstrap.status_code == 200, bootstrap.text
        assert bootstrap.json()['data']['workspaces'][0]['membership']['role'] == 'owner'

        rejected = e2e_client.post('/api/v1/user/auth', json={**startup_credentials, 'password': 'wrong-password'})
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()['code'] == 1
        assert rejected.json().get('data', {}).get('token') is None


class TestStartupStages:
    """Tests that verify individual startup stages worked correctly."""

    def test_config_loaded(self, e2e_client):
        """Verify config was loaded correctly by checking API port."""
        # If API responds on e2e_port, config was loaded
        assert e2e_client.get('/api/v1/system/info').status_code == 200

    def test_migrations_applied(self, langbot_process, e2e_db_path):
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
        from pathlib import Path

        from alembic.script import ScriptDirectory

        migrations = Path(__file__).parents[2] / 'src/langbot/pkg/persistence/alembic'
        assert version == (ScriptDirectory(str(migrations)).get_current_head(),)

        conn.close()

    def test_http_controller_initialized(self, e2e_client, startup_headers):
        """Authenticated business endpoints return their documented collections."""
        info = e2e_client.get('/api/v1/system/info', headers=startup_headers)
        assert info.status_code == 200
        assert isinstance(info.json()['data']['version'], str)

        for endpoint, key in [
            ('/api/v1/pipelines', 'pipelines'),
            ('/api/v1/provider/providers', 'providers'),
            ('/api/v1/platform/bots', 'bots'),
        ]:
            response = e2e_client.get(endpoint, headers=startup_headers)
            assert response.status_code == 200, (endpoint, response.text)
            payload = response.json()
            assert payload['code'] == 0
            assert isinstance(payload['data'][key], list)
            if key == 'providers':
                assert [(item['name'], item['requester'], item['api_keys']) for item in payload['data'][key]] == [
                    ('LangBot Models', 'space-chat-completions', [])
                ]
            else:
                assert payload['data'][key] == []


class TestMinimalStartupNoLLM:
    """Tests verifying LangBot can start without LLM providers."""

    def test_api_available_without_llm(self, e2e_client):
        """API should be available even without LLM providers configured."""
        response = e2e_client.get('/api/v1/system/info')
        assert response.status_code == 200

    def test_pipeline_metadata_available(self, e2e_client, startup_headers):
        """All pipeline configuration groups remain readable without an LLM."""
        response = e2e_client.get('/api/v1/pipelines/_/metadata', headers=startup_headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload['code'] == 0
        configs = payload['data']['configs']
        assert [config['name'] for config in configs] == ['trigger', 'safety', 'ai', 'output']
        ai = configs[2]
        runner = next(stage for stage in ai['stages'] if stage['name'] == 'runner')
        assert any(item['name'] == 'id' for item in runner['config'])
