"""Upgrade a real older Core against a disposable PostgreSQL database.

Set LANGBOT_UPGRADE_OLD_SOURCE, LANGBOT_UPGRADE_OLD_PYTHON and
LANGBOT_UPGRADE_POSTGRES_URL explicitly. The old interpreter must use its own SDK.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import uuid
import zipfile

import httpx
import pytest
import yaml
import xxhash

from tests.e2e.test_runner_plugin_runtime import _free_port, _init_and_auth
from tests.e2e.test_skill_persistence_replicas import _data, _start, _stop
from tests.e2e.utils.config_factory import create_minimal_config, create_test_directories
from tests.e2e.utils.process_manager import LangBotProcess, find_project_root
from tests.integration.skill.test_persistent_skill_replicas import _PNG


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not all(os.environ.get('LANGBOT_UPGRADE_' + key) for key in ('OLD_SOURCE', 'OLD_PYTHON', 'POSTGRES_URL')),
        reason='explicit older Core/interpreter and disposable upgrade database required',
    ),
]


def _clear_content_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith(('SKILLS__', 'STORAGE__', 'BOX__')) or key in (
            'SYSTEM__INSTANCE_ID',
            'DATABASE__USE',
            'DATABASE__POSTGRESQL__URL',
            'PLUGIN__ENABLE',
        ):
            monkeypatch.delenv(key, raising=False)


def test_old_core_upgrade_preserves_versions_assets_and_survives_source_removal(tmp_path, monkeypatch):
    _clear_content_env(monkeypatch)
    old_source = Path(os.environ['LANGBOT_UPGRADE_OLD_SOURCE']).resolve()
    old_python = Path(os.environ['LANGBOT_UPGRADE_OLD_PYTHON']).absolute()
    assert (old_source / 'src/langbot').is_dir() and old_python.is_file()
    project = find_project_root()
    root = tmp_path / 'upgrade'
    root.mkdir()
    port = _free_port()
    path = create_minimal_config(root, port)
    create_test_directories(root)
    config = yaml.safe_load(path.read_text())
    config['system'].update(
        instance_id='upgrade-' + uuid.uuid4().hex,
        disabled_adapters=[
            yaml.safe_load(item.read_text())['metadata']['name']
            for item in (project / 'src/langbot/pkg/platform/sources').glob('*.yaml')
            if item.stem != 'websocket'
        ],
    )
    config['api']['host'] = '127.0.0.1'
    config['database'] = {'use': 'postgresql', 'postgresql': {'url': os.environ['LANGBOT_UPGRADE_POSTGRES_URL']}}
    config['plugin']['enable'] = False
    config['box'] = {'enabled': False, 'file_transfer_mode': 'legacy'}
    source = root / 'legacy-skills'
    source.mkdir()
    config['skills'] = {'persistence': 'filesystem', 'root': str(source)}
    config['storage']['use'] = 'local'
    path.write_text(yaml.safe_dump(config))
    path.chmod(0o600)
    media_name = xxhash.xxh3_128_hexdigest(_PNG) + '.png'
    media = root / 'data/storage/media_cache' / media_name
    media.parent.mkdir(parents=True, exist_ok=True)
    media.write_bytes(_PNG)
    media_url = '/api/v1/files/media/' + media_name
    environment = {'LANGBOT_DATA_ROOT': str(root / 'data'), 'LANGBOT_PLUGIN_FILE_STORAGE_DIR': str(root / 'rpc')}
    old = LangBotProcess(old_source, root, port=port, collect_coverage=False, env_overrides=environment)
    current = LangBotProcess(project, root, port=port, collect_coverage=False, env_overrides=environment)
    replica = None
    try:
        with patch('tests.e2e.utils.process_manager.sys.executable', str(old_python)):
            _start(SimpleNamespace(root=root, process=old))
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=30, trust_env=False) as client:
            token = _init_and_auth(client)
            headers = {'Authorization': 'Bearer ' + token}
            first = _data(
                client.post('/api/v1/skills', headers=headers, json={'name': 'history', 'instructions': 'version one'})
            )['skill']
            second = _data(
                client.put(
                    '/api/v1/skills/history',
                    headers=headers,
                    json={
                        'instructions': 'version two',
                        'base_revision': first['revision'],
                    },
                )
            )['skill']
            removed = _data(
                client.post(
                    '/api/v1/skills', headers=headers, json={'name': 'removed', 'instructions': 'retained deleted'}
                )
            )['skill']
            _data(client.delete('/api/v1/skills/removed', headers=headers))
            versions = [(item['name'], item['revision']) for item in (first, second, removed)]
            packages = {}
            for name, revision in versions:
                response = client.get(f'/api/v1/skills/{name}/package', headers=headers, params={'revision': revision})
                assert response.status_code == 200, response.text
                packages[name, revision] = response.content
            uploaded = _data(
                client.post('/api/v1/files/images', headers=headers, files={'file': ('pixel.png', _PNG, 'image/png')})
            )
            image_url = '/api/v1/files/image/' + uploaded['file_key']
            assert client.get(image_url, headers=headers).content == _PNG
            assert client.get(media_url).content == _PNG
        assert len(list(source.glob('tenants/*/.langbot-skill-store/registry/history.json'))) == 1
        assert len(list(source.glob('tenants/*/.langbot-skill-store/revisions/*/manifest.json'))) == 3
        _stop(old)

        config = yaml.safe_load(path.read_text())
        config['skills'].update(persistence='database', migration={'require_source': True})
        config['storage'].update(use='persistent', migration={'require_source': True}, content={'backend': 'database'})
        config['box']['file_transfer_mode'] = 'network'
        config['box']['workspace_mode'] = 'private'
        path.write_text(yaml.safe_dump(config))
        _start(SimpleNamespace(root=root, process=current))

        def verify(client):
            skills = _data(client.get('/api/v1/skills', headers=headers))['skills']
            assert [(item['name'], item['revision']) for item in skills] == [('history', second['revision'])]
            assert skills[0]['created_at'] == first['created_at']
            for identity, expected in packages.items():
                name, revision = identity
                response = client.get(f'/api/v1/skills/{name}/package', headers=headers, params={'revision': revision})
                assert response.status_code == 200, response.text
                assert response.content == expected
                with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                    assert archive.read('SKILL.md')
            assert client.get(image_url, headers=headers).content == _PNG
            assert client.get(image_url).status_code == 401
            assert client.get(media_url).content == _PNG
            assert client.get('/api/v1/files/media/' + uploaded['file_key'].rsplit('/', 1)[-1]).status_code == 404

        with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=30, trust_env=False) as client:
            verify(client)
        _stop(current)
        source.rename(root / 'retained-skills')
        (root / 'data/storage').rename(root / 'retained-storage')
        _start(SimpleNamespace(root=root, process=current))
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=30, trust_env=False) as client:
            verify(client)
        assert not (source / '.database-cache').exists()

        # A second Core joins from the database without either old volume.
        replica_root = tmp_path / 'replica'
        replica_root.mkdir()
        replica_port = _free_port()
        replica_path = create_minimal_config(replica_root, replica_port)
        create_test_directories(replica_root)
        config['skills']['root'] = str(replica_root / 'absent-skills')
        config['api']['port'] = replica_port
        replica_path.write_text(yaml.safe_dump(config))
        replica = LangBotProcess(
            project,
            replica_root,
            port=replica_port,
            collect_coverage=False,
            env_overrides={
                'LANGBOT_DATA_ROOT': str(replica_root / 'data'),
                'LANGBOT_PLUGIN_FILE_STORAGE_DIR': str(replica_root / 'rpc'),
            },
        )
        _start(SimpleNamespace(root=replica_root, process=replica))
        with httpx.Client(base_url=f'http://127.0.0.1:{replica_port}', timeout=30, trust_env=False) as client:
            verify(client)
    finally:
        for process in (replica, current, old):
            if process is not None:
                _stop(process)


def test_fresh_template_selects_database_and_network_defaults(tmp_path, monkeypatch):
    url = os.environ.get('LANGBOT_FRESH_POSTGRES_URL')
    if not url:
        pytest.skip('LANGBOT_FRESH_POSTGRES_URL must identify a fresh task-owned database')
    _clear_content_env(monkeypatch)
    project = find_project_root()
    disabled = [
        yaml.safe_load(item.read_text())['metadata']['name']
        for item in (project / 'src/langbot/pkg/platform/sources').glob('*.yaml')
        if item.stem != 'websocket'
    ]
    port = _free_port()
    environment = {
        'LANGBOT_DATA_ROOT': str(tmp_path / 'data'),
        'LANGBOT_PLUGIN_FILE_STORAGE_DIR': str(tmp_path / 'rpc'),
        'DATABASE__USE': 'postgresql',
        'DATABASE__POSTGRESQL__URL': url,
        'SYSTEM__INSTANCE_ID': 'fresh-' + uuid.uuid4().hex,
        'SYSTEM__DISABLED_ADAPTERS': ','.join(disabled),
        'PLUGIN__ENABLE': 'false',
        'BOX__ENABLED': 'false',
        'VDB__USE': 'chroma',
        'VDB__CHROMA__PATH': str(tmp_path / 'chroma'),
        'API__HOST': '127.0.0.1',
    }
    process = LangBotProcess(project, tmp_path, port=port, collect_coverage=False, env_overrides=environment)
    try:
        _start(SimpleNamespace(root=tmp_path, process=process))
        config = yaml.safe_load((tmp_path / 'data/config.yaml').read_text())
        assert config['skills']['persistence'] == 'database'
        assert config['storage']['use'] == 'persistent'
        assert config['storage']['content']['backend'] == 'database'
        assert config['box']['file_transfer_mode'] == 'network'
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=30, trust_env=False) as client:
            headers = {'Authorization': 'Bearer ' + _init_and_auth(client)}
            skill = _data(
                client.post(
                    '/api/v1/skills',
                    headers=headers,
                    json={'name': 'fresh', 'instructions': 'Fresh database publication.'},
                )
            )['skill']
            assert 'package_root' not in skill
        assert not list((tmp_path / 'data/skills').glob('**/registry/*.json'))
    finally:
        _stop(process)
