"""Opt-in real HTTP/Core/Runtime/SDK lifecycle on a disposable local instance.

LANGBOT_PERMISSION_E2E=1 .venv/bin/python -m pytest -q -s \
    tests/integration/api/test_plugin_permission_lifecycle.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import time
import zipfile

import httpx
import pytest
import yaml

from tests.e2e.utils.config_factory import create_minimal_config, create_test_directories


pytestmark = pytest.mark.skipif(os.environ.get('LANGBOT_PERMISSION_E2E') != '1', reason='Opt-in local instance E2E')
ROOT = Path(__file__).resolve().parents[3]


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def package(path, name, version, operations):
    manifest = {
        'apiVersion': 'langbot/v1',
        'kind': 'Plugin',
        'metadata': {
            'author': 'permissionse2e',
            'name': name,
            'version': version,
            'label': {'en_US': 'Permission E2E'},
            'description': {'en_US': 'Local-only permission probe'},
            'icon': 'assets/icon.svg',
        },
        'spec': {
            'version': version,
            'config': [],
            'components': {
                'Page': {'fromDirs': [{'path': 'components/pages/'}]},
                'EventListener': {'fromDirs': [{'path': 'components/listeners/'}]},
            },
        },
        'execution': {'python': {'path': 'main.py', 'attr': 'ProbePlugin'}},
    }
    if operations is not None:
        manifest['spec']['permissions'] = {'workspace_operations': operations, 'capabilities': []}
    page = {
        'apiVersion': 'langbot/v1',
        'kind': 'Page',
        'metadata': {'name': 'probe', 'label': {'en_US': 'Probe'}},
        'spec': {'path': 'probe.html'},
        'execution': {'python': {'path': 'probe.py', 'attr': 'ProbePage'}},
    }
    sources = {
        'manifest.yaml': yaml.safe_dump(manifest),
        'main.py': 'from langbot_plugin.api.definition.plugin import BasePlugin\nclass ProbePlugin(BasePlugin):\n    pass\n',
        'components/pages/probe.yaml': yaml.safe_dump(page),
        'components/pages/probe.html': '<!doctype html><title>Permission probe</title>',
        'components/listeners/probe.yaml': yaml.safe_dump(
            {
                'apiVersion': 'langbot/v1',
                'kind': 'EventListener',
                'metadata': {'name': 'permission_probe', 'label': {'en_US': 'Permission probe'}},
                'spec': {},
                'execution': {'python': {'path': 'probe.py', 'attr': 'PermissionProbe'}},
            }
        ),
        'components/listeners/probe.py': (
            'from langbot_plugin.api.definition.components.common.event_listener import EventListener\n'
            'class PermissionProbe(EventListener):\n'
            '    async def initialize(self):\n'
            '        self.plugin.permission_probe = self\n'
            '    async def probe(self, operation):\n'
            '        return await self.plugin.workspace.call(operation)\n'
        ),
        'components/pages/probe.py': (
            'from langbot_plugin.api.definition.components.page import Page, PageResponse\n'
            'class ProbePage(Page):\n'
            '    async def handle_api(self, request):\n'
            '        operation = (request.body or {}).get("operation", "stats.basic")\n'
            '        result = await self.plugin.permission_probe.probe(operation)\n'
            '        return PageResponse.ok(result)\n'
        ),
        'assets/icon.svg': '<svg xmlns="http://www.w3.org/2000/svg"/>',
        'README.md': 'Local permission lifecycle probe. No providers or dependencies.\n',
    }
    with zipfile.ZipFile(path, 'w') as archive:
        for filename, content in sources.items():
            archive.writestr(filename, content)


class Instance:
    def __init__(self, directory, client):
        self.directory = directory
        self.client = client
        self.member = {}
        self.api_key = {}
        self.events = []

    def request(self, label, method, endpoint, *, identity='member', record=True, **kwargs):
        headers = self.api_key if identity == 'api_key' else self.member
        response = self.client.request(method, endpoint, headers=headers, **kwargs)
        if record:
            try:
                body = response.json()
            except ValueError:
                body = response.text[:2000]
            self.events.append(
                {
                    'action': label,
                    'method': method,
                    'endpoint': endpoint,
                    'identity': identity,
                    'http_status': response.status_code,
                    'body': body,
                }
            )
            (self.directory / 'http-actions.json').write_text(json.dumps(self.events, indent=2), encoding='utf-8')
        return response

    def install(self, name, version, operations):
        archive = self.directory / f'{name}-{version}.zip'
        package(archive, name, version, operations)
        with archive.open('rb') as source:
            response = self.request(
                f'install {name} {version}',
                'POST',
                '/api/v1/plugins/install/local',
                files={'file': (archive.name, source, 'application/zip')},
            )
        assert response.status_code == 200, response.text
        task_id = response.json()['data']['task_id']
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            task_response = self.request('poll installation', 'GET', f'/api/v1/system/tasks/{task_id}', record=False)
            task = task_response.json()['data']
            if task['runtime']['done']:
                self.request(f'installation finished {name} {version}', 'GET', f'/api/v1/system/tasks/{task_id}')
                assert task['runtime']['exception'] is None, task
                metadata = json.loads((self.directory / 'instance-metadata.json').read_text())
                ports = set(metadata['ports'])
                listeners = subprocess.check_output(['ss', '-ltnH'], text=True).splitlines()
                owned = [row for row in listeners if int(row.split()[3].rsplit(':', 1)[1]) in ports]
                (self.directory / 'live-listeners.txt').write_text('\n'.join(owned) + '\n', encoding='utf-8')
                assert owned and all(row.split()[3].startswith(('127.0.0.1:', '[::1]:')) for row in owned)
                return
            time.sleep(0.3)
        pytest.fail(f'Installation task {task_id} timed out')

    def permissions(self, name):
        response = self.request(f'permissions {name}', 'GET', f'/api/v1/plugins/permissionse2e/{name}/permissions')
        assert response.status_code == 200, response.text
        return response.json()['data']

    def change(self, name, operations, *, confirm=False, capabilities=None, identity='member'):
        return self.request(
            f'permissions update {name} confirm={confirm}',
            'PUT',
            f'/api/v1/plugins/permissionse2e/{name}/permissions',
            identity=identity,
            json={'workspace_operations': operations, 'capabilities': capabilities or [], 'confirm': confirm},
        )

    def call(self, name, operation='stats.basic', *, wait_ready=False):
        deadline = time.monotonic() + (45 if wait_ready else 0)
        while True:
            response = self.request(
                f'SDK call {name} {operation}',
                'POST',
                f'/api/v1/plugins/permissionse2e/{name}/page-api',
                json={'page_id': 'probe', 'endpoint': '/probe', 'method': 'POST', 'body': {'operation': operation}},
            )
            if response.status_code != 400 or response.json().get('msg') != 'Plugin not found':
                return response
            if time.monotonic() >= deadline:
                return response
            time.sleep(0.5)


@pytest.fixture(scope='module')
def instance():
    directory = Path(tempfile.mkdtemp(prefix='permissions-e2e-', dir=ROOT.parent / 'attachments'))
    os.chmod(directory, 0o700)
    private = directory / 'instance'
    private.mkdir()
    ports = [free_port() for _ in range(3)]
    assert len(set(ports)) == 3 and not set(ports) & {3370, 3380}
    config_path = create_minimal_config(private, ports[0])
    create_test_directories(private)
    config = yaml.safe_load(config_path.read_text())
    config['api']['host'] = '127.0.0.1'
    config['system']['jwt']['secret'] = secrets.token_urlsafe(32)
    config['plugin'].update(
        enable=True,
        enable_marketplace=False,
        runtime_ws_url=f'ws://127.0.0.1:{ports[1]}/control/ws',
        display_plugin_debug_url=f'ws://127.0.0.1:{ports[2]}/plugin/debug/ws',
    )
    adapters = ROOT / 'src/langbot/pkg/platform/sources'
    config['system']['disabled_adapters'] = [
        yaml.safe_load(path.read_text())['metadata']['name']
        for path in adapters.glob('*.yaml')
        if path.stem != 'websocket'
    ]
    config_path.write_text(yaml.safe_dump(config), encoding='utf-8')
    os.chmod(config_path, 0o600)
    environment = {key: value for key, value in os.environ.items() if key in {'PATH', 'LANG', 'LC_ALL', 'VIRTUAL_ENV'}}
    home = private / 'home'
    home.mkdir()
    temporary = private / 'tmp'
    temporary.mkdir()
    environment.update(
        PYTHONPATH=os.pathsep.join([str(ROOT / 'tests/fixtures/permissions_network'), str(ROOT / 'src')]),
        PYTHONUTF8='1',
        PYTHONIOENCODING='utf-8',
        SPACE__DISABLE_TELEMETRY='true',
        SPACE__DISABLE_MODELS_SERVICE='true',
        ANONYMIZED_TELEMETRY='False',
        NO_PROXY='127.0.0.1,localhost',
        UV_OFFLINE='1',
        PIP_NO_INDEX='1',
        HOME=str(home),
        TMPDIR=str(temporary),
        XDG_CONFIG_HOME=str(home / '.config'),
        XDG_CACHE_HOME=str(home / '.cache'),
        PYTHONNOUSERSITE='1',
    )
    command = [sys.executable, '-m', 'langbot']
    metadata = {
        'command': command,
        'ports': ports,
        'root_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'sdk': 'editable sibling SDK',
        'network': 'loopback-only socket guard; stdio Core/Runtime control; no application mocks',
    }
    metadata['schema_setup'] = 'Normal fresh-instance startup, no precreated database'
    process = None
    try:
        with (directory / 'core.stdout.log').open('wb') as stdout, (directory / 'core.stderr.log').open('wb') as stderr:
            process = subprocess.Popen(
                command, cwd=private, env=environment, stdout=stdout, stderr=stderr, start_new_session=True
            )
            metadata['pid'] = process.pid
            (directory / 'instance-metadata.json').write_text(json.dumps(metadata, indent=2))
            print(f'PERMISSION_E2E_ARTIFACTS={directory}', flush=True)
            with httpx.Client(base_url=f'http://127.0.0.1:{ports[0]}', timeout=120, trust_env=False) as client:
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    assert process.poll() is None, f'Core exited; inspect {directory.name} logs'
                    try:
                        if client.get('/api/v1/system/info', timeout=2).status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.5)
                else:
                    pytest.fail('Core startup timed out')
                running = Instance(directory, client)
                credentials = {'user': 'permissions@langbot.test', 'password': secrets.token_urlsafe(24)}
                initialized = client.post('/api/v1/user/init', json=credentials)
                assert initialized.status_code == 200 and initialized.json()['code'] == 0
                authenticated = client.post('/api/v1/user/auth', json=credentials)
                assert authenticated.status_code == 200 and authenticated.json()['code'] == 0
                running.member = {'Authorization': f'Bearer {authenticated.json()["data"]["token"]}'}
                key_response = running.request(
                    'create isolated API key',
                    'POST',
                    '/api/v1/apikeys',
                    json={'name': 'Permission E2E only'},
                    record=False,
                )
                assert key_response.status_code == 200, key_response.text
                running.api_key = {'Authorization': f'Bearer {key_response.json()["data"]["key"]["key"]}'}
                yield running
    finally:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
            except ProcessLookupError:
                pass
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            metadata['exit_code'] = process.poll()
            metadata['stopped'] = process.poll() is not None
            members = subprocess.check_output(['ps', '-eo', 'pid,pgid,stat'], text=True).splitlines()[1:]
            metadata['remaining_live_processes'] = [
                row.strip()
                for row in members
                if row.split()[1] == str(process.pid) and not row.split()[2].startswith('Z')
            ]
            (directory / 'instance-metadata.json').write_text(json.dumps(metadata, indent=2))
            assert not metadata['remaining_live_processes'], 'Owned process group did not stop'


def test_real_permission_lifecycle(instance):
    contract_errors = []
    instance.install('strict-probe', '0.1.0', ['stats.basic'])
    state = instance.permissions('strict-probe')
    assert state['pending_confirmation'] and not state['enabled']
    assert state['grants']['workspace_operations'] == []
    denied = instance.change('strict-probe', ['stats.basic'], identity='api_key')
    assert denied.status_code == 403 and denied.json()['code'] == 'permission_denied', denied.text
    denied = instance.change('strict-probe', ['stats.basic'], confirm=True, identity='api_key')
    assert denied.status_code == 403, denied.text
    assert denied.json()['code'] == 'permission_denied'
    refused = instance.call('strict-probe')
    assert refused.status_code != 200 or not refused.json().get('data', {}).get('ok'), refused.text
    confirmed = instance.change('strict-probe', ['stats.basic'], confirm=True)
    assert confirmed.status_code == 200, confirmed.text
    state = instance.permissions('strict-probe')
    assert state['enabled'] and not state['pending_confirmation']
    called = instance.call('strict-probe', wait_ready=True)
    assert called.status_code == 200 and called.json()['data']['ok'] is True, called.text
    revoked = instance.change('strict-probe', [])
    assert revoked.status_code == 200, revoked.text
    denied = instance.call('strict-probe')
    assert denied.status_code == 200 and denied.json()['data']['ok'] is False, denied.text
    if denied.json()['data']['error']['code'] != 'permission_denied':
        contract_errors.append({'stage': 'revoke', 'response': denied.json()})
    assert instance.change('strict-probe', ['stats.basic'], confirm=True).status_code == 200
    instance.install('strict-probe', '0.2.0', ['stats.basic', 'pipeline.list'])
    state = instance.permissions('strict-probe')
    assert state['enabled'] and state['pending_confirmation']
    assert state['grants']['workspace_operations'] == ['stats.basic']
    old_call = instance.call('strict-probe', wait_ready=True)
    assert old_call.status_code == 200 and old_call.json()['data']['ok'] is True, old_call.text
    new_call = instance.call('strict-probe', 'pipeline.list')
    assert new_call.status_code == 200 and new_call.json()['data']['ok'] is False, new_call.text
    confirmed = instance.change('strict-probe', ['stats.basic', 'pipeline.list'], confirm=True)
    assert confirmed.status_code == 200, confirmed.text
    assert not instance.permissions('strict-probe')['pending_confirmation']
    new_call = instance.call('strict-probe', 'pipeline.list')
    assert new_call.status_code == 200 and new_call.json()['data']['ok'] is True, new_call.text
    assert not contract_errors, contract_errors


def test_real_legacy_confirmation_and_application_denial(instance):
    instance.install('legacy-probe', '0.1.0', None)
    state = instance.permissions('legacy-probe')
    assert state['compatibility_mode'] and state['pending_confirmation'] and not state['enabled']
    refused = instance.call('legacy-probe')
    assert refused.status_code != 200 or not refused.json().get('data', {}).get('ok'), refused.text
    invalid = instance.change('legacy-probe', [], confirm=True)
    assert invalid.status_code == 400, invalid.text
    capabilities = [row['id'] for row in state['permissions'] if row['category'] == 'capabilities']
    confirmed = instance.change('legacy-probe', [], capabilities=capabilities, confirm=True)
    assert confirmed.status_code == 200, confirmed.text
    state = instance.permissions('legacy-probe')
    assert state['enabled'] and state['compatibility_mode'] and not state['pending_confirmation']
    denied = instance.call('legacy-probe', wait_ready=True)
    assert denied.status_code == 200 and denied.json()['data']['ok'] is False, denied.text
    assert denied.json()['data']['error']['code'] == 'permission_denied', denied.text
