"""Opt-in two-process Skill persistence acceptance against a disposable PG DB.

Set LANGBOT_PERSISTENCE_CORE_E2E=1 and LANGBOT_PERSISTENCE_CORE_POSTGRES_URL
(postgresql+asyncpg URL for a fresh, task-owned database). Install the in-tree
SDK in the Python environment used by pytest and its Core subprocesses.
"""

from __future__ import annotations

import json
import os
import shutil
from types import SimpleNamespace
import uuid

import httpx
import pytest
import yaml

from tests.e2e.test_runner_plugin_runtime import _free_port, _init_and_auth
from tests.e2e.utils.config_factory import create_minimal_config, create_test_directories
from tests.e2e.utils.process_manager import LangBotProcess, find_project_root
from tests.integration.skill.test_persistent_skill_replicas import (
    _NAME,
    _PNG,
    _SCRIPT,
    _assert_package,
    _discard_cache,
    _zip_package,
)

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skill_persistence,
    pytest.mark.contract('two_core_cache_recovery'),
    pytest.mark.skipif(os.environ.get('LANGBOT_PERSISTENCE_CORE_E2E') != '1', reason='explicit two-Core acceptance'),
]


def _data(response):
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['code'] == 0, payload
    return payload['data']


def _stop(process):
    if process.is_running():
        process.stop()
    elif process.process is not None:
        process.process.wait(timeout=5)
        process.process = None
        for stream in (process._stdout_file, process._stderr_file):
            if stream:
                stream.close()
        process._stdout_file = process._stderr_file = None


def _start(replica):
    if not replica.process.start():
        stdout, stderr = replica.process.get_logs()
        pytest.fail(f'{replica.root.name} failed to start\nstdout:\n{stdout[-16000:]}\nstderr:\n{stderr[-16000:]}')
    print(
        json.dumps(
            {
                'event': 'core_started',
                'core': replica.root.name,
                'pid': replica.process.process.pid,
                'port': replica.process.port,
            }
        ),
        flush=True,
    )


@pytest.fixture
def core_pair_configure():
    return lambda root, config: []


@pytest.fixture
def core_pair(tmp_path, monkeypatch, core_pair_configure):
    url = os.environ.get('LANGBOT_PERSISTENCE_CORE_POSTGRES_URL')
    if not url:
        pytest.skip('LANGBOT_PERSISTENCE_CORE_POSTGRES_URL must identify a fresh task-owned PostgreSQL database')
    for name in ('SYSTEM__INSTANCE_ID', 'SYSTEM__JWT__SECRET', 'DATABASE__USE', 'DATABASE__POSTGRESQL__URL'):
        monkeypatch.delenv(name, raising=False)
    instance = 'skill-core-processes-' + uuid.uuid4().hex
    secret = uuid.uuid4().hex
    project = find_project_root()
    adapters = project / 'src/langbot/pkg/platform/sources'
    disabled = [
        yaml.safe_load(path.read_text())['metadata']['name']
        for path in adapters.glob('*.yaml')
        if path.stem != 'websocket'
    ]
    created = []

    def create(name):
        root = tmp_path / name
        root.mkdir()
        port = _free_port()
        assert all(replica.process.port != port for replica in created)
        path = create_minimal_config(root, port=port)
        create_test_directories(root)
        config = yaml.safe_load(path.read_text())
        config['api']['host'] = '127.0.0.1'
        config['system'].update(instance_id=instance, disabled_adapters=disabled)
        config['system']['jwt']['secret'] = secret
        config['database'] = {
            'use': 'postgresql',
            'postgresql': {
                'url': url,
                'pool_size': 2,
                'max_overflow': 1,
            },
        }
        config['plugin']['enable'] = False
        config['box']['enabled'] = False
        config['skills'] = {'persistence': 'database', 'root': str(root / 'skills')}
        config['storage'].update(use='persistent', content={'backend': 'database'})
        cli_args = core_pair_configure(root, config)
        path.write_text(yaml.safe_dump(config), encoding='utf-8')
        path.chmod(0o600)
        replica = SimpleNamespace(
            root=root,
            process=LangBotProcess(
                project,
                root,
                port=port,
                timeout=180,
                collect_coverage=False,
                cli_args=cli_args,
                env_overrides={'LANGBOT_PLUGIN_FILE_STORAGE_DIR': str(root / 'rpc-transfers')},
            ),
            client=httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=30, trust_env=False),
        )
        created.append(replica)
        return replica

    try:
        a = create('core-a')
        _start(a)
        token = _init_and_auth(a.client)
        b = create('core-b')
        _start(b)
        assert a.process.process.pid != b.process.process.pid
        yield SimpleNamespace(a=a, b=b, token=token, instance=instance)
    finally:
        for replica in reversed(created):
            replica.client.close()
            _stop(replica.process)


def _exercise_core_pair(core_pair):
    a, b = core_pair.a, core_pair.b
    headers = {'Authorization': f'Bearer {core_pair.token}'}
    workspaces = [
        _data(replica.client.get('/api/v1/workspaces/current', headers=headers))['workspace'] for replica in (a, b)
    ]
    assert workspaces[0] == workspaces[1]
    assert workspaces[0]['instance_uuid'] == core_pair.instance
    installed = _data(
        a.client.post(
            '/api/v1/skills/install/upload',
            headers=headers,
            files={'file': ('probe.zip', _zip_package(), 'application/zip')},
        )
    )
    original = installed['skills'][0]['revision']
    old_url = f'/api/v1/skills/{_NAME}/package?revision={original}'
    old_package = b.client.get(old_url, headers=headers)
    assert old_package.status_code == 200
    _assert_package(old_package.content)
    uploaded = _data(
        a.client.post('/api/v1/files/images', headers=headers, files={'file': ('pixel.png', _PNG, 'image/png')})
    )
    image_url = '/api/v1/files/image/' + uploaded['file_key']
    image = b.client.get(image_url, headers=headers)
    assert image.status_code == 200 and image.content == _PNG

    updated = _data(
        a.client.put(
            f'/api/v1/skills/{_NAME}',
            headers=headers,
            json={'base_revision': original, 'description': 'Published through a real Core process'},
        )
    )['skill']
    current = updated['revision']
    assert current != original
    new_url = f'/api/v1/skills/{_NAME}/package?revision={current}'
    new_package = b.client.get(new_url, headers=headers)
    assert new_package.status_code == 200 and new_package.content != old_package.content
    _assert_package(new_package.content)
    for replica in (a, b):
        skill = _data(replica.client.get(f'/api/v1/skills/{_NAME}', headers=headers))['skill']
        assert skill['revision'] == current and skill['metadata']['released'] == '2024-01-02'
        assert 'package_root' not in skill
        assert not (replica.root / 'skills/.database-cache').exists()
        assert replica.client.get(old_url, headers=headers).content == old_package.content

    script_url = f'/api/v1/skills/{_NAME}/files/scripts/probe.py'
    script = _data(a.client.get(script_url, headers=headers))
    assert script['content'].encode() == _SCRIPT
    assert (a.root / 'skills/.database-cache').is_dir()
    assert not (b.root / 'skills/.database-cache').exists()

    _stop(a.process)
    assert not a.process.is_running() and b.process.is_running()
    _discard_cache(a)
    for filename in ('langbot.stdout.log', 'langbot.stderr.log'):
        shutil.copyfile(a.root / filename, a.root / ('before-restart-' + filename))
    _start(a)
    assert not (a.root / 'skills/.database-cache').exists(), 'Startup must load metadata without materializing packages'
    for replica in (a, b):
        assert replica.client.get(old_url, headers=headers).content == old_package.content
        assert replica.client.get(new_url, headers=headers).content == new_package.content
        assert replica.client.get(image_url, headers=headers).content == _PNG
    assert not (a.root / 'skills/.database-cache').exists(), 'Package download must read durable bytes directly'
    script = _data(a.client.get(script_url, headers=headers))
    assert script['content'].encode() == _SCRIPT
    assert (a.root / 'skills/.database-cache').is_dir()
    assert not (b.root / 'skills/.database-cache').exists()
    print(
        json.dumps(
            {
                'event': 'two_core_persistence_verified',
                'old_revision': original,
                'current_revision': current,
                'image_bytes': len(_PNG),
            }
        ),
        flush=True,
    )


def test_two_core_processes_share_skill_packages_and_uploaded_media(core_pair):
    try:
        _exercise_core_pair(core_pair)
    except Exception:
        for replica in (core_pair.a, core_pair.b):
            for filename in ('langbot.stdout.log', 'langbot.stderr.log'):
                path = replica.root / filename
                if path.exists():
                    print(f'{path}:\n{path.read_text(errors="replace")[-16000:]}', flush=True)
        raise
