"""Exercise immutable production images through authenticated HTTP across upgrades."""

import io
import os
from pathlib import Path
import shlex
import subprocess
import time
from types import SimpleNamespace
import uuid
import zipfile

import httpx
import pytest
import yaml

from tests.e2e.test_runner_plugin_runtime import _free_port, _init_and_auth
from tests.e2e.test_skill_persistence_replicas import _data
from tests.e2e.utils.config_factory import create_minimal_config, create_test_directories
from tests.integration.api.test_plugin_permission_lifecycle import package
from tests.integration.skill.test_persistent_skill_replicas import _BINARY, _GUIDE, _NAME, _PNG, _SCRIPT, _zip_package


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.p0_image,
    pytest.mark.skipif(
        not os.environ.get('LANGBOT_IMAGE_CANDIDATE'), reason='explicit immutable candidate image required'
    ),
]


def _docker(*args):
    return subprocess.run(
        [*shlex.split(os.environ.get('LANGBOT_TEST_DOCKER_COMMAND', 'docker')), *args],
        check=True,
        text=True,
        capture_output=True,
        timeout=180,
    ).stdout


def _configuration(root):
    path = create_minimal_config(root, 5300)
    create_test_directories(root)
    config = yaml.safe_load(path.read_text())
    config['api']['host'] = '0.0.0.0'
    config['database']['sqlite']['path'] = '/app/data/langbot.db'
    config['vdb']['chroma']['path'] = '/app/data/chroma'
    config['storage']['local']['path'] = '/app/data/storage'
    config['skills'] = {'root': '/app/data/skills', 'persistence': 'filesystem'}
    config['plugin'].update(enable=False, runtime_ws_url='ws://langbot_plugin_runtime:5400/control/ws')
    config['box']['enabled'] = False
    source = Path(__file__).resolve().parents[2] / 'src/langbot/pkg/platform/sources'
    config['system']['disabled_adapters'] = [
        yaml.safe_load(item.read_text())['metadata']['name']
        for item in source.glob('*.yaml')
        if item.stem != 'websocket'
    ]
    path.write_text(yaml.safe_dump(config))
    return path


@pytest.fixture
def image_instance(tmp_path):
    containers = []
    clients = []
    root = tmp_path / 'instance'
    root.mkdir()
    evidence = Path(__file__).resolve().parents[2] / '.qa/image-upgrade' / uuid.uuid4().hex
    evidence.mkdir(parents=True)
    network = 'langbot-p0-' + uuid.uuid4().hex
    _docker('network', 'create', network)

    def start(image, phase):
        name = 'langbot-p0-' + uuid.uuid4().hex
        runtime = name + '-runtime'
        port = _free_port()
        runtime_mounts = []
        for directory in ('plugins', 'plugin-runtime'):
            source = root / 'data' / directory
            source.mkdir(parents=True, exist_ok=True)
            runtime_mounts.extend(['--mount', f'type=bind,source={source},target=/app/data/{directory}'])
        _docker(
            'run',
            '-d',
            '--name',
            runtime,
            '--network',
            network,
            '--network-alias',
            'langbot_plugin_runtime',
            *runtime_mounts,
            '--entrypoint',
            '/app/.venv/bin/python',
            image,
            '-m',
            'langbot_plugin.cli.__init__',
            'rt',
        )
        containers.append((runtime, phase + '-runtime'))
        _docker(
            'run',
            '-d',
            '--name',
            name,
            '--network',
            network,
            '-p',
            f'127.0.0.1:{port}:5300',
            '--mount',
            f'type=bind,source={root / "data"},target=/app/data',
            '-e',
            'SPACE__DISABLE_TELEMETRY=true',
            '-e',
            'SPACE__DISABLE_MODELS_SERVICE=true',
            '-e',
            'LANGBOT_PLUGIN_FILE_STORAGE_DIR=/app/data/plugin-runtime',
            image,
        )
        containers.append((name, phase))
        client = httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=120, trust_env=False)
        clients.append(client)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                if client.get('/api/v1/system/info', timeout=2).status_code == 200:
                    return SimpleNamespace(name=name, runtime=runtime, client=client)
            except httpx.TransportError:
                pass
            if _docker('inspect', name, '--format', '{{.State.Running}}').strip() != 'true':
                pytest.fail(_docker('logs', name)[-12000:])
            time.sleep(0.5)
        pytest.fail('Image startup timed out: ' + _docker('logs', name)[-12000:])

    def stop(instance):
        instance.client.close()
        _docker('stop', '-t', '15', instance.name)
        _docker('stop', '-t', '15', instance.runtime)

    try:
        yield SimpleNamespace(root=root, start=start, stop=stop)
    finally:
        for client in clients:
            client.close()
        for name, phase in containers:
            try:
                logs = subprocess.run(
                    [*shlex.split(os.environ.get('LANGBOT_TEST_DOCKER_COMMAND', 'docker')), 'logs', name],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                (evidence / f'container-{phase}.log').write_text(logs.stdout + logs.stderr)
            finally:
                _docker('rm', '-f', name)
        _docker('network', 'rm', network)


def _plugin_call(client, headers, *, wait_ready=False):
    deadline = time.monotonic() + (45 if wait_ready else 0)
    while True:
        response = client.post(
            '/api/v1/plugins/permissionse2e/image-probe/page-api',
            headers=headers,
            json={'page_id': 'probe', 'endpoint': '/probe', 'method': 'POST', 'body': {'operation': 'stats.basic'}},
        )
        # Permission confirmation starts the worker asynchronously, as in the lifecycle suite.
        if response.status_code != 400 or response.json().get('msg') != 'Plugin not found':
            break
        if time.monotonic() >= deadline:
            break
        time.sleep(0.5)
    assert response.status_code == 200, response.text
    return response.json()['data']


def _seed_content(client):
    token = _init_and_auth(client)
    headers = {'Authorization': 'Bearer ' + token}
    first = _data(
        client.post(
            '/api/v1/skills/install/upload',
            headers=headers,
            files={'file': ('probe.zip', _zip_package(), 'application/zip')},
        )
    )['skills'][0]
    second = _data(
        client.put(
            f'/api/v1/skills/{_NAME}',
            headers=headers,
            json={
                'base_revision': first['revision'],
                'instructions': 'Updated image instructions.',
            },
        )
    )['skill']
    assert second['revision'] != first['revision']
    removed = _data(
        client.post(
            '/api/v1/skills',
            headers=headers,
            json={'name': 'image-removed', 'instructions': 'Retained deleted image history.'},
        )
    )['skill']
    _data(client.delete('/api/v1/skills/image-removed', headers=headers))
    uploaded = _data(
        client.post('/api/v1/files/images', headers=headers, files={'file': ('pixel.png', _PNG, 'image/png')})
    )
    return dict(
        token=token,
        first=first,
        second=second,
        removed=removed,
        image_url='/api/v1/files/image/' + uploaded['file_key'],
    )


def _verify_content(client, saved):
    headers = {'Authorization': 'Bearer ' + saved['token']}
    current = _data(client.get(f'/api/v1/skills/{_NAME}', headers=headers))['skill']
    assert current['revision'] == saved['second']['revision']
    assert current['created_at'] == saved['first']['created_at']
    listed = _data(client.get('/api/v1/skills', headers=headers))['skills']
    assert 'image-removed' not in {row['name'] for row in listed}
    # The previous release has no package-download route; expected bytes come from the original input.
    for skill in (saved['first'], saved['second'], saved['removed']):
        downloaded = client.get(
            f'/api/v1/skills/{skill["name"]}/package', headers=headers, params={'revision': skill['revision']}
        )
        assert downloaded.status_code == 200, downloaded.text
        with zipfile.ZipFile(io.BytesIO(downloaded.content)) as archive:
            if skill['name'] == _NAME:
                assert archive.read('scripts/probe.py') == _SCRIPT
                assert archive.read('references/payload.bin') == _BINARY
                assert archive.read('references/guide.md').decode() == _GUIDE
            if skill['revision'] == saved['second']['revision']:
                assert 'Updated image instructions.' in archive.read('SKILL.md').decode()
            if skill['revision'] == saved['first']['revision']:
                assert 'Read references/guide.md.' in archive.read('SKILL.md').decode()
            if skill['name'] == 'image-removed':
                assert 'Retained deleted image history.' in archive.read('SKILL.md').decode()
    downloaded = client.get(saved['image_url'], headers=headers)
    assert downloaded.status_code == 200 and downloaded.content == _PNG
    assert client.get(saved['image_url']).status_code == 401


@pytest.mark.contract('legacy_image_upgrade')
def test_image_upgrade_preserves_content_and_plugin_grants(image_instance, tmp_path):
    image = image_instance
    previous = os.environ.get('LANGBOT_IMAGE_PREVIOUS')
    assert previous, 'The upgrade test requires an explicit previous image'
    config_path = _configuration(image.root)
    old = image.start(previous, 'previous')
    saved = _seed_content(old.client)
    image.stop(old)

    config = yaml.safe_load(config_path.read_text())
    config['storage'].update(use='persistent', content={'backend': 'database'}, migration={'require_source': True})
    config['skills'].update(persistence='database', migration={'require_source': True})
    config['box']['file_transfer_mode'] = 'network'
    config['box']['workspace_mode'] = 'private'
    config['plugin']['enable'] = True
    config_path.write_text(yaml.safe_dump(config))
    current = image.start(os.environ['LANGBOT_IMAGE_CANDIDATE'], 'candidate')
    _verify_content(current.client, saved)
    headers = {'Authorization': 'Bearer ' + saved['token']}
    archive = tmp_path / 'image-probe.zip'
    package(archive, 'image-probe', '0.1.0', ['stats.basic'])
    with archive.open('rb') as stream:
        installed = _data(
            current.client.post(
                '/api/v1/plugins/install/local',
                headers=headers,
                files={'file': (archive.name, stream, 'application/zip')},
            )
        )
    deadline = time.monotonic() + 120
    while True:
        task = _data(current.client.get(f'/api/v1/system/tasks/{installed["task_id"]}', headers=headers))
        if task['runtime']['done']:
            assert task['runtime']['exception'] is None, task
            break
        assert time.monotonic() < deadline, task
        time.sleep(0.2)
    permissions = '/api/v1/plugins/permissionse2e/image-probe/permissions'
    granted = _data(
        current.client.put(
            permissions,
            headers=headers,
            json={'workspace_operations': ['stats.basic'], 'capabilities': [], 'confirm': True},
        )
    )
    assert granted['enabled']
    assert _plugin_call(current.client, headers, wait_ready=True)['ok'] is True
    image.stop(current)

    # Remove the legacy source paths: reads must come from the migrated database.
    for name in ('storage', 'skills'):
        (image.root / 'data' / name).rename(image.root / 'data' / ('retained-' + name))
    replacement = image.start(os.environ['LANGBOT_IMAGE_CANDIDATE'], 'replacement')
    _verify_content(replacement.client, saved)
    assert _data(replacement.client.get(permissions, headers=headers)) == granted
    assert _plugin_call(replacement.client, headers, wait_ready=True)['ok'] is True
    _data(
        replacement.client.put(
            permissions, headers=headers, json={'workspace_operations': [], 'capabilities': [], 'confirm': False}
        )
    )
    assert _plugin_call(replacement.client, headers)['ok'] is False


@pytest.mark.contract('image_fresh_defaults')
def test_candidate_image_fresh_template_defaults(image_instance):
    image = image_instance
    (image.root / 'data').mkdir()
    candidate = image.start(os.environ['LANGBOT_IMAGE_CANDIDATE'], 'fresh')
    config = yaml.safe_load((image.root / 'data/config.yaml').read_text())
    assert config['storage']['use'] == 'persistent'
    assert config['skills']['persistence'] == 'database'
    assert config['box']['file_transfer_mode'] == 'network'
    assert candidate.client.get('/api/v1/system/info').status_code == 200
