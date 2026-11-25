"""Seed and verify real deployed Core instances across externally managed restarts.

Set LANGBOT_DEPLOY_E2E_URL, LANGBOT_DEPLOY_E2E_STATE (a private task JSON file),
and LANGBOT_DEPLOY_E2E_PHASE=seed|verify. Seed content on the old deployment
with ``-k test_content``; seed the Runner only after upgrading to the new deployment.
The verification phase never installs plugins or recreates missing content.
"""

from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from types import SimpleNamespace
import zipfile

import httpx
import pytest

from tests.e2e.test_network_file_plugin_runtime import _turn
from tests.e2e.test_runner_plugin_runtime import QA_RUNNER_ID, _ensure_qa_plugin, _init_and_auth, _wait_for_qa_runner
from tests.e2e.test_skill_network_runtime import _TOOLS, _assert_probe, _create_agent_bot, _probe, _write_skill_runner
from tests.e2e.test_skill_persistence_replicas import _data
from tests.integration.skill.test_persistent_skill_replicas import _NAME, _PNG, _zip_package


pytestmark = pytest.mark.e2e
_PERMISSIONS = '/api/v1/plugins/e2e/agent-runner-qa/permissions'


@pytest.fixture
def deployment():
    values = {key: os.environ.get('LANGBOT_DEPLOY_E2E_' + key) for key in ('URL', 'STATE', 'PHASE')}
    if not all(values.values()):
        pytest.skip('Explicit deployed Core URL, private state file and seed/verify phase are required')
    assert values['PHASE'] in {'seed', 'verify'}, 'LANGBOT_DEPLOY_E2E_PHASE must be seed or verify'
    path = Path(values['STATE'])
    try:
        info = path.lstat()
    except FileNotFoundError:
        assert values['PHASE'] == 'seed', 'Seed state is required before verification'
        state = {}
    else:
        assert stat.S_ISREG(info.st_mode), 'Deployment state must be a regular file'
        assert stat.S_IMODE(info.st_mode) == 0o600, 'Deployment state must have mode 0600'
        state = json.loads(path.read_text())
        assert isinstance(state, dict)
    with httpx.Client(base_url=values['URL'], timeout=90, trust_env=False) as client:
        yield SimpleNamespace(client=client, phase=values['PHASE'], path=path, state=state)


def _save_state(deployment):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', dir=deployment.path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            os.fchmod(stream.fileno(), 0o600)
            json.dump(deployment.state, stream, indent=2)
            stream.write('\n')
        os.replace(temporary, deployment.path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def test_content_survives_deployment_replacement(deployment):
    client = deployment.client
    if deployment.phase == 'seed':
        if 'content' in deployment.state:
            pytest.fail('Content was already seeded; verification must not recreate it')
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
                json={'base_revision': first['revision'], 'instructions': 'Updated deployed content instructions.'},
            )
        )['skill']
        assert second['revision'] != first['revision']
        removed = _data(
            client.post(
                '/api/v1/skills',
                headers=headers,
                json={'name': 'deployed-removed', 'instructions': 'Retained deleted deployment history.'},
            )
        )['skill']
        _data(client.delete('/api/v1/skills/' + removed['name'], headers=headers))
        packages = []
        for skill in (first, second, removed):
            response = client.get(
                f'/api/v1/skills/{skill["name"]}/package', headers=headers, params={'revision': skill['revision']}
            )
            assert response.status_code == 200, response.text
            packages.append(
                {
                    'name': skill['name'],
                    'revision': skill['revision'],
                    'bytes': base64.b64encode(response.content).decode(),
                }
            )
        uploaded = _data(
            client.post('/api/v1/files/images', headers=headers, files={'file': ('pixel.png', _PNG, 'image/png')})
        )
        image_url = '/api/v1/files/image/' + uploaded['file_key']
        image = client.get(image_url, headers=headers)
        assert image.status_code == 200 and image.content == _PNG
        deployment.state['content'] = {
            'token': token,
            'name': _NAME,
            'revision': second['revision'],
            'created_at': first['created_at'],
            'removed_name': removed['name'],
            'packages': packages,
            'image_url': image_url,
        }
        _save_state(deployment)
        return

    if 'content' not in deployment.state:
        pytest.fail('Content seed state is missing')
    saved = deployment.state['content']
    headers = {'Authorization': 'Bearer ' + saved['token']}
    current = _data(client.get('/api/v1/skills/' + saved['name'], headers=headers))['skill']
    assert current['revision'] == saved['revision']
    assert current['created_at'] == saved['created_at']
    skills = _data(client.get('/api/v1/skills', headers=headers))['skills']
    assert saved['removed_name'] not in {skill['name'] for skill in skills}
    for package in saved['packages']:
        response = client.get(
            f'/api/v1/skills/{package["name"]}/package', headers=headers, params={'revision': package['revision']}
        )
        assert response.status_code == 200, response.text
        assert response.content == base64.b64decode(package['bytes'], validate=True)
    image = client.get(saved['image_url'], headers=headers)
    assert image.status_code == 200 and image.content == _PNG
    assert client.get(saved['image_url']).status_code == 401
    assert client.get('/api/v1/files/media/' + saved['image_url'].rsplit('/', 1)[-1]).status_code == 404


def test_runner_and_grants_survive_deployment_replacement(deployment, tmp_path, monkeypatch):
    client = deployment.client
    if deployment.phase == 'seed':
        if 'runner' in deployment.state:
            pytest.fail('Runner was already seeded; verification must not reinstall it')
        if 'content' not in deployment.state:
            pytest.fail('Seed content before the Runner')
        content = deployment.state['content']
        token = _init_and_auth(client)
        headers = {'Authorization': 'Bearer ' + token}
        selection = _data(
            client.put(
                '/api/v1/workspaces/current/sandbox',
                headers=headers,
                json={
                    'backend': 'docker',
                    'limits': {
                        'timeout_sec': 90,
                        'idle_ttl_sec': 300,
                        'max_sessions': 1,
                        'cpus': 0.25,
                        'memory_mb': 128,
                        'pids_limit': 32,
                    },
                },
            )
        )
        assert selection['effective_backend'] == 'docker'
        source = tmp_path / 'qa-runner'
        _write_skill_runner(source)
        package = Path(shutil.make_archive(str(tmp_path / 'qa-runner'), 'zip', root_dir=source))
        _ensure_qa_plugin(client, token, package)
        grant = _data(client.get(_PERMISSIONS, headers=headers))
        assert grant['enabled'] and not grant['pending_confirmation']
        assert set(grant['grants']['capabilities']) == {'sandbox', 'bot.message.send'}
        monkeypatch.setenv('LANGBOT_CORE_NETWORK_BACKEND', 'docker')
        replica = SimpleNamespace(client=client, root=deployment.path.parent)
        _, bot = _create_agent_bot(replica, headers, _TOOLS)
        _assert_probe(_probe(replica, bot, name=content['name']), content['revision'], 'immutable replica bytes')
        sessions = _data(client.get('/api/v1/box/sessions', headers=headers))
        assert sessions and all(session['backend_name'] == 'docker' for session in sessions)
        draft_name = 'deployed-runtime-draft'
        draft, files = _turn(client, bot, {'operation': 'publish', 'name': draft_name})
        assert 'error' not in draft and not files and draft['published']['registered'], draft
        draft_revision = draft['published']['revision']
        draft_url = f'/api/v1/skills/{draft_name}/package?revision={draft_revision}'
        published = client.get(draft_url, headers=headers)
        assert published.status_code == 200, published.text
        with zipfile.ZipFile(io.BytesIO(published.content)) as archive:
            assert archive.read('scripts/probe.py') == b'print("runtime draft bytes")\n'
            assert archive.read('references/guide.md') == b'Runtime draft resource\n'
        deployment.state['runner'] = {
            'token': token,
            'grant': grant,
            'bot': bot,
            'skill_name': content['name'],
            'revision': content['revision'],
            'draft_name': draft_name,
            'draft_revision': draft_revision,
            'draft_url': draft_url,
            'draft_bytes': base64.b64encode(published.content).decode(),
        }
        _save_state(deployment)
        return

    if 'runner' not in deployment.state:
        pytest.fail('Runner seed state is missing')
    saved = deployment.state['runner']
    headers = {'Authorization': 'Bearer ' + saved['token']}
    assert QA_RUNNER_ID in _wait_for_qa_runner(client, saved['token'], timeout=90)
    assert _data(client.get(_PERMISSIONS, headers=headers)) == saved['grant']
    current = _data(client.get('/api/v1/skills/' + saved['draft_name'], headers=headers))['skill']
    assert current['revision'] == saved['draft_revision']
    published = client.get(saved['draft_url'], headers=headers)
    assert published.status_code == 200, published.text
    assert published.content == base64.b64decode(saved['draft_bytes'], validate=True)
    replica = SimpleNamespace(client=client, root=deployment.path.parent)
    _assert_probe(_probe(replica, saved['bot'], name=saved['skill_name']), saved['revision'], 'immutable replica bytes')
    sessions = _data(client.get('/api/v1/box/sessions', headers=headers))
    assert sessions and all(session['backend_name'] == 'docker' for session in sessions)
